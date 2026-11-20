"""Engineering invariants on generated data: not investment-performance experiments."""
from __future__ import annotations
from pathlib import Path
import tempfile
import numpy as np
import pytest
from research.nextgen.joint_state import contracts as C, risk as R, regimes as G, alpha as A, control as O, runner as M


@pytest.fixture(scope='module')
def risk_data():
    rng=np.random.default_rng(41)
    n=14;t=540
    dates=np.arange(np.datetime64('2017-01-02'),np.datetime64('2017-01-02')+np.timedelta64(800,'D'))
    dates=np.asarray([d for d in dates if int(d.astype('datetime64[D]').astype(int))%7 not in (2,3)])[:t]
    market=rng.normal(0,.003,size=(t,14,1))
    coef=rng.uniform(.6,1.2,size=(1,1,n));coef[:,:,0]=1.
    x=market*coef+rng.normal(0,.001,size=(t,14,n))
    x[:,:,0]=market[:,:,0]
    rv=np.sum(x*x,axis=1);daily=x.sum(axis=1)
    names=np.array(['SPY']+[f'A{i:03d}' for i in range(n-1)])
    return C.RiskData(dates,names,x,daily,rv,'synthetic-fixture-ONLY')


@pytest.fixture(scope='module')
def alpha_data():
    rng=np.random.default_rng(91)
    t=1050;n=95
    all_dates=np.arange(np.datetime64('2013-01-02'),np.datetime64('2018-01-02'))
    dates=np.array([d for d in all_dates if d.astype('datetime64[D]').astype(int)%7 not in (2,3)])[:t]
    score=rng.uniform(0,1,size=(t,n))
    y=.004*(score-.5)+rng.normal(0,.01,size=(t,n))
    elig=np.ones((t,n),bool)
    ix=np.flatnonzero(dates.astype(int)%7==0)
    return C.AlphaData(dates,np.array([f'A{i:03d}' for i in range(n)]),score,y,elig,ix[ix+5<t],np.arange(t),'synthetic-fixture-ONLY'),rng.normal(0,.007,size=t)


def test_names_unique():
    with pytest.raises(ValueError,match='duplicate'):C.names_checked(['SPY','SPY'])

def test_dates_strict():
    with pytest.raises(ValueError,match='dates'):C.dates_checked(np.array(['2019-01-01']*120,dtype='datetime64[D]'))

def test_dev_boundary():
    assert C.DEV_END==np.datetime64('2019-12-31')

def test_no_input_output_alias():
    with tempfile.TemporaryDirectory() as t:
        root=Path(t);child=root/'source';child.mkdir()
        with pytest.raises(ValueError):C.safe_new_dir(child/'report',(child,))

def test_file_output_create_only():
    with tempfile.TemporaryDirectory() as t:
        out=C.safe_new_dir(Path(t)/'output',(Path(t)/'input',))
        assert out.exists()
        with pytest.raises(FileExistsError):C.safe_new_dir(out,())

def test_no_pickle_source():
    import inspect
    assert 'allow_pickle=False' in inspect.getsource(C.load_risk)
    assert 'allow_pickle=False' in inspect.getsource(C.load_alpha)

def test_alpha_future_day_purging(alpha_data):
    d,_=alpha_data
    assert np.all(d.decision_ix+5<len(d.dates))

def test_thursday_mask(alpha_data):
    d,_=alpha_data
    assert np.all(d.dates[d.decision_ix].astype(int)%7==0)

def test_poet_symmetric_psd():
    rng=np.random.default_rng(2);x=rng.normal(size=(100,22))
    c=R.poe_residual(x);assert np.allclose(c,c.T,atol=1e-10)
    assert np.min(np.linalg.eigvalsh(c))>0

def test_poet_refuses_nans():
    with pytest.raises(ValueError):R.poe_residual(np.full((100,5),np.nan))

def test_pca_uses_only_past(risk_data):
    o=330;a=R.factor_window(risk_data,o,252,3)
    assert a.factor.shape[0]==252
    modified=risk_data.intraday.copy();modified[o:]*=200
    d=C.RiskData(risk_data.dates,risk_data.names,modified,
                 modified.sum(1),np.sum(modified*modified,axis=1),'fixture')
    b=R.factor_window(d,o,252,3)
    assert np.allclose(a.loading,b.loading)
    assert np.allclose(a.factor_rv,b.factor_rv)

def test_pca_missing_market_fails(risk_data):
    with pytest.raises(ValueError):R.factor_window(risk_data,1,252,3)

def test_pca_factor_covariance_psd(risk_data):
    w=R.factor_window(risk_data,330,252,3)
    cov=R.covariance_from_factors(w,np.mean(w.factor_rv,axis=0))
    assert cov.shape==(len(w.stocks),len(w.stocks))
    assert np.min(np.linalg.eigvalsh(cov))>0

def test_covariance_rejects_negative_variances(risk_data):
    w=R.factor_window(risk_data,330,252,3)
    with pytest.raises(ValueError):R.covariance_from_factors(w,[-1,.2,.3])

def test_heavy_positive_causal():
    rng=np.random.default_rng(77);x=rng.lognormal(-6,1,150)
    p=R.heavy_filter(x,maxiter=45)
    assert p['forecast']>0
    assert 0<=p['a']+p['b']<1
    b=R.heavy_filter(np.r_[x,[100]],maxiter=45)
    assert b['forecast']!=p['forecast']

def test_heavy_rejects_negative():
    with pytest.raises(ValueError):R.heavy_filter(np.full(100,-1.))

def test_realized_garch_fit_positive():
    rng=np.random.default_rng(3);r=rng.normal(0,.02,140);rv=r*r+.0001
    v=R.realized_garch(r,rv,maxiter=45)
    assert v['forecast']>0 and np.isfinite(v['logscore'])

def test_realized_garch_validation():
    with pytest.raises(ValueError):R.realized_garch(np.ones(120),np.zeros(120))

def test_qlike_matched_zero():
    assert R.qlike(.0002,.0002)==pytest.approx(0,abs=1e-12)

def test_qlike_bad():
    with pytest.raises(ValueError):R.qlike(0,1)

def test_small_risk_evaluation(risk_data):
    # fixture risk output NOT historical trading performance
    rows=R.risk_trial(risk_data,'poet',start_year=2017,end_year=2018,step=45,lookback=252,factors=2,max_origins=2)
    assert len(rows)==4
    assert all(x['qlike']>=-1e-9 for x in rows)

def test_bayesian_sv_missing_dependency_clear():
    x=np.ones((50,2))
    with pytest.raises((ValueError,RuntimeError)):
        R.bayesian_factor_sv(x)

def test_hmm_filter_normalization():
    rng=np.random.default_rng(3);x=np.r_[rng.normal(-1,.4,(80,2)),rng.normal(1,.4,(80,2))]
    m=G.gaussian_hmm(x,k=2,iterations=10)
    p,last=m.filter(x)
    assert np.allclose(p.sum(1),1)
    assert np.isclose(m.next_state(last).sum(),1)

def test_hmm_future_input_invariance():
    rng=np.random.default_rng(3);x=rng.normal(size=(120,2))
    m=G.gaussian_hmm(x[:80],k=2,iterations=8)
    p,_=m.filter(x[:101]);q,_=m.filter(np.r_[x[:101],x[101:]*500])
    assert np.allclose(p,q[:101])

def test_hsmm_duration_transitions():
    d=G._duration_matrix(2,5)
    A=G._hsmm_transitions(np.array([[0,1],[1,0.]]),d)
    assert A.shape==(10,10)
    assert np.allclose(A.sum(1),1)
    assert A[3,2]==pytest.approx(1)

def test_hsmm_filter_probabilities():
    rng=np.random.default_rng(13);x=rng.normal(size=(180,2))
    m=G.gaussian_hsmm(x,k=2,dmax=4,iterations=4)
    p,_=m.filter(x)
    assert m.family=='HSMM' and np.allclose(p.sum(1),1)

def test_bocpd_probability_after_jump():
    rng=np.random.default_rng(20);x=np.r_[rng.normal(-.2,.1,80),rng.normal(.8,.1,80)]
    a=G.bocpd(x,max_run=100)
    assert len(a)==160 and all(0<=v['cp_probability']<=1 for v in a)
    assert np.all(np.isfinite([v['variance'] for v in a]))

def test_regime_trial_no_future_smoothed():
    rng=np.random.default_rng(20);x=rng.normal(size=(190,2))
    a=G.regime_trial(x,100,101,145,method='hmm')
    assert len(a)==44 and np.isfinite(a[0]['log_density'])

def test_weekly_slope_panel_avoids_future_labels(alpha_data):
    d,market=alpha_data;w=A.weekly_slope_panel(d,market)
    assert len(w.date)>70
    assert np.all(w.available>w.date)
    ids=A.available_before(w,np.datetime64('2017-03-02'))
    assert np.all(w.available[ids]<np.datetime64('2017-03-02'))

def test_regime_features_are_historical(alpha_data):
    d,market=alpha_data
    a=A._market_features(market,360)
    market[361:]+=999
    b=A._market_features(market,360)
    assert np.array_equal(a,b)

def test_kalman_local_level_posterior():
    rng=np.random.default_rng(14);y=rng.normal(.007,.01,100)
    r=np.ones_like(y)*.0001
    z=A.kalman_slope(y,r)
    assert -1<z['phi']<1 and z['variance']>0 and len(z['posterior_means'])==100

def test_kalman_rejects_invalid():
    with pytest.raises(ValueError):A.kalman_slope(np.ones(50),np.zeros(50))

def test_bayesian_linear_regularizes():
    rng=np.random.default_rng(22);x=rng.normal(size=(100,3));y=rng.normal(0,.02,100)
    z=A.bayesian_linear_state(y,np.ones(100)*.001,x)
    pred,var=z['pred'](x[0])
    assert np.isfinite(pred) and var>0

def test_moe_small_ensemble():
    rng=np.random.default_rng(24);x=rng.normal(size=(86,3));y=x[:,0]*.01+rng.normal(0,.008,86)
    z=A.train_moe(x,y,np.ones(86)*.0001,epochs=25,seeds=(3,7),patience=7,hidden=6)
    p,v=z['predict'](x[:2]);assert p.shape==(2,) and np.all(v>0)

def test_moe_rejects_short_time_series():
    with pytest.raises(ValueError):A.train_moe(np.ones((20,3)),np.ones(20),np.ones(20))

def test_alpha_trial_dev_only(alpha_data):
    d,market=alpha_data;w=A.weekly_slope_panel(d,market)
    with pytest.raises(ValueError):A.alpha_trial(w,eval_end='2020-12-31')

def test_student_t_scenario_reproducible():
    a=O.student_t_scenarios(np.zeros(3),np.eye(3)*.01,80,3,seed=8)
    b=O.student_t_scenarios(np.zeros(3),np.eye(3)*.01,80,3,seed=8)
    assert a.shape==(80,3,3) and np.array_equal(a,b)

def test_student_t_psd_validation():
    with pytest.raises(ValueError):O.student_t_scenarios(np.zeros(3),np.ones((2,2)))

def test_optimizer_shape_validator():
    p=O.Policy(np.array(['A','B']),np.array([1.,1.]))
    a=np.zeros((50,2,2));s=np.zeros((50,2));w=np.zeros(2)
    aa,ss,bb,ww=O._check_scenario(a,s,p,w)
    assert aa.shape==(50,2,2)

def test_optimizer_rejects_infeasible_gross():
    p=O.Policy(np.array(['A','B']),np.array([1.,1.]),cap=.8)
    with pytest.raises(ValueError):O._check_scenario(np.zeros((50,2,2)),np.zeros((50,2)),p,np.zeros(2))

def test_solver_if_cvxpy_available():
    pytest.importorskip('cvxpy')
    p=O.Policy(np.array(['A','B']),np.array([1.,1.]),core=.7,cap=1.9,max_stock_abs=.3)
    a=O.student_t_scenarios(np.array([.001,.001,0]),np.eye(3)*.0002,60,2,seed=4)
    z=O.solve_mpc(a[:,:,:2],a[:,:,-1],p,np.array([.1,-.1]))
    assert z['first_whole_fund_gross']<=1.9+1e-5
    assert z['semantics']=='MODEL_PREDICTED_NOT_HISTORICAL_PROFIT'

def test_no_network_imports():
    import inspect
    for module in (C,R,G,A,O,M):
        source=inspect.getsource(module)
        for banned in ('requests.get','urllib.request','http.client','alpaca_trade_api','subprocess.run(["curl"'):
            assert banned not in source
