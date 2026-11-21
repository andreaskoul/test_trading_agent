"""Conditional efficacy of frozen MASTER scores, not a second trading alpha.

Pre-trade features at t; labels from t+2..t+6 are only admitted to
calibration when that complete six-session delay has elapsed. Per-week
cross-sectional slopes are NOT independent: evaluate by time blocks.
"""
from __future__ import annotations
from dataclasses import dataclass
from scipy.optimize import minimize
import numpy as np
import pandas as pd
from scipy.special import logsumexp

MATURE=6

def weekly_slope(score,y,elig,min_names=40):
    ok=elig&np.isfinite(score)&np.isfinite(y)
    if ok.sum()<min_names:return np.nan,np.nan,int(ok.sum())
    s=np.asarray(score[ok],float);target=np.asarray(y[ok],float)
    order=pd.Series(s).rank(pct=True).to_numpy()
    x=(order-order.mean());x/=max(x.std(),1e-8)
    intercept=target.mean()
    theta=float(x@(target-intercept)/(x@x))
    resid=target-intercept-theta*x
    var=float((resid@resid)/max(ok.sum()-2,1)/(x@x))
    return theta,max(var,1e-9),int(ok.sum())


def extract_weekly(panel):
    """Returns row index, decision date, cross-sectional slope and slope variance."""
    ix=np.where(panel.dates.weekday==3)[0];out=[]
    for t in ix:
        th,var,n=weekly_slope(panel.score[t],panel.outcome[t],panel.eligible[t])
        # Past-only features; computed at close of current decision t.
        r=panel.spy_returns[max(0,t-21):t+1]
        vol=float(np.nanstd(r,ddof=1)) if len(r)>=15 and np.isfinite(r).sum()>=15 else np.nan
        cr=panel.stock_returns[max(0,t-20):t+1]
        dispersion=float(np.nanmean(np.nanstd(cr,axis=1))) if len(cr)>=15 else np.nan
        row=np.array([vol,dispersion,float(np.nanmean(panel.score[t][panel.eligible[t]]))],float)
        out.append({'t':int(t),'date':str(panel.dates[t].date()),'theta':th,'theta_var':var,'n':n,'environment':row})
    return out

@dataclass
class DynamicAlpha:
    """Hierarchical observation-variance-aware AR1 Kalman state for signal efficacy.

    Parameters fit by maximizing the marginal likelihood only on *completed*
    training-period weekly slopes. Online updates admit labels after maturity.
    """
    mu:float=0.
    rho:float=.9
    q:float=.0001
    vfloor:float=.00001
    def _run(self,obs,variances,do_fit=False):
        m=self.mu;P=max(self.q/(1-self.rho**2),self.vfloor)
        nll=0.;states=[]
        for y,vy in zip(obs,variances):
            m=self.mu+self.rho*(m-self.mu);P=self.rho**2*P+self.q
            states.append((m,P))
            if np.isfinite(y):
                S=P+max(vy,self.vfloor);err=y-m
                nll+=.5*(np.log(2*np.pi*S)+err*err/S)
                k=P/S;m+=k*err;P*=(1-k)
        return nll,states
    def fit(self,slopes,errors):
        slopes=np.asarray(slopes,float);errors=np.asarray(errors,float)
        usable=np.isfinite(slopes)&np.isfinite(errors)
        if usable.sum()<60:raise ValueError('Kalman calibration needs >=60 completed weekly outcomes')
        x=slopes[usable];vv=errors[usable];m0=float(np.mean(x))
        def obj(par):
            rho=1/(1+np.exp(-par[0]));q=np.exp(par[1]);vfloor=np.exp(par[2]);self.mu=m0;self.rho=rho;self.q=q;self.vfloor=vfloor
            return self._run(slopes,errors)[0]
        opt=minimize(obj,[2.,np.log(max(np.var(x)*.05,1e-7)),np.log(max(np.median(vv),1e-8))],method='L-BFGS-B',bounds=[(-3,6),(-18,0),(-19,-1)])
        obj(opt.x)
        return self
    def filter_delayed(self,decisions,cutoff_t=None):
        """At decision index t, consume only labels with origin+MATURE <= t."""
        dec=sorted(decisions,key=lambda q:q['t'])
        if not dec:return []
        prior=self.mu;P=max(self.q/(1-self.rho*self.rho),self.vfloor)
        queued=[];out=[]
        for j,row in enumerate(dec):
            t=row['t']
            prior=self.mu+self.rho*(prior-self.mu);P=self.rho**2*P+self.q
            for q in queued[:]:
                if q['t']+MATURE<=t:
                    if np.isfinite(q['theta']):
                        S=P+max(q['theta_var'],self.vfloor);k=P/S
                        prior+=k*(q['theta']-prior);P*=(1-k)
                    queued.remove(q)
            out.append({'date':row['date'],'t':t,'mean':prior,'sd':float(np.sqrt(P)),'labels_available':sum(z['t']+MATURE<=t for z in dec[:j])})
            queued.append(row)
        return out

@dataclass
class SoftRegimeAlpha:
    """Bayesian ridge partial pooling of alpha slope on *filtered* regime probabilities.

    This model does not infer regimes itself and NEVER accepts retrospectively
    smoothed or post-outcome states. The caller must supply dated filtered probs.
    """
    lam:float=50.
    coef:np.ndarray|None=None
    cov:np.ndarray|None=None
    sigma2:float|None=None
    def fit(self,environment,filtered_probs,theta,theta_var,valid):
        X=np.column_stack([np.ones(len(environment)),np.asarray(environment,float),np.asarray(filtered_probs,float)])
        y=np.asarray(theta,float);se=np.asarray(theta_var,float)
        m=np.asarray(valid,bool)&np.isfinite(y)&np.isfinite(se)&np.isfinite(X).all(1)
        if m.sum()<65:raise ValueError('need >=65 mature causal training labels')
        means=X[m,1:].mean(0);sd=np.maximum(X[m,1:].std(0),1e-5)
        X[:,1:]=(X[:,1:]-means)/sd
        self.scaling=(means,sd)
        w=1/np.maximum(se[m],1e-5);Z=X[m]
        penalty=np.eye(Z.shape[1])*self.lam;penalty[0,0]=1e-6
        A=Z.T@(Z*w[:,None])+penalty
        self.coef=np.linalg.solve(A,Z.T@(w*y[m]));self.cov=np.linalg.inv(A)
        self.sigma2=max(float(np.mean((y[m]-Z@self.coef)**2)),1e-10)
        return self
    def predict(self,environment,filtered_probs):
        if self.coef is None:raise ValueError('fit first')
        X=np.column_stack([np.ones(len(environment)),np.asarray(environment,float),np.asarray(filtered_probs,float)])
        X[:,1:]=(X[:,1:]-self.scaling[0])/self.scaling[1]
        return X@self.coef,np.sqrt(self.sigma2+np.einsum('ij,jk,ik->i',X,self.cov,X))


def chronological_year_folds(dates,min_train_year=2015,last=2019):
    years=pd.DatetimeIndex(dates).year
    for y in range(min_train_year,last+1):
        train=np.where(years<y)[0]
        val=np.where(years==y)[0]
        if len(train)>=50 and len(val)>=15:yield y,train,val


def maturity_mask(decisions,training_last_session):
    return np.array([d['t']+MATURE<=training_last_session for d in decisions])
