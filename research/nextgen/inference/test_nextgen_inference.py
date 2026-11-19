import unittest
import numpy as np
from research.nextgen.inference.core import paired_sharpe_block_ci, holm_adjust, _circular_indices

class TestInference(unittest.TestCase):
    def sample(self):
        rng=np.random.default_rng(20261119)
        a=rng.normal(.003,.018,104)
        b=rng.normal(.001,.02,104)
        cash=np.full(104,.0006)
        return a,b,cash
    def test_equal_returns_have_zero_difference(self):
        a,_,c=self.sample()
        r=paired_sharpe_block_ci(a,a,c,draws=200,seed=4)
        self.assertAlmostEqual(r['difference'],0)
        self.assertAlmostEqual(r['lower'],0)
        self.assertAlmostEqual(r['upper'],0)
    def test_reproducible(self):
        a,b,c=self.sample()
        x=paired_sharpe_block_ci(a,b,c,draws=201,seed=101)
        y=paired_sharpe_block_ci(a,b,c,draws=201,seed=101)
        self.assertEqual(x,y)
        self.assertTrue(x['lower']<=x['upper'])
    def test_paired_block_structure(self):
        rng=np.random.default_rng(42)
        idx=_circular_indices(100,5,rng)
        self.assertEqual(len(idx),100)
        self.assertTrue(np.all((np.diff(idx.reshape(-1,5),axis=1)%100)==1))
    def test_invalid_inputs_fail_closed(self):
        a,b,c=self.sample()
        for opts in [dict(draws=199),dict(block_length=27),dict(confidence=1.),dict(periods_per_year=0),dict(seed=-3)]:
            with self.subTest(opts=opts):
                with self.assertRaises(ValueError):paired_sharpe_block_ci(a,b,c,**opts)
        with self.assertRaises(ValueError):paired_sharpe_block_ci(a,b[:-1],c)
        with self.assertRaises(ValueError):paired_sharpe_block_ci(a,b,np.full(104,np.nan))
        with self.assertRaises(ValueError):paired_sharpe_block_ci(a,b,np.full(104,-1.0))
    def test_holm_known_example(self):
        # sorted [.01, .03, .04, .10] -> [.04, .09, .09, .10]
        actual=holm_adjust([.03,.1,.01,.04])
        np.testing.assert_allclose(actual,[.09,.10,.04,.09],atol=1e-15)
    def test_holm_monotonic_sorted(self):
        rng=np.random.default_rng(12)
        p=rng.uniform(size=20)
        a=holm_adjust(p)
        self.assertTrue(np.all(a>=p))
        self.assertTrue(np.all(a<=1))
        self.assertTrue(np.all(np.diff(a[np.argsort(p)])>=-1e-12))
    def test_holm_invalid(self):
        for p in [[],[.01,np.nan],[1.01],[.01,-.1],[[.01,.02]]]:
            with self.assertRaises(ValueError):holm_adjust(p)
if __name__=='__main__':unittest.main()
