"""Synthetic comparison: solve fund jointly vs scale a stand-alone stock optimiser.

Only ex-ante *predicted* quadratic utility on a synthetic model is scored.
No future returns, P&L, Sharpe, borrow rates or market data are observed.
"""
from math import sqrt
import numpy as np
from research.nextgen.optimizer.core import Config as StockConfig, solve as stock_solve
from .core import Config, solve, fund_gross


def uniform_scale_to_fund_cap(core, w, beta, fund_limit):
    """Maximum common scale k in [0,1] meeting exact fund gross.

    The feasible k interval contains k=0 because |core|<=fund_limit;
    convexity of k -> |core - k beta'w| + k||w|| makes bisection valid.
    """
    if abs(core)>fund_limit:
        raise ValueError('fixed core already violates gross cap')
    if fund_gross(core,w,beta) <= fund_limit:
        return w.copy(),1.0
    lo,hi=0.,1.
    for _ in range(70):
        mid=(lo+hi)/2
        if fund_gross(core,mid*w,beta)<=fund_limit:
            lo=mid
        else:
            hi=mid
    return lo*w,lo


def score_policy(*, w, core, beta, mu, cov, spy_mu, spy_var, prev_w,
                 prev_q, half_spread, daily_vol, adv, cfg):
    """Exact same smoothed objective as core.solve, for an external baseline."""
    q=core-float(beta@w)
    dw=w-prev_w
    eps=cfg.epsilon
    k=cfg.impact_k*daily_vol*np.sqrt(cfg.aum/adv)
    spread=float(half_spread@(np.sqrt(dw*dw+eps*eps)-eps))
    impact=float(k@((dw*dw+eps*eps)**.75-eps**1.5))
    hedge=cfg.spy_spread*(np.sqrt((q-prev_q)**2+eps**2)-eps)
    return float(core*spy_mu +mu@w-cfg.gamma/2*(core*core*spy_var+w@cov@w)-spread-impact-hedge)


def experiment(*, n_trials=120, seed=20261119):
    if type(n_trials) is not int or n_trials<10 or n_trials>1000 or type(seed) is not int or seed<0:
        raise ValueError('requires integer 10..1000 trials and nonnegative seed')
    rng=np.random.default_rng(seed)
    rows=[]
    for core in (1.3,.7):
        for i in range(n_trials):
            n=8
            beta=np.clip(1+rng.normal(0,.35,n),.3,1.8)
            mu=rng.normal(0,.018,n)
            mu-=mu.mean()
            cov=np.eye(n)*.004+np.ones((n,n))*.0002
            spr=rng.uniform(.00005,.0006,n)
            sig=np.full(n,.02)
            adv=rng.uniform(3e8,1.5e9,n)
            old=np.zeros(n)
            cfg=Config(gamma=2,max_fund_gross=1.9,max_book_gross=.6,max_name_abs=.15,
                       impact_k=0.02,spy_spread=0,aum=1e7)
            independent=stock_solve(mu,cov,old,beta,spr,sig,adv,
                       StockConfig(gamma=cfg.gamma,gross=.6,name_limit=.15,
                                   beta_limit=1.5,impact_k=cfg.impact_k,aum=cfg.aum))
            raw_w=independent['weights']
            w_baseline,k=uniform_scale_to_fund_cap(core,raw_w,beta,1.9)
            res=solve(expected_residual_excess=mu,residual_covariance=cov,beta=beta,
                      residual_spy_cov=np.zeros(n),spy_expected_excess=.004,
                      spy_variance=.003,core_spy=core,previous_weights=old,
                      previous_net_spy=core,stock_half_spread=spr,
                      stock_daily_vol=sig,stock_adv=adv,config=cfg)
            args=dict(core=core,beta=beta,mu=mu,cov=cov,spy_mu=.004,spy_var=.003,
                      prev_w=old,prev_q=core,half_spread=spr,daily_vol=sig,
                      adv=adv,cfg=cfg)
            utility_joint=res['net_expected_quadratic_utility']
            utility_baseline=score_policy(w=w_baseline,**args)
            utility_zero=score_policy(w=old,**args)
            rows.append(dict(core=core,delta=utility_joint-utility_baseline,
                             joint=utility_joint,scale=1-k,
                             raw_gross=fund_gross(core,raw_w,beta),
                             baseline_gross=fund_gross(core,w_baseline,beta),
                             joint_gross=res['fund_gross'],
                             joint_vs_zero=utility_joint-utility_zero))
    out={}
    for core in (1.3,.7):
        one=[x for x in rows if x['core']==core]
        delta=np.array([x['delta'] for x in one])
        out[str(core)]={'n':len(one),
            'mean_joint_vs_projected_utility':float(delta.mean()),
            'paired_mc_se_utility':float(delta.std(ddof=1)/sqrt(len(one))),
            'fraction_joint_beats_projected':float(np.mean(delta>1e-10)),
            'fraction_stock_only_exceeds_fund_cap':float(np.mean([x['raw_gross']>1.9+1e-8 for x in one])),
            'mean_fund_cap_projection_shrink':float(np.mean([x['scale'] for x in one])),
            'max_baseline_gross_violation':float(max(x['baseline_gross']-1.9 for x in one)),
            'max_joint_gross_violation':float(max(x['joint_gross']-1.9 for x in one)),
            'mean_joint_utility_vs_zero':float(np.mean([x['joint_vs_zero'] for x in one]))}
    return {'kind':'SYNTHETIC EXACT-CAP UTILITY COMPARISON — NO HISTORICAL PNL',
            'n_trials_per_core':n_trials,'seed':seed,'core_scenarios':out,
            'scope':'candidate score/variance inputs are generated iid; true future returns, Sharpe and real funding unknown'}


if __name__=='__main__':
    import json
    print(json.dumps(experiment(),indent=2,allow_nan=False))


def forecast_error_falsification(*, n_trials=240, seed=20261201, noise_levels=(0.0, .012, .04)):
    """Oracle-scored out-of-sample *expected utility* under forecast noise.

    True residual excess returns are generated but NOT used to optimise. This
    can and should fail under some noise levels; do not select a noise level
    based on observed results or imply a real-market edge.
    """
    if type(n_trials) is not int or not 20<=n_trials<=5000 or type(seed) is not int or seed<0:
        raise ValueError('integer 20..5000 trials and nonnegative seed required')
    levels=np.asarray(noise_levels,dtype=float)
    if levels.ndim!=1 or not len(levels) or not np.isfinite(levels).all() or (levels<0).any():
        raise ValueError('finite nonnegative forecast-noise standard deviations required')
    rng=np.random.default_rng(seed)
    summary={}
    for core in (1.3,.7):
        for noise in levels:
            d=[]
            for _ in range(n_trials):
                n=8
                beta=np.clip(1+rng.normal(0,.35,n),.3,1.8)
                true_mu=rng.normal(0,.012,n);true_mu-=true_mu.mean()
                forecast=true_mu+rng.normal(0,noise,n)
                forecast-=forecast.mean()
                cov=np.eye(n)*.004+np.ones((n,n))*.0002
                spr=rng.uniform(.00005,.0006,n)
                sig=np.full(n,.02)
                adv=rng.uniform(3e8,1.5e9,n)
                old=np.zeros(n)
                cfg=Config(gamma=2,max_fund_gross=1.9,max_book_gross=.6,max_name_abs=.15,
                           impact_k=.02,spy_spread=0,aum=1e7)
                book=stock_solve(forecast,cov,old,beta,spr,sig,adv,
                       StockConfig(gamma=cfg.gamma,gross=.6,name_limit=.15,
                                   beta_limit=1.5,impact_k=cfg.impact_k,aum=cfg.aum))
                projected,k=uniform_scale_to_fund_cap(core,book['weights'],beta,1.9)
                joint=solve(expected_residual_excess=forecast,residual_covariance=cov,beta=beta,
                            residual_spy_cov=np.zeros(n),spy_expected_excess=.004,
                            spy_variance=.003,core_spy=core,previous_weights=old,
                            previous_net_spy=core,stock_half_spread=spr,
                            stock_daily_vol=sig,stock_adv=adv,config=cfg)
                args=dict(core=core,beta=beta,cov=cov,spy_mu=.004,spy_var=.003,
                          prev_w=old,prev_q=core,half_spread=spr,daily_vol=sig,
                          adv=adv,cfg=cfg)
                u_true=score_policy(w=joint['weights'],mu=true_mu,**args)
                v_true=score_policy(w=projected,mu=true_mu,**args)
                d.append((u_true-v_true, joint['net_expected_quadratic_utility']-
                          score_policy(w=projected,mu=forecast,**args)))
            data=np.array(d)
            true=data[:,0];pred=data[:,1]
            summary[f'{core}|noise={noise:g}']={
                'trials':n_trials,'core_spy':core,'forecast_error_sigma':float(noise),
                'mean_joint_minus_scaled_true_expected_utility':float(true.mean()),
                'paired_mc_se_true_utility':float(true.std(ddof=1)/sqrt(n_trials)),
                'fraction_joint_true_utility_wins':float(np.mean(true>0)),
                'mean_joint_minus_scaled_predicted_utility':float(pred.mean())}
    return {'kind':'synthetic independent true-mu utility falsification, NOT realised trading Sharpe',
            'seed':seed,'n_trials_per_condition':n_trials,'results':summary,
            'caution':'synthetic oracle truth used exclusively in scoring, not parameter fitting or allocation'}
