"""Causal factor-covariance estimators: POET, HEAVY, realized GARCH, Bayesian factor SV.

Returns and realized variance in *daily log-return* units. Parameters fit at the
origin using observations <= origin-1; a forecast predicts the next h sessions.
No market prices, hidden future returns or data downloaded here.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from scipy.optimize import minimize
from scipy.linalg import eigh
from .contracts import RiskData

EPS=1e-10


def positive_definite(a, floor=1e-9):
    a=(a+a.T)*.5
    vals,vecs=np.linalg.eigh(a)
    return (vecs*np.maximum(vals,floor))@vecs.T


def poe_residual(e, threshold=1.5):
    """POET-style adaptive thresholding of principal orthogonal complement.

    Known past residuals e: T x N, no future labels. Soft threshold off-diagonals
    scaled by residual standard deviations and sqrt(log N / T).
    """
    a=np.asarray(e,float)
    if a.ndim!=2 or a.shape[0]<30 or a.shape[1]<2 or not np.isfinite(a).all():
        raise ValueError("POET: need finite residual training matrix (T>=30,N>=2)")
    t,n=a.shape
    a=a-a.mean(axis=0,keepdims=True)
    cov=a.T@a/(t-1)
    diag=np.maximum(np.diag(cov),EPS)
    sc=np.sqrt(np.outer(diag,diag))
    cutoff=threshold*np.sqrt(np.log(n)/t)*sc
    d=np.sign(cov)*np.maximum(np.abs(cov)-cutoff,0)
    np.fill_diagonal(d,diag)
    return positive_definite(d)


@dataclass
class FactorWindow:
    loading: np.ndarray    # N x k, orthonormal asset-space factors
    factor: np.ndarray     # T x k, observed factor returns from training window
    factor_rv: np.ndarray  # T x k from 14 intraday innovations
    resid: np.ndarray      # T x N
    dates: np.ndarray
    stocks: np.ndarray
    n_dropped: int


def factor_window(d:RiskData, origin:int, lookback=252, factors=3, mincoverage=.95):
    """PCA *at* origin from only earlier daily/intraday returns.

    For comparability the same current universe subset is used within a window;
    removing insufficiently covered securities is explicit and research only.
    """
    if origin<lookback or origin>=len(d.dates):
        raise ValueError("factor window incomplete")
    x=d.daily[origin-lookback:origin]
    z=d.intraday[origin-lookback:origin]
    enough=np.isfinite(x).mean(0)>=mincoverage
    enough &= np.isfinite(z).all(1).mean(0)>=mincoverage
    if "SPY" not in d.names[enough]:
        raise ValueError("SPY missing from factor window")
    idx=np.flatnonzero(enough)
    if len(idx)<factors+2:
        raise ValueError("too few matched stocks")
    # Previous-window constant-imputation *inside* training window only.
    x=x[:,idx]; z=z[:,:,idx]
    mx=np.nanmean(x,axis=0)
    x=np.where(np.isfinite(x),x,mx)
    z=np.where(np.isfinite(z),z,0.0)
    x=x-x.mean(axis=0)
    # PCA on stock return covariance. In high-dimensional panels use time Gram
    # covariance for efficiency; this is equivalent to right singular vectors.
    _,sing,vh=np.linalg.svd(x,full_matrices=False)
    k=min(factors,len(sing))
    load=vh[:k].T
    f=x@load
    intr=np.einsum('tjn,nk->tjk',z,load,optimize=True)
    frv=(intr**2).sum(axis=1)
    resid=x-f@load.T
    return FactorWindow(load,f,frv,resid,d.dates[origin-lookback:origin],idx,len(d.names)-len(idx))


def qlike(actual,pred,eps=1e-10):
    if not (np.isfinite(actual) and np.isfinite(pred) and actual>0 and pred>0):
        raise ValueError("QLIKE requires positive finite target and prediction")
    ratio=max(actual,eps)/max(pred,eps)
    return float(ratio-np.log(ratio)-1)


def heavy_filter(factor_rv,fit=True,maxiter=300):
    """HEAVY variance recursion h[t+1]=omega+a*RV[t]+b*h[t].

    Estimate stationarity-constrained a,b by Gaussian quasi-likelihood using
    past factor daily returns proxy sqrt(RV); no future observations.
    """
    r=np.asarray(factor_rv,float)
    if r.ndim!=1 or len(r)<80 or not np.isfinite(r).all() or np.any(r<=0):
        raise ValueError("HEAVY: need >=80 positive finite realized variances")
    m=float(np.mean(r))
    def recur(a,b):
        h=np.empty(len(r));h[0]=m
        for t in range(1,len(r)):
            h[t]=m*(1-a-b)+a*r[t-1]+b*h[t-1]
        next_=m*(1-a-b)+a*r[-1]+b*h[-1]
        return np.maximum(h,EPS),max(next_,EPS)
    def loss(par):
        a,b=par
        if min(a,b)<0 or a+b>=.995:return 1e9
        h,_=recur(a,b)
        return float(np.mean(np.log(h)+r/h))
    if fit:
        result=minimize(loss,[.15,.78],bounds=[(1e-5,.85),(1e-5,.985)],method='Nelder-Mead',options={'maxiter':maxiter})
        # For stationary parameters explicitly reject a+b close to 1 boundary.
        if not result.success and not np.isfinite(result.fun):raise RuntimeError('HEAVY fit failure')
        a,b=result.x
    else:a,b=.15,.78
    _,future=recur(a,b)
    return dict(forecast=future,a=float(a),b=float(b),logscore=loss((a,b)))


def realized_garch(factor_returns,realized_var,maxiter=300):
    """Log-linear realized GARCH(1,1) with return and realized-vol measurement.

    log(h[t])=omega+b*log(h[t-1])+g*log(RV[t-1]);
    log RV[t] = xi + phi*log h[t] + tau*z[t] + normal measurement error;
    z[t]=return[t]/sqrt(h[t]). Fit Gaussian quasi-likelihood jointly. Not a
    simple autocorrelation regression: measurement and returns both enter loss.
    """
    r=np.asarray(factor_returns,float)
    rv=np.asarray(realized_var,float)
    if r.shape!=rv.shape or r.ndim!=1 or len(r)<100 or not np.isfinite(r).all() or not np.isfinite(rv).all() or np.any(rv<=0):
        raise ValueError("realized GARCH input invalid")
    lr=np.log(np.maximum(rv,EPS));center=float(lr.mean())
    def predict(par):
        b,g=par[0:2]
        omega=(1-b-g)*center
        logh=np.empty(len(rv));logh[0]=center
        for i in range(1,len(rv)):
            logh[i]=np.clip(omega+b*logh[i-1]+g*lr[i-1],-25,5)
        next_=np.clip(omega+b*logh[-1]+g*lr[-1],-25,5)
        return np.exp(logh),float(np.exp(next_))
    def loss(par):
        b,g,xi,phi,tau,lsigma=par
        if b<0 or g<0 or b+g>=.995 or phi<=0 or abs(tau)>1 or not(-6<lsigma<3):return 1e8
        h,_=predict(par);z=r/np.sqrt(h)
        err=lr-xi-phi*np.log(h)-tau*z
        s2=np.exp(2*lsigma)
        return float(np.mean(np.log(h)+r*r/h + 2*lsigma+err*err/s2))
    x0=[.65,.28,0.,1.,0.,-.8]
    bounds=[(.001,.95),(.001,.95),(-3,3),(.1,2),(-.8,.8),(-4,1)]
    rs=minimize(loss,x0,bounds=bounds,method='L-BFGS-B',options={'maxiter':maxiter})
    if not np.isfinite(rs.fun):raise RuntimeError('realized GARCH invalid likelihood')
    _,nxt=predict(rs.x)
    return dict(forecast=nxt,params=[float(z) for z in rs.x],converged=bool(rs.success),logscore=float(rs.fun))


def bayesian_factor_sv(factor_returns,draws=250,tune=250,chains=2,seed=20261120,method='nuts'):
    """True Bayesian stochastic volatility, one latent stationary AR(1) per factor.

    Optional PyMC >=5 and its compatible ArviZ environment required. Uses
    posterior samples of last filtered latent logvol (observations only to t-1).
    Returns posterior predictive variance distribution, NOT a point regression.
    Method='advi' may be used for expensive/large panels; full NUTS preferred
    when available with R-hat / ESS diagnostics checked by caller.
    """
    try:
        import pymc as pm
        import pytensor.tensor as pt
    except Exception as exc:
        raise RuntimeError('Bayesian SV requires compatible pymc>=5, arviz and pytensor; install research extras') from exc
    x=np.asarray(factor_returns,float)
    if x.ndim!=2 or x.shape[0]<100 or not np.isfinite(x).all():
        raise ValueError("Bayesian SV expects finite T x K factor returns")
    if draws<50 or tune<50:raise ValueError('minimum posterior draws/tuning 50')
    ans=[]
    for j in range(x.shape[1]):
        y=x[:,j]
        with pm.Model() as model:
            mu=pm.Normal('mu',mu=float(np.log(max(np.var(y),1e-8))),sigma=2)
            phi=pm.Beta('phi',alpha=12,beta=3)
            sigma=pm.HalfNormal('sigma',sigma=.35)
            latent=pm.AR('latent',rho=pt.stack([phi]),sigma=sigma,
                         init_dist=pm.Normal.dist(mu=0,sigma=1),shape=len(y),constant=False)
            h=mu+latent
            pm.StudentT('obs',nu=8,mu=0,sigma=pm.math.exp(.5*h),observed=y)
            if method=='advi':
                approx=pm.fit(n=25000,method='advi',random_seed=seed,progressbar=False)
                trace=approx.sample(draws=draws,random_seed=seed)
            elif method=='nuts':
                trace=pm.sample(draws=draws,tune=tune,chains=chains,
                                cores=min(chains,2),random_seed=seed+j,
                                progressbar=False,target_accept=.9,return_inferencedata=True)
            else:raise ValueError('method must be nuts or advi')
        # Shape (chain, draw, T). A posterior of latent last training time is
        # filtered relative to the forecast origin; no next-week returns used.
        muv=np.asarray(trace.posterior['mu']).ravel()
        phiv=np.asarray(trace.posterior['phi']).ravel()
        lat=np.asarray(trace.posterior['latent'])[...,-1].ravel()
        sigv=np.asarray(trace.posterior['sigma']).ravel()
        if len(muv)!=len(lat):raise RuntimeError('posterior dimensionality mismatch')
        # Predictive E[var(t+1)|theta,h(t)] for lognormal latent innovation.
        pred=np.exp(muv+phiv*lat+sigv*sigv/2)
        ans.append(dict(mean=float(pred.mean()),p05=float(np.quantile(pred,.05)),
                        p95=float(np.quantile(pred,.95)),samples=pred))
    return ans


def covariance_from_factors(window:FactorWindow,factor_var:np.ndarray,
                            residual='poet',threshold=1.5,regularize=1e-8):
    f=np.asarray(factor_var,float)
    if f.shape!=(window.loading.shape[1],) or not np.all(np.isfinite(f)&(f>0)):
        raise ValueError('bad factor variances')
    if residual=='poet':d=poe_residual(window.resid,threshold)
    elif residual=='diagonal':d=np.diag(np.maximum(window.resid.var(axis=0,ddof=1),EPS))
    else:raise ValueError('unknown residual method')
    return positive_definite((window.loading*f)@window.loading.T+d,regularize)


def risk_trial(d:RiskData,model='poet',start_year=2018,end_year=2019,step=21,
               lookback=252,factors=3,max_origins=None,sv_draws=250):
    """Held-out *development* diagnostic with causal per-origin covariance.

    For each origin fit on previous lookback sessions, measure realized next-5d
    variance of a fixed equal-weight composite and a SPY-only exposure. These
    are TEST PORTFOLIOS, not claimed MASTER portfolio net returns.
    """
    if end_year>2019:raise ValueError('risk trial restricted to dev <=2019')
    date_year=d.dates.astype('datetime64[Y]').astype(int)+1970
    ix=np.flatnonzero((date_year>=start_year)&(date_year<=end_year)&(np.arange(len(d.dates))>=lookback)&(np.arange(len(d.dates))<len(d.dates)-5))
    origins=ix[::step]
    if max_origins is not None:origins=origins[:max_origins]
    if len(origins)<2:raise ValueError('too few causal evaluation origins')
    rows=[]
    for t in origins:
        w=factor_window(d,int(t),lookback,factors)
        preds=[]
        sv = bayesian_factor_sv(w.factor,draws=sv_draws) if model=='bayes_sv' else None
        for k in range(factors):
            if model=='heavy':z=heavy_filter(np.maximum(w.factor_rv[:,k],EPS))['forecast']
            elif model=='realized_garch':z=realized_garch(w.factor[:,k],np.maximum(w.factor_rv[:,k],EPS))['forecast']
            elif model=='bayes_sv':z=sv[k]['mean']
            elif model in ('poet','diagonal'):z=np.mean(w.factor_rv[-22:,k])
            else:raise ValueError(f'unknown risk method {model}')
            preds.append(float(z))
        pred=np.asarray(preds)
        c=covariance_from_factors(w,pred,'poet' if model!='diagonal' else 'diagonal')
        fut=d.daily[t:t+5,w.stocks]
        # Require observed stock data in evaluation (never impute outcomes).
        ok=np.isfinite(fut).all(0)
        if ok.mean()<.9:raise ValueError(f'missing forward risk labels at {d.dates[t]}')
        # Fixed test portfolios: selected names equal weight and zero-ish
        a=np.zeros(len(w.stocks));a[ok]=1/ok.sum()
        spyi=np.where(d.names[w.stocks]=='SPY')[0][0]
        spy=np.zeros(len(a));spy[spyi]=1.
        for name,weights in [('market',spy),('equal_weight',a)]:
            fproj=np.nan_to_num(fut,nan=0.)@weights
            realized=float(np.sum(fproj*fproj)/5)
            variance=float(weights@c@weights)
            rows.append(dict(date=str(d.dates[t]),portfolio=name,model=model,
                             n_stocks=int(len(w.stocks)),coverage=float(ok.mean()),
                             rv=max(realized,EPS),forecast=max(variance,EPS),
                             qlike=qlike(max(realized,EPS),max(variance,EPS))))
    return rows
