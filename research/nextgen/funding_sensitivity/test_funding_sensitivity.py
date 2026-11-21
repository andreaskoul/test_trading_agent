import unittest
from dataclasses import replace
import numpy as np
from research.nextgen.funding_sensitivity.core import FundingScenario, evaluate, fixed_vol_sharpe_shift

class FundingStressTests(unittest.TestCase):
    def simple(self, core=1.3, rates=(0.,0.), margin=.0625, legacy=.0625):
        sc=FundingScenario(margin_rate=margin,legacy_margin_rate=legacy,
                           days=7,stock_borrow_rates=rates,stock_shortable=(True,True))
        return evaluate(core,[.3,-.3],[1,1],sc)

    def test_benchmark_uptrend_financing_gap(self):
        a=self.simple()
        self.assertAlmostEqual(a['net_spy_position'],1.3)
        self.assertAlmostEqual(a['gross_nav'],1.9)
        self.assertAlmostEqual(a['legacy_net_debit_nav'],.3)
        self.assertAlmostEqual(a['segregated_short_debit_nav'],.6)
        self.assertAlmostEqual(a['extra_cost_nav_per_360d_fixed_holdings'],.01875)

    def test_downtrend_core_no_incremental_debit(self):
        a=self.simple(core=.7)
        self.assertAlmostEqual(a['segregated_short_debit_nav'],0)
        self.assertAlmostEqual(a['legacy_net_debit_nav'],0)
        self.assertAlmostEqual(a['extra_cost_nav_period'],0)

    def test_nonzero_beta_hedge_consistent(self):
        sc=FundingScenario(.0625,.0625,7,(0.,0.),(True,True))
        a=evaluate(1.3,[.3,-.3],[1.2,.8],sc)
        self.assertAlmostEqual(a['spy_beta_hedge'],-.12)
        self.assertAlmostEqual(a['gross_nav'],1.78)
        self.assertAlmostEqual(a['financing_debit_gap_nav'],.3)

    def test_shortability_fails_closed(self):
        sc=FundingScenario(.0625,.0625,7,(0.,0.),(True,False))
        with self.assertRaisesRegex(ValueError,'unavailable short'):
            evaluate(1.3,[.3,-.3],[1,1],sc)

    def test_spy_shortability_fails_closed(self):
        sc=FundingScenario(.0625,.0625,7,(0.,0.),(True,True),spy_shortable=False)
        with self.assertRaisesRegex(ValueError,'unavailable short SPY'):
            evaluate(.1,[.3,-.3],[4.,0.],sc)

    def test_borrow_cost_and_rebate_not_same_instrument(self):
        sc=FundingScenario(.0625,.0625,7,(0.,.03),(True,True),short_rebate_rate=.01)
        a=evaluate(1.3,[.3,-.3],[1.,1.],sc)
        self.assertAlmostEqual(a['scenario_borrow_cost_nav_period'],.3*.03*7/360)
        self.assertAlmostEqual(a['scenario_rebate_nav_period'],.3*.01*7/360)

    def test_idle_cash_credit_explicit(self):
        sc=FundingScenario(.0625,.0625,7,(0.,0.),(True,True),idle_cash_yield_rate=.04)
        a=evaluate(.4,[.3,-.3],[1.,1.],sc)
        self.assertAlmostEqual(a['free_cash_nav'],.3)
        self.assertAlmostEqual(a['scenario_cash_credit_nav_period'],.3*.04*7/360)
        self.assertLess(a['extra_cost_nav_period'],0)

    def test_different_actual_and_legacy_margin_rates(self):
        a=self.simple(margin=.05,legacy=.07)
        self.assertAlmostEqual(a['extra_cost_nav_per_360d_fixed_holdings'],.6*.05-.3*.07)

    def test_reject_invalid_beta_and_borrow_rates(self):
        sc=FundingScenario(.0625,.0625,7,(0.,0.),(True,True))
        for b in ([1.,float('nan')],[float('inf'),1.]):
            with self.subTest(beta=b):
                with self.assertRaises(ValueError): evaluate(1.3,[.3,-.3],b,sc)
        with self.assertRaises(ValueError):evaluate(1.3,[.3,-.3],[1,1],replace(sc,stock_borrow_rates=(0.,-.01)))

    def test_invalid_rates_fail_closed(self):
        sc=FundingScenario(.0625,.0625,7,(0.,0.),(True,True))
        for kw in [dict(margin_rate=float('nan')),dict(days=0),dict(day_count=0),dict(short_rebate_rate=-.1),dict(stock_shortable=(True,)),dict(stock_shortable=(1,1))]:
            with self.subTest(k=kw):
                with self.assertRaises(ValueError):evaluate(1.3,[.3,-.3],[1.,1.],replace(sc,**kw))

    def test_random_self_financing_and_gap_bounds(self):
        rng=np.random.default_rng(2098)
        for _ in range(2000):
            core=rng.uniform(-.5,1.7)
            w=rng.uniform(-.4,.4,12)
            beta=rng.uniform(.2,1.8,12)
            sc=FundingScenario(.0625,.0625,7,tuple(np.zeros(12)),tuple([True]*12))
            x=evaluate(core,w,beta,sc)
            self.assertAlmostEqual(x['long_notional_nav']-x['short_notional_nav'],x['net_notional_nav'],places=11)
            self.assertGreaterEqual(x['financing_debit_gap_nav'],-1e-12)
            self.assertLessEqual(x['financing_debit_gap_nav'],x['short_notional_nav']+1e-12)

    def test_sharpe_shift_is_approximation_not_observed(self):
        self.assertAlmostEqual(fixed_vol_sharpe_shift(.936946240442,.2237,.01875),.936946240442-.01875/.2237)
        with self.assertRaises(ValueError):fixed_vol_sharpe_shift(.94,0,.01875)


    def test_scenario_required_and_nonfinite_core(self):
        with self.assertRaisesRegex(ValueError,'FundingScenario'):
            evaluate(1.3,[.3,-.3],[1.,1.],None)
        sc=FundingScenario(.0625,.0625,7,(0.,0.),(True,True))
        with self.assertRaisesRegex(ValueError,'finite core'):
            evaluate(float('nan'),[.3,-.3],[1.,1.],sc)

    def test_nonnumeric_vector_rejected(self):
        sc=FundingScenario(.0625,.0625,7,(0.,0.),(True,True))
        with self.assertRaises(ValueError):
            evaluate(1.3,['not_a_number',-.3],[1.,1.],sc)

    def test_extreme_positions_fail_closed_on_overflow(self):
        sc=FundingScenario(.0625,.0625,7,(0.,0.),(True,True))
        with np.errstate(over='ignore',invalid='ignore'):
            with self.assertRaises((ValueError,ArithmeticError,OverflowError)):
                evaluate(1.3,[1e308,1e308],[1e308,1e308],sc)

if __name__=='__main__':unittest.main()
