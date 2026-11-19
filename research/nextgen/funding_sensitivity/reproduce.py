"""Read-only sensitivity table grounded in an EXISTING published B0 summary.

This does not re-estimate a return series. The last column is a conditional
fixed-volatility shift of the legacy raw-return/volatility statistic.
"""
import json
from pathlib import Path
from .core import FundingScenario, evaluate, fixed_vol_sharpe_shift


def sensitivity(reference_result, rates=(.03,.05,.0625,.08), core_states=(1.3,.7)):
    b0 = reference_result['summary']['B0']
    sr, vol = float(b0['sharpe']), float(b0['vol_pct'])/100
    if not 0 < vol < 100 or not -100 < sr < 100:
        raise ValueError('bad B0 score/volatility')
    rows=[]
    for s in core_states:
        for r in rates:
            scenario=FundingScenario(margin_rate=r,legacy_margin_rate=r,
                days=7,stock_borrow_rates=(0.,0.),stock_shortable=(True,True))
            x=evaluate(s,(.3,-.3),(1.,1.),scenario)
            delta=x['extra_cost_nav_per_360d_fixed_holdings']
            rows.append(dict(core_spy=s,margin_rate_percent=r*100,
                legacy_debit_nav=x['legacy_net_debit_nav'],
                segregated_debit_nav=x['segregated_short_debit_nav'],
                incremental_annual_cost_percent=100*delta,
                fixed_vol_legacy_ratio_approx=fixed_vol_sharpe_shift(sr,vol,delta)))
    return dict(kind='CONDITIONAL_SYNTHETIC_FINANCING_SENSITIVITY',
                reference='L4_exploit/RESULT.json summary.B0, 2020-2025 reused window',
                reference_raw_ratio=sr,reference_vol_pct=100*vol,
                extra_return_pct_to_reach_raw_ratio_1_at_fixed_vol=100*(1-sr)*vol,
                scenarios=rows,
                limitations='not historical net Sharpe; actual settled debit, ETB eligibility, rates, beta hedge and holdings unavailable')


def main():
    root=Path(__file__).resolve().parents[3]
    source=root/'research/tree/L4_exploit/RESULT.json'
    with source.open(encoding='utf-8') as f:
        report=json.load(f)
    print(json.dumps(sensitivity(report),indent=2,allow_nan=False))


if __name__=='__main__':
    main()
