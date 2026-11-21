"""Nonlinear diffusion-map regimes, affine-invariant soft prototypes, Grassmann drift.

Diagnostics predict *next-five-session realized SPY variance* from filtered
state probabilities; regime names are never used as a retrospective truth label.
Every fitted coordinate, bandwidth, transition and target mean uses training
observations whose forecast target matures before training cutoff.
"""
from __future__ import annotations
import numpy as np
from scipy.special import logsumexp
from .geometry import (spd,logm,affine_distance,frechet_mean,DiffusionMap,
                       ortho_columns,grassmann_distance)
from .covariance import CovarianceTape,weekly_origins
from research.nextgen.joint_state.regimes import gaussian_hmm, _emission


def gras_drift(tape:CovarianceTape,origin:int,lookback=100,offset=21,rank=3):
    """Grassmann distance between two overlapping rank-k factor subspaces.

    Uses observed *factor* daily returns in the fixed outer PCA basis; thus
    measures subspace reorientation in factor space, not arbitrary sign flips.
    With k_outer=3, rank must be <3 for meaningful rotation.
    """
    x=tape.factor
    if rank>=x.shape[1] or rank<1 or origin<lookback+offset:
        raise ValueError('invalid Grassmann drift geometry')
    a=x[origin-lookback:origin]
    b=x[origin-offset-lookback:origin-offset]
    if not (np.isfinite(a).all() and np.isfinite(b).all()):raise ValueError('missing factor daily returns')
    _,_,va=np.linalg.svd(a-a.mean(0),full_matrices=False)
    _,_,vb=np.linalg.svd(b-b.mean(0),full_matrices=False)
    return grassmann_distance(va[:rank].T,vb[:rank].T)


def cov_slope_features(tape,origins,grassmann_rank=2):
    """Past-only covariance and Grassmann-state tensors at weekly decisions."""
    mats=[];rot=[];trace=[];kept=[]
    for t in origins:
        t=int(t)
        try:
            mat=tape.at(t-1,5)
            angle=gras_drift(tape,t-1,rank=grassmann_rank)
        except ValueError:continue
        mats.append(mat);rot.append(angle);trace.append(np.log(max(np.trace(mat),1e-12)));kept.append(t)
    if not mats:raise ValueError('no matched weekly manifold states')
    return np.stack(mats),np.array(rot),np.array(trace),np.array(kept,dtype=int)


def spy_next_rv(tape,origin,h=5):
    """Risk target: true projected fixed-factor variance. NOT exact SPY variance.

    In the finite factor frame, use equal-weight factor-portfolio projected RV.
    For actual SPY risk caller should provide SPY intraday tape separately.
    """
    if origin+h>=len(tape.dates):raise ValueError('unmatured risk label')
    cov=tape.target(origin,h)
    w=np.ones(len(cov))/np.sqrt(len(cov))
    return float(w@cov@w)


class AIRMRegime:
    """Intrinsic SPD k-means with soft assignments and causal Markov filtering.

    AIRM radial pseudo-likelihood is NOT a normalized density on SPD: use the
    resulting posterior ONLY for risk prediction, never compare pseudo-LL
    to Gaussian HMM log predictive density as a proper scoring rule.
    """
    def __init__(self,k=3,maxiter=24,temperature=None,seed=11):
        self.k,self.maxiter,self.temperature,self.seed=k,maxiter,temperature,seed

    def fit(self,covariances,matured_risks):
        c=np.asarray(covariances,float);y=np.asarray(matured_risks,float)
        if c.ndim!=3 or c.shape[1]!=c.shape[2] or len(c)<max(35,self.k*12) or y.shape!=(len(c),):
            raise ValueError('invalid AIRM regime samples')
        if not(np.isfinite(c).all() and np.isfinite(y).all() and (y>0).all()):
            raise ValueError('nonfinite SPD state data')
        c=np.stack([spd(x) for x in c]);n=len(c)
        rng=np.random.default_rng(self.seed)
        ids=np.array([int(n*(i+.5)/self.k) for i in range(self.k)])
        centers=c[ids].copy()
        temp=self.temperature
        for iteration in range(self.maxiter):
            dist=np.array([[affine_distance(x,z)**2 for z in centers] for x in c])
            if temp is None:
                d=np.median(dist.min(1));tt=max(float(d),1e-4)
            else:tt=float(temp)
            ll=-dist/(2*tt);ll-=logsumexp(ll,axis=1,keepdims=True)
            resp=np.exp(ll)
            nextcenters=[]
            for j in range(self.k):
                w=resp[:,j]+1e-5
                nextcenters.append(frechet_mean(c,'affine',w,maxiter=80,tol=1e-7))
            centers=np.stack(nextcenters)
        self.centers=centers;self.temperature=tt
        # Posterior emissions only use train data; soft expected transition
        # regularised to preserve support. Transition models weekly states.
        trans=resp[:-1].T@resp[1:]+.05
        self.trans=trans/trans.sum(1,keepdims=True)
        self.prior=resp[-1]
        # Train future risk means from y matured by train cutoff.
        self.risk=(resp.T@y)/np.maximum(resp.sum(0),1e-12)
        return self

    def likelihood(self,cov):
        dist=np.array([affine_distance(spd(cov),z)**2 for z in self.centers])
        ll=-dist/(2*self.temperature)
        return np.exp(ll-np.max(ll))

    def step(self,cov,previous=None):
        prior=self.prior.copy() if previous is None else np.asarray(previous)@self.trans
        p=prior*self.likelihood(cov)
        p/=p.sum()
        return p,float(p@self.risk)


class DiffusionRegime:
    """Inductive diffusion manifold + Gaussian HMM, trained before test windows."""
    def __init__(self,k=3,dim=3,with_grassmann=True,seed=11):
        self.k,self.dim,self.with_grassmann,self.seed=k,dim,with_grassmann,seed

    def _features(self,c,rotation):
        e=self.embedding.transform(c)
        trace=np.log(np.maximum(np.trace(c,axis1=1,axis2=2),1e-12))
        f=np.column_stack([e,trace,rotation]) if self.with_grassmann else np.column_stack([e,trace])
        return (f-self.loc)/self.scale

    def fit(self,c,rotation,matured_risks):
        c=np.asarray(c,float);rot=np.asarray(rotation,float);y=np.asarray(matured_risks,float)
        if len(c)<60 or rot.shape!=(len(c),) or y.shape!=(len(c),):raise ValueError('diffusion regime needs training')
        self.embedding=DiffusionMap(dimension=self.dim,alpha=1,time=1).fit(c)
        e=self.embedding.embedding
        f=np.column_stack([e,np.log(np.trace(c,axis1=1,axis2=2)),rot]) if self.with_grassmann else np.column_stack([e,np.log(np.trace(c,axis1=1,axis2=2))])
        self.loc=f.mean(0);self.scale=np.maximum(f.std(0),.05)
        train=(f-self.loc)/self.scale
        self.hmm=gaussian_hmm(train,k=self.k,iterations=80,seed=self.seed)
        # Always use FILTERED probabilities when mapping states to future risk;
        # fully smoothed EM responsibilities would leak future even in train.
        filtered,_=self.hmm.filter(train)
        self.risk=filtered.T@y/np.maximum(filtered.sum(0),1e-12)
        self.last_state=self.hmm.filter(train)[1]
        return self

    def state(self,c,rotation,previous=None):
        x=self._features(np.asarray(c)[None,:,:],np.asarray([rotation]))
        state=self.last_state if previous is None else np.asarray(previous,float)
        prior=state@self.hmm.transition
        ll=_emission(x,self.hmm.means,self.hmm.variance)[0,self.hmm.map_state]
        z=np.log(np.maximum(prior,1e-300))+ll
        posterior=np.exp(z-logsumexp(z))
        p=np.bincount(self.hmm.map_state,weights=posterior,minlength=self.k)
        return posterior,float(p@self.risk),p


def states_trial(tape,method='diffusion_hmm',train_cutoff='2017-12-31',first='2018-01-01',last='2019-11-01',
                 dim=3,k=3,max_origins=None):
    # Full training regimes are fitted with matured labels ONLY <= cutoff.
    origins=weekly_origins(tape,first='2016-09-01',last=last,minimum=129)
    mats,rots,logtr,idx=cov_slope_features(tape,origins,grassmann_rank=min(2,tape.loading.shape[1]-1))
    cutoff=np.datetime64(train_cutoff,'D')
    tr=(tape.dates[idx+5]<=cutoff)
    ev=(tape.dates[idx]>=np.datetime64(first))&(tape.dates[idx]<=np.datetime64(last))
    if tr.sum()<60 or ev.sum()<10:raise ValueError('insufficient matured state training/test coverage')
    y=np.asarray([spy_next_rv(tape,int(t)) for t in idx])
    if method=='airm':model=AIRMRegime(k=k).fit(mats[tr],y[tr])
    elif method in ('diffusion_hmm','diffusion_grassmann'):
        model=DiffusionRegime(k=k,dim=dim,with_grassmann=method=='diffusion_grassmann').fit(mats[tr],rots[tr],y[tr])
    else:raise ValueError('unregistered geometric regime model')
    last_state=None;rows=[]
    # Bridge the train/test gap using only states observed before each forecast.
    # These intermediate states are NOT fit to their future risk outcomes.
    after_train=(idx>idx[np.flatnonzero(tr)[-1]])&(tape.dates[idx]<=np.datetime64(last))
    for i in np.flatnonzero(after_train):
        if method=='airm':
            last_state,rhat=model.step(mats[i],last_state)
            p=last_state
        else:
            last_state,rhat,p=model.state(mats[i],rots[i],last_state)
        if not ev[i]:
            continue
        real=y[i]
        # Match proper QLIKE baseline on *same target and test dates*.
        baseline=float(np.mean(y[tr])); q=lambda a,b:a/b-np.log(a/b)-1
        rows.append(dict(date=str(tape.dates[idx[i]]),model=method,
                         projected_future_variance=float(real),predicted=float(rhat),
                         train_constant_variance=baseline,qlike=float(q(real,rhat)),
                         baseline_qlike=float(q(real,baseline)),
                         states=[float(x) for x in p],grassmann_rotation_rad=float(rots[i])))
        if max_origins is not None and len(rows)>=max_origins:break
    return rows
