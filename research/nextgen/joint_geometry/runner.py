"""Read-only runner: geometry-aware risk, filtered regimes, MASTER efficacy, MPC.

Every command uses local caches and *development* observations only (<=2019).
It neither fetches market data nor creates/modifies trading, forward or Git files.
Outputs are written once to a new directory OUTSIDE the repository and caches.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np
from .covariance import (build_tape,weekly_origins,rolling_geometric_eval,
                         train_spdnet,curve_metrics,rolling_grassmann,baseline_factor_covariance)
from .states import states_trial
from .alpha import align_master_to_geometry,alpha_geometry_trial,ManifoldGP
from .control import spd_ambiguity,posterior_paths,solve_geometric_mpc
from research.nextgen.joint_state.contracts import (load_alpha,load_risk,sha256,
                                                     safe_new_dir,write_json)
from research.nextgen.joint_state.runner import load_dev_market
from research.nextgen.joint_state.control import Policy

BRANCH='research/manifold-spd-grassmann-diffusion-20261121'


def hac_delta(values,lags=5):
    x=np.asarray(values,float)
    if x.ndim!=1 or len(x)<lags+8 or not np.isfinite(x).all():
        raise ValueError('not enough paired chronological observations')
    mu=x.mean();e=x-mu;n=len(x)
    longrun=float(e@e/n)
    for l in range(1,lags+1):
        longrun+=2*(1-l/(lags+1))*float(e[l:]@e[:-l])/n
    se=float(np.sqrt(max(0,longrun)/n))
    return dict(n=n,mean=float(mu),se=se,t=None if se==0 else float(mu/se),lags=lags)


def _mean_by_method(rows,field,base='euclidean',key='model',group='date',need=8):
    matched=defaultdict(dict)
    for z in rows:
        identity=z[group]
        if z[key] in matched[identity]:raise ValueError('duplicated scoring date/method')
        matched[identity][z[key]]=z
    out={}
    types=sorted({z[key] for z in rows})
    for kind in types:
        sample=[z for z in rows if z[key]==kind]
        by_year={}
        for year in sorted({z[group][:4] for z in sample}):
            by_year[year]=float(np.mean([z[field] for z in sample if z[group].startswith(year)]))
        result=dict(n=len(sample),mean=float(np.mean([z[field] for z in sample])),by_year=by_year)
        if kind!=base:
            common=sorted(k for k in matched if base in matched[k] and kind in matched[k])
            if len(common)>=need:
                dif=[matched[k][base][field]-matched[k][kind][field] for k in common]
                result['vs_'+base+'_paired_gain']=hac_delta(dif,lags=min(8,max(3,len(dif)//12)))
        out[kind]=result
    return out


def evaluate_covariance(tape,models,first,last,history,epochs,device,seeds,max_origins=None):
    numeric={'sample_cov','ewma_cov','heavy','realized_garch'}
    standard=[x for x in models if x not in numeric and x!='spdnet']
    rows=rolling_geometric_eval(tape,methods=standard,first=first,last=last,
                                history_weeks=history,max_origins=max_origins) if standard else []
    if set(models)&numeric:
        times=weekly_origins(tape,first=first,last=last,minimum=max(5*(history+1),253))
        if max_origins is not None:times=times[:max_origins]
        for t in times:
            target=tape.target(int(t),5)
            for method in models:
                if method not in numeric:continue
                forecast=baseline_factor_covariance(tape,int(t),method=method)
                rows.append(dict(date=str(tape.dates[t]),origin=int(t),model=method,
                                 train_end=str(tape.fitted_through),**curve_metrics(target,forecast)))
    extra={}
    if 'spdnet' in models:
        model=train_spdnet(tape,train_cutoff='2017-12-31',dim=min(3,tape.loading.shape[1]),
                           epochs=epochs,seeds=seeds,device=device)
        times=weekly_origins(tape,first=first,last=last,minimum=5*(history+1))
        if max_origins is not None:times=times[:max_origins]
        for t in times:
            seq=np.stack([tape.at(int(t)-1-5*i) for i in reversed(range(4))])
            pred=model['predict'](seq)
            metrics=curve_metrics(tape.target(int(t),5),pred)
            rows.append(dict(date=str(tape.dates[t]),origin=int(t),model='spdnet',
                             train_end=model['train_end'],**metrics))
        extra['spdnet_training']=dict(n=model['n_train'],validation_log_cov_mse=model['val_mse'],
                                      seeds=list(model['seeds']),train_end=model['train_end'])
    if not rows:raise ValueError('no scored risk model')
    return dict(rows=rows,summary=_mean_by_method(rows,'stein',base='ewma_cov'),
                proper_variance_qlike=_mean_by_method(rows,'equal_qlike',base='ewma_cov'),
                trained=extra,scope='FIXED_BASIS_DEV_COVARIANCE_ONLY_NOT_FUND_SHARPE')


def evaluate_states(tape,methods,dim,k,first,last,max_origins=None):
    rows=[]
    for method in methods:
        rows.extend(states_trial(tape,method=method,dim=dim,k=k,first=first,
                                 last=last,max_origins=max_origins))
    # Proper risk-forecast QLIKE on identical date, NOT raw latent-state likelihood
    # across different coordinate systems.
    stats={}
    for method in methods:
        subset=[z for z in rows if z['model']==method]
        if subset:
            gain=[z['baseline_qlike']-z['qlike'] for z in subset]
            stats[method]=dict(n=len(subset),mean_qlike=float(np.mean([z['qlike'] for z in subset])),
                               fixed_train_baseline_qlike=float(np.mean([z['baseline_qlike'] for z in subset])),
                               versus_fixed_train=(hac_delta(gain,lags=min(8,max(3,len(gain)//15))) if len(gain)>=15 else None),
                               inference_warning=None if len(gain)>=15 else "TOO_FEW_ORIGINS_FOR_HAC_SMOKE_ONLY")
    return dict(rows=rows,summary=stats,scope='FILTERED_STATE_VARIANCE_TARGET_DIAGNOSTIC')


def evaluate_alpha(hf,dev,tape,methods,start,end,refit,epochs,seeds,device,max_origins=None):
    market=load_dev_market(dev)
    panel=align_master_to_geometry(load_alpha(dev),market,tape)
    rows=alpha_geometry_trial(panel,methods=methods,start=start,end=end,refit=refit,
                              moe_epochs=epochs,moe_seeds=seeds,device=device,max_origins=max_origins)
    results=_mean_by_method(rows,'squared_error',base='constant',key='method')
    return dict(rows=rows,summary=results,
                training_baseline='rolling precision weighted constant MASTER weekly rank slope',
                alpha_label='five-session ex-post hedged residual; model predicts weekly slope, not whole fund net return',
                scope='DEVELOPMENT_2018_2019_NOT_FUND_RETURN')


def make_control(h,d,tape,dev,origin='2019-11-01',metric='affine',
                 scenarios=500,horizon=4,finance='segregated',max_names=None,seed=20261121):
    if horizon<1 or horizon>15 or scenarios<50:raise ValueError('invalid MPC size')
    at=np.datetime64(origin,'D')
    if at>np.datetime64('2019-12-01') or at<tape.fitted_through:raise ValueError('origin outside permitted development period')
    shared=np.intersect1d(h.dates,d.dates)
    tdates=shared[(shared<=at)&(shared.astype('datetime64[D]').astype(int)%7==0)]
    if len(tdates)==0:raise ValueError('no matching development decision')
    decision=tdates[-1];a=int(np.flatnonzero(d.dates==decision)[0]);t=int(np.flatnonzero(h.dates==decision)[0])
    if t<252 or t+5>=len(h.dates):raise ValueError('insufficient intraday development history')
    market=load_dev_market(dev)
    panel=align_master_to_geometry(d,market,tape)
    matured=np.flatnonzero(panel.available<decision)
    if len(matured)<45:raise ValueError('insufficient matured alpha slope observations')
    est=ManifoldGP('logspd').fit(panel.covariances[matured],panel.features[matured],
                                panel.slopes[matured],panel.measurement_variance[matured])
    cur=np.flatnonzero(panel.dates==decision)
    if not len(cur):raise ValueError('no matched point-in-time current risk state for MASTER')
    strength,unc=est.predict(panel.covariances[cur[:1]],panel.features[cur[:1]])
    amap={s:i for i,s in enumerate(d.names)};hm={s:i for i,s in enumerate(tape.names)}
    stocks=[s for s in tape.names if s!='SPY' and s in amap and d.eligible[a,amap[s]]
            and np.isfinite(d.score[a,amap[s]]) and np.isfinite(d.residual[a,amap[s]])]
    if max_names is not None:stocks=stocks[:max_names]
    if len(stocks)<30:raise ValueError('not enough member coverage for research portfolio')
    score=np.array([d.score[a,amap[s]] for s in stocks])
    from scipy.stats import rankdata
    ranks=rankdata(score)/(len(score)+1)-.5
    idx=np.argsort(score);k=max(1,int(len(stocks)//10))
    baseline=np.zeros(len(stocks));baseline[idx[:k]]=-.3/k;baseline[idx[-k:]]=.3/k
    with np.load(dev,allow_pickle=False) as cache:
        if 'beta' not in cache.files:raise ValueError('development cache lacks per-issuer PIT beta')
        beta=np.asarray(cache['beta'],float)
    if beta.shape!=(len(d.dates),len(d.names)):
        raise ValueError('beta panel not aligned')
    b=np.array([beta[a,amap[s]] for s in stocks])
    if not np.isfinite(b).all():raise ValueError('missing causal stock beta on selected names')
    ordered=stocks+['SPY'];sel=np.array([hm[s] for s in ordered])
    B=tape.loading[sel]
    x=h.daily[max(0,t-252):t, [int(np.flatnonzero(h.names==s)[0]) for s in ordered]]
    f=tape.factor[max(0,t-252):t]
    if x.shape!=(len(f),len(ordered)):raise ValueError('asset return mismatch')
    residual=np.nanvar(x-f@B.T,axis=0,ddof=1)
    if not np.isfinite(residual).all():raise ValueError('residual risk incomplete')
    risk_history=np.stack([tape.at(t-1-5*i) for i in reversed(range(15))])
    alternatives=spd_ambiguity(risk_history,metric=metric)*5
    # 5-session conditional mean MASTER score alpha; the SPY model drift
    # deliberately fixed to zero, not estimated from future returns.
    mu=np.r_[strength[0]*ranks,0.]
    paths=posterior_paths(mu,B,residual*5,alternatives,
                          scenarios=scenarios,horizon=horizon,seed=seed)
    core=1.3
    hedge=-b@baseline
    cap=max(1.9,abs(core+hedge)+np.abs(baseline).sum())
    policy=Policy(np.asarray(stocks),b,core=core,cap=cap,financing=finance,
                  max_stock_abs=max(.035,.3/k),margin_rate_annual=.06,
                  cvar_weight=.12,risk_weight=.05)
    value=solve_geometric_mpc(paths,policy,baseline,B,residual*5,alternatives)
    return dict(status='RESEARCH_MODEL_POLICY_DIAGNOSTIC_NOT_BACKTEST',date=str(decision),
                n_eligible_stocks=len(stocks),baseline_gross=float(abs(core+hedge)+np.abs(baseline).sum()),
                limit=cap,alpha_slope=float(strength[0]),alpha_variance=float(unc[0]),
                scenario_count=scenarios,scenario_horizon=horizon,
                manifold_metric=metric,financing_convention=finance,
                solution={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in value.items()},
                warning='intraday current-constituent survivorship and simulated financing; NOT investment evidence')


def parse_args(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['check','covariance','states','alpha','control'])
    p.add_argument('--hf-cache',type=Path)
    p.add_argument('--alpha-cache',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--methods',nargs='+')
    p.add_argument('--basis-end',default='2016-07-01')
    p.add_argument('--first',default=None)
    p.add_argument('--last',default='2019-11-01')
    p.add_argument('--rank',type=int,default=4)
    p.add_argument('--limit-names',type=int)
    p.add_argument('--history-weeks',type=int,default=12)
    p.add_argument('--max-origins',type=int)
    p.add_argument('--train-cutoff',default='2017-12-31')
    p.add_argument('--states',type=int,default=3)
    p.add_argument('--dimension',type=int,default=3)
    p.add_argument('--epochs',type=int,default=350)
    p.add_argument('--seeds',type=int,nargs='+',default=[11,17,23])
    p.add_argument('--device',default='cpu')
    p.add_argument('--refit',type=int,default=13)
    p.add_argument('--origin',default='2019-11-01')
    p.add_argument('--financing',choices=['net_debit','segregated'],default='segregated')
    p.add_argument('--metric',choices=['affine','logeuclidean','bures'],default='affine')
    p.add_argument('--scenarios',type=int,default=500)
    p.add_argument('--horizon',type=int,default=4)
    p.add_argument('--seed',type=int,default=20261121)
    return p.parse_args(argv)


def main(argv=None):
    a=parse_args(argv)
    if a.hf_cache is None:raise ValueError('local --hf-cache required')
    if a.command in ('alpha','control','check') and a.alpha_cache is None:
        raise ValueError('local --alpha-cache required')
    h=load_risk(a.hf_cache,dev_only=True,n_names=a.limit_names)
    d=load_alpha(a.alpha_cache) if a.alpha_cache else None
    if a.command=='check':
        out=dict(status='LOCAL_CACHE_CONTRACT_OK_WITH_PIT_LIMITATIONS',
                 intraday=dict(sha256=h.sha256,sessions=len(h.dates),names=len(h.names),
                               first=str(h.dates[0]),last=str(h.dates[-1])),
                 alpha=None if d is None else dict(sha256=d.sha256,sessions=len(d.dates),names=len(d.names),
                                                  thursday_origins=len(d.decision_ix)),
                 warning='intraday source has current S&P constituents; historical PIT eligibility NOT certified')
        print(json.dumps(out,indent=2));return 0
    if a.out is None:raise ValueError('new --out directory required')
    protected=[a.hf_cache,a.hf_cache.parent,Path(__file__).resolve().parents[3]]
    if a.alpha_cache:protected.extend([a.alpha_cache,a.alpha_cache.parent])
    # Build and inspect complete input before allocating output folder.
    tape=build_tape(h,basis_end=a.basis_end,rank=a.rank)
    methods=a.methods or {
        'covariance':['sample_cov','ewma_cov','heavy','realized_garch','euclidean','logeuclidean','affine','bures','spdnet'],
        'states':['airm','diffusion_hmm','diffusion_grassmann'],
        'alpha':['constant','logspd_gp','diffusion_gp','logspd_macro_gp','fisher_gp','manifold_moe'],
        'control':[]}[a.command]
    allowed={
        'covariance':{'sample_cov','ewma_cov','heavy','realized_garch','euclidean','logeuclidean','affine','bures','spdnet'},
        'states':{'airm','diffusion_hmm','diffusion_grassmann'},
        'alpha':{'constant','logspd_gp','diffusion_gp','logspd_macro_gp','fisher_gp','manifold_moe'},
        'control':set()}
    if not set(methods)<=allowed[a.command]:raise ValueError('invalid method name')
    if a.command=='covariance':
        result=evaluate_covariance(tape,methods,a.first or '2018-01-01',a.last,a.history_weeks,
                                   a.epochs,a.device,tuple(a.seeds),a.max_origins)
    elif a.command=='states':
        result=evaluate_states(tape,methods,a.dimension,a.states,a.first or '2018-01-01',a.last,a.max_origins)
    elif a.command=='alpha':
        result=evaluate_alpha(h,a.alpha_cache,tape,methods,a.first or '2018-01-01',a.last,
                              a.refit,a.epochs,tuple(a.seeds),a.device,a.max_origins)
    elif a.command=='control':
        result=make_control(h,d,tape,a.alpha_cache,a.origin,a.metric,
                            a.scenarios,a.horizon,a.financing,a.limit_names,a.seed)
    out=safe_new_dir(a.out,tuple(protected))
    manifest=dict(branch=BRANCH,command=a.command,status='RESEARCH_ONLY_NOT_INVESTMENT_EVIDENCE',
                  date_cutoff='2019-12-31',models=methods,risk_sha256=h.sha256,
                  alpha_sha256=None if d is None else d.sha256,
                  model_basis_trained_before=str(tape.fitted_through),
                  cross_section_survivorship='UNVERIFIED_CURRENT_CONSTITUENT_HF_CACHE',
                  result_rows=len(result.get('rows',[])),
                  economic_fund_return_improvement='NOT_TESTED',
                  source_code='PR stacked on existing PR188; no changes to live execution')
    write_json(out,'MANIFEST.json',manifest)
    write_json(out,'RESULT.json',result)
    print(json.dumps(dict(status=manifest['status'],output=str(out),models=methods,
                          n_scored=manifest['result_rows'],investment_return=manifest['economic_fund_return_improvement']),indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
