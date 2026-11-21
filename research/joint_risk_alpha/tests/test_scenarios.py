"""Contract tests; mock prices are never claimed as empirical investment results."""
import numpy as np
import pytest
from research.joint_risk_alpha.scenarios import sample_multivariate_t,validate_forecast_asof,build_bundle


def test_sampling_shapes_and_mean():
    m=np.zeros((3,5));C=np.eye(5)*.0001
    r=sample_multivariate_t(m,C,scenarios=300,seed=22)
    assert r.shape==(300,3,5)
    assert np.isfinite(r).all()
    assert abs(r.mean())<.002


def test_sampling_no_invalid_uncertainty():
    m=np.zeros((2,4));C=np.eye(4)
    with pytest.raises(ValueError):sample_multivariate_t(m,C,20,posterior_std=-np.ones((2,4)))


def test_metadata_date_gate():
    validate_forecast_asof('2018-11-01','2018-10-20','2018-10-19')
    with pytest.raises(ValueError,match='after forecast'):validate_forecast_asof('2018-11-01','2018-11-02','2018-10-19')
    with pytest.raises(ValueError,match='2020'):validate_forecast_asof('2020-10-01','2019-10-02','2019-10-03')


def test_bundle_atomic_no_overwrite(tmp_path):
    H,N=2,3
    data=dict(mu=np.zeros((H,N+1)),cov=np.eye(N+1)*1e-4,
              previous=np.zeros(N),beta=np.ones(N),core=np.array(.7),hedge_prev=np.array(0.),
              alpha_std=np.ones((H,N+1))*.001,asof=np.array('2019-06-01'),
              fit_end=np.array('2019-05-15'),label_maturity_end=np.array('2019-05-14'))
    src=tmp_path/'forecast.npz';np.savez_compressed(src,**data)
    dest=tmp_path/'scenarios.npz'
    out=build_bundle(src,dest,scenarios=40)
    assert out['N_stocks']==N
    with np.load(dest,allow_pickle=False) as z:
        assert z['scenarios'].shape==(40,H,N+1)
    with pytest.raises(FileExistsError):build_bundle(src,dest,scenarios=40)
