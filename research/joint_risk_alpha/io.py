"""Read-only input contracts. No network, cache writes or live fund imports."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class HFPanel:
    dates: pd.DatetimeIndex
    names: tuple[str,...]
    intraday: np.ndarray      # T x 14 x N log returns, overnight plus 13 half-hour bars
    realized_var: np.ndarray  # T x N
    source_sha256: str

@dataclass(frozen=True)
class AlphaPanel:
    dates: pd.DatetimeIndex
    names: tuple[str,...]
    score: np.ndarray
    outcome: np.ndarray
    eligible: np.ndarray
    chars: np.ndarray
    stock_returns: np.ndarray
    spy_returns: np.ndarray
    source_sha256: str


def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def _dates(d):
    dates=pd.DatetimeIndex(d)
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError('STOP: dates not unique or strictly increasing')
    return dates


def _names(a):
    n=tuple(str(x) for x in a)
    if len(n)!=len(set(n)):raise ValueError('STOP: duplicate securities')
    return n


def read_hf(path: str|Path, max_date='2019-12-31') -> HFPanel:
    path=Path(path)
    with np.load(path,allow_pickle=False) as f:
        if not {'S','names','R','rv'}<=set(f.files):raise ValueError('STOP: missing HF arrays')
        dates=_dates(f['S']); names=_names(f['names'])
        # The original riskfield hf.npz contains 2016-2025. Read and mask it
        # immediately; the research pipeline NEVER exposes later rows to fit.
        ndev=int((dates<=pd.Timestamp(max_date)).sum())
        if ndev<100:raise ValueError('STOP: insufficient development intraday history')
        R=np.asarray(f['R'][:ndev],dtype=np.float64)
        rv=np.asarray(f['rv'][:ndev],dtype=np.float64)
        dates=dates[:ndev]
    if R.ndim!=3 or R.shape!=(len(dates),14,len(names)) or rv.shape!=(len(dates),len(names)):
        raise ValueError('STOP: HF shapes inconsistent')
    if 'SPY' not in names:raise ValueError('STOP: SPY missing from HF panel')
    if np.isinf(R).any() or np.isinf(rv).any() or np.any(rv[np.isfinite(rv)]<0):
        raise ValueError('STOP: inf or negative realised variance')
    return HFPanel(dates,names,R,rv,digest(path))


def read_alpha(path: str|Path,max_date='2019-12-31') -> AlphaPanel:
    path=Path(path)
    with np.load(path,allow_pickle=False) as f:
        required={'S','names','master_h5_ref','y5','elig','Z','r','rm'}
        if not required<=set(f.files):raise ValueError('STOP: missing development alpha data '+str(required-set(f.files)))
        dates=_dates(f['S']);names=_names(f['names'])
        if dates[-1]>pd.Timestamp(max_date):raise ValueError('STOP: alpha panel includes non-development dates')
        score=f['master_h5_ref'].astype(float)
        outcome=f['y5'].astype(float)
        eligible=f['elig'].astype(bool)
        chars=f['Z'].astype(float)
        stock_returns=f['r'].astype(float)
        market=f['rm'].astype(float)
    t,n=len(dates),len(names)
    if score.shape!=(t,n) or outcome.shape!=(t,n) or eligible.shape!=(t,n) or stock_returns.shape!=(t,n) or chars.shape[:2]!=(t,n) or market.shape!=(t,):
        raise ValueError('STOP: alpha matrix shape mismatch')
    if not dates[-1].year<=2019:raise ValueError('STOP: attempted reused outcome read')
    return AlphaPanel(dates,names,score,outcome,eligible,chars,stock_returns,market,digest(path))


def hf_daily_returns(p:HFPanel):
    """Strict complete-bar daily returns; no imputation of incompletely observed days."""
    return np.where(np.isfinite(p.intraday).all(axis=1),p.intraday.sum(axis=1),np.nan)


def origin_grid(p:HFPanel,first='2017-01-01',last='2019-12-31',stride=5,horizon=5,warmup=252):
    mask=(p.dates>=pd.Timestamp(first))&(p.dates<=pd.Timestamp(last))
    ix=np.where(mask)[0]
    ix=ix[(ix>=warmup)&(ix+horizon<len(p.dates))]
    return ix[::stride]


def np_json(v):
    """Explicit JSON scalar conversion, never silently write NaN."""
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(np.floating,)):return float(v)
    if isinstance(v,(np.ndarray,)):return v.tolist()
    if isinstance(v,pd.Timestamp):return str(v.date())
    raise TypeError(str(type(v)))
