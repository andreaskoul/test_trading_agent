"""Independent multialpha admission and horizon-matched signal combination.

Approval flags are EXTERNAL governance attestations, not statistical tests.
Only calibrated beta-hedged excess fractional RETURNS can enter the book.
No ranks, fitted beta, or synthetic validation automatically imply approval.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
import numpy as np

UNIT = 'fractional_holding_period_residual_excess_return'


def _utc(value, name):
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f'{name}: timezone-aware datetime required')
    return value.astimezone(timezone.utc)


def _float(x,name):
    if isinstance(x,bool) or not isinstance(x,(int,float,np.integer,np.floating)) or not np.isfinite(x):
        raise ValueError(f'{name}: finite nonboolean scalar required')
    return float(x)


@dataclass(frozen=True)
class Signal:
    source_id: str
    security_ids: tuple[str,...]
    expected_residual_excess: tuple[float,...]
    published_at: datetime
    trained_target_end_at: datetime
    horizon_end_at: datetime
    status: str = 'shadow'    # approved / shadow / rejected
    approved_evidence: str = ''
    configured_weight: float = 0.0
    role: str = 'full_forecast'  # full_forecast | incremental_component
    units: str = UNIT


def combine(signals: Sequence[Signal], *, security_ids: Sequence[str],
            decision_at: datetime, holding_end_at: datetime):
    """Combine explicitly approved signals on the SAME security+horizon+units.

    Weighted *average* (not sum) is duplicate-invariant for identical forecasts
    and nonnegative configured weights; no ex-post weight optimization.
    Unapproved sources are omitted from the trading alpha but audited.
    """
    dt=_utc(decision_at,'decision_at')
    end=_utc(holding_end_at,'holding_end_at')
    if end<=dt:
        raise ValueError('holding_end_at must follow decision_at')
    ids=tuple(security_ids)
    if not ids or len(set(ids))!=len(ids) or any(not isinstance(s,str) or not s.strip() for s in ids):
        raise ValueError('unique stable historical security IDs required')
    if not signals:
        raise ValueError('register explicit signals, including shadow if none approved')
    sources=set(); admitted=[]; excluded=[]
    for sig in signals:
        if not isinstance(sig,Signal) or not isinstance(sig.source_id,str) or not sig.source_id.strip():
            raise ValueError('Signal with nonempty source_id required')
        if sig.source_id in sources:
            raise ValueError('duplicate signal source_id')
        sources.add(sig.source_id)
        if sig.status not in ('approved','shadow','rejected'):
            raise ValueError('invalid governance status')
        if sig.role not in ('full_forecast','incremental_component'):
            raise ValueError('unknown economic alpha decomposition role')
        if sig.units!=UNIT:
            raise ValueError('ordinal rankings or inconsistent return horizons cannot enter mu')
        if tuple(sig.security_ids)!=ids:
            raise ValueError('PIT security IDs/order do not match')
        if (_utc(sig.horizon_end_at,'horizon_end_at') != end or
            not _utc(sig.trained_target_end_at,'trained_target_end_at') <=
            _utc(sig.published_at,'published_at') < dt):
            raise ValueError('signal availability, model training or holding horizon mismatch')
        values=np.asarray(sig.expected_residual_excess,dtype=float)
        if values.shape!=(len(ids),) or not np.isfinite(values).all():
            raise ValueError('finite, aligned expected residual returns required')
        w=_float(sig.configured_weight,'configured_weight')
        if w<0:
            raise ValueError('negative signal weight forbidden')
        if sig.status=='approved':
            if not isinstance(sig.approved_evidence,str) or not sig.approved_evidence.strip() or w<=0:
                raise ValueError('approved source needs explicit evidence reference and positive governance weight')
            if sig.role=='incremental_component' and w>1:
                raise ValueError('incremental alpha scaling above 1 requires new governance design')
            admitted.append((sig,values,w))
        else:
            if w!=0:
                raise ValueError('shadow/rejected signals must have trading weight zero')
            excluded.append(sig.source_id)
    if not admitted:
        return {'mu':np.zeros(len(ids)),'approved':(), 'shadow':tuple(excluded),
                'weights':{},'pairwise_signal_corr':None, 'n':len(ids)}
    full=[(sig,v,w) for sig,v,w in admitted if sig.role=='full_forecast']
    component=[(sig,v,w) for sig,v,w in admitted if sig.role=='incremental_component']
    full_norm=sum(w for _,_,w in full)
    avg=(sum((w*v for _,v,w in full),start=np.zeros(len(ids)))/full_norm
         if full else np.zeros(len(ids)))
    source_weights={sig.source_id:float(w/full_norm) for sig,_,w in full}
    for sig,v,w in component:
        for prior_sig,prior,prior_weight in full+component:
            if prior_sig.source_id==sig.source_id:
                continue
            if np.allclose(v,prior,atol=1e-12,rtol=0):
                raise ValueError('incremental alpha duplicates an approved forecast; double-count risk')
            vc=v-v.mean();pc=prior-prior.mean()
            vn=float(np.linalg.norm(vc));pn=float(np.linalg.norm(pc))
            if vn>1e-12 and pn>1e-12 and abs(float(vc@pc/(vn*pn)))>0.9999:
                raise ValueError('incremental alpha nearly collinear with approved forecast; double-count risk')
        avg=avg+w*v  # incremental alpha components are additive, never normalized
        source_weights[sig.source_id]=float(w)
    corr=None
    if len(admitted)>=2:
        mat=np.stack([v for _,v,_ in admitted])
        # If a signal is constant across names, cross-sectional correlation is
        # undefined, not evidence of independent alpha.
        if np.all(np.std(mat,axis=1)>1e-14):
            corr=np.corrcoef(mat).tolist()
    return {'mu':avg, 'approved':tuple(sig.source_id for sig,_,_ in admitted),
            'shadow':tuple(excluded),'weights':source_weights,
            'pairwise_signal_corr':corr,'n':len(ids)}
