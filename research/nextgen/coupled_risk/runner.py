"""Read-only executable comparison of multivariate factor covariance families on 2018-19 development.

Only new output folder is created. Never downloads or opens any post-2019 returns.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from . import models as M
from .adapters import load_risk, load_alpha, safe_new_dir, write_json, factor_window,poe_residual,qlike
from .models import pdmat

DEV_START=np.datetime64('2018-01-01','D')
DEV_END=np.datetime64('2019-12-31','D')
MODELS=('poet','matrix_heavy','dcc','t_score','particle_sv')


def factor_inputs(d,origin,lookback,k,mincoverage=.95):
    win=factor_window(d,origin,lookback,factors=k,mincoverage=mincoverage)
    # FactorWindow contains projected returns, RV diagonals and residual stocks;
    # reconstruct full, covariance-bearing realized measure from earlier intraday bars.
    z=np.asarray(d.intraday[origin-lookback:origin,:,win.stocks],float)
    z=np.where(np.isfinite(z),z,0.)
    f=np.einsum('tjn,nk->tjk',z,win.loading,optimize=True)
    realized=M.realized_from_intraday(f)
    if np.any(~np.isfinite(realized)): raise ValueError('nonfinite realized covariance')
    return win,realized


def factor_forecast(win,rv,method,particles,seed,maxiter):
    x=win.factor
    if method=='poet':
        cov=M.pdmat(np.cov(x,rowvar=False))
        return dict(covariance=cov,parameters=dict(baseline='static factor covariance'))
    if method=='matrix_heavy':return M.heavy_matrix(x,rv,maxiter=maxiter)
    if method=='dcc':return M.dcc_factor(x,rv,maxiter=maxiter)
    if method=='t_score':return M.robust_score_covariance(x,rv,maxiter=maxiter)
    if method=='particle_sv':return M.joint_particle_sv(x,rv,particles=particles,seed=seed)
    raise ValueError('unsupported model')


def whole_cov(win,model_cov):
    # Five-session realized variance uses next-day forecast held fixed, with
    # residual covariance shrunk from preceding data only.
    d=poe_residual(win.resid)
    return pdmat(win.loading@model_cov@win.loading.T+d)


def _qret(d,indices,t,h=5):
    arr=d.daily[t+1:t+1+h][:,indices]
    if arr.shape[0]!=h:return None
    return arr


def _portfolio_specs(d,win,t,alpha=None):
    """Return matched weight vectors in win stock coordinates, strictly at origin t."""
    names=d.names[win.stocks]
    pi=int(np.where(names=='SPY')[0][0]);n=len(names)
    market=np.zeros(n);market[pi]=1.
    equal=np.ones(n);equal[pi]=0;equal/=max(np.abs(equal).sum(),1)
    out={'market_spy':market,'equal_stock':equal}
    if alpha is None:return out,{}
    # Decision origin t forecasts the next session using returns through t-1.
    # MASTER signals must obey that same as-of cutoff, not use day t.
    if t<1:return out,{'master':'NO_PRIOR_SESSION'}
    ixs=np.flatnonzero(alpha.dates==d.dates[t-1])
    if len(ixs)!=1:return out,{'master':'PRIOR_DATE_UNALIGNED'}
    ix=int(ixs[0]);inames={name:i for i,name in enumerate(alpha.names)}
    # Require PIT master score and membership, and >=90% coverage against all
    # original eligible score names, otherwise no misleading partial-book result.
    valid=np.isfinite(alpha.score[ix]) & alpha.eligible[ix]
    origins=np.flatnonzero(valid)
    common=[(j,inames.get(str(name))) for j,name in enumerate(names) if str(name) in inames and valid[inames[str(name)]]]
    coverage=len(common)/max(len(origins),1)
    if coverage<.90:return out,{'master':'LOW_CONSTITUENT_COVERAGE','coverage':coverage}
    if len(common)<30:return out,{'master':'INSUFFICIENT_RANKED_STOCKS','coverage':coverage}
    eligible=np.array([j for j,i in common if str(names[j])!='SPY'],int)
    scores=np.array([alpha.score[ix,inames[str(names[j])]] for j in eligible])
    rank=np.argsort(np.argsort(scores,kind='stable'),kind='stable')
    p=(rank+1)/len(scores)
    top=eligible[p>.9];bottom=eligible[p<=.1]
    if not len(top) or not len(bottom):return out,{'master':'EMPTY_DECILE'}
    w=np.zeros(n);w[top]=.3/len(top);w[bottom]=-.3/len(bottom)
    # The forecast at t is formed before the t close: use exactly the
    # 200 completed SPY sessions t-200..t-1, never the t observation.
    spying=int(np.where(d.names=='SPY')[0][0])
    if t<200:return out,{'master':'NO_TREND_WARMUP'}
    spy_history=d.daily[t-200:t,spying]
    if not np.isfinite(spy_history).all():
        return out,{'master':'INCOMPLETE_TREND_HISTORY'}
    logprice=np.cumsum(spy_history)
    spy_core=1.3 if logprice[-1]>np.log(np.exp(logprice-np.max(logprice)).mean())+np.max(logprice) else .7
    # Beta values from source dev.npz (point-in-time provenance NOT certified).
    # This trial intentionally does not use a post-2019 issuer CIK.
    return out | {'master_unhedged':w+market*spy_core},dict(master='PROXY_SPY_CORE_NO_BOOK_BETA_HEDGE',coverage=coverage,spy_core=spy_core)


def evaluate_one(d,t,win,model_cov,alpha=None,horizon=5):
    whole=whole_cov(win,model_cov)
    weights,note=_portfolio_specs(d,win,t,alpha)
    future=_qret(d,win.stocks,t,horizon)
    out=[]
    if future is None:return out,note
    for name,w in weights.items():
        eligible=np.flatnonzero(np.abs(w)>0)
        if not len(eligible) or not np.isfinite(future[:,eligible]).all():continue
        observed=float((future[:,eligible]@w[eligible])@(future[:,eligible]@w[eligible]))
        predicted=float(horizon*w@whole@w)
        if observed<=1e-12:continue
        out.append(dict(portfolio=name,actual=observed,forecast=predicted,
                        qlike=qlike(observed,predicted),abs_log_ratio=abs(np.log(observed/predicted))))
    return out,note


def paired_hac(x,lags=5):
    d=np.asarray(x,float)
    if len(d)<12:return dict(n=len(d),mean_gain=float(d.mean()) if len(d) else None,t=None,warning='TOO_FEW_ORIGINS')
    z=d-d.mean();n=len(d);l=min(lags,n-1)
    v=float(z@z/n)
    for j in range(1,l+1):v+=2*(1-j/(l+1))*float(z[j:]@z[:-j]/n)
    se=float(np.sqrt(max(v,0)/n))
    return dict(n=n,mean_gain=float(d.mean()),hac_se=se,t=float(d.mean()/se) if se>0 else None)


def compare(rows,baseline='poet'):
    d={(r['model'],r['date'],r['portfolio']):r for r in rows}
    results={}
    refs=[(a,b) for (model,a,b) in d if model==baseline]
    for model in sorted({r['model'] for r in rows}-{baseline}):
        shared=[(a,b) for a,b in refs if (model,a,b) in d]
        if len(shared)!=len(refs):raise ValueError('model evaluation dates/portfolios differ; no cherry picking')
        keys=sorted(set(b for a,b in shared));o={}
        for port in keys:
            zz=sorted(a for a,b in shared if b==port)
            gain=[d[(baseline,a,port)]['qlike']-d[(model,a,port)]['qlike'] for a in zz]
            o[port]=paired_hac(gain);o[port]['by_year']={str(y):float(np.mean([v for date,v in zip(zz,gain) if date.startswith(str(y))])) for y in sorted({int(a[:4]) for a in zz})}
        results[model]=o
    return dict(status='DEVELOPMENT_DIAGNOSTIC_NOT_TRADING',reference=baseline,positive_gain='lower candidate QLIKE',models=results)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('check','run'))
    p.add_argument('--hf-cache',type=Path,required=True)
    p.add_argument('--alpha-cache',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--models',nargs='+',choices=MODELS,default=list(MODELS))
    p.add_argument('--lookback',type=int,default=252)
    p.add_argument('--factors',type=int,default=3)
    p.add_argument('--step',type=int,default=21)
    p.add_argument('--particles',type=int,default=400)
    p.add_argument('--maxiter',type=int,default=150)
    p.add_argument('--max-origins',type=int)
    p.add_argument('--max-names',type=int)
    args=p.parse_args(argv)
    d=load_risk(args.hf_cache,dev_only=True,n_names=args.max_names)
    a=load_alpha(args.alpha_cache,dev_only=True) if args.alpha_cache else None
    checks=dict(risk_sha256=d.sha256,alpha_sha256=a.sha256 if a else None,
                risk_period=[str(d.dates[0]),str(d.dates[-1])],
                alpha_period=[str(a.dates[0]),str(a.dates[-1])] if a else None,
                current_member_bias=d.survivorship, n_names=len(d.names),
                models=args.models,investment_evidence='NOT_TESTED')
    if args.mode=='check':print(json.dumps(checks,indent=2));return 0
    if args.out is None:raise ValueError('--out required for run')
    if not (100<=args.lookback<=800 and args.factors in range(1,9)
            and args.step in range(1,65) and 64<=args.particles<=20000):
        raise ValueError('unsupported hyperparameters')
    origins=np.flatnonzero((d.dates>=DEV_START)&(d.dates<=DEV_END))
    origins=[t for t in origins if t>=args.lookback and t+5<len(d.dates) and
             (d.dates[t].astype('datetime64[D]').astype(int)%7)==0]
    origins=origins[::args.step//7 if args.step>=7 else 1]
    if args.max_origins:origins=origins[:args.max_origins]
    if not origins:raise ValueError('no development origins')
    rows=[];diagnostics=[]
    for t in origins:
        win,rv=factor_inputs(d,t,args.lookback,args.factors)
        for model in args.models:
            res=factor_forecast(win,rv,model,args.particles,seed=20261122+t,maxiter=args.maxiter)
            scores,note=evaluate_one(d,t,win,res['covariance'],a)
            for z in scores:rows.append(dict(date=str(d.dates[t]),model=model,**z))
            diagnostics.append(dict(date=str(d.dates[t]),model=model,
                                    dropped=win.n_dropped,notes=note,
                                    parameters=res['parameters']))
    report=dict(**checks,real_origin_count=len(origins),rows=rows,diagnostics=diagnostics,
                statistical_comparison=compare(rows) if 'poet' in args.models and len(args.models)>1 else None,
                warning='PIT membership unverified; original MASTER dev labels only. This is NO new OOS read.')
    out=safe_new_dir(args.out,(Path.cwd(),args.hf_cache,args.alpha_cache) if args.alpha_cache else (Path.cwd(),args.hf_cache))
    write_json(out,'RESULT.json',report)
    print(json.dumps(dict(out=str(out),origins=len(origins),n_scored=len(rows),
                          model_comparisons=report['statistical_comparison'],
                          investment_evidence='NOT_TESTED'),indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
