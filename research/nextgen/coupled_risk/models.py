"""Coupled multivariate factor covariance models, strictly past-only.

Returns T x K daily factors and T x K x K INTRADAY realized factor covariances.
At date t, a forecasting recursion has used observations only through t-1.
H_t therefore forecasts the covariance of return t, and H_{T} is next day's.
"""
from __future__ import annotations
import numpy as np
from scipy.linalg import solve_triangular
from scipy.optimize import minimize
from scipy.special import gammaln, logsumexp

EPS = 1e-9


def pdmat(x, floor=EPS):
    x = np.asarray(x, float)
    if x.ndim != 2 or x.shape[0] != x.shape[1] or not np.isfinite(x).all():
        raise ValueError('covariance must be a finite square matrix')
    x = (x + x.T) / 2
    a, q = np.linalg.eigh(x)
    return (q * np.maximum(a, floor)) @ q.T


def validate(returns, realized):
    x = np.asarray(returns, float)
    rv = np.asarray(realized, float)
    if x.ndim != 2 or len(x) < 50 or not 1 <= x.shape[1] <= 16:
        raise ValueError('need >=50 observations and 1..16 factors')
    if rv.shape != (len(x), x.shape[1], x.shape[1]):
        raise ValueError('realized covariance shape mismatch')
    if not np.isfinite(x).all() or not np.isfinite(rv).all():
        raise ValueError('incomplete factor window: no silent imputation')
    if any(np.linalg.eigvalsh((m + m.T) / 2).min() < -1e-8 for m in rv):
        raise ValueError('realized covariance not PSD')
    return x, rv


def realized_from_intraday(intraday):
    z = np.asarray(intraday, float)
    if z.ndim != 3 or z.shape[1] != 14 or not np.isfinite(z).all():
        raise ValueError('expected finite T x 14 x K factor intraday returns')
    return np.einsum('tik,til->tkl', z, z, optimize=True)


def normal_loss(r, h):
    l = np.linalg.cholesky(pdmat(h))
    z = solve_triangular(l, r, lower=True)
    return float(.5 * (len(r) * np.log(2 * np.pi) + 2 * np.log(np.diag(l)).sum() + z @ z))


def student_loss(r, h, nu=7.0):
    k = len(r)
    if nu <= 2: raise ValueError('Student-t df must exceed 2')
    # Covariance of Student-t with df nu is h, not its scale matrix.
    l = np.linalg.cholesky(pdmat(h * ((nu - 2) / nu)))
    z = solve_triangular(l, r, lower=True)
    delta = z @ z
    return float(-(gammaln((nu + k)/2)-gammaln(nu/2)
                   -.5*k*np.log(nu*np.pi)-np.log(np.diag(l)).sum()
                   -.5*(nu+k)*np.log1p(delta/nu)))


def heavy_matrix(x, rv, *, fit=True, a=.20, b=.70, maxiter=150):
    """Multivariate HEAVY covariance: H_t=(1-a-b)S+a*RV_(t-1)+b*H_(t-1)."""
    x, rv = validate(x, rv)
    s = pdmat(rv.mean(0))
    def calc(ab, want_trace=False):
        aa, bb = ab
        if aa < 0 or bb < 0 or aa + bb >= .999: return np.inf
        h = s.copy(); nll = 0.; history=[]
        for t, r in enumerate(x):
            nll += normal_loss(r, h)
            history.append(h)
            h = pdmat((1-aa-bb)*s + aa*rv[t]+bb*h)
        return (h, np.asarray(history), nll) if want_trace else nll
    if fit:
        opt = minimize(calc, [a,b],method='Nelder-Mead',bounds=[(0,.95),(0,.995)],
                       options=dict(maxiter=maxiter,xatol=1e-4,fatol=1e-5))
        if not np.isfinite(opt.fun): raise ValueError('HEAVY fit failed')
        a,b = opt.x
    pred, fitted, ll = calc((a,b),True)
    return dict(covariance=pred,trace=fitted,parameters=dict(a=float(a),b=float(b)),
                neg_log_likelihood=float(ll))


def dcc_factor(x, rv, *, a=.04, b=.93, fit=True,maxiter=120):
    """DCC(1,1) with causal HEAVY-like realized diagonal variance updates.

    Univariate diagonal forecast v_{t+1}=.05*longrun+.15*RV_t+.8*v_t.
    Q_t updates from standardized *past* daily returns; correlation R_t
    normalizes Q_t, then H_t=diag(sqrt(v_t)) R_t diag(sqrt(v_t)).
    """
    x,rv=validate(x,rv); k=x.shape[1]
    vb=np.maximum(np.diag(rv.mean(0)),EPS)
    standardized=x / np.sqrt(np.maximum(rv.diagonal(axis1=1,axis2=2).mean(0),EPS))
    qbar=pdmat(np.cov(standardized,rowvar=False)) if k>1 else np.eye(1)
    qbar=np.asarray(qbar).reshape(k,k)
    diag=np.sqrt(np.diag(qbar));qbar=qbar / np.outer(diag,diag)
    def rec(ab,details=False):
        aa,bb=ab
        if aa<0 or bb<0 or aa+bb>=.999:return np.inf
        v=vb.copy();q=qbar.copy();trace=[];loss=0.
        for t in range(len(x)):
            d=np.sqrt(np.maximum(np.diag(q),EPS))
            cor=pdmat(q/np.outer(d,d))
            h=pdmat(np.sqrt(v)[:,None]*cor*np.sqrt(v)[None,:])
            loss+=normal_loss(x[t],h);trace.append(h)
            zz=x[t]/np.sqrt(np.maximum(v,EPS))
            q=pdmat((1-aa-bb)*qbar + aa*np.outer(zz,zz)+bb*q)
            v=.05*vb + .15*np.maximum(np.diag(rv[t]),EPS) + .80*v
        d=np.sqrt(np.maximum(np.diag(q),EPS))
        cov=pdmat(np.sqrt(v)[:,None]*pdmat(q/np.outer(d,d))*np.sqrt(v)[None,:])
        return (cov,np.asarray(trace),loss) if details else loss
    if fit:
        opt=minimize(rec,[a,b],method='Nelder-Mead',bounds=[(0,.3),(0,.999)],
                     options=dict(maxiter=maxiter,xatol=1e-4,fatol=1e-5))
        if not np.isfinite(opt.fun):raise ValueError('DCC fit failed')
        a,b=opt.x
    h,trace,loss=rec((a,b),True)
    return dict(covariance=h,trace=trace,parameters=dict(a=float(a),b=float(b)),neg_log_likelihood=float(loss))


def robust_score_covariance(x,rv,*,a=.16,b=.78,nu=7,fit=True,maxiter=130):
    """Student-t robust observation-driven covariance with realized-measure anchor.

    Influent shock outer product is downweighted with (nu+K)/(nu-2+Mahalanobis^2).
    This is PSD and Student-t-score-motivated; NOT exact Fisher-scaled GAS.
    """
    x,rv=validate(x,rv);k=x.shape[1];s=pdmat(rv.mean(0))
    def rec(ab,details=False):
        aa,bb=ab
        if aa<0 or bb<0 or aa+bb>=.999:return np.inf
        h=s.copy();ll=0;trace=[]
        for t in range(len(x)):
            ll+=student_loss(x[t],h,nu);trace.append(h)
            q=float(x[t]@np.linalg.solve(h,x[t]))
            scale=(nu+k)/(nu-2+q)
            shock=scale*np.outer(x[t],x[t])
            # Blend realized and robust daily return innovation.
            update=.5*rv[t]+.5*shock
            h=pdmat((1-aa-bb)*s + aa*update+bb*h)
        return (h,np.asarray(trace),ll) if details else ll
    if fit:
        opt=minimize(rec,[a,b],method='Nelder-Mead',bounds=[(0,.95),(0,.995)],
                     options=dict(maxiter=maxiter,xatol=1e-4,fatol=1e-5))
        if not np.isfinite(opt.fun):raise ValueError('t-score filter failed')
        a,b=opt.x
    h,trace,ll=rec((a,b),True)
    return dict(covariance=h,trace=trace,parameters=dict(a=float(a),b=float(b),nu=float(nu)),neg_log_likelihood=float(ll))


def systematic_resampling(weights,rng):
    u=(rng.uniform()+np.arange(len(weights)))/len(weights)
    ix=np.searchsorted(np.cumsum(weights),u,side='right')
    return np.minimum(ix,len(weights)-1)


def joint_particle_sv(x,rv,*,particles=400,seed=20261122,
                      phi_grid=(.90,.97,.995),q_grid=(.10,.25,.5),nu=7):
    """Correlated latent log-variance particle SV, multiple structural settings.

    z_t=mu+phi*(z_(t-1)-mu)+epsilon_t, epsilon_t ~ N(0,Q) with
    off-diagonal Q estimated from *past* realized log-var innovations.
    r_t|z_t ~ multivariate Student-t(nu, covariance D(z_t) R D(z_t)).
    Returns Bayesian model-averaged next-day covariance, log-evidence weights,
    model-specific ESS, Monte Carlo scale diagnostics. All filtering is causal.
    """
    x,rv=validate(x,rv)
    if not 64<=particles<=20000:raise ValueError('particle count outside 64..20000')
    n,k=x.shape;vari=np.maximum(rv.diagonal(axis1=1,axis2=2),EPS)
    logs=np.log(vari);mu=np.median(logs,axis=0)
    innov=np.diff(logs,axis=0)
    qi=pdmat(np.cov(innov,rowvar=False) if k>1 else np.atleast_2d(np.var(innov)))
    qd=np.sqrt(np.maximum(np.diag(qi),EPS));corrq=qi/np.outer(qd,qd)
    # Slow latent vol innovation amplitude under the particle prior, with learned dependence.
    c0=pdmat(np.cov(x,rowvar=False) if k>1 else np.atleast_2d(np.var(x)))
    sd=np.sqrt(np.maximum(np.diag(c0),EPS));corr0=pdmat(c0/np.outer(sd,sd))
    model=[]
    for j,phi in enumerate(phi_grid):
      for m,qscale in enumerate(q_grid):
        rng=np.random.default_rng(seed+100*j+m)
        q=pdmat(corrq*(qscale**2));chol=np.linalg.cholesky(q)
        states=mu+rng.normal(size=(particles,k))*.15
        ll=0.;ess_min=particles;ess_total=0.
        for t in range(n):
            states=mu+phi*(states-mu)+rng.normal(size=(particles,k))@chol.T
            scale=np.exp(np.clip(states,-28,6))
            # Fast Student-t likelihood: shared cross-factor correlation,
            # differing latent log standard deviations per particle.
            zr=x[t][None,:]/np.sqrt(scale)
            qform=np.einsum('ni,ij,nj->n',zr,np.linalg.inv(corr0),zr)
            ldet=np.log(scale).sum(1)+np.linalg.slogdet(corr0)[1]
            lps=(gammaln((nu+k)/2)-gammaln(nu/2)-.5*k*np.log((nu-2)*np.pi)
                 -.5*ldet-.5*(nu+k)*np.log1p(qform/(nu-2)))
            ls=logsumexp(lps)-np.log(particles);ll+=float(ls)
            w=np.exp(lps-logsumexp(lps));ess=1/np.sum(w*w)
            ess_min=min(ess_min,ess);ess_total+=ess
            states=states[systematic_resampling(w,rng)]
        next_states=mu+phi*(states-mu)
        # E[ D(exp(h/2)) R0 D(exp(h/2)) | observations ].
        # Using sqrt(E[variance_i] E[variance_j]) for off-diagonals
        # overstates conditional correlation under stochastic log volatility.
        sigma=np.exp(.5*np.clip(next_states,-28,6))
        cov=pdmat(np.einsum('pi,pj,ij->ij',sigma,sigma,corr0,optimize=True)/particles)
        model.append(dict(phi=float(phi),qscale=float(qscale),log_evidence=ll,
                          covariance=cov,ess_mean=ess_total/n,ess_min=ess_min))
    logw=np.array([m['log_evidence'] for m in model]); weights=np.exp(logw-logsumexp(logw))
    cov=pdmat(sum(float(w)*m['covariance'] for w,m in zip(weights,model)))
    return dict(covariance=cov,parameters=dict(particles=particles,nu=nu,
                model_weights=[dict(phi=m['phi'],qscale=m['qscale'],weight=float(w),
                                    ess_mean=float(m['ess_mean']),ess_min=float(m['ess_min']))
                               for w,m in zip(weights,model)]),
                neg_log_likelihood=float(-logsumexp(logw)+np.log(len(logw))))
