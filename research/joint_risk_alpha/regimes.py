"""Causal Gaussian HMM, explicit-duration HSMM and Bayesian online changepoint detection.

HMM/HSMM train parameters on PAST development only. Predictions must use the
forward FILTER and never retrospective Viterbi/smoothed labels at decision time.
"""
from dataclasses import dataclass
import numpy as np
from scipy.special import logsumexp, gammaln
EPS=1e-9

def _log_gauss(x, mu, var):
    return -.5*(np.sum(np.log(2*np.pi*var),axis=-1)[None,:]
                 +np.sum((x[:,None,:]-mu[None,:,:])**2/var[None,:,:],axis=2))


def _fb(log_em, log_A, log_pi):
    T,K=log_em.shape
    a=np.empty((T,K));b=np.zeros((T,K))
    a[0]=log_pi+log_em[0]
    for t in range(1,T):a[t]=log_em[t]+logsumexp(a[t-1,:,None]+log_A,axis=0)
    ll=logsumexp(a[-1])
    for t in range(T-2,-1,-1):b[t]=logsumexp(log_A+log_em[t+1][None,:]+b[t+1][None,:],axis=1)
    gamma=np.exp(a+b-ll)
    xi=np.zeros((K,K))
    for t in range(T-1):xi+=np.exp(a[t,:,None]+log_A+log_em[t+1][None,:]+b[t+1][None,:]-ll)
    return gamma,xi,ll

@dataclass
class GaussianHMM:
    n_states:int=3
    seed:int=20261121
    mu:np.ndarray|None=None
    var:np.ndarray|None=None
    trans:np.ndarray|None=None
    pi:np.ndarray|None=None
    loglik:float|None=None
    def fit(self, X, max_iter=100,tol=1e-5):
        X=np.asarray(X,float)
        if X.ndim!=2 or X.shape[0]<40 or not np.isfinite(X).all():raise ValueError('HMM needs complete 2D past observations')
        T,D=X.shape;K=self.n_states
        if not 2<=K<=6:raise ValueError('K must be 2..6')
        rng=np.random.default_rng(self.seed)
        inds=np.sort(rng.choice(T,K,replace=False));mu=X[inds].copy()
        var=np.tile(np.maximum(X.var(0),1e-5),(K,1))
        A=.94*np.eye(K)+.06/K*np.ones((K,K));pi=np.ones(K)/K
        previous=-np.inf
        for _ in range(max_iter):
            em=_log_gauss(X,mu,var)
            gamma,xi,ll=_fb(em,np.log(A),np.log(pi))
            g=np.maximum(gamma.sum(0),1e-8)
            mu=(gamma.T@X)/g[:,None]
            var=np.maximum((gamma.T@(X*X))/g[:,None]-mu*mu,1e-6)
            A=(xi+1e-3);A/=A.sum(1,keepdims=True)
            pi=(gamma[0]+.01);pi/=pi.sum()
            if abs(ll-previous)<tol*max(T,1):break
            previous=ll
        self.mu,self.var,self.trans,self.pi,self.loglik=mu,var,A,pi,float(ll)
        return self
    def filter(self,X,prior=None):
        """Filtered p(z_t|x_0,...,x_t), forward only, with fixed parameters."""
        X=np.asarray(X,float)
        if self.mu is None:raise ValueError('fit HMM first')
        if X.ndim!=2 or X.shape[1]!=self.mu.shape[1] or not np.isfinite(X).all():raise ValueError('HMM features')
        p=self.pi.copy() if prior is None else np.asarray(prior,float).copy()
        out=[];em=_log_gauss(X,self.mu,self.var)
        for t in range(len(X)):
            if t:p=p@self.trans
            v=np.log(np.maximum(p,EPS))+em[t]
            p=np.exp(v-logsumexp(v));out.append(p.copy())
        return np.asarray(out)
    def predict_next(self,X):return self.filter(X)[-1]@self.trans

@dataclass
class HiddenSemiMarkov:
    """Explicit-duration HSMM: state=(regime, remaining lifetime).

    Duration d has truncated shifted Poisson law (d>=1), optimised via
    likelihood with emissions learned on historical data by GaussianHMM.
    Emits only *filtered* probabilities. Unlike an ordinary HMM, hazard can
    depend on the age/remaining duration of the regime.
    """
    n_states:int=3
    max_duration:int=20
    hmm:GaussianHMM|None=None
    duration_mean:np.ndarray|None=None
    duration_pmf:np.ndarray|None=None
    def _dist(self,means):
        d=np.arange(1,self.max_duration+1)
        m=np.asarray(means,float)
        logs=(d[None,:]-1)*np.log(np.maximum(m[:,None],EPS))-m[:,None]-gammaln(d[None,:])
        v=np.exp(logs-logsumexp(logs,axis=1,keepdims=True))
        return v
    def fit(self,X,maxiter=120):
        from scipy.optimize import minimize
        self.hmm=GaussianHMM(self.n_states).fit(X)
        log_em=_log_gauss(np.asarray(X,float),self.hmm.mu,self.hmm.var)
        def nll(logmeans):
            pmf=self._dist(np.exp(logmeans));p=self._run(log_em,pmf,return_ll=True)
            return -p
        opt=minimize(nll,np.log(np.full(self.n_states,7.)),method='L-BFGS-B',bounds=[(np.log(1.1),np.log(self.max_duration*2.))]*self.n_states,options={'maxiter':maxiter})
        self.duration_mean=np.exp(opt.x);self.duration_pmf=self._dist(self.duration_mean)
        return self
    def _run(self,log_em,pmf,return_ll=False):
        K,D=pmf.shape
        p=self.hmm.pi[:,None]*pmf
        ll=0.;outs=[]
        for t in range(len(log_em)):
            if t:
                nxt=np.zeros_like(p)
                nxt[:,:-1]+=p[:,1:]
                nxt+=(p[:,0]@self.hmm.trans)[:,None]*pmf
                p=nxt
            lp=np.log(np.maximum(p,EPS))+log_em[t,:,None]
            c=logsumexp(lp)
            p=np.exp(lp-c);ll+=c
            outs.append(p.sum(1))
        return ll if return_ll else np.asarray(outs)
    def filter(self,X):
        if self.hmm is None:raise ValueError('fit HSMM first')
        return self._run(_log_gauss(np.asarray(X,float),self.hmm.mu,self.hmm.var),self.duration_pmf)

@dataclass
class BOCPD:
    """Adams-MacKay Bayesian online changepoint: Student-t NIG conjugacy.

    Fixed constant hazard, with prior parameters for Gaussian return/risk
    measurements. Returns causal reset probability and run-length posterior.
    """
    hazard:float=1/65
    max_run:int=500
    mu0:float=0.
    kappa0:float=.1
    alpha0:float=2.
    beta0:float=1.
    def filter(self,x):
        from scipy.stats import t as student_t
        x=np.asarray(x,float)
        if x.ndim!=1 or not np.isfinite(x).all():raise ValueError('BOCPD scalar series only')
        if not 0<self.hazard<1:raise ValueError('hazard outside (0,1)')
        p=np.array([1.]);mu=np.array([self.mu0]);k=np.array([self.kappa0]);a=np.array([self.alpha0]);b=np.array([self.beta0])
        reset=[];expect=[]
        for val in x:
            scales=np.sqrt(b*(k+1)/(a*k))
            pred=student_t.pdf(val,df=2*a,loc=mu,scale=scales)
            weighted=p*np.maximum(pred,1e-300)
            new=np.zeros(min(len(p)+1,self.max_run))
            new[0]=self.hazard*weighted.sum()
            ncopy=min(len(p),self.max_run-1)
            new[1:1+ncopy]+=(1-self.hazard)*weighted[:ncopy]
            new[-1]+=(1-self.hazard)*weighted[ncopy:].sum()
            new/=new.sum()
            reset.append(new[0]);expect.append(float(new@np.arange(len(new))))
            kn=k+1;mun=(k*mu+val)/kn
            an=a+.5;bn=b+(k*(val-mu)**2)/(2*kn)
            mu=np.r_[self.mu0,mun[:len(new)-1]]
            k=np.r_[self.kappa0,kn[:len(new)-1]]
            a=np.r_[self.alpha0,an[:len(new)-1]]
            b=np.r_[self.beta0,bn[:len(new)-1]]
            p=new
        return {'changepoint_probability':np.asarray(reset),'expected_run':np.asarray(expect),'last_run_probs':p}
