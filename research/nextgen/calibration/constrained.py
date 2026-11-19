"""Read-only synthetic test of shrinkage with the EXISTING research optimizer.

The oracle knows true returns ONLY to measure regret and synthesize a known
error covariance; these quantities cannot be accessed in a real decision.
No selection of portfolio parameters from historical sample takes place.
"""
from math import sqrt
import numpy as np
from research.nextgen.optimizer.core import Config, solve
from .core import characterize


def _true_utility(w, mu, covariance, gamma, spread, impact_k,
                  daily_vol, aum, adv):
    d=np.asarray(w, dtype=float)
    k=impact_k*daily_vol*np.sqrt(aum/adv)
    return float(mu@d-gamma/2*d@covariance@d-spread@np.abs(d)-k@np.abs(d)**1.5)


def run_constrained(*, ratios=(1.0,4.0), repetitions=120, seed=20261119):
    """Predeclared 12-asset cost-aware comparison to a zero-holdings control.

    This does not assert superiority: it may falsify shrinkage under constraints.
    """
    if isinstance(repetitions,bool) or not isinstance(repetitions,int) or repetitions<20:
        raise ValueError('integer repetitions >=20 required')
    if isinstance(seed,bool) or not isinstance(seed,int) or seed<0:
        raise ValueError('nonnegative integer seed required')
    ratios=np.asarray(ratios,dtype=float)
    if ratios.ndim!=1 or not len(ratios) or not np.isfinite(ratios).all() or (ratios<0).any():
        raise ValueError('finite nonnegative ratios required')
    rng=np.random.default_rng(seed)
    n=12
    covariance=np.eye(n)*.0004+np.ones((n,n))*.000025
    mu=np.linspace(-.0007,.0007,n)
    a=float(mu @ np.linalg.solve(covariance,mu))
    old=np.zeros(n)
    beta=np.ones(n)
    spread=np.full(n,.0002)
    daily_vol=np.full(n,.02)
    adv=np.full(n,5e8)
    cfg=Config(gamma=6.,gross=.6,name_limit=.075,beta_limit=.02,
               aum=1e7,impact_k=.025,dollar_neutral=True)
    out=[]
    for ratio in ratios:
        omega=covariance*(ratio*a/n)
        lam=characterize(mu,covariance,omega,cfg.gamma).optimal_shrink
        noise=rng.standard_normal((repetitions,n))@np.linalg.cholesky(omega).T if ratio>0 else np.zeros((repetitions,n))
        utility_raw=[];utility_shrink=[];gross_raw=[];gross_shrink=[]
        for j in range(repetitions):
            forecast=mu+noise[j]
            for factor, uts, gs in ((1,utility_raw,gross_raw),
                                     (lam,utility_shrink,gross_shrink)):
                z=solve(factor*forecast,covariance,old,beta,spread,daily_vol,adv,cfg)
                w=z['weights']
                uts.append(_true_utility(w,mu,covariance,cfg.gamma,spread,cfg.impact_k,
                                         daily_vol,cfg.aum,adv))
                gs.append(float(z['gross']))
        raw=np.asarray(utility_raw);shr=np.asarray(utility_shrink)
        delta=shr-raw
        out.append(dict(noise_to_signal=float(ratio),theoretical_unconstrained_shrink=lam,
                        mean_raw_true_net_utility=float(raw.mean()),
                        mean_shrunk_true_net_utility=float(shr.mean()),
                        mean_paired_utility_improvement=float(delta.mean()),
                        mc_se_paired_improvement=float(delta.std(ddof=1)/sqrt(repetitions)),
                        frequency_shrink_wins=float(np.mean(delta>0)),
                        mean_raw_gross=float(np.mean(gross_raw)),
                        mean_shrunk_gross=float(np.mean(gross_shrink))))
    return dict(method='12-asset synthetic cost-aware optimizer; known true mu used only to score',
                repetitions=repetitions,seed=seed,
                fixed_constraints={'gross':cfg.gross,'name_limit':cfg.name_limit,'beta_limit':cfg.beta_limit},
                results=out,
                caution='not a historical Sharpe test; lambda derived under UNCONSTRAINED quadratic assumptions')
