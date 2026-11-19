import unittest
import numpy as np
from core import Config,solve

class OptimizerTests(unittest.TestCase):
    def case(self):
        return dict(mu=np.array([.012,-.012,0.,0.]),covariance=np.eye(4)*.01,
                    previous=np.zeros(4),beta=np.ones(4),spread=np.zeros(4),
                    daily_vol=np.ones(4)*.02,adv=np.ones(4)*1e9)
    def test_risk_neutral(self):
        a=solve(**self.case(),cfg=Config(gamma=1,gross=.4,name_limit=.2,impact_k=0))
        w=a["weights"]
        self.assertGreater(w[0],0)
        self.assertLess(w[1],0)
        self.assertAlmostEqual(w.sum(),0,places=6)
        self.assertLessEqual(abs(w).sum(),.4+1e-7)
        self.assertGreater(a["net_utility"],0)
    def test_spread_limits_turnover(self):
        q=self.case();q["mu"]=np.array([.0005,-.0005,0,0]);q["spread"]=np.ones(4)*.025
        a=solve(**q,cfg=Config(gross=.4,name_limit=.2,impact_k=0))
        self.assertLess(np.max(abs(a["weights"])),1e-5)
    def test_fail_closed_bad_covariance(self):
        q=self.case();q["covariance"][0,0]=-.01
        with self.assertRaises(ValueError):solve(**q)
    def test_fail_closed_bad_liquidity(self):
        q=self.case();q["adv"][0]=0
        with self.assertRaises(ValueError):solve(**q)
    def test_nonnegative_cost(self):
        a=solve(**self.case(),cfg=Config(gross=.4,name_limit=.2))
        self.assertGreaterEqual(a["components"]["impact"],0)
if __name__=="__main__":unittest.main()
