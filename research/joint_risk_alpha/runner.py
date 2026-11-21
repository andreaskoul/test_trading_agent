"""Read-only local research runner. Fits on data ending no later than 2019.

Run from repository root using `python -m research.joint_risk_alpha.runner`.
It never imports trading modules or reads F_forward/H9, broker secrets or 2020+ labels.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
from .io import read_hf,read_alpha,hf_daily_returns,origin_grid,np_json
from .covariance import ewma_realized_cov,Heavy,RealizedGARCH,poet,psd,realised_cov,_gauss_qlike,factor_sv_pymc,factor_sv_particle,factor_cov_from_variances
from .alpha import extract_weekly,DynamicAlpha,SoftRegimeAlpha,chronological_year_folds,maturity_mask
from .regimes import GaussianHMM,HiddenSemiMarkov,BOCPD

CUT='2019-12-31'

def _serial_write(obj,out):
    out=Path(out)
    if out.exists():raise FileExistsError(f'NO OVERWRITE: {out}')
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf8') as f:json.dump(obj,f,indent=2,default=np_json,allow_nan=False)

def safe(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [safe(x) for x in v]
    if isinstance(v,float) and not np.isfinite(v):return None
    if isinstance(v,(np.floating,np.integer)):return safe(v.item())
    return v

def _prep_factors(p,max_names=120,k=4,train_end='2017-12-29',min_coverage=.95):
    """Fixed PCA fitted on 2016-17 only. SPY + k-1 past PCA components.

    Missing name-day bars => zero weight + re-normalised linear projection;
    sufficiently incomplete days are discarded, not silently zero returns.
    """
    from sklearn.decomposition import PCA
    dates=p.dates; train=np.where(dates<=pd.Timestamp(train_end))[0]
    if len(train)<200:raise ValueError('Need 200 early factor training days')
    returns=hf_daily_returns(p);valid=np.isfinite(returns)
    coverage=valid[train].mean(axis=0)
    selected=np.argsort(coverage)[::-1]
    selected=[i for i in selected if p.names[i]!='SPY' and coverage[i]>.85][:max_names]
    if len(selected)<20:raise ValueError('Not enough observed stock bars for factor risk')
    iSPY=p.names.index('SPY')
    x=returns[np.ix_(train,selected)]
    fill=np.nanmean(x,axis=0);fill=np.where(np.isfinite(fill),fill,0.)
    fit=np.where(np.isfinite(x),x,fill)
    fit=fit-fit.mean(0)
    model=PCA(n_components=k-1,svd_solver='randomized',random_state=20261121).fit(fit)
    W=np.zeros((len(p.names),k));W[iSPY,0]=1.;W[np.asarray(selected),1:]=model.components_.T
    R=np.empty((len(dates),14,k));R[:]=np.nan
    coverage_by_day=[]
    for t in range(len(dates)):
        relevant=p.intraday[t,:,selected] # numpy advanced indexing shape possibly (len(selected),14)
        # use basic indexing to guarantee bars x names
        relevant=p.intraday[t][:,selected]
        complete=np.isfinite(relevant).all(0)
        frac=float(complete.mean());spyok=np.isfinite(p.intraday[t,:,iSPY]).all()
        coverage_by_day.append(frac)
        if frac<min_coverage or not spyok:continue
        R[t,:,0]=p.intraday[t,:,iSPY]
        # PCA projections must renormalize *in-sample* component weights,
        # otherwise missing names artificially shrink factor variance.
        sub=model.components_[:,complete].T
        normalizer=np.sqrt((model.components_**2).sum(1)/np.maximum((sub**2).sum(0),1e-12))
        R[t,:,1:]=(relevant[:,complete]@sub)*normalizer
    return {'R':R,'W':W,'selected_names':[p.names[i] for i in selected],
            'coverage':np.array(coverage_by_day),'factor_train_end':train_end,
            'pca_explained':model.explained_variance_ratio_.tolist()}


def run_risk(hf,models=('ewma','poet','heavy','garch'),stride=21,lookback=252,
             factor_count=4,max_names=120,sv_method='advi',sv_draws=300,sv_tune=500,
             start='2018-01-01',end='2019-12-31'):
    p=read_hf(hf,max_date=CUT)
    factor=_prep_factors(p,max_names=max_names,k=factor_count)
    facbars=factor['R'];allrc=np.empty((len(p.dates),factor_count,factor_count));allrc[:]=np.nan
    for t in range(len(p.dates)):
        if np.isfinite(facbars[t]).all():allrc[t]=facbars[t].T@facbars[t]
    # Stock daily matrix used by high-dimensional POET. Only past days per origin.
    stock_daily=hf_daily_returns(p)
    origins=origin_grid(p,start,end,stride=stride,horizon=5,warmup=lookback)
    if len(origins)<4:raise ValueError('Too few eligible past-only risk origins')
    output=[]
    for t in origins:
        trainbars=facbars[t-lookback:t]
        good=np.isfinite(trainbars).all((1,2))
        n_good=int(good.sum())
        if n_good<180:continue
        RC=realised_cov(trainbars[good])
        X=facbars[t-lookback:t][good].sum(1)
        if any(~np.isfinite(facbars[t:t+5]).all(axis=(1,2))):continue
        target=realised_cov(facbars[t:t+5]).mean(0)
        C=np.mean(RC,axis=0)
        forecasts={}
        if 'ewma' in models:
            # Online EWMA forecast for origin t: assimilate RC[t-1].
            last=ewma_realized_cov(RC)[-1]
            forecasts['ewma']=psd(.94*last+.06*RC[-1])
        if 'poet' in models:
            # POET in the original STOCK cross section, then project into the
            # SAME fixed SPY+PCA factor portfolios used by the other models.
            idx=[p.names.index('SPY')]+[p.names.index(n) for n in factor['selected_names']]
            stocks=stock_daily[t-lookback:t][:,idx]
            count=np.isfinite(stocks).sum(0)
            viable=count>=int(.85*lookback)
            if viable.sum()<20:raise ValueError('POET cannot estimate >=20 historically observed names')
            Xstock=stocks[:,viable]
            historical_mean=np.nanmean(Xstock,axis=0)
            Xstock=np.where(np.isfinite(Xstock),Xstock,historical_mean)
            pmat,_=poet(Xstock,rank=min(factor_count,viable.sum()-1),threshold=.6)
            W=factor['W'][np.asarray(idx)[viable]]
            forecasts['poet']=psd(W.T@pmat@W)
        if 'heavy' in models:forecasts['heavy']=Heavy().fit(RC).predict(RC)
        if 'garch' in models:
            vars=[RealizedGARCH().fit(X[:,j],np.maximum(RC[:,j,j],1e-9)).predict(X[:,j],np.maximum(RC[:,j,j],1e-9)) for j in range(factor_count)]
            forecasts['garch']=factor_cov_from_variances(vars,X)
        if 'sv' in models:
            posterior=factor_sv_particle(X,draws=sv_draws,burn=sv_tune,particles=256)
            forecasts['sv']=factor_cov_from_variances([z['mean'] for z in posterior],X)
        if 'sv-pymc' in models:
            posterior=factor_sv_pymc(X,draws=sv_draws,tune=sv_tune,chains=2,cores=2,method=sv_method)
            forecasts['sv-pymc']=factor_cov_from_variances([z['mean'] for z in posterior],X)
        forecast={name:{'gaussian_logscore':_gauss_qlike(target,P),
                        'spy_variance_qlike':float(target[0,0]/P[0,0]-np.log(target[0,0]/P[0,0])-1),
                        'pred_variance_SPY':float(P[0,0]),
                        'logdet':float(np.linalg.slogdet(P)[1])} for name,P in forecasts.items()}
        output.append({'date':str(p.dates[t].date()),'n_train_days':n_good,
                       'future_target_SPY':float(target[0,0]),'forecasts':forecast})
    if len(output)<4:raise ValueError('Coverage insufficient for >=4 held-out risk evaluations')
    agg={name:{metric:float(np.mean([o['forecasts'][name][metric] for o in output])) for metric in ('gaussian_logscore','spy_variance_qlike')}
         for name in models}
    return safe({'status':'DEVELOPMENT_ONLY_RISK_NOT_TRADING','schema':'hf.npz 14-return array',
           'source_sha256':p.source_sha256,'max_read_date':str(p.dates[-1].date()),
           'origins':len(output),'models':list(models),'pca_factor_calibration_end':factor['factor_train_end'],
           'factor_count':factor_count,'n_stocks_in_basis':len(factor['selected_names']),
           'mean_name_coverage':float(np.mean(factor['coverage'])),
           'pca_explained_early':factor['pca_explained'],
           'score_mean':agg,'period_results':output,
           'warning':'Already-seen 2018-2019 development outcomes, not new OOS; fixed PCA basis has survivor limitations; no investment gains measured.'})


def _alpha_environment(panel):
    rows=extract_weekly(panel)
    # Drop no theta and no features prior to model training; never impute future alpha.
    ix=np.array([z['t'] for z in rows]);x=np.array([z['environment'] for z in rows]);
    ok=np.isfinite(x).all(1)
    return rows,ix,x,ok


def run_alpha(dev,models=('constant','kalman','gated','moe'),
              moe_epochs=250,moe_hidden=64,moe_experts=3,device='cpu',last_year=2019):
    panel=read_alpha(dev,max_date=CUT)
    rows,t,env,ok=_alpha_environment(panel)
    vals=[];model_train=[]
    for year in (2017,2018,2019):
        if year>last_year:break
        train_last=int(np.where(panel.dates.year<year)[0][-1])
        prior=np.array([z['t']+6<=train_last and z['n']>=40 and np.isfinite(z['theta']) and ok[i] for i,z in enumerate(rows)])
        valid=np.array([panel.dates[z['t']].year==year and z['n']>=40 and np.isfinite(z['theta']) and ok[i] for i,z in enumerate(rows)])
        if prior.sum()<65 or valid.sum()<20:continue
        y=np.array([z['theta'] for z in rows]);se=np.array([z['theta_var'] for z in rows])
        constant=float(y[prior].mean())
        pred={'constant':np.full(valid.sum(),constant)}
        if 'kalman' in models:
            K=DynamicAlpha().fit(y[prior],se[prior])
            # Forward filtering with delayed weekly outcomes: ONLY the labels
            # of dates completed before the current decision may update state.
            hist=[dict(z) for z in rows if z['t']<=int(t[valid].max())]
            states=K.filter_delayed(hist)
            pm={z['t']:z['mean'] for z in states}
            pred['kalman']=np.array([pm[int(u)] for u in t[valid]])
        # Market-only risk states. HMM fit on past environment; subsequent
        # filtered probabilities use ONLY information through current row.
        means=env[prior].mean(0);stdev=np.maximum(env[prior].std(0),1e-6)
        norm=(env-means)/stdev
        # Earliest warm-up weeks have no 21-session volatility; substitute
        # the TRAINING mean (0 standardized), never a future observation.
        norm=np.where(np.isfinite(norm),norm,0.)
        H=GaussianHMM(n_states=3).fit(norm[prior])
        probs=H.filter(norm)
        if 'gated' in models:
            G=SoftRegimeAlpha(lam=50).fit(env,probs,y,se,prior)
            pred['gated']=G.predict(env[valid],probs[valid])[0]
        if 'moe' in models:
            # Each labelled row consists of (name, week); split and standardise
            # only using origin sessions before the training cutoff.
            ids=np.array([z['t'] for z in rows])
            sel=prior|valid
            xx=panel.score[ids[sel]];yy=panel.outcome[ids[sel]]
            ee=panel.eligible[ids[sel]];zz=panel.chars[ids[sel]]
            market=np.concatenate([env[sel],probs[sel]],axis=1)
            score=np.asarray(pd.DataFrame(xx).rank(axis=1,pct=True),float)
            score=score-.5
            wt=np.broadcast_to(ids[sel][:,None],xx.shape)
            tr=np.broadcast_to(prior[sel,None],xx.shape)&ee
            va=np.broadcast_to(valid[sel,None],xx.shape)&ee
            mod=__import__('research.joint_risk_alpha.moe',fromlist=['ConditionalMoE'])
            net=mod.ConditionalMoE(market.shape[1],zz.shape[2],moe_experts,moe_hidden)
            ans=net.fit(score.ravel(),zz.reshape(-1,zz.shape[-1]),
                        np.repeat(market,xx.shape[1],axis=0),yy.ravel(),
                        wt.ravel(),tr.ravel(),va.ravel(),epochs=moe_epochs,device=device)
            # Per-week slope of predicted MASTER rank-response, not stock-alpha IC.
            pv=net.predict(score[va],zz[va],np.repeat(market,xx.shape[1],axis=0).reshape(xx.shape[0],xx.shape[1],-1)[va],mc_dropout=10,device=device)
            va_rows=np.flatnonzero(valid)
            ptr=0;slope=[]
            for j in np.where(sel)[0]:
                if not valid[j]:continue
                idx=np.where(ee[np.where(np.where(sel)[0]==j)[0][0]])[0]
                N=len(idx)
                xxv=score[np.where(np.where(sel)[0]==j)[0][0],idx]
                yyv=pv['mean'][ptr:ptr+N];ptr+=N
                slope.append(float(np.cov(xxv,yyv,bias=True)[0,1]/max(np.var(xxv),1e-8)))
            if len(slope)==valid.sum():pred['moe']=np.array(slope)
            model_train.append({'year':year,'moe_training':ans})
        targets=y[valid]
        vals.append({'year':year,'n_valid_weeks':len(targets),
                     'models':{name:{'mse':float(np.mean((p-targets)**2)),
                                      'corr':float(np.corrcoef(p,targets)[0,1]) if np.std(p)>1e-12 else None,
                                      'mean_forecast':float(p.mean())} for name,p in pred.items()}})
    if not vals:raise ValueError('No adequate chronological development folds')
    metrics={name:float(np.mean([z['models'][name]['mse'] for z in vals if name in z['models']])) for name in vals[0]['models']}
    return safe({'status':'DEVELOPMENT_ONLY_ALPHA_NOT_TRADING',
           'source_sha256':panel.source_sha256,'last_date':str(panel.dates[-1].date()),
           'years':vals,'mean_yearly_mse':metrics,'compute':model_train,
           'limitations':'MASTER reference scores are previously examined; historical CIK joins forbidden; time clusters not independent security observations; results are alpha-slope diagnostics not NAV returns.'})


def run_regimes(hf,n_states=3,max_duration=20,end='2019-12-31'):
    p=read_hf(hf,max_date=CUT)
    spy=p.names.index('SPY');v=p.realized_var[:,spy]
    dates=p.dates;ok=np.isfinite(v)&(v>0)
    v=np.log(np.maximum(v,1e-9));x=np.column_stack([v,np.r_[0,np.abs(np.diff(v))]])
    cutoff=np.where(dates<=pd.Timestamp('2017-12-29'))[0][-1]+1
    mean=np.mean(x[:cutoff][ok[:cutoff]],axis=0);sd=np.std(x[:cutoff][ok[:cutoff]],axis=0).clip(1e-6)
    xx=(x-mean)/sd
    if not np.isfinite(xx).all():raise ValueError('regime preprocessing nonfinite')
    H=GaussianHMM(n_states).fit(xx[:cutoff]); S=HiddenSemiMarkov(n_states,max_duration).fit(xx[:cutoff]);B=BOCPD().filter(xx[:,0])
    h=H.filter(xx);s=S.filter(xx)
    selected=np.where((dates>pd.Timestamp('2017-12-29'))&(dates<=pd.Timestamp(end)))[0]
    return safe({'status':'DEVELOPMENT_REGIME_FILTERS_ONLY','source_sha256':p.source_sha256,
                 'n_states':n_states,'hmm_train_loglik':H.loglik,
                 'hsmm_duration_mean':S.duration_mean,
                 'validation':[{'date':str(dates[t].date()),'hmm_filtered':h[t],
                                'hsmm_filtered':s[t],
                                'bocpd_changepoint':B['changepoint_probability'][t]} for t in selected],
                 'warning':'Filtered probabilities are diagnostics; no regime trading rule or newly established alpha.'})


def main():
    ap=argparse.ArgumentParser(description='Isolated research: dynamic risk, states, MASTER calibration')
    sub=ap.add_subparsers(dest='command',required=True)
    q=sub.add_parser('risk');q.add_argument('--hf',required=True);q.add_argument('--models',default='ewma,poet,heavy,garch');q.add_argument('--stride',type=int,default=21);q.add_argument('--lookback',type=int,default=252);q.add_argument('--factors',type=int,default=4);q.add_argument('--max-names',type=int,default=120);q.add_argument('--sv-method',default='advi',choices=['advi','nuts']);q.add_argument('--sv-draws',type=int,default=300);q.add_argument('--sv-tune',type=int,default=500)
    q=sub.add_parser('alpha');q.add_argument('--dev',required=True);q.add_argument('--models',default='constant,kalman,gated,moe');q.add_argument('--moe-epochs',type=int,default=250);q.add_argument('--moe-hidden',type=int,default=64);q.add_argument('--moe-experts',type=int,default=3);q.add_argument('--device',default='cpu')
    q=sub.add_parser('regimes');q.add_argument('--hf',required=True);q.add_argument('--states',type=int,default=3);q.add_argument('--max-duration',type=int,default=20)
    q=sub.add_parser('scenario');q.add_argument('--forecast-npz',required=True);q.add_argument('--draws',type=int,default=1024);q.add_argument('--df',type=float,default=6.)
    q=sub.add_parser('mpc');q.add_argument('--scenario-npz',required=True);q.add_argument('--gross',type=float,default=1.9);q.add_argument('--wasserstein-radius',type=float,default=0.0005);q.add_argument('--funding-mode',choices=['segregated','net_debit'],default='segregated')
    for q in sub.choices.values():q.add_argument('--out',required=True)
    a=ap.parse_args()
    if Path(a.out).exists():ap.error('output exists; no overwrite')
    if a.command=='scenario':
        from .scenarios import build_bundle
        print(json.dumps(build_bundle(a.forecast_npz,a.out,scenarios=a.draws,df=a.df),allow_nan=False));return
    if a.command=='risk':res=run_risk(a.hf,models=tuple(a.models.split(',')),stride=a.stride,lookback=a.lookback,factor_count=a.factors,max_names=a.max_names,sv_method=a.sv_method,sv_draws=a.sv_draws,sv_tune=a.sv_tune)
    elif a.command=='alpha':res=run_alpha(a.dev,models=tuple(a.models.split(',')),moe_epochs=a.moe_epochs,moe_hidden=a.moe_hidden,moe_experts=a.moe_experts,device=a.device)
    elif a.command=='regimes':res=run_regimes(a.hf,a.states,a.max_duration)
    else:
        from .optimize import solve_mpc,TradingPolicy
        with np.load(a.scenario_npz,allow_pickle=False) as z:
            required={'mu','scenarios','previous','beta','core','hedge_prev'}
            if not required<=set(z.files):raise ValueError('STOP: scenario file missing '+str(required-set(z.files)))
            source={key:z[key] for key in required}
            spread=z['half_spread_bp'] if 'half_spread_bp' in z.files else None
            cap=z['adv_max_weight_change'] if 'adv_max_weight_change' in z.files else None
            std=z['alpha_posterior_std'] if 'alpha_posterior_std' in z.files else None
        z=solve_mpc(source['mu'],source['scenarios'],source['previous'],float(source['core']),source['beta'],float(source['hedge_prev']),
            policy=TradingPolicy(gross_limit=a.gross,wasserstein_radius=a.wasserstein_radius,funding_mode=a.funding_mode),
            adv_capacity=cap,prediction_std=std,half_spread_bps=spread)
        res={'status':'RESEARCH_SCENARIO_MPC_NOT_EXECUTABLE','scenario_sha256':__import__('hashlib').sha256(Path(a.scenario_npz).read_bytes()).hexdigest(),
            'first_stock_weights':z['first_stock_weights'],'first_spy_hedge':z['first_spy_hedge'],'gross_by_step':z['gross_by_step'],
            'objective':z['objective'],'predicted_cvar':z['predicted_cvar'],
            'warning':'Scenario file must be constructed from causal out-of-time posterior; NOT a trading instruction, not validated whole-fund PnL.'}
    _serial_write(res,a.out)
    print(json.dumps({'status':res['status'],'out':a.out,'rows':len(res.get('period_results',res.get('validation',res.get('years',[]))))},allow_nan=False))
if __name__=='__main__':main()
