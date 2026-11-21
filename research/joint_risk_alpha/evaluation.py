"""Paired, serial-correlation-aware model forecast comparison.

This is statistical inference on development forecast losses, NOT a Sharpe
estimator or a claim of new independent investment holdout evidence.
"""
import numpy as np
from scipy.stats import norm


def nw_mean(x,lags=4):
    """Bartlett Newey-West standard error of sample mean, with no NaN dropping.

    Declines short/incomplete sequences rather than silently treating missing
    model forecasts as favorable or comparing different dates.
    """
    y=np.asarray(x,float)
    if y.ndim!=1 or len(y)<=lags+2 or not np.isfinite(y).all():
        raise ValueError('HAC needs aligned, complete time-series losses')
    T=len(y);u=y-y.mean();omega=(u@u)/T
    for lag in range(1,lags+1):
        gamma=(u[lag:]@u[:-lag])/T
        omega+=2*(1-lag/(lags+1))*gamma
    se=float(np.sqrt(max(omega,0.)/T))
    t=float(y.mean()/se) if se>0 else None
    return {'n':T,'mean':float(y.mean()),'se':se,'t':t,
            'p_one_sided_improvement':float(norm.sf(t)) if t is not None else None,
            'lags':lags}


def paired_losses(dates,benchmark,candidate,lags=4):
    """Positive return = candidate lower forecast loss than benchmark."""
    d=np.asarray(dates)
    a=np.asarray(benchmark,float);b=np.asarray(candidate,float)
    if a.shape!=b.shape or a.ndim!=1 or len(d)!=len(a):
        raise ValueError('paired forecasts must use identical origins')
    r=nw_mean(a-b,lags=lags)
    r['mean_benchmark']=float(a.mean());r['mean_candidate']=float(b.mean())
    r['mean_gain_fraction']=float((a.mean()-b.mean())/max(abs(a.mean()),1e-12))
    r['by_year']={str(year):float((a-b)[np.array([str(z)[:4]==str(year) for z in d])].mean())
                  for year in sorted({str(z)[:4] for z in d})}
    return r
