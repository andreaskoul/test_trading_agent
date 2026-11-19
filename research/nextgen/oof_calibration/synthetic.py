"""Pre-specified synthetic PIT score calibration studies; no historical data."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from math import sqrt
import numpy as np
from .core import ScoreObservation, CalibrationConfig, walk_forward, predictive_loss


DESIGN = dict(seed=20261119, n_names=32, train_dates=80, evaluation_dates=32,
              idiosyncratic_sigma=0.012, date_shock_sigma=0.003,
              true_slope=0.010, min_train_dates=26, min_names=20,
              ridge=0.03, conservative_z=1.96, hac_lags=4,
              embargo_days=1, lookback_dates=52)


def make_panel(*, scenario: str, seed: int, design: dict | None=None):
    """Create overlapping label dates: model pre-fit; score available predecision."""
    if scenario not in ("stable", "null", "break"):
        raise ValueError("scenario must be stable, null or break")
    p = DESIGN if design is None else design
    rng = np.random.default_rng(seed)
    start = datetime(2014, 1, 2, 16, tzinfo=timezone.utc)
    records=[]
    for week in range(p['train_dates']+p['evaluation_dates']):
        t=start+timedelta(weeks=week)
        scores=rng.normal(size=p['n_names'])
        # Independently implement the same deterministic rank map to generate data.
        order=np.argsort(scores,kind='stable')
        ranks=np.empty(p['n_names'],float)
        ranks[order]=np.arange(p['n_names'])
        rank=2*ranks/(p['n_names']-1)-1
        slope=(p['true_slope'] if scenario=='stable' or
               scenario=='break' and week < p['train_dates'] else 0.0)
        shock=rng.normal(0,p['date_shock_sigma'])
        noise=rng.normal(0,p['idiosyncratic_sigma'],p['n_names'])
        y=slope*rank+shock+noise
        for i in range(p['n_names']):
            records.append(ScoreObservation(
                security_id=f'PIT_SYNTH_{i:04d}',decision_at=t,
                score_available_at=t-timedelta(minutes=4),
                upstream_train_target_end_at=t-timedelta(days=15),
                target_end_at=t+timedelta(days=7),
                target_available_at=t+timedelta(days=8),
                score=float(scores[i]), target_excess=float(y[i]),
                eligible=True))
    return records,start+timedelta(weeks=p['train_dates'])


def single_experiment(scenario: str, *, seed: int, design: dict | None=None):
    p=DESIGN if design is None else design
    records, first=make_panel(scenario=scenario,seed=seed,design=p)
    cfg=CalibrationConfig(min_train_dates=p['min_train_dates'],min_names=p['min_names'],
        ridge=p['ridge'],conservative_z=p['conservative_z'],
        hac_lags=p['hac_lags'],embargo=timedelta(days=p['embargo_days']),
        lookback_dates=p['lookback_dates'])
    forecasts=walk_forward(records,first_decision_at=first,config=cfg)
    results=predictive_loss(records,forecasts,min_names=p['min_names'])
    dates=sorted({p.decision_at for p in forecasts})
    slopes=[next(p for p in forecasts if p.decision_at==t) for t in dates]
    results['fraction_dates_slope_zero_after_gate']=sum(
        abs(p.mu_conservative)<1e-15 for p in forecasts)/len(forecasts)
    results['last_unshrunk_slope']=slopes[-1].slope
    results['last_estimation_se']=slopes[-1].slope_standard_error
    return results


def study(*, replicates: int=40, seed: int=20261119):
    """Register scenario comparisons in code; all seeds fixed before execution."""
    if type(replicates) is not int or replicates<3 or replicates>1000 or type(seed) is not int or seed<0:
        raise ValueError('replicates must be integer 3..1000 and seed nonnegative')
    out={}
    for case in ('stable','null','break'):
        x=[single_experiment(case,seed=seed+j) for j in range(replicates)]
        d_raw=np.array([z['mse_zero']-z['mse_raw'] for z in x])
        d_safe=np.array([z['mse_zero']-z['mse_conservative'] for z in x])
        improve=np.array([z['improvement_conservative_vs_raw'] for z in x])
        out[case]={
            'replicates':replicates,'eval_dates_per_rep':DESIGN['evaluation_dates'],
            'avg_mse_zero':float(np.mean([z['mse_zero'] for z in x])),
            'avg_mse_raw':float(np.mean([z['mse_raw'] for z in x])),
            'avg_mse_conservative':float(np.mean([z['mse_conservative'] for z in x])),
            'zero_minus_raw_mse':float(d_raw.mean()),
            'zero_minus_conservative_mse':float(d_safe.mean()),
            'conservative_minus_raw_mse_reduction':float(improve.mean()),
            'mc_se_conservative_minus_raw':float(improve.std(ddof=1)/sqrt(replicates)),
            'avg_fraction_dates_gated_to_zero':float(np.mean([
                z['fraction_dates_slope_zero_after_gate'] for z in x])),
            'avg_last_unshrunk_slope':float(np.mean([z['last_unshrunk_slope'] for z in x])),
        }
    return {'study':'synthetic rank-to-cross-sectional-excess calibration, no market data',
            'design':dict(DESIGN),'seed':seed,'scenarios':out,
            'limitations':'MSE of demeaned returns, not net NAV or whole-fund Sharpe; no execution or financing'}


if __name__=='__main__':
    import json
    print(json.dumps(study(),indent=2))


def comparative_study(*,replicates: int=40,seed: int=20261201):
    """EXPLORATORY FOLLOWUP, design chosen after seeing initial 52-date failures.

    Results must not be treated as new sealed evidence of trading edge.
    The state-space process variance and short-window length are held fixed.
    """
    from .state_space import StateSpaceConfig, state_space_walk_forward
    if type(replicates) is not int or not 3<=replicates<=200 or type(seed) is not int or seed<0:
        raise ValueError('invalid replicate count or seed')
    cfg_short=CalibrationConfig(min_train_dates=8,min_names=DESIGN['min_names'],
        ridge=DESIGN['ridge'],conservative_z=DESIGN['conservative_z'],
        hac_lags=DESIGN['hac_lags'],embargo=timedelta(days=DESIGN['embargo_days']),
        lookback_dates=12)
    cfg_kalman=StateSpaceConfig(min_train_dates=26,min_names=DESIGN['min_names'],
        process_variance_per_week=.0015**2,prior_variance=.02**2,
        conservative_z=1.96,embargo=timedelta(days=1))
    out={}
    for case in ('stable','null','break'):
        matrix=[]
        for j in range(replicates):
            rows,first=make_panel(scenario=case,seed=seed+j)
            a=walk_forward(rows,first_decision_at=first,config=cfg_short)
            b=state_space_walk_forward(rows,first_decision_at=first,config=cfg_kalman)
            la=predictive_loss(rows,a,min_names=DESIGN['min_names'])
            lb=predictive_loss(rows,b,min_names=DESIGN['min_names'])
            matrix.append([la['mse_zero'],la['mse_raw'],la['mse_conservative'],
                           lb['mse_raw'],lb['mse_conservative']])
        m=np.array(matrix)
        out[case]={
            'replicates':replicates,
            'zero_mse':float(m[:,0].mean()),
            'short12_raw_mse':float(m[:,1].mean()),
            'short12_gated_mse':float(m[:,2].mean()),
            'kalman_raw_mse':float(m[:,3].mean()),
            'kalman_gated_mse':float(m[:,4].mean()),
            'kalman_raw_minus_zero':float((m[:,3]-m[:,0]).mean()),
            'kalman_gated_minus_short12_gated':float((m[:,4]-m[:,2]).mean()),
            'paired_mc_se_kalman_gated_minus_short':float((m[:,4]-m[:,2]).std(ddof=1)/sqrt(replicates)),
        }
    return dict(kind='exploratory synthetic adaptation comparison, no financial backtest',
                settings={'replicates':replicates,'seed':seed,'short_window':12,
                          'state_process_variance_per_week':cfg_kalman.process_variance_per_week,
                          'state_prior_variance':cfg_kalman.prior_variance},
                scenarios=out)
