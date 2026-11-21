"""Four distinct conditional covariance families, trained only on completed observations.

No model selection on reused 2020-2026. Compute-heavy algorithms are deliberate:
POET sparse residual; multivariate HEAVY likelihood; realized GARCH; and
PyMC Bayesian factor stochastic volatility (NUTS/ADVI, optional).
"""
from __future__ import annotations
import warnings
from dataclasses import dataclass
import numpy as np
from scipy.linalg import eigh
from scipy.optimize import minimize
from scipy.special import gammaln

TINY=1e-9

def psd(M, floor=1e-8):
    M=np.asarray(M,float);M=(M+M.T)/2
    d,Q=np.linalg.eigh(M)
    return (Q*np.maximum(d,floor))@Q.T


def realised_cov(R):
    """Intraday log returns: (days,bars,factors) -> realized covariance per day."""
    r=np.asarray(R,float)
    if r.ndim!=3 or not np.isfinite(r).all():raise ValueError('complete intraday factor bars required')
    return np.einsum('tbk,tbl->tkl',r,r)


def ewma_realized_cov(RC, lam=.94):
    """Forecast at t uses realised factor covariance only through t-1."""
    RC=np.asarray(RC,float)
    if RC.ndim!=3 or RC.shape[1]!=RC.shape[2] or len(RC)<2:raise ValueError('cov array shape')
    out=np.empty_like(RC)
    out[0]=psd(RC[0]) # warmup at first observed session; no future data
    for t in range(1,len(RC)):
        out[t]=psd(lam*out[t-1]+(1-lam)*RC[t-1])
    return out


def poet(X, rank=3, threshold=.6):
    """POET-like top-eigenfactor plus thresholded residual covariance.

    The adaptive residual threshold is proportional to sqrt(log(N)/T)*sqrt(D_iD_j).
    Data matrix X must contain ONLY historical complete daily returns at prediction t.
    """
    X=np.asarray(X,float)
    if X.ndim!=2 or X.shape[0]<20 or X.shape[1]<2 or not np.isfinite(X).all():
        raise ValueError('POET needs at least 20 complete past observations')
    n=X.shape[1];t=X.shape[0];rank=min(rank,n-1)
    X=X-X.mean(0)
    C=(X.T@X)/t
    vals,vecs=eigh(C,subset_by_index=(n-rank,n-1))
    common=(vecs*np.maximum(vals,0))@vecs.T
    resid=C-common
    d=np.maximum(np.diag(resid),TINY)
    cutoff=threshold*np.sqrt(np.log(n)/t)*np.sqrt(d[:,None]*d[None,:])
    R=np.where(np.abs(resid)>=cutoff,resid,0.)
    np.fill_diagonal(R,d)
    return psd(common+psd(R)), {'lowrank':common,'residual':psd(R),'factor_eigenvalues':vals}


def _gauss_qlike(target, pred):
    """Proper Gaussian covariance log score, up to target-only constants."""
    P=psd(pred)
    sign,ld=np.linalg.slogdet(P)
    if sign<=0:raise ArithmeticError('not PD')
    return float(ld+np.trace(np.linalg.solve(P,target)))

@dataclass
class Heavy:
    """Matrix HEAVY: H_t=omega + a*RC_{t-1} + b*H_{t-1}.

    Fits shared a,b by quasi-Gaussian realised covariance predictive likelihood.
    All training data must end before first evaluated prediction.
    """
    a:float=.12
    b:float=.84
    unconditional:np.ndarray|None=None
    def fit(self,RC):
        RC=np.asarray(RC,float)
        if len(RC)<65:raise ValueError('HEAVY needs >=65 historical days')
        C=psd(np.mean(RC,axis=0))
        def run(a,b):
            H=C.copy();loss=0.
            for t in range(1,len(RC)):
                H=psd((1-a-b)*C+a*RC[t-1]+b*H)
                if t>=32:loss+=_gauss_qlike(RC[t],H)
            return loss/max(len(RC)-32,1)
        def obj(x):
            a,b=x
            if a<0 or b<0 or a+b>.999:return 1e5+1e6*max(a+b-.999,0)**2
            return run(a,b)
        fit=minimize(obj,[.12,.84],method='SLSQP',bounds=[(.001,.6),(.01,.995)],constraints=[{'type':'ineq','fun':lambda x:.999-x.sum()}],options={'maxiter':120})
        if not fit.success: warnings.warn('HEAVY optimum not converged; keep bounded last iterate',RuntimeWarning)
        self.a,self.b=np.asarray(fit.x,float)
        self.unconditional=C
        return self
    def predict(self,history):
        RC=np.asarray(history,float)
        if self.unconditional is None:raise ValueError('fit first')
        H=self.unconditional.copy()
        for rc in RC:H=psd((1-self.a-self.b)*self.unconditional+self.a*rc+self.b*H)
        return H


@dataclass
class RealizedGARCH:
    """Univariate log-realized-GARCH(1,1) with return leverage and measurement error.

    log(h_t)=omega+beta*log(h_{t-1})+gamma*log(x_{t-1})
    log(x_t)=xi+phi*log(h_t)+tau1*z_t+tau2*(z_t^2-1)+u_t.
    Joint Gaussian return/measurement pseudo-likelihood (not a full Bayesian model).
    """
    pars:np.ndarray|None=None
    first_var:float|None=None
    def _states(self,p,r,x):
        omega,beta,gamma,xi,phi,tau1,tau2,lsigma=p
        logx=np.log(np.maximum(x,TINY));h=np.empty(len(x));h[0]=np.log(self.first_var)
        for t in range(1,len(x)):
            h[t]=np.clip(omega+beta*h[t-1]+gamma*logx[t-1],-24,3)
        z=r*np.exp(-h/2)
        err=logx-(xi+phi*h+tau1*z+tau2*(z*z-1))
        return np.exp(h),z,err,h
    def fit(self,r,x,maxiter=450):
        r=np.asarray(r,float);x=np.asarray(x,float)
        if len(r)<90 or len(r)!=len(x) or not np.isfinite(r).all() or not np.isfinite(x).all() or np.any(x<=0):raise ValueError('bad realised GARCH sample')
        self.first_var=float(np.mean(x[:20]));mu=np.log(np.mean(x))
        def obj(p):
            h,z,e,_=self._states(p,r,x)
            sigma2=np.exp(2*p[-1])
            return float(np.mean(.5*(np.log(h)+z*z+np.log(sigma2)+e*e/sigma2)))
        x0=np.array([.03*mu,.9,.07,0.,1.,0.,0.,-.4])
        bounds=[(-3,3),(.05,.995),(.001,.5),(-8,8),(.25,1.8),(-1,1),(-1,1),(-5,2)]
        out=minimize(obj,x0,method='L-BFGS-B',bounds=bounds,options={'maxiter':maxiter})
        if not np.isfinite(out.fun):raise RuntimeError('GARCH likelihood not finite')
        self.pars=out.x;return self
    def predict(self,r,x):
        if self.pars is None:raise ValueError('fit first')
        _,_,_,h=self._states(self.pars,np.asarray(r),np.asarray(x))
        omega,beta,gamma,*_=self.pars
        return float(np.exp(np.clip(omega+beta*h[-1]+gamma*np.log(max(x[-1],TINY)),-24,3)))


def factor_sv_pymc(factor_return,draws=600,tune=600,chains=2,cores=2,method='nuts',seed=20261121):
    """Bayesian AR(1) log stochastic volatility, factor by factor, on PAST returns only.

    Intensive: one PyMC posterior fit per factor, ideally one fit per held-out month.
    Returns predictive next-session factor variances with posterior credible intervals.
    Forecast uses the LAST FILTERED TRAINING state, never a latent state inferred with
    future observations. Factor correlations are estimated separately from past data.
    """
    import pymc as pm
    r=np.asarray(factor_return,float)
    if r.ndim!=2 or len(r)<120 or not np.isfinite(r).all():raise ValueError('need complete past factor returns')
    output=[]
    for j in range(r.shape[1]):
        x=r[:,j];scale=max(np.std(x),1e-5);y=x/scale
        with pm.Model() as model:
            rho=pm.Beta('rho',15,2)
            sigma=pm.HalfNormal('sigma',.35)
            mu=pm.Normal('mu',0,2)
            h0=pm.AR('h_center',rho=pm.math.stack([rho]),sigma=sigma,init_dist=pm.Normal.dist(0,1),shape=len(y))
            h=mu+h0
            nu=pm.Exponential('nu_minus2',.1)+2
            pm.StudentT('returns',nu=nu,mu=0,sigma=pm.math.exp(h/2),observed=y)
            if method=='nuts':
                trace=pm.sample(draws=draws,tune=tune,chains=chains,cores=cores,random_seed=seed+j,progressbar=False,target_accept=.9,return_inferencedata=True)
            elif method=='advi':
                approx=pm.fit(n=int(tune*20),method='advi',progressbar=False,random_seed=seed+j)
                trace=approx.sample(draws=draws,random_seed=seed+j,return_inferencedata=True)
            else:raise ValueError('choose nuts or advi')
        post=trace.posterior
        rho_s=np.asarray(post['rho']).ravel();sig_s=np.asarray(post['sigma']).ravel()
        mu_s=np.asarray(post['mu']).ravel();h_s=np.asarray(post['h_center'][..., -1]).ravel()
        nextlog=mu_s+rho_s*h_s
        future=(scale**2)*np.exp(np.clip(nextlog+.5*sig_s**2,-28,8))
        output.append({'factor':j,'mean':float(np.mean(future)), 'q05':float(np.quantile(future,.05)), 'q95':float(np.quantile(future,.95)), 'n_draws':len(future)})
    return output


def factor_cov_from_variances(var,training_factor_returns):
    """Combine conditional stochastic factor variance with historical shrunk factor correlation."""
    x=np.asarray(training_factor_returns,float)
    c=np.corrcoef(x,rowvar=False)
    c=psd(.95*c+.05*np.eye(c.shape[0]))
    a=np.sqrt(np.maximum(np.asarray(var,float),TINY))
    return psd(c*a[:,None]*a[None,:])

@dataclass
class ParticleSV:
    """Univariate Bayesian stochastic volatility with particle marginal MH.

    Bootstrap particle filter estimates the marginal likelihood unbiasedly;
    pseudo-marginal Metropolis-Hastings samples the SV parameters. Posterior
    prediction averages exp(h_next) conditional on filtered past particles.
    Student-t observation distribution with fixed nu=6 robustifies shocks.
    This is COMPUTATIONALLY EXPENSIVE but has no optional Bayesian dependency.
    """
    particles:int=256
    draws:int=300
    burn:int=150
    seed:int=20261121
    nu:float=6.
    step:tuple=(.06,.12,.08) # random walk in (log-vol mean, logit rho, log vol-of-vol)
    def _filter(self,y,p,rng):
        from scipy.special import gammaln, logsumexp
        mu,unrho,logsigma=p
        rho=1/(1+np.exp(-unrho));sigma=np.exp(logsigma)
        # Stationary initial state based on parameter draw (not future data).
        h=rng.normal(mu,sigma/np.sqrt(max(1-rho*rho,.01)),size=self.particles)
        ll=0.
        for obs in y:
            h=mu+rho*(h-mu)+sigma*rng.normal(size=self.particles)
            var=np.exp(np.clip(h,-25,10))
            z=obs/np.sqrt(var)
            lg=(gammaln((self.nu+1)/2)-gammaln(self.nu/2)
                -.5*np.log(self.nu*np.pi)-.5*np.log(var)
                -(self.nu+1)/2*np.log1p(z*z/self.nu))
            c=logsumexp(lg)
            ll+=c-np.log(self.particles)
            w=np.exp(lg-c)
            # Always resample (bootstrap PF); resampling from a PF estimate
            # gives a valid pseudo-marginal likelihood for MH.
            h=h[rng.choice(self.particles,size=self.particles,p=w)]
        next_h=mu+rho*(h-mu)+.5*sigma*sigma
        # Student-t innovation has variance nu/(nu-2) times sigma_t**2.
        # Forecast the variance, not merely the Student-t scale parameter.
        return ll,float(np.mean(np.exp(np.clip(next_h,-25,10)))*self.nu/(self.nu-2))
    def _prior(self,p,center):
        mu,lr,ls=p
        return -.5*((mu-center)/2)**2-.5*((lr-2.7)/1.0)**2-.5*((ls+1.4)/.7)**2
    def fit_predict(self,r):
        r=np.asarray(r,float)
        if r.ndim!=1 or len(r)<90 or not np.isfinite(r).all() or self.particles<32 or self.draws<10:
            raise ValueError('ParticleSV needs 90+ historical returns, 32+ particles, 10+ posterior draws')
        scale=max(float(np.std(r)),1e-5);y=r/scale
        rng=np.random.default_rng(self.seed)
        center=float(np.log(np.var(y)))
        p=np.array([center,2.7,-1.4]);ll,forecast=self._filter(y,p,rng)
        stored=[];accepted=0
        for i in range(self.burn+self.draws):
            q=p+rng.normal(size=3)*np.asarray(self.step)
            lq,fq=self._filter(y,q,rng)
            if np.log(rng.random()) < lq+self._prior(q,center)-ll-self._prior(p,center):
                p,ll,forecast=q,lq,fq;accepted+=1
            if i>=self.burn:stored.append(forecast*scale**2)
        a=np.asarray(stored)
        return {'mean':float(a.mean()),'q05':float(np.quantile(a,.05)),
                'q95':float(np.quantile(a,.95)),
                'acceptance':accepted/(self.burn+self.draws),
                'particles':self.particles,'draws':self.draws,'burn':self.burn}


def factor_sv_particle(factor_returns,draws=300,burn=150,particles=256,seed=20261121):
    """Independent latent log-vol per common factor, posterior covariance with shrunk correlations."""
    X=np.asarray(factor_returns,float)
    if X.ndim!=2 or not np.isfinite(X).all():raise ValueError('past factor returns matrix required')
    result=[]
    for j in range(X.shape[1]):
        res=ParticleSV(draws=draws,burn=burn,particles=particles,seed=seed+j).fit_predict(X[:,j]);res['factor']=j
        result.append(res)
    return result
