"""Reproduce synthetic calibration experiment and *conditional* L4 power check.

L4 read is exclusively a previously-published summary, not raw market data.
Never fit the calibration factor on that outcome. Oracle mu is synthetic only.
"""
import json
from pathlib import Path
from .core import simulate
from .constrained import run_constrained
from .power import power_projection


def produce(repo_root=None):
    root = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    with (root/'research/tree/L4_exploit/RESULT.json').open(encoding='utf-8') as f:
        l4 = json.load(f)
    score = l4['tests_vs_B0']['B5a']['lw2008_hac']
    weeks = int(l4['summary']['B0']['weeks'])
    powers = [power_projection(delta_sr=float(score['sharpe_diff_ann']),
                               historical_se=float(score['se_ann']),
                               historical_weeks=weeks,proposed_weeks=k,
                               family_size=7) for k in (43,52,302,520)]
    return {'label':'NO NEW HISTORICAL BACKTEST; synthetic forecast noise only',
            'published_report_input':'research/tree/L4_exploit/RESULT.json',
            'analytic_mc':simulate(),
            'cost_aware_mc':run_constrained(),
            'conditional_research_power':powers}


if __name__=='__main__':
    print(json.dumps(produce(),indent=2,allow_nan=False))
