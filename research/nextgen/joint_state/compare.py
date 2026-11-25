"""Paired development-only comparison of completed risk, regime and MASTER experiments.

Does NOT auto-promote a model or calculate historical fund Sharpe. All paired
origins must match exactly; this prevents changing test dates between models.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from .contracts import sha256


def paired_hac(diff,lags=4):
    x=np.asarray(diff,float)
    if x.ndim!=1 or len(x)==0 or not np.isfinite(x).all():
        raise ValueError('paired HAC needs finite paired observations')
    n=len(x);mu=float(x.mean())
    if n<max(8,lags+3):
        return dict(n=n,mean=mu,hac_se=None,t=None,lags=lags,
                    warning='INSUFFICIENT_TIME_ORIGINS_FOR_INFERENCE')
    z=x-mu;v=float(z@z/n)
    for lag in range(1,min(lags+1,n)):
        v+=2*(1-lag/(lags+1))*float(z[lag:]@z[:-lag]/n)
    se=float(np.sqrt(max(v,0)/n))
    return dict(n=n,mean=mu,hac_se=se,t=mu/se if se>1e-14 else None,
                lags=lags,warning=('LOW_EFFECTIVE_TIME_SAMPLES' if n<30 else None))


def _load(path):
    p=Path(path)
    data=json.loads(p.read_text())
    if 'rows' not in data or not isinstance(data['rows'],list):
        raise ValueError(f'{p}: missing model rows')
    return data['rows']


def _key_map(rows,keys):
    m={}
    for r in rows:
        k=tuple(r[key] for key in keys)
        if k in m:raise ValueError(f'duplicate evaluation origin {k}')
        m[k]=r
    if not m:raise ValueError('no results to compare')
    return m


def _equal_keys(base,other):
    if set(base)!=set(other):
        a=set(base);b=set(other)
        raise ValueError(f'evaluation origin mismatch, benchmark only={len(a-b)}, challenger only={len(b-a)}')


def compare_risk(path):
    folder=Path(path)
    baseline=_key_map(_load(folder/'risk_poet.json'),('date','portfolio'))
    results={}
    for f in sorted(folder.glob('risk_*.json')):
        method=f.stem[len('risk_'):]
        if method=='poet':continue
        cand=_key_map(_load(f),('date','portfolio'))
        _equal_keys(baseline,cand)
        group={}
        for port in ('market','equal_weight'):
            keys=sorted(k for k in baseline if k[1]==port)
            d=[baseline[k]['qlike']-cand[k]['qlike'] for k in keys]
            group[port]=paired_hac(d)
            group[port]['by_year']=_years(keys,d)
        results[method]=group
    return dict(reference='poet',loss='QLIKE lower is better',
                positive_gain='baseline loss minus candidate loss',
                models=results,source_sha256={f.name:sha256(f) for f in sorted(folder.glob('risk_*.json'))})


def _years(keys,d):
    y={}
    for k,delta in zip(keys,d):
        name=str(k[0])[:4]
        y.setdefault(name,[]).append(float(delta))
    return {k:dict(n=len(v),mean_gain=float(np.mean(v))) for k,v in y.items()}


def _nll(r):
    s=max(float(r['forecast_variance'])+float(r['measurement_variance']),1e-10)
    e=float(r['actual'])-float(r['forecast'])
    return .5*(np.log(2*np.pi*s)+e*e/s)


def compare_alpha(path):
    folder=Path(path)
    baseline=_key_map(_load(folder/'alpha_constant.json'),('date',))
    results={}
    for f in sorted(folder.glob('alpha_*.json')):
        method=f.stem[len('alpha_'):]
        if method=='constant':continue
        cand=_key_map(_load(f),('date',))
        _equal_keys(baseline,cand)
        keys=sorted(baseline)
        gain_mse=[];gain_nll=[]
        for k in keys:
            b,c=baseline[k],cand[k]
            if abs(float(b['actual'])-float(c['actual']))>1e-12:
                raise ValueError('alpha actual label differs on same decision date')
            gain_mse.append((b['actual']-b['forecast'])**2-(c['actual']-c['forecast'])**2)
            gain_nll.append(_nll(b)-_nll(c))
        results[method]=dict(mse=paired_hac(gain_mse),nll=paired_hac(gain_nll),
                             by_year_mse=_years(keys,gain_mse),by_year_nll=_years(keys,gain_nll))
    return dict(reference='constant',positive_gain='lower candidate loss',models=results,
                source_sha256={f.name:sha256(f) for f in sorted(folder.glob('alpha_*.json'))})


def compare_regimes(path):
    folder=Path(path)
    a=_key_map(_load(folder/'regime_hmm.json'),('origin',))
    b=_key_map(_load(folder/'regime_hsmm.json'),('origin',))
    _equal_keys(a,b)
    keys=sorted(a)
    deltas=[b[k]['log_density']-a[k]['log_density'] for k in keys]
    return dict(reference='hmm',challenger='hsmm',positive_gain='higher out-of-time log predictive density',
                gain=paired_hac(deltas),
                note='BOCPD targets univariate log-SPY-RV and is NOT directly comparable with the multivariate HMM/HSMM density',
                source_sha256={f.name:sha256(f) for f in sorted(folder.glob('regime_*.json'))})


def compare_all(risk_dir=None,alpha_dir=None,regime_dir=None):
    if not any([risk_dir,alpha_dir,regime_dir]):
        raise ValueError('at least one completed model directory required')
    o=dict(status='REUSED_DEV_DIAGNOSTICS_ONLY',model_selection='NOT_AUTOMATIC',
           economic_performance='NOT_TESTED',old_trial_inventory_minimum=162,
           warning='No 2020-2026 reuse for tuning, prospective shadow required before trading')
    if risk_dir:o['risk']=compare_risk(risk_dir)
    if alpha_dir:o['alpha']=compare_alpha(alpha_dir)
    if regime_dir:o['regimes']=compare_regimes(regime_dir)
    return o
