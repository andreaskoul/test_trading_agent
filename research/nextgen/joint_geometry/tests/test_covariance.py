import unittest
from dataclasses import replace
import numpy as np
from research.nextgen.joint_geometry.covariance import CovarianceTape,build_tape,weekly_origins,geometric_forecast,predictive_loss,rolling_geometric_eval,train_spdnet
from research.nextgen.joint_state.contracts import RiskData

class TestCovariance(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(21);n=18;T=760
        dates=np.datetime64('2016-01-04')+np.arange(T).astype('timedelta64[D]')
        intr=rng.normal(0,.0025,size=(T,14,n))
        intr[:,0,:]*=1.7
        daily=intr.sum(1);rv=(intr**2).sum(1)
        self.d=RiskData(dates,np.array(['SPY']+[f'A{i}' for i in range(1,n)]),intr,daily,rv,'fake-risk-sha')
        self.tape=build_tape(self.d,basis_end='2016-04-30',rank=3)
    def test_fixed_basis(self):
        w=self.tape;np.testing.assert_allclose(w.loading.T@w.loading,np.eye(3),atol=1e-9)
    def test_spd_daily(self):
        self.assertGreater(np.linalg.eigvalsh(self.tape.at(150)).min(),0)
    def test_future_target_is_not_current(self):
        a=self.tape.target(200);b=self.tape.at(200)
        self.assertGreater(np.linalg.norm(a-b),0)
    def test_future_target_unmatured_fails(self):
        with self.assertRaises(ValueError):self.tape.target(len(self.tape.dates)-2)
    def test_geometric_mean_valid(self):
        x=[self.tape.at(t) for t in (140,145,150,155,160)]
        for m in ['euclidean','affine','logeuclidean','bures']:
            self.assertGreater(np.linalg.eigvalsh(geometric_forecast(x,m)).min(),0)
    def test_loss_zero_if_equal(self):
        a=self.tape.at(140);self.assertAlmostEqual(predictive_loss(a,a),0,places=7)
    def test_loss_positive_for_wrong(self):
        a=self.tape.at(140);self.assertGreater(predictive_loss(a,2*a),0)
    def test_loss_factor_basis_rotation_invariant(self):
        a,b=self.tape.at(140),self.tape.at(145)
        rng=np.random.default_rng(9);q,_=np.linalg.qr(rng.normal(size=(3,3)))
        self.assertAlmostEqual(predictive_loss(a,b),predictive_loss(q.T@a@q,q.T@b@q),places=8)
    def test_origin_only_future_complete(self):
        x=weekly_origins(self.tape,first='2016-05-01',last='2017-03-01')
        self.assertTrue(all(t+5<len(self.tape.dates) for t in x))
    def test_future_mutation_does_not_change_past_forecast(self):
        t=170
        x=[self.tape.at(t-20),self.tape.at(t-15),self.tape.at(t-10),self.tape.at(t-5),self.tape.at(t)]
        prior=geometric_forecast(x)
        tt=replace(self.tape,daily_spd=self.tape.daily_spd.copy())
        tt.daily_spd[t+1:]*=100
        np.testing.assert_array_equal(prior,geometric_forecast([tt.at(t-20),tt.at(t-15),tt.at(t-10),tt.at(t-5),tt.at(t)]))
    def test_spdnet_smoke(self):
        try:import torch
        except ImportError:self.skipTest('torch optional')
        # Use longer original fixture to ensure >35 Thursday origins.
        t=train_spdnet(self.tape,train_cutoff='2017-06-01',dim=2,lookback=3,epochs=7,seeds=(11,),patience=3)
        seq=np.stack([self.tape.at(196),self.tape.at(201),self.tape.at(206)])
        pred=t['predict'](seq)
        self.assertGreater(np.linalg.eigvalsh(pred).min(),0)

if __name__=='__main__':unittest.main()
