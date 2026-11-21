"""GitHub PR review smoke tests for the exact research-only implementation."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import numpy as np
import pytest
from scipy.optimize import approx_fprime
from research.nextgen.multialpha.signals import Signal, combine, UNIT
from research.nextgen.multialpha.factors import RiskModel,covariance
from research.nextgen.multialpha.portfolio import Policy,solve
from research.nextgen.multialpha.study import study

T=datetime(2026,11,19,15,tzinfo=timezone.utc)
H=T+timedelta(days=7)
IDS=tuple('PIT_%d'%i for i in range(6))

def signal(name='M',values=None,status='approved',role='full_forecast',weight=1):
    if values is None:values=np.linspace(-.018,.018,6)
    return Signal(name,IDS,tuple(values),T-timedelta(minutes=2),
                  T-timedelta(days=15),H,status,
                  'synthetic approval only' if status=='approved' else '',
                  weight if status=='approved' else 0,role,UNIT)

def inputs(**kw):
    B=np.c_[np.linspace(-1,1,6),np.array([1,-1,1,-1,1,-1])]
    d=dict(sources=[signal()],security_ids=IDS,decision_at=T,holding_end_at=H,
      risk=RiskModel(T-timedelta(days=1),B,np.diag([.001,.0007]),
          np.full(6,.0015),np.zeros(6),.003),beta=np.ones(6),
      spy_expected_excess=.003,core_spy=1.3,previous_weights=np.zeros(6),
      previous_net_spy=1.3,stock_half_spread=np.full(6,.00005),
      stock_daily_vol=np.full(6,.02),stock_adv=np.full(6,1e9),
      stock_short_borrow_rates=np.full(6,.015),stock_shortable=[True]*6,
      factor_lower=np.full(2,-.2),factor_upper=np.full(2,.2),
      market_asof_at=T-timedelta(days=1),borrow_asof_at=T-timedelta(minutes=2),
      holdings_asof_at=T-timedelta(minutes=1),policy=Policy())
    d.update(kw)
    return d


def test_shadow_never_contributes_to_alpha():
    x=combine([signal(),signal('S',values=np.full(6,999),status='shadow')],
              security_ids=IDS,decision_at=T,holding_end_at=H)
    np.testing.assert_allclose(x['mu'],np.linspace(-.018,.018,6))
    assert x['approved']==('M',)

def test_full_forecast_average_prevents_double_count():
    x=combine([signal(),signal('copy')],security_ids=IDS,decision_at=T,holding_end_at=H)
    np.testing.assert_allclose(x['mu'],np.linspace(-.018,.018,6))
    assert x['weights']=={'M':.5,'copy':.5}

def test_incremental_component_adds_only_with_approval():
    extra=np.array([.003,-.003,.003,-.003,.003,-.003])
    x=combine([signal(),signal('I',extra,role='incremental_component',weight=.4)],
              security_ids=IDS,decision_at=T,holding_end_at=H)
    np.testing.assert_allclose(x['mu'],np.linspace(-.018,.018,6)+.4*extra)

def test_duplicate_and_rank_signal_fail_closed():
    with pytest.raises(ValueError,match='double-count'):
        combine([signal(),signal('fake',2*np.linspace(-.018,.018,6),role='incremental_component')],
                security_ids=IDS,decision_at=T,holding_end_at=H)
    with pytest.raises(ValueError,match='ordinal'):
        combine([replace(signal(),units='rank')],security_ids=IDS,decision_at=T,holding_end_at=H)

def test_future_signal_or_model_cutoff_rejected():
    with pytest.raises(ValueError):
        combine([replace(signal(),published_at=T)],security_ids=IDS,decision_at=T,holding_end_at=H)
    with pytest.raises(ValueError):
        combine([replace(signal(),trained_target_end_at=T)],security_ids=IDS,decision_at=T,holding_end_at=H)

def test_factor_psd_model_and_broken_joint_covariance():
    r=inputs()['risk'];cov=covariance(r)
    assert np.linalg.eigvalsh(cov['residual_cov']).min()>0
    with pytest.raises(ValueError,match='combined SPY'):
        covariance(replace(r,spy_covariance=np.full(6,1.)))

def test_exact_fund_and_factor_hard_constraints():
    z=solve(**inputs())
    assert z['fund_gross']<=1.9+1e-7
    assert z['segregated_debit']<=.5+1e-7
    assert np.max(abs(z['factor_exposures']))<=.2+1e-7
    assert z['approved_alphas']==('M',)

def test_strict_factor_band_actually_changes_weights():
    d=inputs()
    a=solve(**dict(d,factor_lower=np.full(2,-10.),factor_upper=np.full(2,10.)))
    b=solve(**dict(d,factor_lower=np.full(2,-.025),factor_upper=np.full(2,.025)))
    assert np.linalg.norm(a['weights']-b['weights'])>.005
    assert np.max(abs(b['factor_exposures']))<=.025+1e-7

def test_conservative_cash_and_shortability():
    z=solve(**inputs(policy=Policy(max_segregated_debit=.34)))
    assert z['segregated_debit']<=.34+1e-7
    flags=[True]*6;flags[0]=False
    x=solve(**inputs(stock_shortable=flags))
    assert x['weights'][0]>=-1e-10

def test_causal_risk_and_market_data_vintages():
    d=inputs()
    with pytest.raises(ValueError,match='market_asof_at'):
        solve(**dict(d,market_asof_at=T+timedelta(minutes=1)))
    with pytest.raises(ValueError,match='risk.asof_at'):
        solve(**dict(d,risk=replace(d['risk'],asof_at=T+timedelta(minutes=1))))

def test_solver_failure_fails_closed():
    from types import SimpleNamespace
    import research.nextgen.multialpha.portfolio as m
    with patch.object(m,'minimize',return_value=SimpleNamespace(success=False,message='injected')):
        with pytest.raises(RuntimeError,match='did not converge'):
            solve(**inputs())

def test_analytic_gradient_matches_finite_differences():
    import research.nextgen.multialpha.portfolio as m
    real=m.minimize;errors=[]
    def inspect(f,x0,**kw):
        z=x0.copy();z[:6]=[-.03,-.012,.008,.014,.011,.012]
        errors.append(float(np.max(np.abs(approx_fprime(z,f,1e-8)-kw['jac'](z)))))
        return real(f,x0,**kw)
    with patch.object(m,'minimize',inspect):solve(**inputs())
    assert errors[0]<1e-6

def test_synthetic_true_alpha_falsification_reproduces():
    x=study(repetitions=20,seed=20261119)
    assert x==study(repetitions=20,seed=20261119)
    assert x['results']['complementary_incremental']['mean_true_utility_delta']>0
    assert x['results']['spurious_incremental']['mean_true_utility_delta']<0
    assert x['results']['spurious_incremental']['mean_predicted_utility_delta']>0

def test_parent_optimizer_consistency_when_extra_costs_off():
    from research.nextgen.fund_aware.core import solve as parent,Config
    d=inputs(policy=Policy(margin_rate_annual=0,max_segregated_debit=2),
             stock_short_borrow_rates=np.zeros(6),
             factor_lower=np.full(2,-10.),factor_upper=np.full(2,10.))
    z=solve(**d);c=covariance(d['risk'])
    q=parent(expected_residual_excess=np.array(d['sources'][0].expected_residual_excess),
        residual_covariance=c['residual_cov'],beta=d['beta'],
        residual_spy_cov=c['spy_cov'],spy_expected_excess=d['spy_expected_excess'],
        spy_variance=c['spy_var'],core_spy=d['core_spy'],
        previous_weights=d['previous_weights'],previous_net_spy=d['previous_net_spy'],
        stock_half_spread=d['stock_half_spread'],stock_daily_vol=d['stock_daily_vol'],
        stock_adv=d['stock_adv'],
        config=Config(gamma=5,max_fund_gross=1.9,max_book_gross=.6,max_name_abs=.15,
                      aum=1e7,impact_k=.05,spy_spread=.0001))
    assert abs(z['predicted_utility_net_costs']-q['net_expected_quadratic_utility'])<2e-6
