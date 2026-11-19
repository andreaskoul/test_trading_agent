import unittest
import numpy as np
from research.nextgen.optimizer.core import Config,solve

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

    def test_gradient_matches_finite_differences(self):
        from scipy.optimize import approx_fprime
        from unittest.mock import patch
        import research.nextgen.optimizer.core as mod
        data=self.case()
        data["spread"]=np.ones(4)*.0002
        data["beta"]=np.array([1.,1.2,.8,1.4])
        original=mod.minimize
        errors=[]
        def inspect(f,x0,**kwargs):
            w=np.array([.015,-.025,.02,-.01])
            numeric=approx_fprime(w,f,1e-8)
            errors.append(np.max(np.abs(numeric-kwargs["jac"](w))))
            return original(f,x0,**kwargs)
        with patch.object(mod,"minimize",inspect):
            solve(**data,cfg=Config(gross=.4,name_limit=.2))
        self.assertLess(errors[0],1e-6)
    def test_optimisation_does_not_underperform_no_trade(self):
        a=solve(**self.case(),cfg=Config(gamma=1,gross=.4,name_limit=.2))
        self.assertGreaterEqual(a["net_utility"],-1e-9)
    def test_deterministic_random_psd_cases(self):
        rng=np.random.default_rng(391)
        for n in (4,8,16):
            for rep in range(6):
                x=rng.normal(size=(n,n))
                data=dict(mu=rng.normal(0,.007,n),covariance=x@x.T*.01/n,
                          previous=np.zeros(n), beta=1+rng.normal(0,.2,n),
                          spread=np.full(n,.0002),daily_vol=np.full(n,.02),adv=np.full(n,1e8))
                cfg=Config(gross=.3,name_limit=.05,beta_limit=.01)
                a=solve(**data,cfg=cfg)
                self.assertLessEqual(a["gross"],cfg.gross+cfg.tolerance)
                self.assertLessEqual(abs(a["beta"]),cfg.beta_limit+cfg.tolerance)
                self.assertGreaterEqual(a["net_utility"],-1e-8)
    def test_solver_failure_is_explicit(self):
        from unittest.mock import patch
        import types
        import research.nextgen.optimizer.core as mod
        with patch.object(mod,"minimize",return_value=types.SimpleNamespace(x=np.zeros(4),success=False,message="injected failure")):
            with self.assertRaises(RuntimeError):solve(**self.case())
if __name__=="__main__":unittest.main()
