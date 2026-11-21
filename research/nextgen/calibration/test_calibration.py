import unittest
import numpy as np
from research.nextgen.calibration.core import characterize,realized_utility,simulate

class TestCalibration(unittest.TestCase):
    def example(self):
        mu=np.array([1.,-1.])
        S=np.diag([2.,.5])
        O=np.eye(2)*.5
        return mu,S,O

    def test_formula_unshrunk_and_oracle_regret(self):
        m,S,O=self.example()
        x=characterize(m,S,O,4.)
        A=m@np.linalg.solve(S,m)
        B=np.trace(np.linalg.solve(S,O))
        self.assertAlmostEqual(x.signal_strength,A)
        self.assertAlmostEqual(x.forecast_noise_strength,B)
        self.assertAlmostEqual(x.predicted_unshrunk_regret,B/8)
        self.assertAlmostEqual(x.unshrunk_expected_utility,(A-B)/8)

    def test_shrink_exact_solution(self):
        m,S,O=self.example()
        x=characterize(m,S,O,4.)
        self.assertAlmostEqual(x.optimal_shrink,x.signal_strength/(x.signal_strength+x.forecast_noise_strength))
        self.assertGreaterEqual(x.shrunk_expected_utility,x.unshrunk_expected_utility)
        self.assertGreaterEqual(x.shrunk_expected_utility,0)

    def test_bad_covariance_rejected(self):
        m,S,O=self.example()
        S[0,0]=-1.
        with self.assertRaises(ValueError):characterize(m,S,O)

    def test_non_psd_forecast_noise_rejected(self):
        m,S,O=self.example()
        O[0,0]=-1.
        with self.assertRaises(ValueError):characterize(m,S,O)

    def test_zero_signal_shrinks_to_cash(self):
        m,S,O=self.example()
        x=characterize(np.zeros_like(m),S,O)
        self.assertEqual(x.optimal_shrink,0)
        self.assertEqual(x.shrunk_expected_utility,0)

    def test_zero_noise_full_confidence(self):
        m,S,_=self.example()
        x=characterize(m,S,np.zeros_like(S))
        self.assertEqual(x.optimal_shrink,1)
        self.assertAlmostEqual(x.shrunk_expected_utility,x.oracle_utility)

    def test_forecast_error_small_eigenvalue_direction(self):
        m=np.array([1.,1.])
        S=np.diag([1.,.01])
        O_a=np.diag([.01,0])
        O_b=np.diag([0,.01])
        a=characterize(m,S,O_a)
        b=characterize(m,S,O_b)
        self.assertAlmostEqual(b.forecast_noise_strength/a.forecast_noise_strength,100)

    def test_realized_utility(self):
        m,S,_=self.example()
        w=np.linalg.solve(S,m)/4
        self.assertAlmostEqual(realized_utility(m,S,w,4),characterize(m,S,np.zeros_like(S),4).oracle_utility)

    def test_mc_agrees_with_analytic_within_six_se(self):
        r=simulate(ratios=(0.25,1.,4.),draws=2000,seed=38,n_assets=12)
        for x in r['per_ratio']:
            for mode in ('unshrunk','shrunk'):
                diff=abs(x['theory_'+mode+'_utility']-x['mc_'+mode+'_utility'])
                self.assertLess(diff,6*x['mc_se_'+mode]+1e-10)

    def test_ordered_shrink_coefficients(self):
        z=simulate(draws=500,seed=3)
        a=z['per_ratio']
        self.assertEqual([x['noise_to_signal'] for x in a],[.25,1.,4.,16.])
        self.assertTrue(all(a[i]['theoretical_optimal_shrink']>a[i+1]['theoretical_optimal_shrink'] for i in range(3)))
        self.assertTrue(all(x['mc_shrunk_utility']>x['mc_unshrunk_utility'] for x in a))

    def test_bad_matrix_symmetry_and_shape(self):
        m,S,O=self.example()
        with self.assertRaises(ValueError): characterize(m,S[:1,:1],O)
        S[0,1]=.1
        with self.assertRaises(ValueError): characterize(m,S,O)
        m,S,O=self.example()
        O[0,1]=.1
        with self.assertRaises(ValueError): characterize(m,S,O)

    def test_zero_signal_zero_noise(self):
        m,S,O=self.example()
        z=characterize(np.zeros_like(m),S,np.zeros_like(O))
        self.assertEqual(z.optimal_shrink,0)
        self.assertEqual(z.forecast_noise_strength,0)

    def test_realized_invalid_inputs(self):
        m,S,O=self.example()
        with self.assertRaises(ValueError): realized_utility(m,S,[0.],5)
        with self.assertRaises(ValueError): realized_utility(m,S,[1.,0.],0)
        with self.assertRaises(ValueError): simulate(n_assets=1)

    def test_invalid_inputs_fail_closed(self):
        m,S,O=self.example()
        with self.assertRaises(ValueError):characterize(m,S,O,risk_aversion=0)
        with self.assertRaises(ValueError):characterize([float('nan')],[[1]],[[1]])
        with self.assertRaises(ValueError):simulate(draws=100)
        with self.assertRaises(ValueError):simulate(ratios=(-1,))
        with self.assertRaises(ValueError):simulate(seed=-1)

if __name__=='__main__':unittest.main()
