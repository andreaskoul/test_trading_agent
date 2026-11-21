import numpy as np
import pytest
from research.nextgen.coupled_risk import models as M
from research.nextgen.coupled_risk import adapters as A
from research.nextgen.coupled_risk import runner as U

@pytest.fixture(scope='module')
def panel():
    rng=np.random.default_rng(5)
    t,n,k=85,14,3
    fac=rng.standard_normal((t,14,k))*0.009
    daily=fac.sum(1)
    rv=M.realized_from_intraday(fac)
    return daily,rv,fac


def test_realized_shape_psd(panel):
    x,rv,f=panel
    assert rv.shape==(85,3,3)
    assert np.min(np.linalg.eigvalsh(rv))>=-1e-14


def test_covariance_is_psd():
    x=np.array([[1,4],[4,1.]],float)
    h=M.pdmat(x)
    assert np.linalg.eigvalsh(h).min()>0
    assert np.allclose(h,h.T)


def test_missing_data_fails(panel):
    x,rv,_=panel
    x=x.copy();x[0,0]=np.nan
    with pytest.raises(ValueError): M.validate(x,rv)


def test_mismatched_covariance_fails(panel):
    x,rv,_=panel
    with pytest.raises(ValueError): M.validate(x,rv[:20])


def test_negative_realized_eigenvalue_fails(panel):
    x,rv,_=panel
    rv=rv.copy();rv[0,0,0]=-1.0
    with pytest.raises(ValueError): M.validate(x,rv)


def test_student_covariance_consistent(panel):
    x,rv,_=panel
    h=M.pdmat(np.cov(x,rowvar=False))
    assert np.isfinite(M.student_loss(x[-1],h,7))
    assert np.isfinite(M.normal_loss(x[-1],h))


def test_matrix_heavy_recursion(panel):
    x,rv,_=panel
    z=M.heavy_matrix(x,rv,fit=False,a=.2,b=.7)
    assert z['trace'].shape==(len(x),3,3)
    assert np.allclose(z['trace'][0],M.pdmat(rv.mean(0)))
    assert np.linalg.eigvalsh(z['covariance']).min()>0
    assert z['parameters']['a']==.2


def test_heavy_fit(panel):
    x,rv,_=panel
    z=M.heavy_matrix(x,rv,fit=True,maxiter=40)
    assert np.isfinite(z['neg_log_likelihood'])
    assert z['parameters']['a']+z['parameters']['b']<1


def test_dcc_spd(panel):
    x,rv,_=panel
    z=M.dcc_factor(x,rv,fit=False)
    assert np.linalg.eigvalsh(z['covariance']).min()>0
    assert z['trace'].shape==(85,3,3)


def test_dcc_fit(panel):
    x,rv,_=panel
    z=M.dcc_factor(x,rv,fit=True,maxiter=25)
    assert np.isfinite(z['neg_log_likelihood'])


def test_student_robust_filter(panel):
    x,rv,_=panel
    z=M.robust_score_covariance(x,rv,fit=False)
    assert np.linalg.eigvalsh(z['covariance']).min()>0


def test_student_robust_fit(panel):
    x,rv,_=panel
    z=M.robust_score_covariance(x,rv,fit=True,maxiter=30)
    assert np.isfinite(z['neg_log_likelihood'])


def test_particle_reproducible(panel):
    x,rv,_=panel
    q=dict(particles=64,phi_grid=(.97,),q_grid=(.2,),seed=123)
    a=M.joint_particle_sv(x,rv,**q)
    b=M.joint_particle_sv(x,rv,**q)
    assert np.array_equal(a['covariance'],b['covariance'])
    assert np.linalg.eigvalsh(a['covariance']).min()>0
    assert len(a['parameters']['model_weights'])==1


def test_particle_model_average_normalized(panel):
    x,rv,_=panel
    z=M.joint_particle_sv(x,rv,particles=64,phi_grid=(.9,.97),q_grid=(.15,.3),seed=22)
    assert abs(sum(a['weight'] for a in z['parameters']['model_weights'])-1)<1e-12


def test_invalid_particles_fails(panel):
    x,rv,_=panel
    with pytest.raises(ValueError):M.joint_particle_sv(x,rv,particles=32)


def test_resample_valid():
    rng=np.random.default_rng(7)
    ix=M.systematic_resampling(np.array([.1,.2,.7]),rng)
    assert len(ix)==3 and np.max(ix)==2 and np.min(ix)>=0


def test_future_data_cannot_change_same_forecast(panel):
    x,rv,_=panel
    first=M.heavy_matrix(x[:70],rv[:70],fit=False)['covariance']
    x2=x.copy();x2[70:]=5.
    rv2=rv.copy();rv2[70:]*=1000
    second=M.heavy_matrix(x2[:70],rv2[:70],fit=False)['covariance']
    assert np.array_equal(first,second)


def test_hac_short_series_no_significance():
    z=U.paired_hac([1.,1.,1.])
    assert z['t'] is None


def test_matched_date_refuses_cherry_pick():
    a=[dict(date='2018-01-04',model='poet',portfolio='market_spy',qlike=.3),
       dict(date='2018-01-11',model='poet',portfolio='market_spy',qlike=.4),
       dict(date='2018-01-04',model='dcc',portfolio='market_spy',qlike=.2)]
    with pytest.raises(ValueError,match='differ'):U.compare(a)


def test_poe_psd():
    rng=np.random.default_rng(5)
    res=A.poe_residual(rng.normal(size=(50,20)))
    assert np.linalg.eigvalsh(res).min()>0


def test_qlike_loss_minimized_when_correct():
    assert abs(A.qlike(.05,.05))<1e-14
    assert A.qlike(.05,.1)>0


def test_alpha_dev_date_only(tmp_path):
    d=np.arange(np.datetime64('2018-01-01'),np.datetime64('2018-08-01'))
    n=np.array(['SPY','AAA','BBB'])
    path=tmp_path/'alpha.npz'
    np.savez(path,S=d,names=n,master_h5_ref=np.zeros((len(d),3)),elig=np.ones((len(d),3),bool))
    a=A.load_alpha(path)
    assert a.dates[-1]<np.datetime64('2020-01-01')


def test_alpha_post_2019_fails(tmp_path):
    d=np.arange(np.datetime64('2020-01-01'),np.datetime64('2020-08-01'))
    n=np.array(['SPY','AAA'])
    path=tmp_path/'alpha.npz'
    np.savez(path,S=d,names=n,master_h5_ref=np.zeros((len(d),2)),elig=np.ones((len(d),2),bool))
    with pytest.raises(ValueError,match='post-2019'):A.load_alpha(path)


def test_risk_post_2019_is_truncated(tmp_path):
    dates=np.arange(np.datetime64('2019-01-01'),np.datetime64('2020-03-01'))
    n=np.array(['SPY','AAA','BBB'])
    z=np.ones((len(dates),14,3))*0.001
    path=tmp_path/'risk.npz'
    np.savez(path,S=dates,names=n,R=z,rv=(z*z).sum(1))
    a=A.load_risk(path)
    assert np.max(a.dates)<=np.datetime64('2019-12-31')


def test_reject_out_inside_input(tmp_path):
    src=tmp_path/'source.npz'
    src.write_bytes(b'xx')
    with pytest.raises(ValueError): A.safe_new_dir(tmp_path/'new',(tmp_path,src))


def test_report_no_strategy_sharpe_fixture():
    assert U.MODELS==('poet','matrix_heavy','dcc','t_score','particle_sv')
