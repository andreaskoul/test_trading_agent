"""Mathematical and causal unit tests; fixtures are not investment experiments."""
import unittest
from dataclasses import replace
from pathlib import Path
import numpy as np
from research.nextgen.joint_geometry.geometry import (probability_root,
    fisher_rao_distance,probability_hellinger_kernel,spd)
from research.nextgen.joint_geometry.alpha import FisherStateGP
from research.nextgen.joint_geometry.covariance import (baseline_factor_covariance,
    build_tape,weekly_origins)
from research.nextgen.joint_geometry.runner import hac_delta,parse_args
from research.nextgen.joint_state.contracts import RiskData


class TestInformationGeometry(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(73)
        self.prob=rng.dirichlet(np.ones(4),size=45)
        self.spd=np.stack([spd(np.diag([.4+.2*rng.random(),.2+.1*rng.random(),.3+.1*rng.random()])) for _ in range(90)])
    def test_fisher_sphere_normalisation(self):
        r=probability_root(self.prob)
        np.testing.assert_allclose((r*r).sum(1),1.,atol=1e-12)
    def test_rao_symmetry_and_identical(self):
        self.assertAlmostEqual(fisher_rao_distance(self.prob[0],self.prob[0]),0.,places=6)
        self.assertAlmostEqual(fisher_rao_distance(self.prob[0],self.prob[1]),
                               fisher_rao_distance(self.prob[1],self.prob[0]),places=12)
    def test_rao_orthogonal_corners(self):
        self.assertAlmostEqual(fisher_rao_distance([1,0],[0,1]),np.pi,places=10)
    def test_hellinger_mercer_psd(self):
        k=probability_hellinger_kernel(self.prob)
        self.assertGreaterEqual(np.linalg.eigvalsh(k).min(),-1e-8)
        np.testing.assert_allclose(k,np.transpose(k),atol=1e-13)
    def test_hellinger_invalid_simplex_fails(self):
        with self.assertRaises(ValueError):probability_root([-1,2])
    def test_fisher_gp_has_inductive_posterior(self):
        rng=np.random.default_rng(13)
        y=.001*rng.normal(size=90)
        m=FisherStateGP(k_states=2,dim=2).fit(self.spd[:72],np.zeros((72,1)),y[:72],np.ones(72)*.0002)
        first=m.predict(self.spd[72:74])[0]
        self.assertEqual(first.shape,(2,))
        self.assertTrue(np.isfinite(first).all())
        self.assertEqual(len(m.embedding.train),72) # test samples were not embedded into training
    def test_hac_rejects_uninformative_small_sample(self):
        with self.assertRaises(ValueError):hac_delta(np.zeros(5))
    def test_hac_sign_symmetry(self):
        a=hac_delta(np.arange(20,dtype=float)+.5,lags=4)
        b=hac_delta(-np.arange(20,dtype=float)-.5,lags=4)
        self.assertAlmostEqual(a['t'],-b['t'],places=12)
    def test_cli_no_network_options(self):
        args=parse_args(['check','--hf-cache','/tmp/hf.npz','--alpha-cache','/tmp/dev.npz'])
        self.assertEqual(args.command,'check')


class TestCausalRiskRisk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng=np.random.default_rng(8);T=800;n=14
        dates=np.datetime64('2016-01-04')+np.arange(T).astype('timedelta64[D]')
        intr=rng.normal(0,.003,size=(T,14,n))
        cls.d=RiskData(dates,np.array(['SPY']+[f'A{k}' for k in range(n-1)]),intr,
                       intr.sum(1),(intr*intr).sum(1),'fixture')
        cls.tape=build_tape(cls.d,basis_end='2016-06-01',rank=3)
    def test_basis_fitted_on_early_data_unchanged_by_later_returns(self):
        d=self.d;t=170;late=d.intraday.copy();late[t+1:]*=20
        changed=replace(d,intraday=late,daily=late.sum(1),realized=(late*late).sum(1))
        o=build_tape(changed,basis_end='2016-06-01',rank=3)
        np.testing.assert_allclose(self.tape.loading,o.loading,atol=1e-12)
    def test_recent_risk_forecasts_ignore_same_decision_day(self):
        t=440;future=self.tape.daily_spd.copy();future[t:]*=100
        from research.nextgen.joint_geometry.covariance import geometric_forecast
        a=geometric_forecast([self.tape.at(t-1-5*i) for i in range(4)],'affine')
        tape=replace(self.tape,daily_spd=future)
        b=geometric_forecast([tape.at(t-1-5*i) for i in range(4)],'affine')
        np.testing.assert_allclose(a,b,atol=0)
    def test_all_baseline_risk_models_return_spd(self):
        t=410
        for m in ('sample_cov','ewma_cov','heavy','realized_garch'):
            a=baseline_factor_covariance(self.tape,t,method=m,lookback=300)
            self.assertGreater(np.linalg.eigvalsh(a).min(),0)
    def test_input_quality_failure(self):
        with self.assertRaises(ValueError):baseline_factor_covariance(self.tape,200,lookback=252)

if __name__=='__main__':unittest.main()
