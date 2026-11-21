"""Engineering fixtures only; never interpreted as synthetic investment performance."""
import numpy as np
import pytest
from research.joint_risk_alpha.covariance import (psd,poet,realised_cov,ewma_realized_cov,Heavy,RealizedGARCH)
from research.joint_risk_alpha.regimes import GaussianHMM,HiddenSemiMarkov,BOCPD
from research.joint_risk_alpha.alpha import weekly_slope,DynamicAlpha,SoftRegimeAlpha,maturity_mask
from research.joint_risk_alpha.runner import _serial_write

RNG=np.random.default_rng(12)

def test_psd():
    m=np.array([[1,2],[2,1]])
    assert np.min(np.linalg.eigvalsh(psd(m)))>0

def test_realised_cov():
    R=np.arange(2*14*3).reshape(2,14,3)/1000
    out=realised_cov(R)
    assert out.shape==(2,3,3)
    assert np.allclose(out[0],R[0].T@R[0])

def test_ewma_uses_only_past():
    A=np.array([np.eye(2)*(.1+j*.0001) for j in range(25)])
    x=ewma_realized_cov(A)
    A[12:]*=10000
    y=ewma_realized_cov(A)
    assert np.allclose(x[:13],y[:13])

def test_poet_psd():
    X=RNG.normal(size=(100,17))*0.01
    M,stuff=poet(X,rank=3)
    assert M.shape==(17,17)
    assert np.linalg.eigvalsh(M).min()>0
    assert len(stuff['factor_eigenvalues'])==3

def test_poet_incomplete_fails():
    with pytest.raises(ValueError):poet(np.ones((8,4)))

def test_heavy():
    R=np.array([np.outer(x,x)+np.eye(2)*.01 for x in RNG.normal(size=(78,2))])
    m=Heavy().fit(R)
    out=m.predict(R)
    assert out.shape==(2,2)
    assert np.linalg.eigvalsh(out).min()>0
    assert m.a>=0 and m.b>=0 and m.a+m.b<1

def test_garch():
    r=RNG.normal(0,.01,110)
    x=(.008+np.abs(r))**2
    m=RealizedGARCH().fit(r,x,maxiter=55)
    assert m.predict(r,x)>0

def test_garch_invalid():
    with pytest.raises(ValueError):RealizedGARCH().fit(np.ones(200),np.zeros(200))

def test_hmm_causal_normalizes():
    x=RNG.normal(size=(90,2))
    model=GaussianHMM(2).fit(x[:70],max_iter=12)
    p=model.filter(x)
    assert p.shape==(90,2)
    assert np.allclose(p.sum(1),1)
    v=x.copy();v[80:]=400
    assert np.allclose(p[:80],model.filter(v)[:80])

def test_hsmm_duration():
    x=RNG.normal(size=(95,2))
    model=HiddenSemiMarkov(n_states=2,max_duration=8).fit(x[:75],maxiter=12)
    a=model.filter(x)
    assert np.allclose(a.sum(1),1,atol=1e-8)
    assert model.duration_pmf.shape==(2,8)

def test_bocpd_filter():
    x=RNG.normal(size=120)
    m=BOCPD(hazard=.04,max_run=35)
    a=m.filter(x)
    assert len(a['changepoint_probability'])==120
    assert np.all((a['changepoint_probability']>=0)&(a['changepoint_probability']<=1))
    assert np.isclose(a['last_run_probs'].sum(),1)

def test_bocpd_causality():
    x=RNG.normal(size=90)
    x2=x.copy();x2[-10:]=x2[-10:]+10
    assert np.allclose(BOCPD().filter(x)['changepoint_probability'][:-10],BOCPD().filter(x2)['changepoint_probability'][:-10])

def test_cross_section_slope():
    a=np.arange(80,dtype=float);b=a*.004
    theta,se,n=weekly_slope(a,b,np.ones(80,bool))
    assert theta>0 and n==80
    assert se>=0

def test_delayed_kalman_filters():
    d=[{'t':i*5,'date':str(i),'theta':float(i%4)/100,'theta_var':1e-3} for i in range(70)]
    model=DynamicAlpha(mu=.01,rho=.9,q=1e-3)
    orig=model.filter_delayed(d)
    new=[dict(x) for x in d];new[15]['theta']=1e4
    changed=model.filter_delayed(new)
    assert np.isclose(orig[15]['mean'],changed[15]['mean'])
    assert not np.isclose(orig[17]['mean'],changed[17]['mean'])

def test_dynamic_alpha_fit():
    y=RNG.normal(.002,.005,size=90)
    se=np.full(90,.0001)
    fit=DynamicAlpha().fit(y,se)
    assert 0<fit.rho<1 and fit.q>0

def test_soft_regime_alpha():
    n=100
    e=RNG.normal(size=(n,2));p=np.column_stack([np.ones(n)*.2,np.ones(n)*.8]);y=RNG.normal(0,.01,n)
    s=SoftRegimeAlpha().fit(e,p,y,np.ones(n)*.001,np.ones(n,bool))
    m,sd=s.predict(e[:10],p[:10]);assert m.shape==(10,) and np.all(sd>0)

def test_mature_mask():
    d=[{'t':1},{'t':10},{'t':20}]
    assert maturity_mask(d,16).tolist()==[True,True,False]

def test_no_overwrite(tmp_path):
    p=tmp_path/'result.json';_serial_write({'a':2},p)
    with pytest.raises(FileExistsError):_serial_write({'b':5},p)

def test_mpc_shapes_and_solver_dependency():
    from research.joint_risk_alpha.optimize import solve_mpc
    mu=np.zeros((2,3));scen=np.zeros((40,2,4));prev=np.zeros(3);beta=np.ones(3)
    try:import cvxpy
    except ImportError:
        with pytest.raises(RuntimeError,match='cvxpy'):solve_mpc(mu,scen,prev,.7,beta,0.)
    else:
        z=solve_mpc(mu,scen,prev,.7,beta,0.)
        assert np.all(z['gross_by_step']<=1.9+1e-5)

def test_particle_sv_posterior():
    from research.joint_risk_alpha.covariance import ParticleSV
    x=RNG.normal(0,.01,100)
    r=ParticleSV(particles=32,draws=12,burn=10,seed=17).fit_predict(x)
    assert r['mean']>0 and 0<=r['acceptance']<=1 and r['q95']>=r['q05']

def test_mpc_dro_nonnegative():
    from research.joint_risk_alpha.optimize import TradingPolicy
    assert TradingPolicy().wasserstein_radius>=0
