import unittest
import math
from research.nextgen.funding_sensitivity.reproduce import sensitivity

class PublishedReferenceSensitivityTests(unittest.TestCase):
    def reference(self):
        return {'summary':{'B0':{'sharpe':.9369462404420277,'vol_pct':22.37378782545176}}}
    def test_constant_state_sensitivity(self):
        x=sensitivity(self.reference())
        self.assertEqual(len(x['scenarios']),8)
        self.assertAlmostEqual(x['scenarios'][2]['incremental_annual_cost_percent'],1.875)
        self.assertAlmostEqual(x['scenarios'][2]['fixed_vol_legacy_ratio_approx'],.8531428176766139)
        self.assertAlmostEqual(x['extra_return_pct_to_reach_raw_ratio_1_at_fixed_vol'],1.4107514379471238)
    def test_downtrend_scenario_without_cost(self):
        x=sensitivity(self.reference())
        for r in x['scenarios'][4:]:
            self.assertAlmostEqual(r['incremental_annual_cost_percent'],0)
    def test_invalid_reference_fail_closed(self):
        with self.assertRaises(ValueError):sensitivity({'summary':{'B0':{'sharpe':.94,'vol_pct':float('nan')}}})
        with self.assertRaises(ValueError):sensitivity({'summary':{'B0':{'sharpe':.94,'vol_pct':0}}})

if __name__=='__main__':unittest.main()
