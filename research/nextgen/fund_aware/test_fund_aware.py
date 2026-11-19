"""Synthetic capital-constraint tests; no market outcomes or historical returns."""
from dataclasses import replace
from unittest.mock import patch
import numpy as np
import pytest
from scipy.optimize import approx_fprime
from research.nextgen.fund_aware.core import Config, fund_gross, solve


def case(core=1.3, gross=1.9, mu=None):
    n=4
    return dict(expected_residual_excess=np.array([-.03,.03,-.03,.03]) if mu is None else np.array(mu,float),
      residual_covariance=np.eye(n)*.005,
      beta=np.array([1.2,.8,1.2,.8]),
      residual_spy_cov=np.zeros(n), spy_expected_excess=.004,spy_variance=.002,
      core_spy=core,previous_weights=np.zeros(n),previous_net_spy=core,
      stock_half_spread=np.ones(n)*.00001,stock_daily_vol=np.ones(n)*.02,
      stock_adv=np.ones(n)*5e9,
      config=Config(gamma=1.,max_fund_gross=gross,max_book_gross=.6,
         max_name_abs=.15,impact_k=0,spy_spread=0))


def test_gross_identity_core_and_hedge():
    w=np.array([-.15,.15,-.15,.15])
    beta=np.array([1.2,.8,1.2,.8])
    assert np.isclose(beta@w,-.12)
    assert np.isclose(fund_gross(1.3,w,beta),2.02)
    assert np.isclose(fund_gross(.7,w,beta),1.42)


def test_joint_allocator_honors_real_fund_gross():
    x=solve(**case())
    assert x['fund_gross']<=1.9+1e-8
    assert x['book_gross']<=.6+1e-8
    assert np.isclose(x['net_spy'],1.3-x['book_beta'])
    assert abs(x['weights'].sum())<1e-8
    assert x['book_beta'] < 0
    assert x['book_gross'] < .6-1e-3  # capital scarce in 1.3x regime
    assert x['fund_gross']>1.895


def test_downtrend_allows_full_book():
    x=solve(**case(core=.7))
    assert x['book_gross'] > .59
    assert x['fund_gross']<=1.9+1e-8
    assert x['net_spy'] >.7


def test_standalone_optimizer_can_violate_whole_fund_gross():
    from research.nextgen.optimizer.core import solve as standalone, Config as OldConfig
    c=case()
    old=standalone(c['expected_residual_excess'],c['residual_covariance'],
      c['previous_weights'],c['beta'],c['stock_half_spread'],
      c['stock_daily_vol'],c['stock_adv'],
      OldConfig(gamma=1.,gross=.6,name_limit=.15,beta_limit=.4,
                aum=1e7,impact_k=0))
    assert old['gross']<=.6+1e-8
    assert fund_gross(1.3,old['weights'],c['beta'])>1.9+.05


def test_gamma_risk_cross_covariance_penalizes_correctly():
    c=case()
    c['residual_spy_cov']=np.array([.0001,-.0001,.0001,-.0001])
    c['spy_variance']=.002
    # Joint covariance remains positive-definite; cross-cov changes solution.
    x=solve(**c)
    assert x['risk_full_variance']>=0
    assert x['fund_gross']<=1.9+1e-7


def test_non_psd_joint_covariance_fails_closed():
    c=case(); c['residual_spy_cov']=np.ones(4)*.2
    with pytest.raises(ValueError, match='joint'):
        solve(**c)


def test_core_alone_is_infeasible():
    with pytest.raises(ValueError,match='fixed core'):
        solve(**case(core=2.0))


def test_zero_alpha_zero_book_when_spy_core_uncorrelated():
    x=solve(**case(mu=[0,0,0,0]))
    assert np.linalg.norm(x['weights'],ord=1)<1e-5


def test_exact_hard_cap_vs_smooth_gross_underestimate():
    # It is not enough to test sqrt(w^2 + eps^2) - eps because this
    # underestimates |w|. The epigraph enforces the true norm.
    x=solve(**case())
    assert np.abs(x['net_spy'])+np.abs(x['weights']).sum() <=1.9+1e-8


def test_previous_breach_can_be_repaired_not_silently_retained():
    c=case()
    c['previous_weights']=np.array([-.15,.15,-.15,.15])
    c['previous_net_spy']=1.42
    # It begins at 2.02 gross, but new optimizer returns feasible w.
    x=solve(**c)
    assert x['fund_gross']<=1.9+1e-8
    assert x['stock_turnover_one_way']>0


def test_spy_turnover_cost_suppresses_deviation():
    c=case()
    c['config']=replace(c['config'],spy_spread=.2)
    x=solve(**c)
    assert abs(x['net_spy']-c['previous_net_spy'])<1e-3


def test_cost_increase_reduces_mean_opportunity():
    c=case()
    x=solve(**c)
    c['stock_half_spread']=np.full(4,.1)
    y=solve(**c)
    assert y['book_gross'] < x['book_gross']


def test_objective_analytic_gradient_matches_finite_difference():
    import research.nextgen.fund_aware.core as mod
    c=case()
    orig=mod.minimize
    err=[]
    def inspect(f,x0,**kwargs):
        n=4
        z=np.r_[[-.08,.06,-.06,.08],[.08,.06,.06,.08],1.35]
        numeric=approx_fprime(z,f,1e-8)
        err.append(float(np.max(abs(numeric-kwargs['jac'](z)))))
        return orig(f,x0,**kwargs)
    with patch.object(mod,'minimize',inspect):
        solve(**c)
    assert err[0]<1e-7


def test_multiple_random_psd_cases_remain_feasible():
    rng=np.random.default_rng(20261119)
    for n in (4,8,12):
        for iteration in range(20):
            v=rng.normal(size=(n,n))
            cov=(v@v.T)/n*.003 +np.eye(n)*.003
            beta=1+rng.normal(0,.25,n)
            mu=rng.normal(0,.007,n)
            c=dict(expected_residual_excess=mu,residual_covariance=cov,
                   beta=beta,residual_spy_cov=np.zeros(n),
                   spy_expected_excess=.005,spy_variance=.003,
                   core_spy=1.3 if iteration%2 else .7,
                   previous_weights=np.zeros(n),previous_net_spy=1.3 if iteration%2 else .7,
                   stock_half_spread=np.full(n,.0001),stock_daily_vol=np.full(n,.02),
                   stock_adv=np.full(n,5e8),config=Config(gamma=3,max_fund_gross=1.9,
                      max_book_gross=.6,max_name_abs=.15,impact_k=0.05,spy_spread=.0001))
            x=solve(**c)
            assert x['max_violation']<=1e-7
            assert x['fund_gross']<=1.9+1e-7
            assert x['book_gross']<=.6+1e-7
            assert x['risk_full_variance']>=-1e-12


def test_invalid_costs_and_parameters_fail_closed():
    c=case();c['stock_half_spread'][0]=-1
    with pytest.raises(ValueError):solve(**c)
    c=case();c['stock_adv'][0]=0
    with pytest.raises(ValueError):solve(**c)
    c=case();c['config']=replace(c['config'],max_fund_gross=float('nan'))
    with pytest.raises(ValueError):solve(**c)
    c=case();c['config']=replace(c['config'],gamma=0)
    with pytest.raises(ValueError):solve(**c)
    c=case();c['expected_residual_excess'][0]=float('nan')
    with pytest.raises(ValueError):solve(**c)
    c=case();c['residual_covariance'][0,0]=-1
    with pytest.raises(ValueError):solve(**c)


def test_spy_net_can_be_negative_and_epigraph_handles_it():
    c=case(core=-.3,gross=.9)
    x=solve(**c)
    assert x['fund_gross']<=.9+1e-7
    assert x['net_spy']<0


def test_equal_beta_stocks_hedge_zero_and_max_book():
    c=case()
    c['beta']=np.ones(4)
    x=solve(**c)
    assert abs(x['beta_hedge'])<1e-10
    assert x['book_gross']>.59
    assert x['fund_gross']<=1.9+1e-7


def test_solver_failure_is_fail_closed():
    from types import SimpleNamespace
    import research.nextgen.fund_aware.core as mod
    with patch.object(mod,'minimize',return_value=SimpleNamespace(
            x=np.zeros(9),success=False,message='synthetic optimizer fault')):
        with pytest.raises(RuntimeError,match='fails closed'):
            solve(**case())


def test_input_validation_rejects_invalid_neutrality_and_spy_cost():
    c=case();c['config']=replace(c['config'],dollar_neutral=1)
    with pytest.raises(ValueError):solve(**c)
    c=case();c['config']=replace(c['config'],spy_spread=-.1)
    with pytest.raises(ValueError):solve(**c)
