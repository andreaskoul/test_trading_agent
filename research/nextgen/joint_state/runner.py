"""Read-only CLI for academically motivated risk, regime, alpha and MPC research.

CLI never contacts the network, changes source caches, modifies broker accounts,
or reopens any previously-locked 2020-2026 investment holdout.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import numpy as np
from .contracts import load_risk,load_alpha,sha256,safe_new_dir,write_json
from . import risk,regimes,alpha,control,compare


def load_dev_market(path):
    with np.load(path,allow_pickle=False) as z:
        if 'rm' not in z.files:
            raise ValueError('dev.npz lacks rm market-return field; stop rather than invent proxy')
        m=np.asarray(z['rm'],float)
        n=len(z['S'])
    if m.shape!=(n,):raise ValueError('market return shape mismatch')
    return m


def risk_features(d):
    ix=int(np.flatnonzero(d.names=='SPY')[0])
    spy=d.daily[:,ix]
    rv=d.realized[:,ix]
    valid=np.isfinite(spy)&np.isfinite(rv)&(rv>0)
    if valid.mean()<.9:raise ValueError('risk regime features too sparse')
    # No global interpolation with future information. Preserve only complete
    # observations, with their own monotonic dates for chronological folds.
    cross=np.nanmedian(np.where(d.realized>0,d.realized,np.nan),axis=1)
    v=valid&np.isfinite(cross)&(cross>0)
    x=np.column_stack((spy[v],np.log(rv[v]),np.log(cross[v])))
    return x,d.dates[v]


def hac_t(x,lags=5):
    x=np.asarray(x,float)
    if len(x)<lags+3 or not np.isfinite(x).all():return None
    u=x-x.mean();n=len(x)
    var=float(u@u/n)
    for l in range(1,min(lags+1,n)):
        var+=2*(1-l/(lags+1))*float(u[l:]@u[:-l])/n
    return float(x.mean()/np.sqrt(max(var,1e-12)/n))


def _risk_summary(rows,source):
    a={}
    for name in sorted(set(x['portfolio'] for x in rows)):
        w=[x for x in rows if x['portfolio']==name]
        a[name]=dict(n=len(w),mean_qlike=float(np.mean([v['qlike'] for v in w])),
                     mean_forecast=float(np.mean([v['forecast'] for v in w])),
                     mean_realized=float(np.mean([v['rv'] for v in w])),
                     mean_held_coverage=float(np.mean([v['coverage'] for v in w])))
    return dict(stats=a,source_sha256=source.sha256,
                survivorship=source.survivorship,
                scope='REUSED_DEV_RISK_DIAGNOSTIC_NOT_INVESTMENT_PERFORMANCE')


def _alpha_summary(rows,source):
    loss=[];ql=[];by={}
    for row in rows:
        e=row['actual']-row['forecast']
        s=max(row['forecast_variance']+row['measurement_variance'],1e-10)
        loss.append(e*e)
        ql.append(float(.5*(np.log(2*np.pi*s)+e*e/s)))
        year=row['date'][:4]
        by.setdefault(year,[]).append(e*e)
    return dict(n=len(rows),mse=float(np.mean(loss)),gaussian_nll=float(np.mean(ql)),
                by_year_mse={k:float(np.mean(v)) for k,v in by.items()},
                source_sha256=source.sha256,scope='DEVELOPMENT_FROZEN_MASTER_EFFICACY_DIAGNOSTIC',
                not_independent_time_observations='per-stock weekly slopes are aggregated by decision week')


def make_and_solve(d,h,market,args):
    # Choose latest matching development decision date with complete available
    # labels; no search over strategy performance or best alpha outcomes.
    common=set(h.dates.astype('datetime64[D]').astype(int).tolist())
    eligible=[int(t) for t in d.decision_ix if int(d.dates[t].astype(int)) in common and d.dates[t]<=np.datetime64(args.origin)]
    if not eligible:raise ValueError('no aligned development Thursday decision')
    t=eligible[-1]
    t_h=int(np.flatnonzero(h.dates==d.dates[t])[0])
    w0=risk.factor_window(h,t_h,lookback=args.lookback,factors=args.factors)
    intr_names=h.names[w0.stocks]
    amap={name:i for i,name in enumerate(d.names)}
    hm={name:i for i,name in enumerate(intr_names)}
    stocks=[name for name in intr_names if name!='SPY' and name in amap and d.eligible[t,amap[name]]
            and np.isfinite(d.score[t,amap[name]])]
    if len(stocks)<40:raise ValueError(f'PIT/member coverage too low for a research portfolio: {len(stocks)}')
    # Strictly no score knowledge after the chosen t.
    w=alpha.weekly_slope_panel(d,market)
    ids=alpha.available_before(w,d.dates[t])
    if len(ids)<80:raise ValueError('insufficient matured MASTER effectiveness labels')
    kf=alpha.kalman_slope(w.slope[ids],w.variance[ids])
    if args.forecaster=='heavy':fv=[risk.heavy_filter(np.maximum(w0.factor_rv[:,j],risk.EPS))['forecast'] for j in range(args.factors)]
    elif args.forecaster=='realized_garch':fv=[risk.realized_garch(w0.factor[:,j],np.maximum(w0.factor_rv[:,j],risk.EPS))['forecast'] for j in range(args.factors)]
    elif args.forecaster=='bayes_sv':fv=[z['mean'] for z in risk.bayesian_factor_sv(w0.factor,draws=args.draws,tune=args.draws)]
    elif args.forecaster=='poet':fv=np.mean(w0.factor_rv[-22:],axis=0)
    else:raise ValueError('invalid forecaster')
    full_cov=risk.covariance_from_factors(w0,np.asarray(fv))
    ordered=np.asarray(stocks+['SPY'])
    idx=[hm[x] for x in ordered]
    cov=full_cov[np.ix_(idx,idx)]*args.holding_sessions
    scores=np.asarray([d.score[t,amap[name]] for name in stocks])
    from scipy.stats import rankdata
    centered=rankdata(scores)/(len(scores)+1)-.5
    mu=np.r_[kf['mean']*centered,0.]
    scenarios=control.student_t_scenarios(mu,cov,args.scenarios,args.horizon,seed=args.seed)
    from .control import Policy
    with np.load(args.alpha_cache,allow_pickle=False) as z:
        if 'beta' not in z.files:raise ValueError('dev.npz lacks PIT beta matrix')
        values=np.asarray(z['beta'])
    if values.shape!=(len(d.dates),len(d.names)):raise ValueError('beta shape incorrect')
    betas=np.asarray([values[t,amap[name]] for name in stocks])
    if not np.isfinite(betas).all():raise ValueError('missing beta in potential portfolio')
    pick=np.argsort(scores,kind='mergesort')
    n=max(1,len(stocks)//10)
    baseline=np.zeros(len(stocks));baseline[pick[:n]]=-.3/n;baseline[pick[-n:]]=.3/n
    core=1.3 if args.core==1.3 else .7
    baseline_hedge=-float(betas@baseline)
    cap=max(1.9,abs(core+baseline_hedge)+np.sum(np.abs(baseline)))
    policy=Policy(ordered[:-1],betas,core=core,cap=cap,financing=args.financing,
                  margin_rate_annual=args.margin_rate,max_stock_abs=max(.035,.3/n),
                  cvar_weight=args.cvar_weight,uncertainty_weight=args.uncertainty_weight,
                  risk_weight=args.risk_weight)
    value=control.solve_mpc(scenarios[:,:,:-1],scenarios[:,:,-1],policy,baseline,
                             uncertain_sigma=cov[:-1,:-1],days_per_step=int(7*args.holding_sessions/5))
    out=dict(status='MODEL_OPTIMISATION_FEASIBILITY_ONLY_NOT_BACKTEST',
             origin=str(d.dates[t]),stock_count=len(stocks),
             matched_current_member_panel_ratio=len(stocks)/int(d.eligible[t].sum()),
             baseline_gross=float(abs(core+baseline_hedge)+np.sum(np.abs(baseline))),
             cap=cap,forecast_alpha_slope=kf['mean'],forecast_alpha_variance=kf['variance'],
             new_gross=value['first_whole_fund_gross'],
             model_expected_utility=value['model_expected_path_utility'],
             first_spy_hedge=value['first_spy_hedge'],
             first_targets={str(name):float(v) for name,v in zip(stocks,value['first_step_weights'])},
             model_cost_first=value['model_cost_first'],model_financing_first=value['model_financing_first'],
             input_sha256={'risk':h.sha256,'alpha':d.sha256},
             warning='Survivorship of HF current constituents and simulated funding prevent investment promotion')
    return out


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['check','risk','regimes','alpha','optimize','compare'])
    p.add_argument('--hf-cache',type=Path)
    p.add_argument('--risk-results',type=Path)
    p.add_argument('--alpha-results',type=Path)
    p.add_argument('--regime-results',type=Path)
    p.add_argument('--alpha-cache',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--models',nargs='+')
    p.add_argument('--risk-methods',nargs='+')
    p.add_argument('--regime-methods',nargs='+')
    p.add_argument('--alpha-methods',nargs='+')
    p.add_argument('--risk-only',action='store_true')
    p.add_argument('--max-names',type=int)
    p.add_argument('--max-origins',type=int)
    p.add_argument('--step',type=int,default=42)
    p.add_argument('--lookback',type=int,default=252)
    p.add_argument('--factors',type=int,default=3)
    p.add_argument('--draws',type=int,default=250)
    p.add_argument('--seed',type=int,default=20261120)
    p.add_argument('--device',default='cpu')
    p.add_argument('--moe-epochs',type=int,default=400)
    p.add_argument('--moe-seeds',type=int,nargs='+',default=[11,17,23])
    p.add_argument('--refit-every',type=int,default=13)
    p.add_argument('--origin',default='2019-11-01')
    p.add_argument('--forecaster',choices=['poet','heavy','realized_garch','bayes_sv'],default='heavy')
    p.add_argument('--scenarios',type=int,default=250)
    p.add_argument('--horizon',type=int,default=3)
    p.add_argument('--holding-sessions',type=int,default=5)
    p.add_argument('--core',type=float,default=1.3,choices=[1.3,.7])
    p.add_argument('--financing',choices=['net_debit','segregated'],default='segregated')
    p.add_argument('--margin-rate',type=float,default=.06)
    p.add_argument('--cvar-weight',type=float,default=.12)
    p.add_argument('--uncertainty-weight',type=float,default=.05)
    p.add_argument('--risk-weight',type=float,default=.05)
    a=p.parse_args(argv)
    if a.command in ('check','risk','regimes','optimize') and a.hf_cache is None:
        p.error('risk cache --hf-cache required')
    if a.command in ('check','alpha','optimize') and a.alpha_cache is None and not a.risk_only:
        p.error('MASTER development cache --alpha-cache required')
    h=load_risk(a.hf_cache,n_names=a.max_names) if a.hf_cache else None
    d=load_alpha(a.alpha_cache) if a.alpha_cache else None
    market=load_dev_market(a.alpha_cache) if d is not None else None
    if a.command=='compare':
        if a.out is None:p.error('--out required')
        out=safe_new_dir(a.out,tuple(x for x in (a.risk_results,a.alpha_results,a.regime_results) if x is not None))
        result=compare.compare_all(a.risk_results,a.alpha_results,a.regime_results)
        write_json(out,'PAIRED_COMPARISON.json',result)
        print(json.dumps(dict(status=result['status'],economic_performance=result['economic_performance'],output=str(out)),indent=2))
        return 0
    if a.command=='check':
        print(json.dumps(dict(status='CONTRACT_CHECK_ONLY',risk=dict(sessions=len(h.dates),names=len(h.names),first=str(h.dates[0]),last=str(h.dates[-1]),sha256=h.sha256),
                alpha=None if d is None else dict(sessions=len(d.dates),names=len(d.names),decision_origins=len(d.decision_ix),sha256=d.sha256),
                warning='current intraday constituents not independently PIT certified'),indent=2))
        return 0
    if a.out is None:p.error('--out required for research runs')
    forbidden=tuple(x for x in (a.hf_cache,a.alpha_cache) if x is not None)
    # Treat cache parent directory as protected output destination, not only file.
    forbidden += tuple(x.parent for x in forbidden)
    # Cache file lives under <repo>/.cache/<module>/file.npz: exclude
    # repository roots as output destinations as well as cache parents.
    forbidden += tuple(x.parents[2] for x in (a.hf_cache,a.alpha_cache) if x is not None and len(x.parents)>=3 and x.parents[1].name=='.cache')
    out=safe_new_dir(a.out,forbidden)
    summary=dict(command=a.command,status='DEVELOPMENT_RESEARCH_NO_LIVE_SIGNAL',
                 cutoff='2019-12-31',risk_source=h.sha256 if h else None,
                 alpha_source=d.sha256 if d else None)
    if a.command=='risk':
        models=a.models or a.risk_methods or ['poet','heavy','realized_garch','bayes_sv']
        for model in models:
            print(f'Fitting factor-risk model {model}',file=sys.stderr,flush=True)
            rows=risk.risk_trial(h,model=model,step=a.step,lookback=a.lookback,
                                 factors=a.factors,max_origins=a.max_origins,sv_draws=a.draws)
            write_json(out,'risk_'+model+'.json',dict(rows=rows,summary=_risk_summary(rows,h)))
            summary[model]=_risk_summary(rows,h)['stats']
    elif a.command=='regimes':
        x,dates=risk_features(h)
        train_end=int(np.searchsorted(dates,np.datetime64('2018-01-01')))
        end=int(np.searchsorted(dates,np.datetime64('2020-01-01')))
        start=train_end+1
        for method in (a.models or a.regime_methods or ['hmm','hsmm','bocpd']):
            print(f'Fitting filtered regime {method}',file=sys.stderr,flush=True)
            rr=regimes.regime_trial(x,train_end,start,end,method=method,seed=a.seed)
            write_json(out,'regime_'+method+'.json',dict(rows=rr,
                           warning='Filtered probabilities: not smooth retrospective states'))
            summary[method]=dict(n=len(rr),mean_log_density=float(np.mean([v['log_density'] for v in rr])) if method!='bocpd' else None)
    elif a.command=='alpha':
        w=alpha.weekly_slope_panel(d,market)
        for method in (a.models or a.alpha_methods or ['constant','kalman','state_regression','moe','bayesian']):
            print(f'Fitting frozen-MASTER efficacy model {method}',file=sys.stderr,flush=True)
            rows=alpha.alpha_trial(w,method=method,refit_every=a.refit_every,
                                   draws=a.draws,device=a.device,moe_epochs=a.moe_epochs,moe_seeds=tuple(a.moe_seeds))
            write_json(out,'alpha_'+method+'.json',dict(rows=rows,summary=_alpha_summary(rows,d)))
            summary[method]=_alpha_summary(rows,d)
    elif a.command=='optimize':
        result=make_and_solve(d,h,market,a)
        write_json(out,'optimizer_decision_diagnostic.json',result)
        summary['optimizer']=dict(origin=result['origin'],matched=result['stock_count'],
                                  status=result['status'])
    write_json(out,'MANIFEST.json',summary)
    print(json.dumps(summary,indent=2,default=str))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
