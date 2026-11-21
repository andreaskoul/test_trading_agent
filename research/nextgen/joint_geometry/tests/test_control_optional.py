"""Optional end-to-end CVXPY feasibility; skipped if optimization extras absent."""
import importlib.util
import unittest
import numpy as np
from research.nextgen.joint_geometry.control import solve_geometric_mpc,spd_ambiguity
from research.nextgen.joint_state.control import Policy

@unittest.skipUnless(importlib.util.find_spec('cvxpy') is not None,'CVXPY optional research extra is not installed')
class TestOptionalMPC(unittest.TestCase):
    def test_geodesic_worst_case_constrained_solution(self):
        rng=np.random.default_rng(20261121)
        N=6;K=3;S=60;H=2
        names=np.array([f'A{i}' for i in range(N)])
        beta=np.zeros(N)
        load=rng.normal(0,.2,size=(N+1,K))
        residual=np.ones(N+1)*.0002
        base=np.diag([.0004,.0003,.0002])
        past=np.stack([base*(.7+.05*i) for i in range(12)])
        family=spd_ambiguity(past,'affine')
        paths=rng.normal(0,.01,size=(S,H,N+1))
        policy=Policy(names,beta,core=1.3,cap=1.9,max_stock_abs=.10,
                      risk_weight=.02,cvar_weight=.12,financing='segregated')
        result=solve_geometric_mpc(paths,policy,np.zeros(N),load,residual,family)
        self.assertIn(result['status'],('MODEL_ONLY_NOT_BACKTEST',))
        self.assertLessEqual(result['first_whole_fund_gross'],1.9001)
        self.assertTrue(np.isfinite(result['predicted_worst_case_risk']))

if __name__=='__main__':unittest.main()
