import unittest
import numpy as np
from research.nextgen.selection_bias.core import run, iid_sharpe_se

class SelectionBiasTests(unittest.TestCase):
    def test_reproducible(self):
        a=run(n_candidates=12,repetitions=120,seed=102)
        b=run(n_candidates=12,repetitions=120,seed=102)
        self.assertEqual(a,b)
    def test_no_search_has_nearly_zero_optimism(self):
        a=run(n_candidates=1,repetitions=600,seed=102)
        self.assertLess(abs(a['mean_selection_optimism']),.06)
    def test_search_causes_optimism(self):
        a=run(n_candidates=162,repetitions=150,strategy_correlation=.7,seed=104)
        self.assertGreater(a['mean_selection_optimism'],.3)
    def test_correlation_controls_search_bias(self):
        a=run(n_candidates=30,repetitions=200,strategy_correlation=0,seed=204)
        b=run(n_candidates=30,repetitions=200,strategy_correlation=.95,seed=204)
        self.assertGreater(a['mean_selection_optimism'],b['mean_selection_optimism']+.25)
    def test_selected_forward_unbiased_in_expectation(self):
        a=run(n_candidates=40,repetitions=450,strategy_correlation=.8,seed=1001)
        self.assertLess(abs(a['mean_selected_forward_sharpe']-.6),.08)
    def test_population_never_exceeds_one_in_normal_case(self):
        a=run(n_candidates=162,repetitions=200,strategy_correlation=.8,seed=22)
        self.assertLess(a['population_annual_sharpe'],1)
        self.assertGreater(a['fraction_selected_insample_above_threshold_but_population_below'],.3)
    def test_asymptotic_se_formula(self):
        self.assertAlmostEqual(iid_sharpe_se(.6,302),np.sqrt((52+.6**2/2)/302))
    def test_bad_inputs_fail_closed(self):
        for kw in [{'n_candidates':0},{'weeks':20},{'repetitions':50},
                   {'strategy_correlation':1.0},{'strategy_correlation':-0.1},
                   {'seed':-1},{'population_sharpe':np.nan},{'n_candidates':True}]:
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError):run(**kw)
        with self.assertRaises(ValueError):iid_sharpe_se(.6,2)
if __name__=='__main__':unittest.main()
