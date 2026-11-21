"""PIT fixed-basis covariance tape and geometry respecting SPD forecasting.

All models fit/forecast on a single factor basis trained strictly prior to
scored development weeks. Weekly targets require next five sessions and are
*never* used for model fitting before their complete maturity date.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .geometry import (spd,logm,expm,frechet_mean,logeuclidean_distance,
                       affine_distance,bures_distance,grassmann_distance,ortho_columns)
from research.nextgen.joint_state.contracts import RiskData


@dataclass(frozen=True)
class CovarianceTape:
    dates: np.ndarray
    daily_spd: np.ndarray  # T x K x K realized intraday covariance in fixed basis
    factor: np.ndarray  # T x K daily projected log-return, supports future risk scoring
    loading: np.ndarray  # names_selected x K, orthogonal basis trained before cutoff
    names: np.ndarray
    coverage: np.ndarray
    fitted_through: np.datetime64
    source_sha256: str

    def at(self,t,window=5):
        if not (t>=window-1 and t<len(self.dates)):raise ValueError('covariance window outside history')
        s=self.daily_spd[t-window+1:t+1]
        if not np.isfinite(s).all():raise ValueError('missing intraday covariance in risk history')
        return spd(s.mean(axis=0))

    def target(self,t,horizon=5):
        if not(t>=0 and t+horizon<len(self.dates)):raise ValueError('unmatured covariance target')
        s=self.daily_spd[t+1:t+1+horizon]
        if not np.isfinite(s).all():raise ValueError('missing intraday target coverage')
        return spd(s.mean(axis=0))


def build_tape(data:RiskData,basis_end='2016-07-01',rank=4,min_coverage=.97,limit_names=None):
    """Train one PCA basis on early data; apply to ALL later origins unchanged.

    Basis fit observations end BEFORE the basis_end date (<=~June 2016). No
    cross-date PCA alignment or reusing late eigenvectors for 2018 outcomes.
    Higher-dimensional portfolio covariance can be reconstructed as U H U' + D,
    but the experiment evaluates H in its common, identified rank-K basis.
    """
    end=np.datetime64(basis_end,'D')
    prefix=np.flatnonzero(data.dates<end)
    if len(prefix)<90 or prefix[-1]+1>len(data.dates):raise ValueError('need initial 90-session basis history')
    if rank<2 or rank>15:raise ValueError('rank must be 2..15')
    R=data.intraday
    valid=np.isfinite(R).all(axis=1)
    ok=valid[prefix].mean(axis=0)>=min_coverage
    ix=np.flatnonzero(ok)
    if limit_names is not None:
        if limit_names<rank+3:raise ValueError('limit_names less than rank+3')
        ix=ix[:limit_names] if np.flatnonzero(data.names[ix]=='SPY').size else ix
        if 'SPY' not in data.names[ix] and 'SPY' in data.names[ok]:
            ix=np.r_[np.flatnonzero(data.names=='SPY')[0],ix[:limit_names-1]]
    if len(ix)<rank+3 or 'SPY' not in data.names[ix]:raise ValueError('insufficient covered assets including SPY')
    x=np.where(valid[prefix][:,ix],data.daily[prefix][:,ix],np.nan)
    # Missing training values imputed to mean FROM training prefix only.
    center=np.nanmean(x,axis=0)
    x=np.where(np.isfinite(x),x,center)-center
    _,_,vt=np.linalg.svd(x,full_matrices=False)
    basis=ortho_columns(vt[:rank].T)
    z=R[:,:,ix]
    coverage=valid[:,ix].mean(axis=1)
    # Assumes missing name's centred log return equals 0; disclose coverage.
    projected=np.einsum('thn,nk->thk',np.nan_to_num(z,nan=0,posinf=0,neginf=0),basis,optimize=True)
    day=np.einsum('thk,thl->tkl',projected,projected,optimize=True)
    floor=1e-9
    day+=np.eye(rank)[None,:,:]*floor
    day[coverage<.92]=np.nan
    factor=np.where(np.isfinite(projected).all(1),projected.sum(1),np.nan)
    return CovarianceTape(data.dates,day,factor,basis,data.names[ix],coverage,end,data.sha256)


def weekly_origins(tape,first='2017-01-01',last='2019-12-01',minimum=35):
    first,last=np.datetime64(first,'D'),np.datetime64(last,'D')
    x=tape.dates.astype('datetime64[D]').astype(int)
    idx=np.flatnonzero((x%7==0)&(tape.dates>=first)&(tape.dates<=last))
    return np.asarray([t for t in idx if t>=minimum+4 and t+5<len(x) and
                       np.isfinite(tape.daily_spd[t-minimum-4:t+6]).all()],dtype=int)


def geometric_forecast(matrices,kind='logeuclidean',halflife=8):
    """Intrinsic exponentially recency-weighted Fréchet mean; no future refits."""
    x=np.asarray(matrices,float)
    if x.ndim!=3 or x.shape[0]<4:raise ValueError('need 4+ recent risk observations')
    w=2.**(-np.arange(len(x)-1,-1,-1)/halflife)
    if kind=='euclidean':return spd(np.average(x,weights=w,axis=0))
    if kind in ('logeuclidean','affine','bures'):
        return frechet_mean(x,metric=kind,weights=w)
    raise ValueError('unknown covariance geometry')


def predictive_loss(realized,forecast):
    """Gaussian/log-determinant covariance divergence, dimensionless and nonnegative.

    tr(S F^-1) - logdet(S F^-1) - k. A proper Gaussian covariance
    score difference, even when S is a noisy realized-covariance proxy.
    """
    a,b=spd(realized),spd(forecast)
    n=len(a)
    s1,la=np.linalg.slogdet(a);s2,lb=np.linalg.slogdet(b)
    if s1<=0 or s2<=0:raise ValueError('covariance not SPD')
    return float(np.trace(np.linalg.solve(b,a))+lb-la-n)


def curve_metrics(actual,forecast):
    a,b=spd(actual),spd(forecast)
    w=np.eye(len(a))[0]
    p=np.ones(len(a))/np.sqrt(len(a))
    def qlike(x,y):
        r=x/y
        return float(r-np.log(r)-1)
    return dict(stein=predictive_loss(a,b),logeuclidean=logeuclidean_distance(a,b),
                affine=affine_distance(a,b),bures=bures_distance(a,b),
                f1_qlike=qlike(w@a@w,w@b@w),equal_qlike=qlike(p@a@p,p@b@p))


def rolling_geometric_eval(tape:CovarianceTape,methods=('euclidean','logeuclidean','affine','bures'),
                           first='2018-01-01',last='2019-11-01',history_weeks=12,step=5,max_origins=None):
    """Fixed hyperparameters; causal snapshots [origin-5*history, origin]."""
    if step<1 or history_weeks<4:raise ValueError('invalid lookback')
    idx=weekly_origins(tape,first,last,minimum=5*(history_weeks+1))
    idx=idx[::max(1,step//5)] if step>=5 else idx[::step]
    if max_origins is not None:idx=idx[:max_origins]
    if not len(idx):raise ValueError('no covered held-out risk origins')
    rows=[]
    for t in idx:
        seq=np.stack([tape.at(int(t)-1-5*i) for i in reversed(range(history_weeks))])
        target=tape.target(int(t),5)
        for method in methods:
            forecast=geometric_forecast(seq,method)
            rows.append(dict(origin=int(t),date=str(tape.dates[t]),model=method,
                             train_end=str(tape.fitted_through),**curve_metrics(target,forecast)))
    return rows


def rolling_grassmann(data:RiskData,first='2017-01-01',last='2019-11-01',rank=4,
                       lookback=126,offset=21):
    """Local factor subspace change, evaluated with no future data.

    This is a *Grassmann diagnostic*, not an allocator and not an artificial
    multivariate risk forecast. Uses identical instruments at both dates.
    """
    if rank<2 or lookback<rank+20 or offset<1:raise ValueError('invalid Grassmann configuration')
    dates=data.dates
    ix=np.flatnonzero((dates>=np.datetime64(first))&(dates<=np.datetime64(last)))
    ix=ix[(dates[ix].astype('datetime64[D]').astype(int)%7)==0]
    rows=[]
    for t in ix:
        if t<lookback+offset or t+5>=len(dates):continue
        x1=data.daily[t-lookback:t]
        x0=data.daily[t-lookback-offset:t-offset]
        ok=(np.isfinite(x1).mean(0)>.95)&(np.isfinite(x0).mean(0)>.95)
        if ok.sum()<rank+3:continue
        x1=x1[:,ok];x0=x0[:,ok]
        x1=np.where(np.isfinite(x1),x1,np.nanmean(x1,axis=0))
        x0=np.where(np.isfinite(x0),x0,np.nanmean(x0,axis=0))
        _,_,v1=np.linalg.svd(x1-x1.mean(0),full_matrices=False)
        _,_,v0=np.linalg.svd(x0-x0.mean(0),full_matrices=False)
        gap=grassmann_distance(v0[:rank].T,v1[:rank].T)
        # Next future SPY realized variance: risk diagnostic target only.
        spy=int(np.flatnonzero(data.names=='SPY')[0])
        spy_fut=data.intraday[t:t+5,:,spy]
        if not np.isfinite(spy_fut).all():continue
        rows.append(dict(date=str(dates[t]),angle_rad=gap,spy_next5_rv=float((spy_fut**2).sum()/5),coverage=float(ok.mean())))
    return rows


def train_spdnet(tape:CovarianceTape,train_cutoff='2017-12-31',dim=3,
                 lookback=4,epochs=350,seeds=(11,17,23),device='cpu',patience=40):
    """SPDNet-inspired differentiable BiMap -> ReEig -> LogEig -> MLP forecast.

    Learns an orthonormal Stiefel map using differentiable torch.linalg.qr,
    predicts *full-space* log SPD target. Chronological early stop uses only
    training-period completed five-session covariance targets; no future
    measured target informs basis, architecture or early stop.
    """
    try:
        import torch
        from torch import nn
    except ImportError as ex:raise RuntimeError('SPDNet needs torch; install advanced requirements') from ex
    if epochs<5 or lookback<2 or not seeds:raise ValueError('bad neural training design')
    k=tape.loading.shape[1]
    d=min(dim,k)
    times=weekly_origins(tape,first='2016-07-01',last=train_cutoff,minimum=5*(lookback+2))
    times=times[tape.dates[times+5]<=np.datetime64(train_cutoff)]
    if len(times)<35:raise ValueError('too few matured training targets for SPDNet')
    xs=np.stack([[tape.at(int(t)-1-5*i) for i in reversed(range(lookback))] for t in times])
    yy=np.stack([logm(tape.target(int(t),5)) for t in times])
    ntrain=max(25,int(len(times)*.8))
    xtr=torch.tensor(xs,dtype=torch.float64,device=device)
    ytr=torch.tensor(yy,dtype=torch.float64,device=device)
    targets=ytr.reshape(len(times),k*k)
    scale=torch.clamp(targets[:ntrain].std(0),min=.05)
    center=targets[:ntrain].mean(0)

    class Network(nn.Module):
        def __init__(self):
            super().__init__()
            self.raw=nn.Parameter(torch.randn(k,d,dtype=torch.float64)/np.sqrt(k))
            nfeat=lookback*d*d
            self.net=nn.Sequential(nn.Linear(nfeat,64,dtype=torch.float64),nn.GELU(),
                                   nn.Linear(64,64,dtype=torch.float64),nn.GELU(),
                                   nn.Linear(64,k*k,dtype=torch.float64))
        def forward(self,x):
            q,_=torch.linalg.qr(self.raw)
            z=q.T@x@q
            ev,U=torch.linalg.eigh((z+z.transpose(-2,-1))/2)
            ev=ev.clamp(min=1e-9)
            tangent=(U*torch.log(ev).unsqueeze(-2))@U.transpose(-2,-1)
            pred=self.net(tangent.reshape(len(x),-1))*scale+center
            p=pred.reshape(-1,k,k)
            return (p+p.transpose(-2,-1))/2
    nets=[];losses=[]
    for seed in seeds:
        torch.manual_seed(seed);net=Network().to(device)
        opt=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.002)
        best=float('inf');weights=None;stale=0
        for epoch in range(epochs):
            net.train();opt.zero_grad()
            p=net(xtr[:ntrain]);target=ytr[:ntrain]
            loss=torch.mean(((p-target)/.2)**2)
            if not torch.isfinite(loss):raise RuntimeError('SPDNet train loss nonfinite')
            loss.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),5)
            opt.step()
            net.eval()
            with torch.no_grad():
                val=float(torch.mean((net(xtr[ntrain:])-ytr[ntrain:])**2))
            if val<best-1e-9:
                best=val;stale=0;weights={x:v.detach().clone() for x,v in net.state_dict().items()}
            else:stale+=1
            if stale>=patience:break
        net.load_state_dict(weights);net.eval();nets.append(net);losses.append(best)

    def predict(seq):
        x=np.asarray(seq,float)
        if x.shape!=(lookback,k,k):raise ValueError('SPDNet sequence shape mismatch')
        x=torch.tensor(x[None],dtype=torch.float64,device=device)
        with torch.no_grad():
            tangent=np.mean([n(x).cpu().numpy()[0] for n in nets],axis=0)
        return spd(expm(tangent))

    return dict(predict=predict,val_mse=losses,train_end=str(tape.dates[times[-1]+5]),
                n_train=len(times),seeds=tuple(seeds),basis_end=str(tape.fitted_through),rank=k)


def baseline_factor_covariance(tape:CovarianceTape,origin:int,method='ewma_cov',lookback=252):
    """HEAVY, realized-GARCH, EWMA and sample benchmarks in SAME factor basis.

    Inputs end at the preceding completed session origin-1, even if orders
    were sent just before the current close. Predictions are daily factor
    realized-covariance units, corresponding to target mean over next 5 days.
    """
    from research.nextgen.joint_state.risk import heavy_filter,realized_garch
    if origin<lookback+1:raise ValueError('risk training history incomplete')
    rv=tape.daily_spd[origin-lookback:origin]
    factor=tape.factor[origin-lookback:origin]
    if not(np.isfinite(rv).all() and np.isfinite(factor).all()):
        raise ValueError('risk baseline cannot fill missing historical panel')
    if method=='sample_cov':
        return spd(np.cov(factor.T,ddof=1))
    if method=='ewma_cov':
        result=spd(rv[0]);lambda_=0.94
        for a in rv[1:]:result=lambda_*result+(1-lambda_)*a
        return spd(result)
    if method not in ('heavy','realized_garch'):
        raise ValueError('invalid factor risk baseline')
    diag=np.maximum(np.diagonal(rv,axis1=1,axis2=2),1e-10)
    variances=[]
    for j in range(diag.shape[1]):
        if method=='heavy':
            v=heavy_filter(diag[:,j])['forecast']
        else:
            v=realized_garch(factor[:,j],diag[:,j])['forecast']
        variances.append(float(v))
    std=np.sqrt(np.maximum(variances,1e-10))
    s=spd(np.mean(rv[-42:],axis=0))
    scales=np.sqrt(np.diag(s))
    corr=spd(s/np.outer(scales,scales),floor=1e-6)
    return spd(std[:,None]*corr*std[None,:])
