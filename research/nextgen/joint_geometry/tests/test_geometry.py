import unittest
import numpy as np
from research.nextgen.joint_geometry.geometry import (spd,logm,expm,matrix_power,affine_distance,logeuclidean_distance,
                        bures_distance,frechet_mean,affine_geodesic,logeuclidean_geodesic,
                        bures_geodesic,ortho_columns,grassmann_distance,rbf_kernel_logspd,DiffusionMap)


class TestGeometry(unittest.TestCase):
    def setUp(self):
        self.rng=np.random.default_rng(7)
        def a(n):
            x=self.rng.normal(size=(n,n));return x@x.T+np.eye(n)*.6
        self.a,self.b=a(4),a(4)
    def assert_spd(self,a):
        self.assertLess(np.max(np.abs(a-a.T)),1e-9)
        self.assertGreater(np.linalg.eigvalsh(a).min(),0)
    def test_log_exponential_round_trip(self):
        np.testing.assert_allclose(expm(logm(self.a)),self.a,atol=1e-10)
    def test_power_inverse(self):
        s=matrix_power(self.a,.5)
        np.testing.assert_allclose(s@s,self.a,atol=1e-10)
    def test_geodesic_endpoints(self):
        for geo in (affine_geodesic,logeuclidean_geodesic,bures_geodesic):
            np.testing.assert_allclose(geo(self.a,self.b,0),self.a,atol=1e-7)
            np.testing.assert_allclose(geo(self.a,self.b,1),self.b,atol=1e-7)
    def test_geodesic_intermediate_positive(self):
        for geo in (affine_geodesic,logeuclidean_geodesic,bures_geodesic):self.assert_spd(geo(self.a,self.b,.45))
    def test_airm_congruence_invariant(self):
        p=self.rng.normal(size=(4,4))+np.eye(4)*3
        self.assertAlmostEqual(affine_distance(self.a,self.b),affine_distance(p@self.a@p.T,p@self.b@p.T),places=7)
    def test_log_euclidean_NOT_claim_congruence_invariant(self):
        p=np.diag([1.,3.,.7,2.])
        self.assertGreater(abs(logeuclidean_distance(self.a,self.b)-logeuclidean_distance(p@self.a@p.T,p@self.b@p.T)),1e-4)
    def test_distance_symmetry(self):
        for metric in (affine_distance,logeuclidean_distance,bures_distance):
            self.assertAlmostEqual(metric(self.a,self.b),metric(self.b,self.a),places=8)
    def test_frechet_per_metric(self):
        for m in ('logeuclidean','affine','bures'):
            x=frechet_mean(np.stack([self.a,self.b]),metric=m,maxiter=250)
            self.assert_spd(x)
    def test_two_equal_weights_affine_midpoint(self):
        mid=frechet_mean([self.a,self.b],metric='affine')
        np.testing.assert_allclose(mid,affine_geodesic(self.a,self.b,.5),rtol=1e-6,atol=1e-6)
    def test_grassmann_rotation_invariant(self):
        u=ortho_columns(self.rng.normal(size=(17,3)))
        r=ortho_columns(self.rng.normal(size=(3,3)))
        self.assertLess(grassmann_distance(u,u@r),1e-6)
    def test_grassmann_angle(self):
        u=np.eye(6)[:,:2];v=np.eye(6)[:,2:4]
        self.assertAlmostEqual(grassmann_distance(u,v),np.sqrt(2)*np.pi/2,places=7)
    def test_rbf_psd(self):
        x=[self.a,self.b,spd(self.a*.8+self.b*.2),spd(self.b*.5+self.a*.5)]
        k,bw=rbf_kernel_logspd(x)
        self.assertGreater(np.linalg.eigvalsh(k).min(),-1e-9)
        self.assertGreater(bw,0)
    def test_diffusion_train_nystrom(self):
        base=self.rng.normal(size=(4,4))
        matrices=[spd(self.a+.04*i*np.eye(4)+.05*np.sin(i)*self.b) for i in range(22)]
        f=DiffusionMap(dimension=2).fit(matrices)
        np.testing.assert_allclose(f.transform(matrices),f.embedding,atol=1e-6)
        self.assertEqual(f.transform(matrices[:3]).shape,(3,2))
    def test_diffusion_late_point_no_refit(self):
        x=[spd(self.a+i*.2*self.b) for i in np.linspace(0,1,30)]
        f=DiffusionMap(dimension=2).fit(x[:20]);a=f.embedding.copy()
        _=f.transform(x[20:])
        np.testing.assert_array_equal(a,f.embedding)
    def test_bad_cov_rejected(self):
        with self.assertRaises(ValueError):logm(np.zeros((3,4)))
    def test_bad_interpolation_rejected(self):
        with self.assertRaises(ValueError):affine_geodesic(self.a,self.b,1.4)

if __name__=='__main__':unittest.main()
