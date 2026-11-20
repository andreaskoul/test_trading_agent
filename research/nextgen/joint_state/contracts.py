"""Strict local cache adapters; all outputs use new, explicit schemas.

Risk cache: research/riskfield/panel.py bars -> .cache/riskfield/hf.npz
Alpha cache: research/tree/harness.py load() -> .cache/tree/dev.npz

These adapters DO NOT assert historical survivorship/PIT membership provenance: the
intraday cache contains current S&P500 constituents; an explicit warning survives
in every result. Do not use .cache/p8/edgar/ciks.json for issuer identity.
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import numpy as np

DEV_END = np.datetime64("2019-12-31", "D")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dates_checked(a, name="S"):
    d = np.asarray(a).astype("datetime64[D]")
    if d.ndim != 1 or d.size < 100 or np.isnat(d).any():
        raise ValueError(f"{name}: invalid/missing dates")
    if not np.all(d[1:] > d[:-1]):
        raise ValueError(f"{name}: dates must be unique, increasing")
    return d


def names_checked(a):
    n = [str(x) for x in a]
    if len(n) != len(set(n)) or any(not x or x.lower() == "nan" for x in n):
        raise ValueError("duplicate/invalid security names")
    return np.asarray(n)


@dataclass(frozen=True)
class RiskData:
    dates: np.ndarray
    names: np.ndarray
    intraday: np.ndarray        # sessions x 14 x names, log-return units
    daily: np.ndarray           # sessions x names
    realized: np.ndarray        # sessions x names, sum of intraday squared returns
    sha256: str
    survivorship: str = "UNVERIFIED_CURRENT_CONSTITUENTS_RISKFIELD"


@dataclass(frozen=True)
class AlphaData:
    dates: np.ndarray
    names: np.ndarray
    score: np.ndarray           # weekly decision rows x names, frozen historical MASTER
    residual: np.ndarray        # 5-session forward hedged returns from dev cache
    eligible: np.ndarray
    decision_ix: np.ndarray     # selected Thursdays, within development window
    row_ix: np.ndarray
    sha256: str
    membership: str = "DEV_UNIVERSE_NOT_INDEPENDENTLY_REAUDITED"


def load_risk(path: Path, dev_only=True, n_names: Optional[int]=None) -> RiskData:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"risk intraday cache absent: {path}")
    with np.load(path, allow_pickle=False) as z:
        required = {"S", "names", "R", "rv"}
        if not required <= set(z.files):
            raise ValueError(f"risk cache missing {required - set(z.files)}")
        dates = dates_checked(z["S"])
        names = names_checked(z["names"])
        raw = np.asarray(z["R"], dtype=np.float64)
        rv = np.asarray(z["rv"], dtype=np.float64)
    if raw.ndim != 3 or raw.shape != (len(dates), 14, len(names)):
        raise ValueError("riskfield R expected (sessions, 14 returns, names)")
    if rv.shape != (len(dates), len(names)) or "SPY" not in names:
        raise ValueError("riskfield rv shape/SPY missing")
    if dev_only:
        mask = dates <= DEV_END
        dates, raw, rv = dates[mask], raw[mask], rv[mask]
    if n_names:
        # Explicit subset, deterministic; always include SPY. This is a compute
        # diagnostic only, and NOT an independently PIT universe.
        syms = [int(np.flatnonzero(names == "SPY")[0])] + [i for i,x in enumerate(names) if x != "SPY"][:max(0,n_names-1)]
        raw, rv, names = raw[:,:,syms], rv[:,syms], names[syms]
    if len(dates) < 252:
        raise ValueError("insufficient intraday history")
    if np.nanmin(rv) < 0 or not np.isfinite(raw[:,:,np.where(names=="SPY")[0][0]]).mean() > .85:
        raise ValueError("invalid variance/SPY coverage")
    daily = np.where(np.isfinite(raw).all(axis=1), raw.sum(axis=1), np.nan)
    return RiskData(dates,names,raw,daily,rv,sha256(path))


def load_alpha(path: Path, dev_only=True) -> AlphaData:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"development panel absent: {path}")
    with np.load(path, allow_pickle=False) as z:
        keys = {"S","names","master_h5_ref","y5","elig"}
        if not keys <= set(z.files):
            raise ValueError(f"MASTER dev cache missing {keys - set(z.files)}")
        dates = dates_checked(z["S"])
        names = names_checked(z["names"])
        score, y, elig = (np.asarray(z[k]) for k in ("master_h5_ref","y5","elig"))
    if score.shape != (len(dates),len(names)) or y.shape != score.shape or elig.shape != score.shape:
        raise ValueError("MASTER dev panel shapes do not match")
    if not (elig.dtype.kind in "biu"):
        raise ValueError("eligibility must be boolean or integer")
    if dev_only and dates[-1] > DEV_END:
        # Unlike risk, restrict the alpha panel to the original development file.
        raise ValueError("alpha panel extends past 2019: refusing a reused selection window")
    decision_ix = np.flatnonzero((dates.astype('datetime64[D]').astype(int)+3)%7==0)
    # Explicit and portable Thursday check: 1970-01-01 was Thursday (integer day %7 ==0)
    decision_ix = np.flatnonzero(dates.astype("datetime64[D]").astype(int) % 7 == 0)
    decision_ix = decision_ix[decision_ix + 5 < len(dates)]
    return AlphaData(dates,names,np.asarray(score,float),np.asarray(y,float),elig.astype(bool),decision_ix,np.arange(len(dates)),sha256(path))


def safe_new_dir(path: Path, forbidden: tuple[Path,...]):
    """Create-only output; no write under any input or repository root."""
    p=Path(path).expanduser().resolve()
    if p.exists():
        raise FileExistsError(f"output must not exist: {p}")
    for f in forbidden:
        f=Path(f).expanduser().resolve()
        if p == f or f in p.parents or p in f.parents:
            raise ValueError(f"output is inside, or ancestor of, protected data: {f}")
    p.mkdir(parents=True,exist_ok=False)
    return p


def write_json(out: Path, name: str, value):
    if "/" in name or "\\" in name or not name.endswith(".json"):
        raise ValueError("unsafe report name")
    (out/name).write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False,default=lambda x: x.item() if isinstance(x,np.generic) else str(x))+"\n")
