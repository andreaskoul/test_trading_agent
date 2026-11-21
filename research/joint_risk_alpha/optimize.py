"""Convex robust multi-period trading (MPC) with scenario CVaR, turnover and financing.

A research-only CVXPY problem. Scenario returns are **future samples drawn
from a model trained only on history**, never realised future returns. The
optimiser sees no actual next-week returns. It chooses weights in NAV units.
"""
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class TradingPolicy:
    risk_aversion:float=8.
    cvar_aversion:float=2.
    uncertainty_aversion:float=4.
    transaction_bps:float=5.
    impact_coefficient:float=.001
    borrow_rate_per_week:float=.001
    gross_limit:float=1.9
    name_limit:float=.08
    alpha_cvar:float=.95
    wasserstein_radius:float=0.0005  # 1-Wasserstein linear-payoff penalty, L2 transport norm
    cvar_scenario_weights:tuple|None=None


def solve_mpc(mu,scenario_returns,previous,core_spy,stock_beta,prev_hedge,
              policy=TradingPolicy(),adv_capacity=None,prediction_std=None,
              half_spread_bps=None,hedge_spy_cost_bps=5.,solver='CLARABEL'):
    """Scenario MPC for a fixed core and optional stock basket over H weeks.

    Shapes: mu(H,N); scenarios(M,H,N+1), last asset SPY, previous(N).
    Controls w(H,N), h(H): active stock weights and stock book SPY hedge.
    NAV weekly scenario return = stock return dot w + SPY return*(core+h).
    Gross = ||w||_1 + |core+h|, same for every scenario/week.
    Optional ADV capacity per stock is max NAV weight change per week.
    Funding: conservative gross debit upper bound with stock shorts
    uncredited; actual settled debit must be validated before promotion.

    Robust CVaR applied to the *per-scenario full H-week cumulative
    arithmetic* return. Future weights are open-loop scenario-nonanticipative:
    this approximation is receding-horizon trading, not full stochastic DP.
    """
    try:import cvxpy as cp
    except ImportError as e:raise RuntimeError('pip install cvxpy to execute robust MPC') from e
    m=np.asarray(mu,float);S=np.asarray(scenario_returns,float);prev=np.asarray(previous,float)
    beta=np.asarray(stock_beta,float)
    if m.ndim!=2 or S.ndim!=3:raise ValueError('mu(H,N), scenarios(M,H,N+1) required')
    H,N=m.shape;M,HS,NS=S.shape
    if (HS,NS)!=(H,N+1) or prev.shape!=(N,) or beta.shape!=(N,) or M<20 or H<1:
        raise ValueError('invalid joint prediction shape')
    if not np.isfinite(S).all() or not np.isfinite(m).all() or not np.isfinite(prev).all() or not np.isfinite(beta).all():
        raise ValueError('STOP: non-finite predictive inputs')
    if not .5<policy.alpha_cvar<1:raise ValueError('CVaR confidence invalid')
    std=np.zeros_like(m) if prediction_std is None else np.asarray(prediction_std,float)
    if std.shape!=m.shape or np.any(std<0):raise ValueError('uncertainty shape')
    spread=np.full(N,policy.transaction_bps) if half_spread_bps is None else np.asarray(half_spread_bps,float)
    if spread.shape!=(N,) or np.any(spread<0):raise ValueError('spread shape')
    if adv_capacity is not None:
        capacity=np.asarray(adv_capacity,float)
        if capacity.shape!=(N,) or np.any(capacity<=0):raise ValueError('ADV change cap shape')
    w=cp.Variable((H,N));h=cp.Variable(H)
    constraints=[];prev_w=prev;prev_h=float(prev_hedge)
    reward=0
    scen_total=[]
    deterministic_friction=[]
    for t in range(H):
        wt=w[t,:];ht=h[t]
        dw=wt-prev_w;dh=ht-prev_h
        constraints += [cp.norm1(wt)+cp.abs(core_spy+ht)<=policy.gross_limit,
                        cp.abs(wt)<=policy.name_limit,
                        cp.sum(wt)==0]
        if adv_capacity is not None:constraints += [cp.abs(dw)<=capacity]
        # Equity book dollar-neutral; SPY book hedge beta-neutral if feasible.
        constraints += [ht+beta@wt==0]
        funding_debit=cp.pos(core_spy+cp.sum(cp.pos(wt))+cp.pos(ht)-1)
        spread_cost=cp.sum(cp.multiply(spread*1e-4,cp.abs(dw)))+hedge_spy_cost_bps*1e-4*cp.abs(dh)
        impact=policy.impact_coefficient*(cp.sum_squares(dw)+cp.square(dh))
        uncertainty=policy.uncertainty_aversion*cp.sum(cp.multiply(std[t],cp.abs(wt)))
        friction=spread_cost+impact+policy.borrow_rate_per_week*funding_debit
        deterministic_friction.append(friction)
        # Wasserstein DRO worst-case shift of linear expected return under
        # L2 ground metric: epsilon*dual_norm(w)=epsilon*||w||_2.
        reward += m[t]@wt-policy.risk_aversion*.5*cp.sum_squares(wt) - friction - uncertainty - policy.wasserstein_radius*cp.norm2(wt)
        prev_w=wt;prev_h=ht
    # CVaR is formed on full scenario path, with *same* positions for all scenarios.
    for j in range(M):
        ret=0
        for t in range(H):
            ret+= S[j,t,:N]@w[t,:] + S[j,t,N]*(core_spy+h[t])
        scen_total.append(ret-cp.sum(cp.hstack(deterministic_friction)))
    losses=-cp.hstack(scen_total)
    eta=cp.Variable();u=cp.Variable(M,nonneg=True)
    constraints += [u>=losses-eta]
    cvar=eta+cp.sum(u)/(M*(1-policy.alpha_cvar))
    objective=cp.Maximize(reward-policy.cvar_aversion*cvar)
    problem=cp.Problem(objective,constraints)
    problem.solve(solver=solver,warm_start=True,verbose=False)
    if problem.status not in ('optimal','optimal_inaccurate') or w.value is None:
        raise RuntimeError(f'MPC did not converge: {problem.status}')
    W=np.asarray(w.value,float);hedge=np.asarray(h.value,float)
    if max(np.max(np.abs(W.sum(1))),np.max(np.abs(hedge+W@beta)))>1e-4:
        raise RuntimeError('MPC dollar/beta constraint failed')
    gross=np.sum(np.abs(W),axis=1)+np.abs(core_spy+hedge)
    if np.max(gross)>policy.gross_limit+1e-4:raise RuntimeError('MPC gross constraint failed')
    return {'stock_weights':W,'spy_hedge':hedge,'first_stock_weights':W[0],
            'first_spy_hedge':float(hedge[0]),'gross_by_step':gross,
            'objective':float(problem.value),'status':problem.status,
            'predicted_cvar':float(cvar.value),'risk_posterior_required':True}
