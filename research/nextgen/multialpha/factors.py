"""Transparent factor risk, separate from forecast-error signal covariance.

Model is for beta-hedged residual stock returns. SPY market exposure and
market covariance are explicit. Neither GICS nor current-ticker metadata is
inferred here; all factor/loadings must be PIT upstream.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import numpy as np


@dataclass(frozen=True)
class RiskModel:
    asof_at: datetime           # factor/idio/SPY covariance vintage
    residual_loadings: np.ndarray  # N x K, e.g. value/quality/industry
    factor_cov: np.ndarray          # K x K, holding-period fractional-return covariance
    idiosyncratic_variance: np.ndarray  # N, same units
    spy_covariance: np.ndarray      # N, covariance residual stocks with SPY
    spy_variance: float             # positive holding-period variance


def covariance(model: RiskModel):
    if not isinstance(model, RiskModel) or not isinstance(model.asof_at, datetime) or model.asof_at.tzinfo is None or model.asof_at.utcoffset() is None:
        raise ValueError('risk model requires a timezone-aware asof_at')
    B=np.asarray(model.residual_loadings,dtype=float)
    F=np.asarray(model.factor_cov,dtype=float)
    d=np.asarray(model.idiosyncratic_variance,dtype=float)
    c=np.asarray(model.spy_covariance,dtype=float)
    sv=float(model.spy_variance)
    if B.ndim!=2 or B.shape[0]<1 or B.shape[1]<1 or not np.isfinite(B).all():
        raise ValueError('finite nonempty N x K factor loadings required')
    n,k=B.shape
    if (F.shape!=(k,k) or not np.isfinite(F).all() or
        not np.allclose(F,F.T,atol=1e-11,rtol=0) or np.linalg.eigvalsh(F).min() < -1e-11):
        raise ValueError('factor covariance must be symmetric PSD')
    if d.shape!=(n,) or not np.isfinite(d).all() or (d<=0).any():
        raise ValueError('positive idiosyncratic variance required for each name')
    if c.shape!=(n,) or not np.isfinite(c).all() or not np.isfinite(sv) or sv<=0:
        raise ValueError('finite SPY residual cross-covariance and positive SPY variance required')
    stock=B@F@B.T+np.diag(d)
    joint=np.block([[stock,c[:,None]],[c[None,:],np.array([[sv]])]])
    if np.linalg.eigvalsh(joint).min()<-1e-10:
        raise ValueError('combined SPY/stock covariance is not PSD')
    return {'residual_cov':stock,'spy_cov':c,'spy_var':sv,
            'factor_loadings':B,'factor_cov':F,'specific_variance':d}
