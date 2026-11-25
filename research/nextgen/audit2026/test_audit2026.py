import copy
import math
import unittest

from research.nextgen.audit2026.audit import audit_reports, audit_repository


def published_fixture():
    f = {"weeks": 43, "pct_per_year": -1.4932577181053488,
         "net_sharpe": -0.10359456122647678,
         "worst_fall_pct": -11.915751151719666}
    arms = {k: {"weeks": 43, "period": ["2026-01-08", "2026-10-29"],
                "fund_alone": copy.deepcopy(f)} for k in ("H7a", "H7b")}
    h7 = {"arms": arms, "fund_info": {"rf_last_date": "2026-10-22"}}
    decomp = {"fund": {"by_year_pct_per_year": {"2026": {
        "weeks": 43, "total": -1.4932577181053488,
        "master_book": -2.8999097467448984,
        "book_sharpe": -0.3451203089162944}}}}
    l4 = {"y2026_already_read_reported_not_tested": {"B0": {
        "period": ["2026-01-08", "2026-10-29"],
        "weeks": 43, "sharpe": -0.10359456122647678,
        "vol_pct": 14.414441264351824,
        "worst_fall_pct": -11.915751151719666,
        "book_pct_per_year_arith": -2.8999097467448984,
        "book_sharpe": -0.3451203089162944,
        "pct_simple_2026": 0.35679965365083,
        "pct_per_year": 0.43312509595343496,
        "mean_gross": 1.924813391649911}}}
    return h7, decomp, l4


class TestPublishedReportAudit(unittest.TestCase):
    def test_published_summary_numbers_reconcile(self):
        report = audit_reports(*published_fixture())
        self.assertAlmostEqual(report["annual_arithmetic_percent"], -1.4932577181053488)
        self.assertAlmostEqual(report["annual_geometric_percent"], 0.433125095953435)
        self.assertAlmostEqual(report["implied_elapsed_days"], 301)
        self.assertEqual(report["rf_last_date_age_at_report_end_days"], 7)
        self.assertGreater(report["mean_gross_minus_nominal_cap"], 0)
    def test_fails_on_one_arm_inconsistent_return(self):
        h, d, l = published_fixture()
        h["arms"]["H7b"]["fund_alone"]["pct_per_year"] += 0.01
        with self.assertRaisesRegex(ValueError, "arithmetic"):
            audit_reports(h, d, l)
    def test_fails_on_book_inconsistency(self):
        h, d, l = published_fixture()
        l["y2026_already_read_reported_not_tested"]["B0"]["book_sharpe"] *= -1
        with self.assertRaises(ValueError):
            audit_reports(h, d, l)
    def test_fails_on_period_inconsistency(self):
        h, d, l = published_fixture()
        h["arms"]["H7a"]["period"][0] = "2026-01-09"
        with self.assertRaisesRegex(ValueError, "period"):
            audit_reports(h, d, l)
    def test_fails_on_nonfinite_sharpe(self):
        h, d, l = published_fixture()
        l["y2026_already_read_reported_not_tested"]["B0"]["sharpe"] = float("nan")
        with self.assertRaises(ValueError):
            audit_reports(h, d, l)
    def test_fails_on_compounding_invalidity(self):
        h, d, l = published_fixture()
        l["y2026_already_read_reported_not_tested"]["B0"]["pct_simple_2026"] = -101
        with self.assertRaises(ValueError):
            audit_reports(h, d, l)
    def test_differently_sized_holding_periods_can_reverse_signs(self):
        # Two observed strategy holding intervals of 2 and 12 calendar days.
        # Positive total realised wealth, negative mean of week-normalised returns.
        days = [2, 12]
        simple_returns = [-0.02, 0.04]
        weekly_arithmetic = sum(r * 7 / d for r, d in zip(simple_returns, days)) / 2
        total_cumulative = math.prod(1 + r for r in simple_returns) - 1
        self.assertLess(weekly_arithmetic, 0)
        self.assertGreater(total_cumulative, 0)
    def test_io_round_trip_does_not_require_market_cache(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        h, d, l = published_fixture()
        with TemporaryDirectory() as folder:
            root = Path(folder)
            for rel, value in (("research/tree/H7_RESULT.json",h),
                               ("research/tree/H7_DECOMP.json",d),
                               ("research/tree/L4_exploit/RESULT.json",l)):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding="utf-8")
            report = audit_repository(root)
            self.assertAlmostEqual(report["implied_elapsed_days"],301)
    def test_wrong_weeks_fails_closed(self):
        h, d, l = published_fixture()
        d["fund"]["by_year_pct_per_year"]["2026"]["weeks"] = 42
        with self.assertRaisesRegex(ValueError,"weeks"):
            audit_reports(h,d,l)
    def test_future_riskfree_report_date_rejected(self):
        h, d, l = published_fixture()
        h["fund_info"]["rf_last_date"] = "2026-11-20"
        with self.assertRaisesRegex(ValueError, "risk-free"):
            audit_reports(h,d,l)
    def test_zero_geometric_with_positive_cumulative_fails(self):
        h, d, l = published_fixture()
        l["y2026_already_read_reported_not_tested"]["B0"]["pct_per_year"] = 0
        with self.assertRaisesRegex(ValueError,"compounding"):
            audit_reports(h,d,l)
    def test_invalid_dates_fail_closed(self):
        h, d, l = published_fixture()
        l["y2026_already_read_reported_not_tested"]["B0"]["period"] = ["2026-11-01","2026-10-29"]
        with self.assertRaisesRegex(ValueError,"period"):
            audit_reports(h,d,l)
    def test_both_h7_arms_must_have_same_sharpe(self):
        h, d, l = published_fixture()
        h["arms"]["H7a"]["fund_alone"]["net_sharpe"] -= .001
        with self.assertRaises(ValueError):
            audit_reports(h, d, l)


if __name__ == "__main__":
    unittest.main()
