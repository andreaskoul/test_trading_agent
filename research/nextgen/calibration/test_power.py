import unittest
from scipy.stats import norm
from research.nextgen.calibration.power import power_projection

class TestPower(unittest.TestCase):
    def ref(self, **kw):
        a=dict(delta_sr=.050399043857478475,historical_se=.05402454118653946,
               historical_weeks=302,proposed_weeks=302,family_size=7)
        a.update(kw)
        return power_projection(**a)
    def test_l4_historical_inputs_roundtrip(self):
        x=self.ref()
        self.assertAlmostEqual(x['approximate_power'],.06461996162589222)
        self.assertAlmostEqual(x['required_weeks_at_target_power'],3759.790237518475)
    def test_one_comparison_requires_less_data(self):
        self.assertLess(self.ref(family_size=1)['required_weeks_at_target_power'],
                        self.ref(family_size=7)['required_weeks_at_target_power'])
    def test_power_grows_with_sample(self):
        self.assertLess(self.ref(proposed_weeks=43)['approximate_power'],
                        self.ref(proposed_weeks=302)['approximate_power'])
    def test_nonzero_effect_zero_power_limit(self):
        x=self.ref(delta_sr=1e-10)
        self.assertAlmostEqual(x['approximate_power'],.05/7,places=7)
    def test_invalid_inputs(self):
        for kw in ({'historical_se':0},{'delta_sr':-1},{'family_size':0},
                   {'proposed_weeks':1},{'one_sided_alpha':1},{'target_power':.1},
                   {'historical_se':float('nan')},{'family_size':3.5}):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError): self.ref(**kw)

if __name__=='__main__':unittest.main()
