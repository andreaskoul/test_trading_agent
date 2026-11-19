import unittest
from research.nextgen.selection_bias.core import run
from research.nextgen.selection_bias.reproduce import produce

class ReproducibilityTests(unittest.TestCase):
    def test_fixed_design_matches_reference_call(self):
        # Small independent smoke check of the configuration semantics; full
        # 3 * 1000 Monte Carlo repetitions are executed by reproduce.py.
        actual=run(n_candidates=162,weeks=302,repetitions=100,
                   strategy_correlation=.8,population_sharpe=.6,
                   screening_threshold=1.0,seed=20261119)
        self.assertEqual(actual['n_candidates'],162)
        self.assertEqual(actual['weeks_per_period'],302)
        self.assertLess(actual['mean_selected_forward_sharpe'],1.0)
if __name__=='__main__':unittest.main()
