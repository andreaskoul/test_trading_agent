"""Research-only convex one-period cost-aware allocation; not a trading engine.

Inputs mu and Sigma are holding-period CALIBRATED excess returns/covariance;
cross-sectional neural model ranks are not expected return units.
"""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import minimize

@dataclass(frozen=True)
class Config:
    gamma: float = 5.0
    gross: float = 0.6
    name_limit: float = 0.05
    beta_limit: float = 0.01
    aum: float = 10_000_000.0
    impact_k: float = 0.5
    dollar_neutral: bool = True
    epsilon: float = 1e-9
    tolerance: float = 1e-7

def _v(x,n=None):
    a=np.asarray(x,dtype=float)
    if a.ndim != 1 or a.size == 0 or not np.isfinite(a).all() or (n is not None and len(a)!=n):
        raise ValueError("expected finite aligned 1D input")
    return a

def solve(mu,covariance,previous,beta,spread,daily_vol,adv,cfg=Config()):
    """Maximum predicted net excess utility subject to gross/name/beta/neutrality.

    Objective: mu'w - gamma/2 w'Sigma w - s'|dw| -
      sum_i k*sigma_i*sqrt(AUM/ADV_i)*|dw_i|**(3/2).
    Smooth convex approximations allow analytic SLSQP gradients.
    """
    m=_v(mu); n=len(m)
    old=_v(previous,n); b=_v(beta,n); s=_v(spread,n)
    sig=_v(daily_vol,n); v=_v(adv,n); cov=np.asarray(covariance,float)
    if (not np.isfinite([cfg.gamma,cfg.gross,cfg.name_limit,cfg.beta_limit,cfg.aum,cfg.impact_k,cfg.epsilon,cfg.tolerance]).all()
        or min(cfg.gamma,cfg.gross,cfg.name_limit,cfg.aum,cfg.epsilon,cfg.tolerance)<=0
        or cfg.impact_k<0 or cfg.beta_limit<0):
        raise ValueError("invalid configuration")
    if cov.shape!=(n,n) or not np.isfinite(cov).all() or not np.allclose(cov,cov.T,atol=1e-10) or np.linalg.eigvalsh(cov).min() < -1e-10:
        raise ValueError("covariance is not finite symmetric PSD")
    if (s<0).any() or (sig<0).any() or (v<=0).any():
        raise ValueError("nonnegative costs/vol and positive liquidity required")
    if (abs(old).sum()>cfg.gross+cfg.tolerance or np.max(abs(old))>cfg.name_limit+cfg.tolerance
        or abs(b@old)>cfg.beta_limit+cfg.tolerance
        or (cfg.dollar_neutral and abs(old.sum())>cfg.tolerance)):
        raise ValueError("previous holdings are infeasible")
    k=cfg.impact_k*sig*np.sqrt(cfg.aum/v); eps=cfg.epsilon
    def parts(w):
        delta=w-old
        soft=np.sqrt(delta*delta+eps*eps)-eps
        impact=(delta*delta+eps*eps)**.75-eps**1.5
        return dict(expected_excess=float(w@m), risk=float(cfg.gamma*(w@cov@w)/2),
                    spread=float(s@soft), impact=float(k@impact))
    def f(w):
        q=parts(w)
        return -q["expected_excess"]+q["risk"]+q["spread"]+q["impact"]
    def jac(w):
        d=w-old; h=d*d+eps*eps
        return -m+cfg.gamma*(cov@w)+s*d/np.sqrt(h)+1.5*k*d*h**(-.25)
    def approx_gross(w):
        return np.sum(np.sqrt(w*w+eps*eps)-eps)
    constraints=[
      dict(type="ineq",fun=lambda w: cfg.gross-approx_gross(w),
           jac=lambda w: -w/np.sqrt(w*w+eps*eps)),
      dict(type="ineq",fun=lambda w: cfg.beta_limit-b@w,jac=lambda w:-b),
      dict(type="ineq",fun=lambda w: cfg.beta_limit+b@w,jac=lambda w:b)]
    if cfg.dollar_neutral:
        constraints.append(dict(type="eq",fun=lambda w:w.sum(),jac=lambda w:np.ones(n)))
    res=minimize(f,old.copy(),method="SLSQP",jac=jac,
                 bounds=[(-cfg.name_limit,cfg.name_limit)]*n,
                 constraints=constraints,options={"maxiter":1000,"ftol":1e-11})
    w=np.asarray(res.x,float)
    violation=max(0.,abs(w).sum()-cfg.gross,
                  np.max(abs(w))-cfg.name_limit,
                  abs(b@w)-cfg.beta_limit,
                  abs(w.sum()) if cfg.dollar_neutral else 0)
    if not res.success or not np.isfinite(w).all() or violation>cfg.tolerance:
        raise RuntimeError(f"optimization failed closed: {res.message}; violation={violation}")
    return dict(weights=w,net_utility=float(-f(w)),components=parts(w),
                turnover_one_way=float(abs(w-old).sum()/2),
                predicted_variance=float(w@cov@w),gross=float(abs(w).sum()),
                beta=float(b@w),max_violation=float(violation))
