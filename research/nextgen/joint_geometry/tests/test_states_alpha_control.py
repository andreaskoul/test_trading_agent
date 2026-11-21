import unittest
import numpy as np
from research.nextgen.joint_geometry.geometry import spd
from research.nextgen.joint_geometry.states import AIRMRegime,DiffusionRegime,gras_drift,states_trial
from research.nextgen.joint_geometry.alpha import ManifoldGP,GeometricAlphaPanel,alpha_geometry_trial
from research.nextgen.joint_geometry.control import spd_ambiguity,posterior_paths,asset_covariance
from research.nextgen.joint_geometry.covariance import build_tape,CovarianceTape
from research.nextgen.joint_state.contracts import RiskData


class TestStatesAlphaControl(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(53)
        self.mats=np.stack([spd(np.diag([.3+(.1 if i>=40 else 0)+.015*rng.random(),.5+.08*rng.random(),.4+.03*rng.random()])) for i in range(110)])
        self.rot=rng.uniform(.01,.2,len(self.mats))
        self.y=.05+.2*np.array([np.trace(z) for z in self.mats])
        self.market=rng.normal(size=(110,5))
    def test_airm_state_probabilities(self):
        m=AIRMRegime(k=2,maxiter=3).fit(self.mats[:80],self.y[:80]);p,val=m.step(self.mats[80]);self.assertAlmostEqual(p.sum(),1)
        self.assertGreater(val,0)
    def test_affine_state_rotation_invariant(self):
        rng=np.random.default_rng(7);q,_=np.linalg.qr(rng.normal(size=(3,3)))
        train=np.stack([q.T@x@q for x in self.mats[:80]])
        m=AIRMRegime(k=2,maxiter=3).fit(self.mats[:80],self.y[:80])
        n=AIRMRegime(k=2,maxiter=3).fit(train,self.y[:80])
        p,_=m.step(self.mats[84]);p2,_=n.step(q.T@self.mats[84]@q)
        np.testing.assert_allclose(p,p2,atol=5e-4)
    def test_diffusion_hmm_positive_risk(self):
        model=DiffusionRegime(k=2,dim=2).fit(self.mats[:80],self.rot[:80],self.y[:80]);post,v,p=model.state(self.mats[80],self.rot[80])
        self.assertAlmostEqual(p.sum(),1);self.assertGreater(v,0)
        self.assertAlmostEqual(post.sum(),1)
    def test_state_future_no_change_to_trained_map(self):
        m=DiffusionRegime(k=2,dim=2).fit(self.mats[:80],self.rot[:80],self.y[:80]);past=m.embedding.embedding.copy()
        m.state(self.mats[100],self.rot[100]);np.testing.assert_array_equal(m.embedding.embedding,past)
    def test_manifold_gp_logspd_predicts_uncertainty(self):
        m=ManifoldGP('logspd').fit(self.mats[:80],self.market[:80],self.y[:80],np.full(80,.02))
        pred,var=m.predict(self.mats[80],self.market[80]);self.assertEqual(pred.shape,(1,))
        self.assertGreater(var[0],0)
    def test_gp_macro_and_diffusion(self):
        for kind in ('logspd_plus_macro','diffusion'):
            m=ManifoldGP(kind,dim=2).fit(self.mats[:80],self.market[:80],self.y[:80],np.full(80,.01))
            _,var=m.predict(self.mats[80:82],self.market[80:82]);self.assertTrue((var>0).all())
    def test_alpha_trial_requires_valid_cutoff(self):
        dates=np.datetime64('2016-01-01')+np.arange(110).astype('timedelta64[7D]')
        panel=GeometricAlphaPanel(dates,dates+np.timedelta64(7,'D'),self.y,np.ones(110)*.01,self.mats,self.market,np.arange(110),np.ones(110))
        with self.assertRaises(ValueError):alpha_geometry_trial(panel,start='2020-01-01',end='2022-01-01')
    def test_posterior_path_dimensions_and_determinism(self):
        f=np.eye(3);diag=np.ones(3)*.0001
        g=spd_ambiguity(self.mats[:15],metric='affine')
        a=posterior_paths(np.zeros(3),f,diag,g,scenarios=51,horizon=3,seed=11)
        b=posterior_paths(np.zeros(3),f,diag,g,scenarios=51,horizon=3,seed=11)
        self.assertEqual(a.shape,(51,3,3));np.testing.assert_array_equal(a,b)
    def test_uncertainty_set_positive(self):
        for kind in ('affine','logeuclidean','bures'):
            mats=spd_ambiguity(self.mats[:40],metric=kind)
            self.assertTrue(all(np.linalg.eigvalsh(z).min()>0 for z in mats))
    def test_asset_covariance_exposure(self):
        b=np.random.default_rng(43).normal(size=(9,3));d=np.ones(9)*.02
        full=asset_covariance(self.mats[4],b,d)
        self.assertGreater(np.linalg.eigvalsh(full).min(),0)
    def test_future_changes_leave_ambiguity_same(self):
        a=spd_ambiguity(self.mats[:30]);new=self.mats.copy();new[30:]*=13
        b=spd_ambiguity(new[:30]);np.testing.assert_array_equal(a,b)
    def test_invalid_future_input(self):
        with self.assertRaises(ValueError):spd_ambiguity(self.mats[:2])

if __name__=='__main__':unittest.main()
