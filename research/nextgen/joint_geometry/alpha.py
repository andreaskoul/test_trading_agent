"""Inductive geometry-aware MASTER-alpha efficacy calibration.

Log-SPD Gaussian kernels are Mercer kernels. Diffusion maps use only previously
matured training coordinates, transformed with Nyström extension at decision.
No time-shuffled labels, oracle regime states, stock-level pseudo-replications,
or information after the decision close.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.linalg import cho_factor,cho_solve
from .geometry import DiffusionMap,rbf_kernel_logspd,spd
from .covariance import CovarianceTape
from research.nextgen.joint_state.alpha import weekly_slope_panel,train_moe,_market_features
from research.nextgen.joint_state.contracts import AlphaData


@dataclass(frozen=True)
class GeometricAlphaPanel:
    dates:np.ndarray
    available:np.ndarray
    slopes:np.ndarray
    measurement_variance:np.ndarray
    covariances:np.ndarray
    features:np.ndarray
    original_training_week:np.ndarray
    coverage:np.ndarray


def align_master_to_geometry(d:AlphaData,market,tape:CovarianceTape,min_names=50,
                             min_coverage=.92):
    """Frozen basis trained before alpha rows. All labels mature at t+5.

    Correlations of score and future residual return are computed at each week
    only for the pre-existing eligible MASTER stock set, and aggregated to one
    noisy *weekly* slope, the independent statistical unit for inference.
    """
    w=weekly_slope_panel(d,market,min_names=min_names)
    lookup={int(date.astype('datetime64[D]').astype(int)):j for j,date in enumerate(tape.dates)}
    keep=[];covs=[];coverage=[];features=[]
    for j,date in enumerate(w.date):
        t=lookup.get(int(date.astype('datetime64[D]').astype(int)))
        if t is None or date<=tape.fitted_through or t<21:continue
        if tape.coverage[t-21:t].min()<min_coverage:continue
        try:c=tape.at(t-1,window=21)
        except ValueError:continue
        # Last completed close strictly precedes Thursday's trade decision.
        state=_market_features(market,int(w.original_rows[j])-1)
        if state is None:continue
        covs.append(c);coverage.append(float(tape.coverage[t-21:t].mean()));features.append(state);keep.append(j)
    if len(keep)<60:raise ValueError('insufficient aligned, mature-able MASTER+intraday slope weeks')
    keep=np.asarray(keep)
    dates,available=w.date[keep],w.available[keep]
    if np.any(available<=dates):raise ValueError('invalid future label maturity')
    return GeometricAlphaPanel(dates,available,w.slope[keep],w.variance[keep],
                               np.stack(covs),np.stack(features),w.original_rows[keep],np.array(coverage))


def _weighted_constant(y,measurement_var):
    r=np.asarray(measurement_var,float)
    weights=1/np.maximum(r,1e-9)
    mean=float(np.sum(weights*y)/weights.sum())
    residual=y-mean
    var=float(max(np.var(residual,ddof=1),1e-9))
    return mean,var


class ManifoldGP:
    """Heteroskedastic Gaussian process on the Log-Euclidean SPD manifold.

    Kernel = covariance-amplitude * Gaussian(log-SPD distance) + optional
    Gaussian RBF on lagged market features. Kernels are PSD as both distances
    are Euclidean after a globally defined log/feature transformation.
    """
    def __init__(self,kind='logspd',lengthscale=None,ridge=.1,dim=3):
        if kind not in ('logspd','diffusion','logspd_plus_macro'):
            raise ValueError('unknown manifold kernel')
        self.kind,self.lengthscale,self.ridge,self.dim=kind,lengthscale,ridge,dim

    def _transform(self,cov,features):
        n=len(cov);features=np.asarray(features,float)
        if features.ndim!=2 or features.shape[0]!=n:raise ValueError('malformed state features')
        if self.kind=='diffusion':
            x=self.embedding.transform(cov)
        else:
            from .geometry import tangent_vector
            x=np.stack([tangent_vector(c) for c in cov])
        if self.kind=='logspd_plus_macro':
            macro=(features-self.market_mean)/self.market_scale
            x=np.column_stack([x,macro])
        return x

    def fit(self,cov,features,y,noise):
        c=np.asarray(cov,float);f=np.asarray(features,float)
        yy=np.asarray(y,float);vv=np.asarray(noise,float)
        if len(c)<35 or f.ndim!=2 or f.shape[0]!=len(c) or yy.shape!=(len(c),) or vv.shape!=yy.shape:
            raise ValueError('manifold GP needs >=35 completed weekly labels')
        if not(np.isfinite(c).all() and np.isfinite(f).all() and np.isfinite(yy).all() and
               np.isfinite(vv).all() and (vv>0).all()):raise ValueError('nonfinite GP inputs')
        self.mean,self.variance=_weighted_constant(yy,vv)
        self.market_mean=f.mean(0);self.market_scale=np.maximum(f.std(0),1e-3)
        if self.kind=='diffusion':
            self.embedding=DiffusionMap(dimension=self.dim,alpha=1,time=1).fit(c)
        x=self._transform(c,f)
        d2=np.maximum(0,(x*x).sum(1)[:,None]+(x*x).sum(1)[None,:]-2*x@x.T)
        positive=d2[np.triu_indices(len(d2),1)]
        positive=positive[positive>1e-12]
        self.scale=float(self.lengthscale or (np.sqrt(np.median(positive)/2) if len(positive) else 1.))
        self.scale=max(self.scale,1e-6)
        amp=max(self.variance,1e-8)
        K=amp*np.exp(-d2/(2*self.scale*self.scale))
        K+=np.diag(vv+self.ridge*amp+1e-9)
        self.chol=cho_factor(K,lower=True,check_finite=True)
        self.dual=cho_solve(self.chol,yy-self.mean)
        self.train=x;self.amplitude=amp
        return self

    def predict(self,cov,features):
        c=np.asarray(cov,float);f=np.asarray(features,float)
        if c.ndim==2:c=c[None,:,:]
        if f.ndim==1:f=f[None,:]
        x=self._transform(c,f)
        d2=np.maximum(0,(x*x).sum(1)[:,None]+(self.train*self.train).sum(1)[None,:]-2*x@self.train.T)
        K=self.amplitude*np.exp(-d2/(2*self.scale*self.scale))
        mu=self.mean+K@self.dual
        variance=np.maximum(self.amplitude-np.sum(K*cho_solve(self.chol,K.T).T,axis=1),1e-9)
        return mu,variance


def alpha_geometry_trial(panel:GeometricAlphaPanel,methods=('constant','logspd_gp','diffusion_gp','logspd_macro_gp','manifold_moe'),
                         start='2018-01-01',end='2019-12-31',refit=13,
                         moe_epochs=400,moe_seeds=(11,17,23),device='cpu',max_origins=None):
    """Walk-forward conditional MASTER slope prediction, no post-2019 scores.

    Each method has the same matured labels and common dates. Models are fitted
    on all outcomes with available+label timestamp < test decision. Embedding
    never sees future, and validation/test dates do not affect its bandwidth.
    """
    if refit<1:raise ValueError('invalid refit cadence')
    start,end=np.datetime64(start),np.datetime64(end)
    if end>np.datetime64('2019-12-31') or end<=start:
        raise ValueError('only 2018-2019 development evaluation allowed')
    origins=np.flatnonzero((panel.dates>=start)&(panel.dates<=end))
    if max_origins is not None:origins=origins[:max_origins]
    if len(origins)<1:raise ValueError('no scored alpha dates')
    results=[];models={};trained_week={};trained_n={}
    for j,t in enumerate(origins):
        matched=np.flatnonzero(panel.available<panel.dates[t])
        # Strictly mature target from prior 5-session forecast origin.
        if len(matched)<45:continue
        yy=panel.slopes[matched];vv=panel.measurement_variance[matched]
        cc=panel.covariances[matched];ff=panel.features[matched]
        for method in methods:
            if method=='constant':
                p,internal=_weighted_constant(yy,vv)
            else:
                should_refit=method not in models or j-trained_week[method]>=refit
                if should_refit:
                    if method=='logspd_gp':model=ManifoldGP('logspd').fit(cc,ff,yy,vv)
                    elif method=='diffusion_gp':model=ManifoldGP('diffusion',dim=3).fit(cc,ff,yy,vv)
                    elif method=='logspd_macro_gp':model=ManifoldGP('logspd_plus_macro').fit(cc,ff,yy,vv)
                    elif method=='fisher_gp':model=FisherStateGP().fit(cc,ff,yy,vv)
                    elif method=='manifold_moe':
                        # Gate on inductively fitted diffusion coordinates with
                        # market features, then train chronological weekly MoE.
                        if len(yy)<80:continue
                        emb=DiffusionMap(dimension=3,alpha=1).fit(cc)
                        X=np.column_stack([emb.embedding,ff])
                        model=dict(embedding=emb,model=train_moe(X,yy,vv,
                            n_experts=3,hidden=32,epochs=moe_epochs,seeds=moe_seeds,device=device))
                    else:raise ValueError(f'unrecognised alpha model {method}')
                    models[method]=model;trained_week[method]=j;trained_n[method]=len(matched)
                model=models[method]
                if method=='manifold_moe':
                    z=model['embedding'].transform(panel.covariances[t:t+1])
                    px=np.column_stack([z,panel.features[t:t+1]])
                    pp,pv=model['model']['predict'](px)
                    p,internal=float(pp[0]),float(pv[0])
                else:
                    pp,pv=model.predict(panel.covariances[t:t+1],panel.features[t:t+1])
                    p,internal=float(pp[0]),float(pv[0])
            if not np.isfinite(p) or internal<=0:raise RuntimeError('non-finite conditional efficacy posterior')
            results.append(dict(date=str(panel.dates[t]),method=method,forecast=float(p),
                                actual=float(panel.slopes[t]),posterior_variance=float(internal),
                                observation_variance=float(panel.measurement_variance[t]),
                                trained_on_n=int(len(matched) if method=='constant' else trained_n[method]),
                                matched_intraday_coverage=float(panel.coverage[t]),
                                label_matured_at=str(panel.available[t]),
                                squared_error=float((p-panel.slopes[t])**2)))
    if not results:raise ValueError('no complete alpha geometry trials')
    return results


class FisherStateGP:
    """Bayesian MASTER efficacy on latent *probabilities*, not hard state labels.

    States come from an inductive diffusion map and pre-origin Gaussian HMM.
    A 50/50 mixture of Log-Euclidean SPD and Hellinger simplex Gaussian kernels
    is positive semidefinite and propagates geometric regime uncertainty.
    """
    def __init__(self,k_states=3,dim=3,ridge=.1):
        self.k_states,self.dim,self.ridge=k_states,dim,ridge

    def fit(self,cov,features,y,noise):
        from .geometry import tangent_vector,probability_root,probability_hellinger_kernel
        from research.nextgen.joint_state.regimes import gaussian_hmm
        c=np.asarray(cov,float);yy=np.asarray(y,float);v=np.asarray(noise,float)
        if len(c)<60 or yy.shape!=(len(c),) or v.shape!=yy.shape or not(np.isfinite(c).all() and np.isfinite(yy).all() and np.isfinite(v).all()):
            raise ValueError('Fisher GP needs >=60 complete training weeks')
        if (v<=0).any():raise ValueError('Fisher GP invalid measurement variances')
        self.embedding=DiffusionMap(dimension=self.dim,alpha=1).fit(c)
        z=self.embedding.embedding
        self.hmm=gaussian_hmm(z,k=self.k_states)
        p,self.last_state=self.hmm.filter(z)
        self.prior_sqrt=probability_root(p)
        self.train_log=np.stack([tangent_vector(A) for A in c])
        # Training-only median scales, no validation/test model selection.
        x=self.train_log
        ds=np.maximum(0,(x*x).sum(1)[:,None]+(x*x).sum(1)[None,:]-2*x@x.T)
        distinct=ds[np.triu_indices(len(ds),1)]
        distinct=distinct[distinct>1e-12]
        self.log_scale=float(max(np.sqrt(np.median(distinct)/2),1e-6)) if len(distinct) else 1.
        self.mean,self.variance=_weighted_constant(yy,v)
        amp=max(self.variance,1e-8)
        self.amp=amp
        log_kernel=np.exp(-ds/(2*self.log_scale**2))
        fisher_kernel=probability_hellinger_kernel(p,bandwidth=.5)
        K=amp*(.5*log_kernel+.5*fisher_kernel)
        K+=np.diag(v+self.ridge*amp+1e-9)
        self.chol=cho_factor(K,lower=True)
        self.dual=cho_solve(self.chol,yy-self.mean)
        return self

    def predict(self,cov,features=None):
        from .geometry import tangent_vector,probability_hellinger_kernel
        from research.nextgen.joint_state.regimes import _emission
        from scipy.special import logsumexp
        c=np.asarray(cov,float)
        if c.ndim==2:c=c[None,:,:]
        mus=[];vars=[]
        for A in c:
            z=self.embedding.transform(A[None,:,:])
            ll=_emission(z,self.hmm.means,self.hmm.variance)[0,self.hmm.map_state]
            prior=self.last_state@self.hmm.transition
            px=np.log(np.maximum(prior,1e-300))+ll
            post=np.exp(px-logsumexp(px))
            self.last_state=post
            p=np.bincount(self.hmm.map_state,weights=post,minlength=self.k_states)
            x=tangent_vector(A)
            d2=np.maximum(0,((self.train_log-x)**2).sum(1))
            a=np.exp(-d2/(2*self.log_scale**2))
            # input is state probability, original training rows filtered only.
            from .geometry import probability_root
            b=probability_hellinger_kernel(p,self.prior_sqrt**2,bandwidth=.5).reshape(-1)
            k=self.amp*(.5*a+.5*b)
            mu=self.mean+k@self.dual
            v=max(self.amp-k@cho_solve(self.chol,k),1e-9)
            mus.append(mu);vars.append(v)
        return np.array(mus),np.array(vars)
