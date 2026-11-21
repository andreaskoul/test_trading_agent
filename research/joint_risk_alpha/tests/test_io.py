"""File schema, point-in-time and source-integrity tests (engineering only)."""
import numpy as np
import pandas as pd
import pytest
from research.joint_risk_alpha.io import read_hf,read_alpha,origin_grid,digest,hf_daily_returns


def test_hf_trims_future_without_writing(tmp_path):
    S=pd.bdate_range('2018-01-01','2020-03-01')
    n=7;R=np.ones((len(S),14,n),dtype='float32')*.001
    p=tmp_path/'hf.npz'
    np.savez(p,S=S.values,names=np.array(['SPY']+[f'X{i}' for i in range(n-1)]),R=R,rv=np.sum(R*R,axis=1))
    sha=digest(p)
    z=read_hf(p)
    assert z.dates[-1]==pd.Timestamp('2019-12-31')
    assert len(z.dates)==np.sum(S<=pd.Timestamp('2019-12-31'))
    assert z.source_sha256==sha==digest(p)
    assert hf_daily_returns(z).shape==(len(z.dates),n)


def test_hf_no_spy(tmp_path):
    S=pd.bdate_range('2018-01-01','2018-12-31');R=np.ones((len(S),14,2))
    p=tmp_path/'bad.npz';np.savez(p,S=S.values,names=np.array(['A','B']),R=R,rv=(R*R).sum(1))
    with pytest.raises(ValueError,match='SPY'):read_hf(p)


def test_hf_no_pit_future_origin(tmp_path):
    S=pd.bdate_range('2018-01-01','2019-12-31');R=np.ones((len(S),14,2))
    p=tmp_path/'hf.npz';np.savez(p,S=S.values,names=np.array(['SPY','X']),R=R,rv=(R*R).sum(1))
    z=read_hf(p);orig=origin_grid(z,first='2019-11-01',last='2019-12-31',horizon=5)
    assert all(t+5<len(z.dates) for t in orig)


def test_alpha_rejects_reused_return_year(tmp_path):
    S=pd.bdate_range('2018-01-01','2020-03-01');T=len(S);N=4
    a=dict(S=S.values,names=np.array(['A','B','C','D']),master_h5_ref=np.ones((T,N)),
           y5=np.ones((T,N)),elig=np.ones((T,N),bool),Z=np.ones((T,N,2)),
           r=np.ones((T,N)),rm=np.ones(T))
    p=tmp_path/'dev.npz';np.savez(p,**a)
    with pytest.raises(ValueError,match='non-development'):read_alpha(p)


def test_duplicate_names_fail(tmp_path):
    S=pd.bdate_range('2018-01-01','2019-12-31');R=np.ones((len(S),14,2))
    p=tmp_path/'hf.npz';np.savez(p,S=S.values,names=np.array(['SPY','SPY']),R=R,rv=(R*R).sum(1))
    with pytest.raises(ValueError,match='duplicate'):read_hf(p)
