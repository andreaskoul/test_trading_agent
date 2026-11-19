import unittest
import numpy as np
from core import excess_sharpe, compound_return, max_drawdown, ledger_residual, paired_hac_mean_test

class TestMetrics(unittest.TestCase):
    def test_cash_is_subtracted(self):
        r=np.array([.01,.02,-.01,.03]); rf=np.array([.004]*4)
        self.assertAlmostEqual(excess_sharpe(r,rf), np.sqrt(52)*np.mean(r-rf)/np.std(r-rf,ddof=1))
        self.assertNotAlmostEqual(excess_sharpe(r,rf), np.sqrt(52)*r.mean()/r.std(ddof=1))
    def test_alignment(self):
        with self.assertRaises(ValueError): excess_sharpe([.01,.02,.03],[.0,.0])
        with self.assertRaises(ValueError): excess_sharpe([.01,.02,float("nan")],[.0]*3)
    def test_compound_drawdown(self):
        self.assertAlmostEqual(compound_return([.1,-.1]),-.01)
        self.assertAlmostEqual(max_drawdown([.1,-.2,.05]),-.2)
    def test_reconcile(self):
        self.assertAlmostEqual(ledger_residual([.008],[.010],[.002],[.001],[.003]),0)
        with self.assertRaises(ValueError): ledger_residual([.009],[.010],[.002],[.001],[.003])
    def test_hac_mean(self):
        x=[.01,-.02,.025,.004,.012,-.005,.013,.001]
        t=paired_hac_mean_test(x,0)
        self.assertAlmostEqual(t["hac_se"],np.std(x,ddof=0)/np.sqrt(len(x)))
        with self.assertRaises(ValueError): paired_hac_mean_test(x,len(x))
if __name__=="__main__": unittest.main()
