"""Scenario-based, cost/financing-aware receding horizon robust convex optimizer.

Solve-only: never place orders. Scenario paths are conditional model forecasts,
NOT historical realized equity outcomes. This package does not claim a Sharpe.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Policy:
    names: np.ndarray
    beta: np.ndarray
    stock_cost: float = .0005
    spy_cost: float = .0005
    borrow_cost_annual:float = 0.
    margin_rate_annual:float = .06
    cash_rate_annual:float = .04
    cap:float = 1.9
    max_stock_abs:float = .035
    beta_band:float = .15
    core:float = 1.3
    risk_weight:float = .05
    cvar_weight:float = .12
    uncertainty_weight:float = .05
    tail_probability:float = .05
    financing:str = 'segregated'


def student_t_scenarios(mu,cov,n_scenarios=500,horizon=4,df=8,seed=20261120):
    """Multivariate t return scenarios from *fitted* model predictions, never historic oracle returns.

    Assumes per-holding-period mu and cov (e.g., 5-session values). Innovations
    independent across steps here; advanced dynamic posterior generation may
    pass externally correlated scenarios to solve_mpc instead.
    """
    mu=np.asarray(mu,float);cov=np.asarray(cov,float)
    if mu.ndim!=1 or cov.shape!=(len(mu),len(mu)) or len(mu)<2 or not np.isfinite(mu).all() or not np.isfinite(cov).all() or df<=2:
        raise ValueError('scenario mean/cov invalid')
    from .risk import positive_definite
    cov=positive_definite(cov)
    rng=np.random.default_rng(seed)
    l=np.linalg.cholesky(cov*(df-2)/df)
    normals=rng.normal(size=(n_scenarios,horizon,len(mu)))
    chi=rng.chisquare(df,size=(n_scenarios,horizon,1))
    return mu[None,None,:]+(normals@l.T)/np.sqrt(chi/df)


def _check_scenario(paths,spy_paths,policy,w_prev):
    a=np.asarray(paths,float);spy=np.asarray(spy_paths,float)
    beta=np.asarray(policy.beta,float);w0=np.asarray(w_prev,float)
    if a.ndim!=3 or a.shape[:2]!=spy.shape or a.shape[2]!=len(beta) or w0.shape!=beta.shape:
        raise ValueError('scenario dimensions do not match names, beta, positions')
    if len(policy.names)!=len(beta) or not np.isfinite(a).all() or not np.isfinite(spy).all():
        raise ValueError('invalid scenarios')
    if not np.isfinite(beta).all() or not np.isfinite(w0).all():
        raise ValueError('invalid beta or previous holdings')
    if not(0<policy.tail_probability<.5 and policy.margin_rate_annual>=0 and policy.cash_rate_annual>=0 and policy.borrow_cost_annual>=0):
        raise ValueError('invalid costs or tail probability')
    if policy.financing not in ('net_debit','segregated') or policy.cap<abs(policy.core)-1e-8:
        raise ValueError('invalid financing or infeasible core gross cap')
    if policy.risk_weight<0 or policy.cvar_weight<0 or policy.uncertainty_weight<0:
        raise ValueError('negative risk aversion')
    return a,spy,beta,w0


def solve_mpc(paths,spy_paths,policy:Policy,w_prev,
              uncertain_sigma=None,sector_matrix=None,sector_limits=None,
              solver=None,days_per_step=7,max_iter=None):
    """Robust CVaR receding horizon with identical whole-fund gross each step.

    Optimized decision variables: next H future stock-book weight vectors. SPY
    hedge is -beta@w, core is fixed separately; no invented independent SPY
    alpha. Models transaction cost as convex 5bp per absolute turnover unit.

    Returns ONLY first-step order targets and model-predicted diagnostics.
    Final trading approval requires an entirely separate prospective backtest.
    """
    try:import cvxpy as cp
    except ImportError as exc:raise RuntimeError('MPC requires cvxpy>=1.5, install research extras') from exc
    a,spy,beta,prev=_check_scenario(paths,spy_paths,policy,w_prev)
    S,H,N=a.shape
    if S<50 or H<1 or H>20:raise ValueError('at least 50 scenarios and 1..20 steps required')
    sigma=np.zeros((N,N)) if uncertain_sigma is None else np.asarray(uncertain_sigma,float)
    if sigma.shape!=(N,N) or not np.isfinite(sigma).all():raise ValueError('uncertainty covariance invalid')
    sigma=(sigma+sigma.T)/2
    ev=np.linalg.eigvalsh(sigma)
    if np.min(ev)<-1e-8:raise ValueError('uncertainty matrix not PSD')
    sigma+=np.eye(N)*max(0,1e-10-np.min(ev))
    W=cp.Variable((H,N));losses=[];future=[];constraints=[]
    last=prev;last_hedge=-beta@last
    cost=[];finance=[];risk=[];exante_risk=[]
    for h in range(H):
        w=W[h,:]
        hedge=-beta@w
        core_spy=policy.core+hedge
        gross=cp.norm1(w)+cp.abs(core_spy)
        constraints += [gross<=policy.cap,cp.abs(w)<=policy.max_stock_abs,
                        cp.abs(beta@w)<=policy.beta_band,
                        cp.abs(cp.sum(w))<=.05]
        if sector_matrix is not None:
            sm=np.asarray(sector_matrix,float)
            lim=np.asarray(sector_limits,float)
            if sm.ndim!=2 or sm.shape[1]!=N or lim.shape!=(sm.shape[0],):
                raise ValueError('invalid sector constraints')
            constraints += [cp.abs(sm@w)<=lim]
        turnover=policy.stock_cost*cp.norm1(w-last)+policy.spy_cost*cp.abs(hedge-last_hedge)
        if policy.financing=='segregated':
            # Stocks short proceeds are collateral, not spendable. The SPY
            # hedge is modelled as a signed derivative/ETF exposure; broker
            # confirmed policy is still required before live use.
            debit=cp.pos(policy.core+cp.sum(cp.pos(w))+hedge-1)
        else:
            debit=cp.pos(policy.core+cp.sum(w)+hedge-1)
        funding=(policy.margin_rate_annual*debit+
                 policy.borrow_cost_annual*cp.sum(cp.pos(-w)))*days_per_step/360
        # Cash return is shared by both arms under same finance convention;
        # explicit excess scenarios already omit the cash benchmark.
        realized=a[:,h,:]@w+spy[:,h]*core_spy
        net=realized-turnover-funding
        future.append(net)
        cost.append(turnover);finance.append(funding)
        risk.append(cp.quad_form(w,sigma,assume_PSD=True))
        # Empirical model scenario covariance of the joint SPY+stock position,
        # recomputed within each decision horizon, penalizes investable risk.
        if policy.risk_weight:
            scen_cov=np.cov(a[:,h,:].T,ddof=1)
            scen_cov=(scen_cov+scen_cov.T)/2
            eig=np.linalg.eigvalsh(scen_cov)
            scen_cov+=np.eye(N)*max(1e-10,-float(eig.min())+1e-10)
            exante_risk.append(cp.quad_form(w,scen_cov,assume_PSD=True))
        last=w;last_hedge=hedge
    path_returns=cp.sum(cp.vstack(future),axis=0)
    tail_eta=cp.Variable();tail_slack=cp.Variable(S,nonneg=True)
    constraints+=[tail_slack>=-path_returns-tail_eta]
    cvar=tail_eta+cp.sum(tail_slack)/(S*policy.tail_probability)
    utility=(cp.sum(path_returns)/S - policy.cvar_weight*cvar -
             policy.uncertainty_weight*cp.sum(cp.hstack(risk)) -
             (policy.risk_weight*cp.sum(cp.hstack(exante_risk)) if exante_risk else 0))
    prob=cp.Problem(cp.Maximize(utility),constraints)
    options={}
    if max_iter is not None:options['max_iter']=max_iter
    if solver is not None:options['solver']=solver
    try:prob.solve(**options)
    except Exception as exc:raise RuntimeError(f'MPC solver failed: {exc}') from exc
    if prob.status not in ('optimal','optimal_inaccurate') or W.value is None:
        raise RuntimeError(f'MPC is not feasible/optimal: {prob.status}')
    first=np.asarray(W.value[0]).ravel();hdg=-float(beta@first)
    gross=float(np.sum(np.abs(first))+abs(policy.core+hdg))
    if gross>policy.cap+1e-4 or np.max(np.abs(first))>policy.max_stock_abs+1e-4:
        raise RuntimeError('solver returned constraint violation')
    return dict(first_step_weights=first,first_spy_hedge=hdg,
                first_whole_fund_gross=gross,
                model_expected_path_utility=float(prob.value),
                model_expected_cvar_loss=float(cvar.value),
                model_cost_first=float(cost[0].value),
                model_financing_first=float(finance[0].value),
                status=str(prob.status),
                semantics='MODEL_PREDICTED_NOT_HISTORICAL_PROFIT',
                all_weight_paths=np.asarray(W.value))
