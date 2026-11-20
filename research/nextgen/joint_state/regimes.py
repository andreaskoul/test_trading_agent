"""HMM, explicit-duration HSMM, conjugate Bayesian online changepoint filter.

All filter probabilities at origin t condition on observations up to t only.
An evaluation at t+1 must use the previous filtered distribution, not smoothed
Viterbi labels fit using the entire evaluation period.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from scipy.special import logsumexp, gammaln

EPS=1e-12


def _norm(x):
    x=np.asarray(x,float)
    if x.ndim!=2 or x.shape[0]<50 or x.shape[1]<1 or not np.isfinite(x).all():
        raise ValueError('regime input must be finite T x features, T>=50')
    return x


def _emission(x,mean,var):
    # Gaussian emissions with per-state diagonal covariance.
    dx=x[:,None,:]-mean[None,:,:]
    return -.5*(np.log(2*np.pi*var)[None,:,:]+dx*dx/var[None,:,:]).sum(2)


def _fb(loge,A,pi):
    """Log-scaled exact forward-backward with aggregate emissions."""
    n,s=loge.shape
    la=np.where(A>0,np.log(np.maximum(A,EPS)),-np.inf);lp=np.where(pi>0,np.log(np.maximum(pi,EPS)),-np.inf)
    f=np.empty((n,s));c=np.empty(n)
    f[0]=lp+loge[0];c[0]=logsumexp(f[0]);f[0]-=c[0]
    for t in range(1,n):
        f[t]=loge[t]+logsumexp(f[t-1][:,None]+la,axis=0)
        c[t]=logsumexp(f[t]);f[t]-=c[t]
    b=np.zeros((n,s))
    for t in range(n-2,-1,-1):
        b[t]=logsumexp(la+loge[t+1][None,:]+b[t+1][None,:],axis=1)-c[t+1]
    g=f+b;g=np.exp(g-logsumexp(g,axis=1,keepdims=True))
    xi=np.zeros((s,s))
    for t in range(n-1):
        pair=f[t,:,None]+la+loge[t+1,None,:]+b[t+1,None,:]
        xi+=np.exp(pair-logsumexp(pair))
    return g,xi,float(c.sum()),np.exp(f)


@dataclass
class StateModel:
    family:str
    means:np.ndarray
    variance:np.ndarray
    transition:np.ndarray
    start:np.ndarray
    map_state:np.ndarray
    log_likelihood:float
    k:int

    def filter(self,observations,prior=None):
        x=np.asarray(observations,float)
        if x.ndim==1:x=x[None,:]
        if x.shape[1]!=self.means.shape[1] or not np.isfinite(x).all():
            raise ValueError('invalid state features')
        state=self.start.copy() if prior is None else np.asarray(prior,float).copy()
        if state.shape!=self.start.shape or not np.isclose(state.sum(),1):
            raise ValueError('invalid prior state')
        emit=_emission(x,self.means,self.variance)
        path=[]
        for t in range(len(x)):
            if t:state=state@self.transition
            state=state*np.exp(emit[t,self.map_state]-np.max(emit[t,self.map_state]))
            state/=state.sum()
            agg=np.bincount(self.map_state,weights=state,minlength=self.k)
            path.append(agg)
        return np.asarray(path),state

    def next_state(self,state):
        nxt=np.asarray(state)@self.transition
        return np.bincount(self.map_state,weights=nxt,minlength=self.k)


def gaussian_hmm(x,k=3,iterations=80,seed=11):
    x=_norm(x);n,d=x.shape
    if k<2 or k>min(n//12,6):raise ValueError('unreasonable number of states')
    rng=np.random.default_rng(seed)
    means=x[np.linspace(0,n-1,k,dtype=int)].copy()+.01*rng.normal(size=(k,d))
    var=np.maximum(np.var(x,axis=0)[None,:],1e-5)*np.ones((k,1))
    a=np.ones((k,k))*.05/(k-1);np.fill_diagonal(a,.95)
    pi=np.ones(k)/k;last=-np.inf
    for it in range(iterations):
        loge=_emission(x,means,var)
        g,xi,ll,_=_fb(loge,a,pi)
        mass=np.maximum(g.sum(0),EPS)
        means=(g.T@x)/mass[:,None]
        var=np.maximum((g[:,:,None]*(x[:,None,:]-means[None,:,:])**2).sum(0)/mass[:,None],1e-6)
        a=(xi+.5);a/=a.sum(1,keepdims=True)
        pi=(g[0]+.1);pi/=pi.sum()
        if abs(ll-last)<1e-6:break
        last=ll
    return StateModel('HMM',means,var,a,pi,np.arange(k),ll,k)


def _duration_matrix(k,dmax,shape=3.):
    # Explicit durations 1..dmax with truncated discrete gamma-like PMF.
    d=np.arange(1,dmax+1,dtype=float)
    center=np.linspace(3,8,k)
    probs=np.exp(-(d[None,:]-center[:,None])**2/(2*shape**2))
    return probs/probs.sum(axis=1,keepdims=True)


def _hsmm_transitions(trans,duration):
    k,dmax=duration.shape;s=k*dmax
    out=np.zeros((s,s))
    for i in range(k):
        for d in range(1,dmax+1):
            src=i*dmax+d-1
            if d>1:out[src,i*dmax+d-2]=1
            else:
                for j in range(k):
                    if j==i:continue
                    out[src,j*dmax:(j+1)*dmax]+=trans[i,j]*duration[j]
    if not np.allclose(out.sum(1),1):raise AssertionError('invalid HSMM transition')
    return out


def gaussian_hsmm(x,k=3,dmax=12,iterations=35,seed=11):
    """Expanded-state explicit-duration Gaussian HSMM with EM re-estimation.

    Duration is a learned categorical PMF on 1..dmax. Hidden states include
    (regime, time remaining) and cannot exit prematurely. No simulation labels
    or post-test smoothing used in forecasting.
    """
    x=_norm(x);n,dim=x.shape
    if not (2<=k<=5 and 2<=dmax<=20 and n>=k*dmax*3):raise ValueError('HSMM design invalid')
    h=gaussian_hmm(x,k=k,iterations=20,seed=seed)
    means=h.means.copy();var=h.variance.copy()
    trans=np.full((k,k),1/(k-1));np.fill_diagonal(trans,0.)
    duration=_duration_matrix(k,dmax)
    amap=np.repeat(np.arange(k),dmax)
    ll=-np.inf
    for it in range(iterations):
        a=_hsmm_transitions(trans,duration)
        pi=np.concatenate([duration[j]/k for j in range(k)])
        loge=_emission(x,means,var)[:,amap]
        g,xi,ll,_=_fb(loge,a,pi)
        agg=g.reshape(n,k,dmax).sum(2)
        mass=np.maximum(agg.sum(0),EPS)
        means=agg.T@x/mass[:,None]
        var=np.maximum((agg[:,:,None]*(x[:,None,:]-means[None,:,:])**2).sum(0)/mass[:,None],1e-6)
        count=np.zeros((k,k));dur=np.ones_like(duration)*.01
        for i in range(k):
            end_idx=i*dmax
            for j in range(k):
                if i==j:continue
                for di in range(dmax):
                    num=xi[end_idx,j*dmax+di]
                    count[i,j]+=num;dur[j,di]+=num
        trans=count+.1;np.fill_diagonal(trans,0)
        trans=trans/np.maximum(trans.sum(1,keepdims=True),EPS)
        duration=dur/dur.sum(1,keepdims=True)
    a=_hsmm_transitions(trans,duration)
    pi=np.concatenate([duration[j]/k for j in range(k)])
    return StateModel('HSMM',means,var,a,pi,amap,ll,k)


@dataclass
class BOCPDPosterior:
    run_prob:np.ndarray
    mus:np.ndarray
    kappas:np.ndarray
    alphas:np.ndarray
    betas:np.ndarray


def bocpd(x,hazard=1/80,max_run=252,prior_mu=0.,kappa0=.1,alpha0=2.,beta0=.1):
    """Adams-MacKay online changepoint with Normal-Inverse-Gamma observations.

    Returns for each observed time its posterior changepoint probability,
    posterior probability of long run and a predictive mean/variance. No
    hindsight, likelihood computed using Student-t conjugate predictive.
    """
    from scipy.stats import t as student_t
    x=np.asarray(x,float)
    if x.ndim!=1 or len(x)<10 or not np.isfinite(x).all() or not 0<hazard<1:
        raise ValueError('BOCPD inputs invalid')
    if max_run<10:raise ValueError('max_run too short')
    r=np.array([1.]);mu=np.array([prior_mu]);k=np.array([kappa0]);a=np.array([alpha0]);b=np.array([beta0]);out=[]
    for date,val in enumerate(x):
        df=2*a;scale=np.sqrt(b*(k+1)/(a*k))
        evidence=student_t.pdf(val,df,loc=mu,scale=scale)
        grow=r*evidence*(1-hazard);cp=float(np.sum(r*evidence*hazard))
        updated=np.r_[cp,grow][:max_run]
        total=updated.sum()
        if total<=0 or not np.isfinite(total):raise RuntimeError('BOCPD likelihood degenerate')
        updated/=total
        # New changepoint run length 0 holds the prior predictive; 1.. run
        # length n+1 assimilates this observation under all previous histories.
        kp=k+1;mp=(k*mu+val)/kp;ap=a+.5;bp=b+.5*k*(val-mu)**2/kp
        r=updated
        mu=np.r_[prior_mu,mp][:len(r)];k=np.r_[kappa0,kp][:len(r)]
        a=np.r_[alpha0,ap][:len(r)];b=np.r_[beta0,bp][:len(r)]
        # Predictive moments for NIG posterior exist when alpha>1.
        vf=b*(k+1)/(k*np.maximum(a-1,EPS))
        pm=float(r@mu);pv=float(r@(vf+mu**2)-pm**2)
        out.append(dict(origin=date,cp_probability=float(r[0]),
                        p_run_gt_20=float(r[21:].sum()),mean=pm,variance=max(pv,EPS)))
    return out


def regime_trial(x,train_end,pred_start,pred_end,method='hmm',seed=11):
    """Train <= train_end, filter *forward* from that date; never re-fit on trial dates.

    Return one-step ahead log predictive density, not an in-sample state fit.
    """
    x=_norm(x)
    if not (100<=train_end<pred_start<pred_end<=len(x)):
        raise ValueError('strict chronological train/pred separation required')
    if method=='hmm':m=gaussian_hmm(x[:train_end],seed=seed)
    elif method=='hsmm':m=gaussian_hsmm(x[:train_end],seed=seed)
    elif method=='bocpd':
        prior=float(np.mean(x[:train_end,0]));return bocpd(x[:pred_end,0],prior_mu=prior)[pred_start:pred_end]
    else:raise ValueError('bad regime model')
    _,last=m.filter(x[:train_end])
    # Between train_end and pred_start, pass causal observations but no fitting.
    for t in range(train_end,pred_start):_,last=m.filter(x[t],last@m.transition)
    rows=[]
    for t in range(pred_start,pred_end):
        prior=last@m.transition
        loge=_emission(x[t:t+1],m.means,m.variance)[0,m.map_state]
        predictive=float(logsumexp(np.log(np.maximum(prior,EPS))+loge))
        _,last=m.filter(x[t],prior) # one-step prior, filtered with current observation
        rows.append(dict(origin=t,log_density=predictive,
                         state=m.next_state(last).tolist(),family=method))
    return rows
