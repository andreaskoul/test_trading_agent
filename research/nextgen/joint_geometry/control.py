"""Riemannian covariance ambiguity + distributionally robust multi-period control.

Risk uncertainty is a set of SPD matrices obtained from *past-known* covariance
snapshots by intrinsic geodesics. The CVXPY objective penalizes the maximum
modelled quadratic variance over this family, not a single Euclidean estimate.
No order placement, use as a decision-policy diagnostic only.
"""
from __future__ import annotations
import numpy as np
from .geometry import (spd,frechet_mean,logeuclidean_geodesic,affine_geodesic,
                       bures_geodesic,logeuclidean_distance)
from research.nextgen.joint_state.control import Policy


def spd_ambiguity(history,metric='affine',n_centers=3,radius=.75):
    """Geodesic uncertainty set from historical SPD factor covariances only.

    Includes pooled Fréchet mean, recent covariance and q=.15,.85 intrinsic
    extremes (observed past points), and bounded geodesic interpolants.
    Does not fit ambiguity radius using future portfolio returns.
    """
    x=np.asarray(history,float)
    if x.ndim!=3 or x.shape[1]!=x.shape[2] or len(x)<6:
        raise ValueError('need >=6 prior SPD observations, fixed common basis')
    if not 0<radius<=1 or n_centers<2:raise ValueError('invalid geometric ambiguity design')
    x=np.stack([spd(a) for a in x]);center=frechet_mean(x,metric)
    recent=frechet_mean(x[-min(5,len(x)):],metric)
    ds=np.array([logeuclidean_distance(a,center) for a in x]);order=np.argsort(ds)
    family=[center,recent,x[-1]]
    method={'affine':affine_geodesic,'logeuclidean':logeuclidean_geodesic,'bures':bures_geodesic}.get(metric)
    if method is None:raise ValueError('unsupported SPD metric')
    for idx in np.linspace(0,len(order)-1,n_centers,dtype=int):
        family.append(method(center,x[order[idx]],radius))
    unique=[]
    for a in family:
        if not any(np.linalg.norm(a-b)<1e-12 for b in unique):unique.append(spd(a))
    return np.stack(unique)


def asset_covariance(factor_cov,loadings,residual_diag):
    k=spd(factor_cov);B=np.asarray(loadings,float);d=np.asarray(residual_diag,float)
    if B.ndim!=2 or B.shape[1]!=len(k) or d.shape!=(len(B),) or not np.isfinite(B).all() or not np.isfinite(d).all() or (d<0).any():
        raise ValueError('factor covariance exposure mismatch')
    return spd(B@k@B.T+np.diag(np.maximum(d,1e-10)))


def posterior_paths(expected_excess,loading,residual_diag,risk_set,
                    scenarios=500,horizon=4,df=7,seed=20261121):
    """Multimodal Student-t paths with geometry-aware covariance uncertainty.

    Draw one SPD risk model from the pre-origin geodesic uncertainty set each
    scenario and simulate conditional heavy-tailed log-price shocks. The
    scenario covariance is not a historical return or an actual Sharpe.
    """
    mu=np.asarray(expected_excess,float);G=np.asarray(risk_set,float)
    if mu.ndim!=1 or G.ndim!=3 or scenarios<50 or horizon<1 or df<=2:
        raise ValueError('invalid posterior scenario specification')
    if G.shape[1:]!=(loading.shape[1],loading.shape[1]) or loading.shape[0]!=len(mu):
        raise ValueError('risk-factor alignment mismatch')
    cov=[asset_covariance(g,loading,residual_diag)*(df-2)/df for g in G]
    rng=np.random.default_rng(seed)
    ids=rng.integers(0,len(cov),size=scenarios)
    result=np.empty((scenarios,horizon,len(mu)))
    chol=[np.linalg.cholesky(a) for a in cov]
    for i,j in enumerate(ids):
        eps=rng.normal(size=(horizon,len(mu)))@chol[j].T
        scale=np.sqrt(rng.chisquare(df,size=(horizon,1))/df)
        result[i]=mu+eps/scale
    return result


def solve_geometric_mpc(paths,policy:Policy,w_prev,loadings,residual_diag,
                        risk_set,solver=None,days_per_step=7):
    """CVXPY robust MPC with max quadratic risk across geodesic SPD set.

    Identical Policy whole-fund gross (core+hedge), stock leverage, beta band,
    financing and turnover constraints to the previous scenario optimizer.
    Additional worst-case factor-risk epigraph across supplied SPD matrices.
    All returns are *model scenarios*. Output only proposed first weights.
    """
    try:import cvxpy as cp
    except ImportError as exc:raise RuntimeError('Geometric MPC requires cvxpy research extra') from exc
    x=np.asarray(paths,float);prev=np.asarray(w_prev,float)
    beta=np.asarray(policy.beta,float);factors=np.asarray(loadings,float)
    residual=np.asarray(residual_diag,float);rset=np.asarray(risk_set,float)
    if x.ndim!=3 or len(x)<50 or x.shape[1]>20 or x.shape[2]!=len(prev)+1 or beta.shape!=prev.shape:
        raise ValueError('scenario / positions dimensions mismatch')
    S,H,N1=x.shape;N=N1-1
    if factors.shape[0]!=N1 or residual.shape!=(N1,) or rset.ndim!=3 or rset.shape[1:]!=(factors.shape[1],)*2:
        raise ValueError('factor-risk exposures mismatch')
    if not (np.isfinite(x).all() and np.isfinite(beta).all() and np.isfinite(prev).all() and
            np.isfinite(factors).all() and np.isfinite(residual).all() and (residual>=0).all()):
        raise ValueError('nonfinite optimizer input')
    if not(policy.cap>=abs(policy.core) and 0<policy.tail_probability<.5 and
           policy.financing in ('net_debit','segregated') and policy.margin_rate_annual>=0 and
           policy.borrow_cost_annual>=0 and policy.stock_cost>=0 and policy.spy_cost>=0):
        raise ValueError('invalid funded policy')
    G=np.stack([spd(a) for a in rset])
    W=cp.Variable((H,N));R=[];cost_terms=[];carry_terms=[];limits=[];risk_terms=[];last=prev
    lasthedge=-beta@prev
    for h in range(H):
        w=W[h,:];hedge=-beta@w;full_spy=policy.core+hedge
        gross=cp.norm1(w)+cp.abs(full_spy)
        limits += [gross<=policy.cap,cp.abs(w)<=policy.max_stock_abs,
                   cp.abs(cp.sum(w))<=.05,cp.abs(beta@w)<=policy.beta_band]
        turnover=policy.stock_cost*cp.norm1(w-last)+policy.spy_cost*cp.abs(hedge-lasthedge)
        if policy.financing=='segregated':
            debit=cp.pos(policy.core+cp.sum(cp.pos(w))+hedge-1)
        else:
            debit=cp.pos(policy.core+cp.sum(w)+hedge-1)
        finance=(policy.margin_rate_annual*debit+
                 policy.borrow_cost_annual*cp.sum(cp.pos(-w)))*days_per_step/360
        pnl=x[:,h,:N]@w+x[:,h,N]*full_spy-turnover-finance
        R.append(pnl);cost_terms.append(turnover);carry_terms.append(finance)
        invested=cp.hstack([w,full_spy])
        z=factors.T@invested
        q=cp.Variable(nonneg=True)
        for A in G:
            limits.append(q>=cp.quad_form(z,A,assume_PSD=True)+cp.sum_squares(cp.multiply(np.sqrt(residual),invested)))
        risk_terms.append(q)
        last=w;lasthedge=hedge
    ret=cp.sum(cp.vstack(R),axis=0)
    eta=cp.Variable();slack=cp.Variable(S,nonneg=True)
    limits.append(slack>=-ret-eta)
    cvar=eta+cp.sum(slack)/(S*policy.tail_probability)
    obj=cp.sum(ret)/S-policy.cvar_weight*cvar-policy.risk_weight*cp.sum(cp.hstack(risk_terms))
    # Separate parameter/measurement uncertainty penalty is already priced
    # through a geodesic risk-set sup, not a fabricated dynamic alpha premium.
    problem=cp.Problem(cp.Maximize(obj),limits)
    try:problem.solve(solver=solver) if solver else problem.solve()
    except Exception as exc:raise RuntimeError(f'geometric MPC solver failed: {exc}') from exc
    if problem.status not in ('optimal','optimal_inaccurate') or W.value is None:
        raise RuntimeError('geometric MPC infeasible or inaccurate')
    w0=np.asarray(W.value[0]).ravel();spy=-float(beta@w0)
    gross=float(np.abs(w0).sum()+abs(policy.core+spy))
    if gross>policy.cap+1e-4 or max(abs(w0))>policy.max_stock_abs+1e-4:
        raise RuntimeError('geometric MPC constraint violation')
    return dict(status='MODEL_ONLY_NOT_BACKTEST',decision_weights=w0,
                spy_hedge=spy,first_whole_fund_gross=gross,
                predicted_utility=float(problem.value),
                predicted_worst_case_risk=float(risk_terms[0].value),
                predicted_cvar_loss=float(cvar.value),
                predicted_first_turnover_cost=float(cost_terms[0].value),
                predicted_first_margin_cost=float(carry_terms[0].value),
                error_if_treated_as_historical_return=True)
