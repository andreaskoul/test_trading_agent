"""Chronologically filtered MASTER-alpha efficacy: Gaussian state space, Bayesian AR, neural MoE.

This is conditional calibration of the *frozen* MASTER scores. It does not create
new alpha labels, retrain MASTER, write portfolio weights or trade anything.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp
from .contracts import AlphaData


@dataclass
class WeeklySlope:
    date:np.ndarray
    available:np.ndarray
    slope:np.ndarray
    variance:np.ndarray
    n:np.ndarray
    features:np.ndarray
    original_rows:np.ndarray


def _market_features(market,t):
    if t<252:return None
    m=np.asarray(market,float)
    if not np.isfinite(m[t-252:t+1]).all():return None
    # At the week-start close, returns through index t are timestamp-available.
    lag=m[:t+1]
    def sd(k):return np.std(lag[-k:],ddof=1)
    return np.asarray([np.sum(lag[-63:]),np.sum(lag[-21:]),
                       np.log(max(sd(21),1e-6)),np.log(max(sd(63),1e-6)),
                       np.sum(lag[-252:]),np.mean(np.abs(lag[-21:]))],float)


def weekly_slope_panel(d:AlphaData,market:np.ndarray,min_names=50)->WeeklySlope:
    """Cross-sectional slope with measurement variance; weekly time is unit of information.

    y5 is already the known 5-session future residual return in dev.npz;
    it is ONLY consumed as a target when its required future sessions mature.
    """
    market=np.asarray(market,float)
    if market.shape!=(len(d.dates),):raise ValueError('market return array must align with dev dates')
    out=[]
    for t in d.decision_ix:
        state=_market_features(market,int(t))
        ok=np.isfinite(d.score[t])&np.isfinite(d.residual[t])&d.eligible[t]
        if ok.sum()<min_names or state is None:continue
        x=d.score[t,ok];y=d.residual[t,ok]
        # Use only a fixed, cross-sectional rank transform. Ties use midrank.
        from scipy.stats import rankdata
        x=rankdata(x,method='average')/(len(x)+1)-.5
        x=x-x.mean();cy=y-y.mean();s=float(x@x)
        if s<1e-5:continue
        slope=float(x@cy/s)
        eps=cy-slope*x
        var=float(np.sum(eps**2)/(len(x)-2)/s)
        if var<=0 or not np.isfinite(var):continue
        # Target d.y5[t] spans 5 sessions AFTER t and becomes available at t+5.
        out.append((d.dates[t],d.dates[t+5],slope,max(var,1e-10),int(ok.sum()),state,t))
    if len(out)<70:raise ValueError('too few labelled weekly development observations')
    return WeeklySlope(np.asarray([x[0] for x in out]),np.asarray([x[1] for x in out]),
                       np.asarray([x[2] for x in out]),np.asarray([x[3] for x in out]),
                       np.asarray([x[4] for x in out]),np.vstack([x[5] for x in out]),
                       np.asarray([x[6] for x in out]))


def available_before(w:WeeklySlope,decision_date):
    return np.flatnonzero(w.available < np.datetime64(decision_date,'D'))


def kalman_slope(y,measurement_variance,train_features=None,
                 fit=True,phi_prior=.95):
    """Empirical Bayes Gaussian latent AR(1), measurement error known from weekly slopes.

    theta_(t)=m+phi(theta_(t-1)-m)+eta_t, observed slope y_t=theta_t+eps_t.
    Kalman filtering returns *real time* posterior estimates and variances.
    """
    y=np.asarray(y,float);r=np.asarray(measurement_variance,float)
    if y.ndim!=1 or r.shape!=y.shape or len(y)<25 or not np.isfinite(y).all() or np.any(~np.isfinite(r)|(r<=0)):
        raise ValueError('invalid Kalman slope series')
    mu=float(np.mean(y));z=float(np.var(y,ddof=1))
    def filt(phi,q,ret=False):
        m=mu;p=max(z,1e-8);ll=0.;history=[]
        for i in range(len(y)):
            pred=mu+phi*(m-mu);vp=phi*phi*p+q
            innovation=y[i]-pred;s=vp+r[i]
            gain=vp/s;m=pred+gain*innovation;p=max((1-gain)*vp,1e-12)
            ll+=.5*(np.log(2*np.pi*s)+innovation*innovation/s)
            history.append((m,p))
        return (np.asarray(history),ll) if ret else ll
    if fit:
        def obj(x):
            phi=.999/(1+np.exp(-x[0]));q=np.exp(np.clip(x[1],-30,3))
            return filt(phi,q)
        initial=[np.log(phi_prior/(1-phi_prior)),np.log(max(z*.1,1e-8))]
        zfit=minimize(obj,initial,method='L-BFGS-B',bounds=[(-6,9),(-25,0)],options={'maxiter':300})
        phi=.999/(1+np.exp(-zfit.x[0]));q=float(np.exp(zfit.x[1]))
    else:phi,q=phi_prior,max(z*.1,1e-8)
    history,ll=filt(phi,q,True)
    last=history[-1]
    predicted_mean=mu+phi*(last[0]-mu)
    predicted_variance=phi**2*last[1]+q
    return dict(mean=float(predicted_mean),variance=float(predicted_variance),
                phi=float(phi),process_variance=float(q),n=len(y),nll=float(ll),
                posterior_means=history[:,0],posterior_variances=history[:,1])


def bayesian_dynamic_slope(y,measurement_variance,draws=350,tune=350,
                           chains=2,seed=20261120,method='nuts'):
    """Full Bayesian latent AR(1) posterior for *weekly* MASTER rank efficacy.

    No hard gating on a noisy low recent Sharpe. Uses explicit observation
    variance per weekly cross-sectional slope, with partial-pooling around m.
    """
    try:
        import pymc as pm
        import pytensor.tensor as pt
    except Exception as exc:
        raise RuntimeError('Bayesian dynamic alpha requires compatible pymc>=5/arviz') from exc
    y=np.asarray(y,float);r=np.asarray(measurement_variance,float)
    if y.ndim!=1 or len(y)<40 or r.shape!=y.shape or not np.isfinite(y).all() or np.any(r<=0):
        raise ValueError('invalid Bayesian alpha series')
    with pm.Model() as model:
        mu=pm.Normal('mu',mu=float(y.mean()),sigma=float(max(np.std(y),.005)))
        phi=pm.Beta('phi',alpha=12,beta=3)
        q=pm.HalfNormal('q',sigma=float(max(np.std(y)*.3,.002)))
        z=pm.AR('z',rho=pt.stack([phi]),sigma=q,
                init_dist=pm.Normal.dist(mu=0,sigma=float(max(np.std(y),.005))),shape=len(y),constant=False)
        pm.Normal('obs',mu=mu+z,sigma=np.sqrt(r),observed=y)
        if method=='nuts':
            trace=pm.sample(draws=draws,tune=tune,chains=chains,cores=min(chains,2),
                            random_seed=seed,target_accept=.9,progressbar=False)
        elif method=='advi':
            approx=pm.fit(n=30000,random_seed=seed,progressbar=False)
            trace=approx.sample(draws=draws,random_seed=seed)
        else:raise ValueError('only nuts/advi')
    mup=np.asarray(trace.posterior['mu']).ravel()
    phip=np.asarray(trace.posterior['phi']).ravel()
    zp=np.asarray(trace.posterior['z'])[...,-1].ravel()
    qp=np.asarray(trace.posterior['q']).ravel()
    nxt=mup+phip*zp
    return dict(mean=float(nxt.mean()),variance=float(np.var(nxt)+np.mean(qp**2)),
                credible_interval_90=[float(z) for z in np.quantile(nxt,[.05,.95])],
                posterior_samples=int(len(nxt)),method=method)


def bayesian_linear_state(y,measurement_variance,features,ridge=10.):
    """Bayesian partial-pooled alpha~market-state regression, with posterior uncertainty.

    This model has exact Gaussian posterior (not a heuristic OLS fit); the prior
    centres the varying-state coefficients at zero, preserving constant-alpha
    behavior unless supported by data.
    """
    y=np.asarray(y,float);r=np.asarray(measurement_variance,float);x=np.asarray(features,float)
    if x.shape[0]!=len(y) or x.ndim!=2 or len(y)<30 or r.shape!=y.shape or not np.isfinite(x).all():
        raise ValueError('state regression shapes invalid')
    center=x.mean(0);scale=np.maximum(x.std(0),1e-5)
    zz=(x-center)/scale
    X=np.c_[np.ones(len(y)),zz]
    prec=np.diag(np.r_[1e-8,np.full(x.shape[1],ridge)])
    A=(X.T/r)@X+prec
    cov=np.linalg.inv(A)
    beta=cov@(X.T@(y/r))
    return dict(coef=beta,posterior_cov=cov,center=center,scale=scale,
                pred=lambda new_x: _state_predict(new_x,beta,cov,center,scale))


def _state_predict(x,beta,cov,center,scale):
    a=np.r_[1.,(np.asarray(x)-center)/scale]
    return float(a@beta),float(a@cov@a)


def train_moe(features,targets,noise,n_experts=3,hidden=32,epochs=400,
              seeds=(11,17,23),device='cpu',patience=45,learning_rate=.002):
    """Regularized neural soft mixture-of-experts, ensemble uncertainty.

    One observation per *decision week*; avoids pseudo-independent stock rows.
    Train/validation order is strictly chronological: last 20% of matured
    development labels withheld for early stopping, not shuffled.
    """
    try:import torch
    except ImportError as exc:raise RuntimeError('neural MoE requires torch>=2') from exc
    import torch.nn as nn
    X=np.asarray(features,float);y=np.asarray(targets,float);se=np.asarray(noise,float)
    if X.ndim!=2 or y.shape!=(len(X),) or se.shape!=y.shape or len(X)<80:
        raise ValueError('MoE must have >=80 development weeks')
    if not(np.isfinite(X).all() and np.isfinite(y).all() and np.isfinite(se).all() and np.all(se>0)):
        raise ValueError('invalid MoE features or label uncertainty')
    center=X.mean(0);scale=np.maximum(X.std(0),1e-5);xx=(X-center)/scale
    loc=y.mean();std=max(y.std(),.001);yy=(y-loc)/std
    split=max(50,int(len(X)*.8))
    Xt=torch.tensor(xx,dtype=torch.float32,device=device)
    Yt=torch.tensor(yy,dtype=torch.float32,device=device)
    wt=torch.tensor(1/np.maximum(se/std**2,.01),dtype=torch.float32,device=device)
    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.gate=nn.Sequential(nn.Linear(X.shape[1],hidden),nn.GELU(),
                                    nn.Linear(hidden,hidden),nn.GELU(),
                                    nn.Linear(hidden,n_experts))
            self.experts=nn.Parameter(torch.zeros(n_experts,X.shape[1]+1))
        def forward(self,x):
            logits=self.gate(x);gate=torch.softmax(logits,dim=-1)
            design=torch.cat((torch.ones((len(x),1),device=x.device),x),1)
            vals=design@self.experts.T
            return (gate*vals).sum(1)
    nets=[];hist=[];validation_variances=[]
    for seed in seeds:
        torch.manual_seed(seed)
        net=Net().to(device);opt=torch.optim.AdamW(net.parameters(),lr=learning_rate,weight_decay=.03)
        best=float('inf');best_dict=None;stalled=0
        for epoch in range(epochs):
            net.train();opt.zero_grad()
            p=net(Xt[:split]);loss=((p-Yt[:split])**2*wt[:split]).mean()+.002*(net.experts**2).mean()
            loss.backward();opt.step()
            net.eval()
            with torch.no_grad():
                val=float(((net(Xt[split:])-Yt[split:])**2*wt[split:]).mean().item())
            if val<best-1e-5:
                best=val;best_dict={k:v.clone().detach() for k,v in net.state_dict().items()};stalled=0
            else:stalled+=1
            if stalled>=patience:break
        net.load_state_dict(best_dict)
        net=net.cpu().eval()
        with torch.no_grad():
            holdout_pred=net(Xt[split:].cpu()).numpy()*std+loc
        # Distribution-free conservative epistemic floor from *past*
        # development-only validation errors, including single-seed pilots.
        val_var=max(float(np.mean((y[split:]-holdout_pred)**2)),1e-8)
        nets.append(net);validation_variances.append(val_var)
        hist.append(dict(seed=seed,best_validation_loss=best,epochs=epoch+1,development_validation_variance=val_var))
    def predict(new_features):
        z=(np.atleast_2d(np.asarray(new_features,float))-center)/scale
        if z.shape[1]!=X.shape[1] or not np.isfinite(z).all():raise ValueError('MoE features invalid')
        inputs=torch.tensor(z,dtype=torch.float32)
        with torch.no_grad():pred=np.asarray([net(inputs).numpy()*std+loc for net in nets])
        ensemble_var=(pred.var(0,ddof=1) if len(nets)>1 else np.zeros(len(z)))
        return pred.mean(0),np.maximum(ensemble_var+np.mean(validation_variances),1e-10)
    return dict(predict=predict,diagnostics=hist,n_experts=n_experts,
                n_seeds=len(seeds),train_n=split,validation_n=len(X)-split)


def alpha_trial(w:WeeklySlope,train_end='2016-12-31',eval_end='2019-12-31',
                method='kalman',refit_every=13,draws=250,device='cpu',moe_epochs=400,moe_seeds=(11,17,23)):
    """Out-of-time development forecast of weekly MASTER-strength slope.

    Week t can train only on *already matured* previous labels. Refitting
    occurs every 13 decision weeks to allow expensive NUTS / neural models.
    All candidate predictions use identical origin dates and label targets.
    """
    first=np.datetime64(train_end,'D');last=np.datetime64(eval_end,'D')
    if last>np.datetime64('2019-12-31') or first>=last:
        raise ValueError('alpha research strictly development-only')
    origins=np.flatnonzero((w.date>first)&(w.date<=last))
    results=[];cached=None;cached_n=-1
    for j,t in enumerate(origins):
        date=w.date[t]
        indices=available_before(w,date)
        indices=indices[w.date[indices]<=first] if method=='fixed_train' else indices
        if len(indices)<80:continue
        if cached is None or j%refit_every==0 or len(indices)!=cached_n and method=='kalman':
            y=w.slope[indices];v=w.variance[indices];f=w.features[indices]
            if method=='kalman':cached=kalman_slope(y,v)
            elif method=='bayesian':cached=bayesian_dynamic_slope(y,v,draws=draws,tune=draws)
            elif method=='state_regression':cached=bayesian_linear_state(y,v,f)
            elif method=='moe':cached=train_moe(f,y,v,device=device,epochs=moe_epochs,seeds=moe_seeds)
            elif method=='constant':cached=dict(mean=float(np.average(y,weights=1/v)),variance=float(np.var(y)))
            else:raise ValueError('unknown alpha method')
            cached_n=len(indices)
        if method=='state_regression':mu,variance=cached['pred'](w.features[t])
        elif method=='moe':p,var=cached['predict'](w.features[t]);mu=float(p[0]);variance=float(var[0])
        else:mu=float(cached['mean']);variance=float(cached['variance'])
        results.append(dict(date=str(date),available=str(w.available[t]),
                            method=method,forecast=mu,forecast_variance=variance,
                            actual=float(w.slope[t]),measurement_variance=float(w.variance[t]),
                            train_n=cached_n))
    if len(results)<25:raise ValueError('too few chronological alpha predictions')
    return results
