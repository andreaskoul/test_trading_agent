import unittest
import numpy as np
from research.nextgen.calibration.constrained import _true_utility,run_constrained

class TestConstrained(unittest.TestCase):
    def test_no_trade_zero_utility(self):
        z=np.zeros(4)
        S=np.eye(4)*.0001
        self.assertEqual(_true_utility(z,z,S,4.,z,0.,z,1e7,np.full(4,1e8)),0)
    def test_costs_penalize_positions(self):
        w=np.array([.1,-.1])
        mu=np.array([.001,-.001]); S=np.eye(2)*.0004
        a=_true_utility(w,mu,S,6.,np.zeros(2),0.,np.full(2,.02),1e7,np.full(2,5e8))
        b=_true_utility(w,mu,S,6.,np.full(2,.0003),.1,np.full(2,.02),1e7,np.full(2,5e8))
        self.assertGreater(a,b)
    def test_predeclared_small_smoke_reproducible(self):
        a=run_constrained(repetitions=20,seed=24)
        b=run_constrained(repetitions=20,seed=24)
        self.assertEqual(a,b)
    def test_integrated_constraints_vs_no_trade(self):
        z=run_constrained(repetitions=20,seed=26)
        self.assertEqual(len(z['results']),2)
        self.assertTrue(all(row['mean_raw_gross']<=.6+1e-7 for row in z['results']))
        self.assertTrue(all(row['mean_shrunk_gross']<=.6+1e-7 for row in z['results']))
    def test_bad_constrained_seed(self):
        with self.assertRaises(ValueError): run_constrained(repetitions=20,seed=-1)

    def test_nonpositive_ratio_and_invalid_params(self):
        with self.assertRaises(ValueError):run_constrained(ratios=(-1,),repetitions=20)
        with self.assertRaises(ValueError):run_constrained(repetitions=10)

if __name__=='__main__':unittest.main()
