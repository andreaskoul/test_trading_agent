import numpy as np
import pytest
from research.joint_risk_alpha.evaluation import nw_mean,paired_losses


def test_hac_constant_zero_uncertainty():
    assert nw_mean(np.zeros(50),lags=4)['t'] is None


def test_hac_numeric_iid():
    x=np.array([1.,-1.]*30)
    z=nw_mean(x,lags=0)
    assert np.isclose(z['se'],1/np.sqrt(60))


def test_paired_alignment():
    dates=['2018-01-01']*8+['2019-01-01']*8
    r=paired_losses(dates,np.ones(16),np.zeros(16),lags=2)
    assert r['mean']==1. and r['n']==16
    assert r['by_year']=={'2018':1.,'2019':1.}


def test_paired_missing_fails():
    with pytest.raises(ValueError):paired_losses(['2019']*12,np.zeros(12),np.full(12,np.nan))
