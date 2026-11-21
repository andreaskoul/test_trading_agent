"""Pre-specified controlled synthetic alpha admission falsification.

NOT historical PnL or whole-fund Sharpe; oracle true alpha is used ONLY to
score policies after they are computed. No model-selection holdout accessed.
"""
from datetime import datetime,timedelta,timezone
from math import sqrt
import numpy as np
from .signals import Signal,UNIT,combine
from .factors import RiskModel
from .portfolio import solve,Policy

SEED=20261119
T=datetime(2026,11,19,15,tzinfo=timezone.utc)
H=T+timedelta(days=7)
N=6
IDS=tuple(f'SYNTH_PIT:{i:04d}' for i in range(N))
B=np.c_[np.linspace(-1,1,N),np.array([1,-1,1,-1,1,-1])]
RISK=RiskModel(T-timedelta(days=1),B,np.diag([.001,.0007]),
               np.full(N,.0015),np.zeros(N),.003)
POL=Policy(max_fund_gross=1.9,max_book_gross=.6,max_name_abs=.15,
           max_segregated_debit=.5,margin_rate_annual=.06,
           stock_impact_k=.05,spy_spread=.0001,gamma=5.)


def source(name,mu,role='full_forecast',status='approved',weight=1):
    return Signal(name,IDS,tuple(mu),T-timedelta(minutes=15),
                  T-timedelta(days=15),H,status,
                  'SYNTHETIC APPROVAL ONLY' if status=='approved' else '',
                  weight if status=='approved' else 0.,role,UNIT)


def _solve(signals, policy=POL):
    return solve(sources=signals,security_ids=IDS,decision_at=T,holding_end_at=H,
            risk=RISK,beta=np.ones(N),spy_expected_excess=.003,core_spy=1.3,
            previous_weights=np.zeros(N),previous_net_spy=1.3,
            stock_half_spread=np.full(N,.00005),stock_daily_vol=np.full(N,.02),
            stock_adv=np.full(N,1e9),stock_short_borrow_rates=np.full(N,.015),
            stock_shortable=[True]*N,
            factor_lower=np.array([-.2,-.2]),factor_upper=np.array([.2,.2]),
            market_asof_at=T-timedelta(days=1),borrow_asof_at=T-timedelta(hours=1),
            holdings_asof_at=T-timedelta(minutes=1),policy=policy)


def true_utility(res, signals, true_alpha):
    # Evaluation retains identical variance, real modeled costs and core.
    # The only substitution is hidden true stock residual expected returns.
    known=combine(signals,security_ids=IDS,decision_at=T,holding_end_at=H)['mu']
    return res['predicted_utility_net_costs']+float(res['weights']@(true_alpha-known))


def study(*, repetitions=100, seed=SEED):
    """Two pre-specified contexts: independent incremental vs noise spuriously approved."""
    if type(repetitions) is not int or not 10<=repetitions<=2000 or type(seed) is not int or seed<0:
        raise ValueError('invalid repetitions or seed')
    rng=np.random.default_rng(seed)
    rows={'complementary_incremental':[], 'spurious_incremental':[]}
    for _ in range(repetitions):
        base=rng.normal(0,.018,N);base-=base.mean()
        complement=rng.normal(0,.012,N);complement-=complement.mean()
        master=base+rng.normal(0,.005,N)
        master-=master.mean()
        v=complement+rng.normal(0,.005,N)
        v-=v.mean()
        bad=rng.normal(0,.025,N);bad-=bad.mean()
        main=source('MASTER_synthetic',master)
        new=source('independent_component_synthetic',v,role='incremental_component')
        noisy=source('spurious_component_synthetic',bad,role='incremental_component')
        # Three allocations on independently generated synthetic forecasts.
        alpha0=[main]
        combo=[main,new]
        badcombo=[main,noisy]
        a=_solve(alpha0)
        b=_solve(combo)
        c=_solve(badcombo)
        truth_complement=base+complement
        truth_null=base
        rows['complementary_incremental'].append(
            (true_utility(b,combo,truth_complement)-true_utility(a,alpha0,truth_complement),
             b['predicted_utility_net_costs']-a['predicted_utility_net_costs'],
             b['fund_gross']-a['fund_gross']))
        rows['spurious_incremental'].append(
            (true_utility(c,badcombo,truth_null)-true_utility(a,alpha0,truth_null),
             c['predicted_utility_net_costs']-a['predicted_utility_net_costs'],
             c['fund_gross']-a['fund_gross']))
    out={}
    for name,v in rows.items():
        x=np.array(v)
        out[name]=dict(repetitions=repetitions,
            mean_true_utility_delta=float(x[:,0].mean()),
            paired_mc_se_true_utility_delta=float(x[:,0].std(ddof=1)/sqrt(repetitions)),
            mean_predicted_utility_delta=float(x[:,1].mean()),
            fraction_true_utility_improvements=float(np.mean(x[:,0]>0)),
            mean_fund_gross_delta=float(x[:,2].mean()))
    return dict(kind='synthetic 1.3x SPY core, factor-aware cost/cash cap multi-alpha study',
                seed=seed,truth_access='after allocation only for evaluation',
                independent_component='new independent latent forecast of residual return premium',
                spurious_component='random nonpredictive incremental forecast, deliberately misapproved',
                results=out,
                scope='conditional quadratic net utility, NOT historical returns, real Sharpe or broker margin')


if __name__=='__main__':
    import json
    print(json.dumps(study(),indent=2))
