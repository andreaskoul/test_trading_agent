"""Causal, date-balanced score-to-beta-hedged-excess-return calibration.

Research only. A declared PIT/OOF contract is *necessary but not proof* the
upstream score-generating model was properly trained. No market data is read.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from math import isfinite, sqrt
from typing import Iterable

import numpy as np
from scipy.stats import rankdata


def utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ScoreObservation:
    """One eligible historical security (stable PIT ID) at one decision instant.

    target_excess is a *beta-hedged*, risk-free-adjusted simple holding-period
    return, provided only for historical evaluation. It is not a raw stock
    expected return. target_available_at is the availability of the realised
    target, not the decision-date feature vintage.
    """
    security_id: str
    decision_at: datetime
    score_available_at: datetime
    upstream_train_target_end_at: datetime
    target_end_at: datetime
    target_available_at: datetime | None
    score: float
    target_excess: float | None
    eligible: bool = True

    def __post_init__(self):
        if not isinstance(self.security_id, str) or not self.security_id.strip():
            raise ValueError("nonempty stable PIT security_id required")
        if type(self.eligible) is not bool:
            raise ValueError("eligible must be boolean")
        decision = utc(self.decision_at, "decision_at")
        score_at = utc(self.score_available_at, "score_available_at")
        trained = utc(self.upstream_train_target_end_at, "upstream_train_target_end_at")
        end = utc(self.target_end_at, "target_end_at")
        if not trained <= score_at < decision < end:
            raise ValueError("model training target end <= score availability < decision < label end required")
        if not isinstance(self.score, (int, float, np.integer, np.floating)) or not isfinite(self.score):
            raise ValueError("finite score required")
        if self.target_excess is None:
            if self.target_available_at is not None:
                raise ValueError("unknown target cannot have target availability")
        else:
            if not isinstance(self.target_excess, (int,float,np.integer,np.floating)) or not isfinite(self.target_excess):
                raise ValueError("finite target_excess required")
            if self.target_available_at is None or utc(self.target_available_at, "target_available_at") < end:
                raise ValueError("realised target must have availability at or after target end")


@dataclass(frozen=True)
class CalibrationConfig:
    min_train_dates: int = 26
    min_names: int = 20
    ridge: float = 0.03  # added to mean(x^2), fixed *before* evaluation
    conservative_z: float = 1.96  # soft threshold, not sequential hypothesis significance
    hac_lags: int = 4
    embargo: timedelta = timedelta(days=1)
    lookback_dates: int | None = 104

    def __post_init__(self):
        if (type(self.min_train_dates) is not int or self.min_train_dates < 3 or
            type(self.min_names) is not int or self.min_names < 2 or
            type(self.hac_lags) is not int or self.hac_lags < 0 or
            self.hac_lags >= self.min_train_dates or
            type(self.embargo) is not timedelta or self.embargo < timedelta(0)):
            raise ValueError("invalid min train/names, lags or embargo")
        if self.lookback_dates is not None and (type(self.lookback_dates) is not int or self.lookback_dates < self.min_train_dates):
            raise ValueError("lookback_dates must retain at least min_train_dates")
        if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and isfinite(v) and v >= 0
                   for v in (self.ridge, self.conservative_z)):
            raise ValueError("nonnegative finite ridge and conservative_z required")


@dataclass(frozen=True)
class CalibratedForecast:
    security_id: str
    decision_at: datetime
    centered_rank: float
    mu_unshrunk: float
    mu_conservative: float
    slope: float
    slope_standard_error: float
    fitted_train_dates: int
    latest_training_target_available_at: datetime | None


@dataclass(frozen=True)
class Fit:
    slope: float
    se: float
    conservative_slope: float
    n_dates: int
    last_available: datetime | None


def _rank_scores(group: list[ScoreObservation]) -> np.ndarray:
    if len(group) < 2:
        return np.zeros(len(group),dtype=float)
    ranks = rankdata([r.score for r in group], method="average")
    return 2.0*(ranks - 1.0)/(len(group)-1.0) - 1.0


def _group_rows(records: Iterable[ScoreObservation]):
    dates = defaultdict(list)
    ids = set()
    for r in records:
        if not isinstance(r, ScoreObservation):
            raise TypeError("ScoreObservation records required")
        t = utc(r.decision_at,"decision_at")
        pair = (t, r.security_id)
        if pair in ids:
            raise ValueError("duplicate (decision time, PIT security ID); resolve revisions upstream")
        ids.add(pair)
        if r.eligible:
            dates[t].append(r)
    return {t: sorted(dates[t], key=lambda r:r.security_id) for t in sorted(dates)}


def _date_label_matured(rows: list[ScoreObservation], cutoff: datetime) -> bool:
    """Entire eligible date cross-section must have matured; no partial survivors."""
    return all(r.target_excess is not None and
               utc(r.target_end_at,"target_end_at") < cutoff and
               utc(r.target_available_at,"target_available_at") < cutoff for r in rows)


def _fit(train_dates: list[tuple[datetime, list[ScoreObservation]]], cfg: CalibrationConfig) -> Fit:
    if len(train_dates) < cfg.min_train_dates:
        return Fit(0., float("inf"), 0., len(train_dates), None)
    h, q, latest = [], [], None
    for _,rows in train_dates:
        x = _rank_scores(rows)
        y = np.array([r.target_excess for r in rows],float)
        y -= y.mean()  # calibrated CROSS-SECTIONAL alpha; intercept cancels
        h.append(float(np.mean(x*x)))
        q.append(float(np.mean(x*y)))
        for r in rows:
            t = utc(r.target_available_at,"target_available_at")
            latest=t if latest is None or t>latest else latest
    h, q = np.array(h), np.array(q)
    den = float(h.mean()+cfg.ridge)
    slope = float(q.mean()/den) if den>1e-15 else 0.0
    u = q-slope*(h+cfg.ridge)  # exactly mean-zero ridge estimating equation
    n = len(u)
    # Newey-West Bartlett long-run variance of DATE-LEVEL scores, not assets.
    omega = float(u @ u/n)
    for lag in range(1,min(cfg.hac_lags,n-1)+1):
        omega += 2*(1-lag/(cfg.hac_lags+1))*float(u[lag:] @ u[:-lag]/n)
    omega=max(omega,0.0)  # numerical negative noise near the machine floor
    se=float(sqrt(omega/n)/den) if den>1e-15 else float('inf')
    conservative=float(np.sign(slope)*max(abs(slope)-cfg.conservative_z*se,0.0))
    return Fit(slope,se,conservative,n,latest)


def walk_forward(records: Iterable[ScoreObservation], *, first_decision_at: datetime,
                 config: CalibrationConfig=CalibrationConfig()) -> list[CalibratedForecast]:
    """Expanding/rolling chronological calibration, purged by label *availability*.

    Strictly mature before decision - embargo. Never accesses a test target to
    construct its forecast, including when an upstream record has labels from
    already-known later rows. Returns zero alpha on insufficient training.
    """
    first=utc(first_decision_at,"first_decision_at")
    grouped=_group_rows(records)
    preds=[]
    for t,rows in grouped.items():
        if t<first or len(rows)<config.min_names:
            continue
        cutoff=t-config.embargo
        candidates=[(dt,rr) for dt,rr in grouped.items()
                    if dt<t and len(rr)>=config.min_names and _date_label_matured(rr,cutoff)]
        if config.lookback_dates is not None:
            candidates=candidates[-config.lookback_dates:]
        fit=_fit(candidates,config)
        x=_rank_scores(rows)
        for r,xx in zip(rows,x):
            preds.append(CalibratedForecast(r.security_id,t,float(xx),
                float(fit.slope*xx), float(fit.conservative_slope*xx),
                fit.slope,fit.se,fit.n_dates,fit.last_available))
    return preds


def predictive_loss(records: Iterable[ScoreObservation], predictions: Iterable[CalibratedForecast],
                    *, min_names: int=2) -> dict:
    """Ex-post DATE-balanced MSE diagnostic. Never used within walk_forward.

    Do not tune parameters on this evaluation if the dates will be claimed OOS.
    Requires complete cross-section labels for every evaluated date and aborts
    on incomplete outcomes (e.g. missing delistings), rather than dropping rows.
    """
    grouped=_group_rows(records)
    indexed={}
    for p in predictions:
        key=(utc(p.decision_at,"decision_at"),p.security_id)
        if key in indexed:
            raise ValueError("duplicate calibrated forecast")
        indexed[key]=p
    date_loss=[]
    for t,rr in grouped.items():
        forecast=[indexed.get((t,r.security_id)) for r in rr]
        if all(x is None for x in forecast):
            continue
        if any(x is None for x in forecast):
            raise ValueError("incomplete date cross-section of forecasts")
        if len(rr)<min_names:
            raise ValueError("insufficient eligible names")
        if any(r.target_excess is None for r in rr):
            raise ValueError("missing outcome; do not silently drop delisted names")
        y=np.array([r.target_excess for r in rr],dtype=float)
        y-=y.mean()
        raw=np.array([p.mu_unshrunk for p in forecast])
        safe=np.array([p.mu_conservative for p in forecast])
        date_loss.append([float(np.mean((y-raw)**2)),
                          float(np.mean((y-safe)**2)),
                          float(np.mean(y*y))])
    if not date_loss:
        raise ValueError("no comparable evaluated dates")
    arr=np.array(date_loss)
    return dict(n_dates=len(arr),mse_raw=float(arr[:,0].mean()),
                mse_conservative=float(arr[:,1].mean()),mse_zero=float(arr[:,2].mean()),
                improvement_conservative_vs_raw=float((arr[:,0]-arr[:,1]).mean()),
                improvement_conservative_vs_zero=float((arr[:,2]-arr[:,1]).mean()))
