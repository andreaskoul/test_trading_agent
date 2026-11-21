import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from research.nextgen.calibration.reproduce import produce

class TestReproduceCalibration(unittest.TestCase):
    def test_published_summary_only_no_cache(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            p=root/'research/tree/L4_exploit/RESULT.json'
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'tests_vs_B0': {'B5a': {'lw2008_hac': {
                'sharpe_diff_ann':.050399043857478475,
                'se_ann':.05402454118653946}}},
                'summary':{'B0':{'weeks':302}}}))
            with patch('research.nextgen.calibration.reproduce.simulate',return_value={'status':'synthetic'}),patch('research.nextgen.calibration.reproduce.run_constrained',return_value={'status':'synthetic'}):
                r=produce(root)
            self.assertEqual(r['analytic_mc']['status'],'synthetic')
            self.assertEqual(len(r['conditional_research_power']),4)
            self.assertAlmostEqual(r['conditional_research_power'][2]['required_weeks_at_target_power'],3759.790237518475)
    def test_missing_published_summary_fails_closed(self):
        with TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):produce(d)

if __name__=='__main__':unittest.main()
