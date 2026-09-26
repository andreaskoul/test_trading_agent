"""Audits of scripts/daily/daily_ladder.py: loop re-implementation of the P&L,
timing placebo (1-day leak / extra delays), shuffled-target placebo for ridge,
and the post-hoc pooled predictive regression. Run from the repo root."""
import sys,warnings;warnings.filterwarnings("ignore")
src=open('scripts/daily/daily_ladder.py').read().split('# ---------------------------------------------------------------- run')[0]
G={'__file__':'scripts/daily/daily_ladder.py'};exec(compile(src,'d','exec'),G)
import numpy as np,pandas as pd
cal,close,R,F=G['cal'],G['close'],G['R'],G['F']
hold=(cal>=G['HOLD'][0])&(cal<=G['HOLD'][1]);dev=(cal>=G['DEV'][0])&(cal<=G['DEV'][1])
# 1. independent loop re-implementation of pnl for tsmom12, H=1, 2bp
sig=np.sign(F['ret_250']).where(hold).fillna(0).to_numpy();c=close.to_numpy()
pos_prev=0.0;out=[];pos=np.zeros(len(c))
for t in range(1,len(c)):
    pos[t]=sig[t-1]            # set at close t from signal t-1
for u in range(2,len(c)):
    r=pos[u-1]*(c[u]/c[u-1]-1) - 2e-4*abs(pos[u-1]-pos[u-2])
    out.append((cal[u],r))
o=pd.Series(dict(out));o=o[hold[2:]] if False else o[o.index.isin(cal[hold])]
r2,_=G['pnl'](np.sign(F['ret_250']),1,2.0,hold)
print('loop vs vectorised: max abs diff',np.nanmax(np.abs(o.reindex(r2.index).to_numpy()-r2.to_numpy())), ' sharpe', o.mean()/o.std()*np.sqrt(252), r2.mean()/r2.std()*np.sqrt(252))
# 2. ridge H1 holdout: sensitivity to extra delay and to a deliberate 1-day LEAK
score=G['fit_predict']('ridge',cal[dev],cal[hold],1)
s=pd.Series(np.nan,index=cal);s[hold]=score.to_numpy()
for lab,sh in (('leak -1 day (uses tomorrow info)',-1),('as registered',0),('+1 day extra delay',1),('+2 days',2)):
    r,_=G['pnl'](np.sign(s.shift(sh)),1,2.0,hold&s.shift(sh).notna().to_numpy())
    print(f'{lab:36s} sharpe {r.mean()/r.std()*np.sqrt(252):6.2f}')
# 3. placebo: ridge fitted on time-shuffled dev targets
rng=np.random.default_rng(0);y=G['fwd'](1);srs=[]
Xd=F.loc[dev,G['FEATS']];yd=y[dev];ok=Xd.notna().all(1)&yd.notna()
from sklearn.linear_model import Ridge;from sklearn.preprocessing import StandardScaler
sc=StandardScaler().fit(Xd[ok]);Xh=F.loc[hold,G['FEATS']];okh=Xh.notna().all(1)
for k in range(200):
    m=Ridge(alpha=10).fit(sc.transform(Xd[ok]),rng.permutation(yd[ok].to_numpy()))
    p=pd.Series(np.nan,index=cal);p[cal[hold][okh.to_numpy()]]=m.predict(sc.transform(Xh[okh]))
    r,_=G['pnl'](np.sign(p),1,2.0,hold&p.notna().to_numpy());srs.append(r.mean()/r.std()*np.sqrt(252))
srs=np.array(srs);print('placebo ridge (shuffled dev targets) holdout sharpe: mean %.2f sd %.2f, p(>=0.935)=%.3f'%(srs.mean(),srs.std(),(srs>=0.935).mean()))
# 4. post-hoc: pooled predictive regression t (HAC, lags H+5) of fwd return on score, holdout
for H in (1,5):
    y=G['fwd'](H)
    for rule in G['RULES']:
        sc_=G['fit_predict'](rule,cal[dev],cal[hold],H)
        d=pd.DataFrame({'s':sc_,'y':y[hold]}).dropna();d=d[d.s!=0] if rule=='cot' else d
        z=(d.s-d.s.mean())/d.s.std()
        b,t,_=G['alpha_t'](d.y.to_numpy(),z.to_numpy(),H+5)
        X=np.column_stack([np.ones(len(z)),z]);bb=np.linalg.lstsq(X,d.y.to_numpy(),rcond=None)[0]
        # slope t: reuse alpha_t by regressing y on [1,z] -> need slope; quick HAC slope
        e=d.y.to_numpy()-X@bb;XtX=np.linalg.inv(X.T@X);S=(X*e[:,None]).T@(X*e[:,None])/len(e)
        for k in range(1,H+6):
            Gm=(X[k:]*e[k:,None]).T@(X[:-k]*e[:-k,None])/len(e);S+=(1-k/(H+6))*(Gm+Gm.T)
        V=len(e)*XtX@S@XtX
        print(f'H{H} {rule:9s} pooled slope t (HAC) {bb[1]/np.sqrt(V[1,1]):6.2f}  n={len(d)}')
