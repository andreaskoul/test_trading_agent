"""Causal one-dimensional Kalman score calibration; synthetic proof of concept.

The cross-sectional slope is a random walk and target dates are admitted only
once the *entire eligible* cross-section becomes available. Estimate is noisy;
no regime-change probability or full forecast-error covariance is implied.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime,timedelta
from math import sqrt,isfinite
import numpy as np

from .core import ScoreObservation, CalibratedForecast, CalibrationConfig, utc, _group_rows, _date_label_matured, _rank_scores


@dataclass(frozen=True)
class StateSpaceConfig:
    min_train_dates: int = 26
    min_names: int = 20
    process_variance_per_week: float = 0.0015**2
    prior_variance: float = 0.02**2
    conservative_z: float = 1.96
    embargo: timedelta = timedelta(days=1)

    def __post_init__(self):
        if (type(self.min_train_dates) is not int or self.min_train_dates < 3 or
            type(self.min_names) is not int or self.min_names < 3 or
            type(self.embargo) is not timedelta or self.embargo<timedelta(0) or
            not all(isinstance(v,(int,float)) and not isinstance(v,bool) and isfinite(v) and v >=0
                    for v in (self.process_variance_per_week,self.prior_variance,self.conservative_z)) or
            self.prior_variance<=0):
            raise ValueError('invalid state-space parameters')


def _cross_section_slope(rows: list[ScoreObservation]):
    x=_rank_scores(rows)
    y=np.array([r.target_excess for r in rows],dtype=float)
    y -= y.mean()
    h=float(x@x)
    if h<1e-12:
        return None
    b=float(x@y/h)
    residual=y-b*x
    # Uses date's eligible complete universe; two fitted degrees (mean + slope).
    noise=float((residual@residual)/(len(rows)-2)/h)
    return b,max(noise,1e-14)


def state_space_walk_forward(records, *, first_decision_at: datetime,
                             config: StateSpaceConfig=StateSpaceConfig()):
    """Chronological filter processing each *matured* date once, with embargo.

    Process variance scales with elapsed observation dates. Even a fast filter
    cannot know about a change before the corresponding outcome becomes PIT.
    """
    first=utc(first_decision_at,'first_decision_at')
    grouped=_group_rows(records)
    all_dates=list(grouped)
    mean,variance=0.0,config.prior_variance
    prior_date=None
    processed=set()
    n_processed=0
    last_label=None
    results=[]
    for t in all_dates:
        if t<first:
            # Need process matured observations chronologically at time of first prediction;
            # bypass here and scan all past dates at each later decision.
            continue
        cutoff=t-config.embargo
        for dt in all_dates:
            if dt>=t:
                break
            if dt in processed or len(grouped[dt])<config.min_names:
                continue
            if not _date_label_matured(grouped[dt],cutoff):
                continue
            processed.add(dt)
            b_r=_cross_section_slope(grouped[dt])
            if b_r is None:
                continue
            obs,noise_var=b_r
            delta_weeks=1.0 if prior_date is None else max((dt-prior_date).total_seconds()/(7*86400),0.0)
            variance += config.process_variance_per_week * delta_weeks
            gain=variance/(variance+noise_var)
            mean=mean+gain*(obs-mean)
            variance=max((1-gain)*variance,0.0)
            prior_date=dt
            n_processed+=1
            for o in grouped[dt]:
                a=utc(o.target_available_at,'target_available_at')
                if last_label is None or a>last_label:
                    last_label=a
        rows=grouped[t]
        if len(rows)<config.min_names:
            continue
        active=n_processed>=config.min_train_dates
        current=mean if active else 0.
        # Project state uncertainty from last label decision to *today*;
        # observations mature after their target_end, so this gap is nonzero.
        unseen_weeks=(t-prior_date).total_seconds()/(7*86400) if prior_date is not None else 0.0
        projected_variance=variance+config.process_variance_per_week*max(unseen_weeks,0.0)
        se=sqrt(projected_variance) if active else float('inf')
        gated=float(np.sign(current)*max(abs(current)-config.conservative_z*se,0.)) if active else 0.
        x=_rank_scores(rows)
        for o,rank in zip(rows,x):
            results.append(CalibratedForecast(o.security_id,t,float(rank),
                float(rank*current),float(rank*gated),float(current),float(se),
                n_processed,last_label if active else None))
    return results
