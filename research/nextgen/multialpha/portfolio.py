"""Joint one-period, fund-level alpha/factor/cost/collateral research optimizer.

This is a static *conditional* cost forecast, NOT a settled broker ledger.
Uses conservative segregated-short-sale proceeds and fixed long exposure.
Any hard exposure bands and financing line must be approved fund policy.
"""
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, minimize

from .signals import Signal, combine, _utc
from .factors import RiskModel, covariance


@dataclass(frozen=True)
class Policy:
    gamma: float = 5.0
    max_fund_gross: float = 1.9
    max_book_gross: float = 0.6
    max_name_abs: float = 0.15
    max_segregated_debit: float = 0.5
    margin_rate_annual: float = 0.06
    spy_short_borrow_rate_annual: float = 0.0
    stock_impact_k: float = 0.05
    spy_spread: float = 0.0001
    aum: float = 10_000_000.0
    holding_days: float = 7.0
    day_count: float = 360.0
    epsilon: float = 1e-9
    tolerance: float = 2e-6
    dollar_neutral: bool = True
    spy_shortable: bool = True


def _v(x, n, name):
    a = np.asarray(x,dtype=float)
    if a.shape != (n,) or not np.isfinite(a).all():
        raise ValueError(f'{name}: finite vector of {n} elements required')
    return a


def _scalar(x,name):
    if isinstance(x,bool) or not isinstance(x,(int,float,np.integer,np.floating)) or not np.isfinite(x):
        raise ValueError(f'{name}: finite numeric value required')
    return float(x)


def solve(*, sources: list[Signal], security_ids: tuple[str,...], decision_at:datetime,
          holding_end_at:datetime, risk:RiskModel, beta, spy_expected_excess,
          core_spy, previous_weights, previous_net_spy, stock_half_spread,
          stock_daily_vol, stock_adv, stock_short_borrow_rates, stock_shortable,
          factor_lower=None, factor_upper=None, market_asof_at=None,
          borrow_asof_at=None, holdings_asof_at=None,
          policy:Policy=Policy()):
    """Minimize convex negative of full-fund expected net utility.

    x=[w(n), abs_w_epigraph(n), long_stock_epigraph(n), abs_spy,
       long_spy, segregated_cash_debit]. Factor bands apply to *residual*
    stock exposures B.T@w. SPY market beta hedge remains q=core-beta@w.

    No optimisation of alpha weights or core regime; both are externally
    governed. Borrow fee/interest magnitudes are hypothetical research inputs.
    """
    if not isinstance(policy,Policy):
        raise ValueError('explicit Policy required')
    nums={k:_scalar(getattr(policy,k),k) for k in (
        'gamma','max_fund_gross','max_book_gross','max_name_abs',
        'max_segregated_debit','margin_rate_annual',
        'spy_short_borrow_rate_annual','stock_impact_k','spy_spread',
        'aum','holding_days','day_count','epsilon','tolerance')}
    if any(nums[k]<=0 for k in ('gamma','max_fund_gross','max_book_gross',
              'max_name_abs','aum','holding_days','day_count','epsilon','tolerance')):
        raise ValueError('positive risk, capital, size and numerical scales required')
    if any(nums[k]<0 for k in ('max_segregated_debit','margin_rate_annual',
                 'spy_short_borrow_rate_annual','stock_impact_k','spy_spread')):
        raise ValueError('nonnegative funding/cost parameters required')
    if type(policy.dollar_neutral) is not bool or type(policy.spy_shortable) is not bool:
        raise ValueError('boolean fund policy controls required')
    for stamp,name in ((risk.asof_at,'risk.asof_at'),
                       (market_asof_at,'market_asof_at'),
                       (borrow_asof_at,'borrow_asof_at'),
                       (holdings_asof_at,'holdings_asof_at')):
        if _utc(stamp,name)>_utc(decision_at,'decision_at'):
            raise ValueError(f'{name}: future information relative to decision')
    packet=combine(sources,security_ids=security_ids,
                   decision_at=decision_at,holding_end_at=holding_end_at)
    mu=np.asarray(packet['mu'],float)
    n=len(mu)
    rm=covariance(risk)
    S=rm['residual_cov']
    c=rm['spy_cov']
    sv=rm['spy_var']
    B=rm['factor_loadings']
    if B.shape[0]!=n:
        raise ValueError('factor risk securities must align with alpha universe')
    _,k_f=B.shape
    beta=_v(beta,n,'beta')
    old=_v(previous_weights,n,'previous_weights')
    spread=_v(stock_half_spread,n,'stock_half_spread')
    daily_vol=_v(stock_daily_vol,n,'stock_daily_vol')
    adv=_v(stock_adv,n,'stock_adv')
    borrow=_v(stock_short_borrow_rates,n,'stock_short_borrow_rates')
    if (spread<0).any() or (daily_vol<0).any() or (adv<=0).any() or (borrow<0).any():
        raise ValueError('nonnegative costs and strictly positive ADV required')
    eligible=tuple(stock_shortable)
    if len(eligible)!=n or any(type(flag) not in (bool,np.bool_) for flag in eligible):
        raise ValueError('known-at-decision shortable flag required for every historical name')
    s=_scalar(core_spy,'core_spy')
    old_spy=_scalar(previous_net_spy,'previous_net_spy')
    spy_mu=_scalar(spy_expected_excess,'spy_expected_excess')
    if abs(s)>policy.max_fund_gross+policy.tolerance:
        raise ValueError('frozen core itself breaches proposed whole-fund gross limit')
    if max(s-1.0,0.0)>policy.max_segregated_debit+policy.tolerance:
        raise ValueError('frozen core alone breaches segregated cash debit limit')
    low=np.full(k_f,-np.inf) if factor_lower is None else _v(factor_lower,k_f,'factor_lower')
    high=np.full(k_f,np.inf) if factor_upper is None else _v(factor_upper,k_f,'factor_upper')
    if (low>high).any() or (low>0).any() or (high<0).any():
        raise ValueError('factor bands must be ordered and contain zero for core-only feasible start')
    # Trading risk is not allowed to be inferred from model-error covariance.
    t=policy.holding_days/policy.day_count
    impact=policy.stock_impact_k*daily_vol*np.sqrt(policy.aum/adv)
    eps=policy.epsilon
    N=3*n+3
    wi=slice(0,n);ui=slice(n,2*n);pi=slice(2*n,3*n)
    v=3*n; pspy=3*n+1; debit=3*n+2

    def parts(z):
        w=z[wi]; q=s-float(beta@w)
        dw=w-old;dq=q-old_spy
        stock_sp=float(spread@(np.sqrt(dw*dw+eps*eps)-eps))
        imp=float(impact@((dw*dw+eps*eps)**.75-eps**1.5))
        spy_sp=float(policy.spy_spread*(np.sqrt(dq*dq+eps*eps)-eps))
        short_st=np.clip(-w,0,None);short_spy=max(-q,0)
        L=float(np.clip(w,0,None).sum()+max(q,0))
        d=max(L-1.0,0.0)
        # For a valid optimum auxiliary epigraph components are minimal as
        # rates >= 0. Evaluate the REAL quantities from w independently.
        return dict(expected_excess=float(s*spy_mu+mu@w),
                    variance=float(s*s*sv+2*s*(c@w)+w@S@w),
                    spread=stock_sp,impact=imp,spy_spread=spy_sp,
                    funding=t*policy.margin_rate_annual*d,
                    stock_borrow=t*float(borrow@short_st),
                    spy_short_borrow=t*policy.spy_short_borrow_rate_annual*short_spy,
                    debit=d,long_notional=L,spy_position=q)

    def f(z):
        w=z[wi];p=z[pi];q=s-float(beta@w)
        dw=w-old;dq=q-old_spy
        return float(-(s*spy_mu+mu@w)
            +policy.gamma/2*(s*s*sv+2*s*c@w+w@S@w)
            +spread@(np.sqrt(dw*dw+eps*eps)-eps)
            +impact@((dw*dw+eps*eps)**.75-eps**1.5)
            +policy.spy_spread*(np.sqrt(dq*dq+eps*eps)-eps)
            +t*(policy.margin_rate_annual*z[debit]
                 +borrow@(p-w)
                 +policy.spy_short_borrow_rate_annual*(z[pspy]-q)))

    def jac(z):
        w=z[wi];dw=w-old;q=s-float(beta@w);dq=q-old_spy
        H=dw*dw+eps*eps
        g=(-mu +policy.gamma*(s*c+S@w)
           +spread*dw/np.sqrt(H)
           +1.5*impact*dw*H**(-.25)
           -policy.spy_spread*beta*dq/np.sqrt(dq*dq+eps*eps)
           +t*(-borrow+policy.spy_short_borrow_rate_annual*beta))
        ans=np.zeros(N)
        ans[wi]=g
        ans[pi]=t*borrow
        ans[pspy]=t*policy.spy_short_borrow_rate_annual
        ans[debit]=t*policy.margin_rate_annual
        return ans

    rows=[];lower=[];upper=[]
    def constrain(a,l=-np.inf,u=np.inf):
        rows.append(a);lower.append(l);upper.append(u)
    for i in range(n):
        a=np.zeros(N);a[n+i]=1;a[i]=-1;constrain(a,0)   # u>=w
        a=np.zeros(N);a[n+i]=1;a[i]=1;constrain(a,0)    # u>=-w
        a=np.zeros(N);a[2*n+i]=1;a[i]=-1;constrain(a,0) # p>=w
    a=np.zeros(N);a[v]=1;a[wi]=beta;constrain(a,s)        # v>=q=s-beta@w
    a=np.zeros(N);a[v]=1;a[wi]=-beta;constrain(a,-s)      # v>=-q
    a=np.zeros(N);a[pspy]=1;a[wi]=beta;constrain(a,s)    # pspy>=q
    a=np.zeros(N);a[ui]=1;a[v]=1;constrain(a,u=policy.max_fund_gross)
    a=np.zeros(N);a[ui]=1;constrain(a,u=policy.max_book_gross)
    a=np.zeros(N);a[pi]=1;a[pspy]=1;a[debit]=-1;constrain(a,u=1.0)
    for j in range(k_f):
        if np.isfinite(low[j]) or np.isfinite(high[j]):
            a=np.zeros(N);a[wi]=B[:,j];constrain(a,low[j],high[j])
    if policy.dollar_neutral:
        a=np.zeros(N);a[wi]=1;constrain(a,0,0)
    if not policy.spy_shortable:
        a=np.zeros(N);a[wi]=beta;constrain(a,u=s)  # q>=0
    bounds_low=np.r_[np.full(n,-policy.max_name_abs),np.zeros(2*n+3)]
    bounds_high=np.r_[np.full(n,policy.max_name_abs),np.full(2*n,np.inf),
                      np.inf,np.inf,policy.max_segregated_debit]
    for i,can_short in enumerate(eligible):
        if not can_short:
            bounds_low[i]=0
    init=np.zeros(N)
    init[v]=abs(s);init[pspy]=max(s,0);init[debit]=max(s-1.0,0.0)
    A=np.stack(rows); lo=np.asarray(lower); hi=np.asarray(upper)
    equal=np.isfinite(lo)&np.isfinite(hi)&(lo==hi)
    constraints=[]
    if np.any(~equal):
        constraints.append(LinearConstraint(A[~equal],lo[~equal],hi[~equal]))
    if np.any(equal):
        constraints.append(LinearConstraint(A[equal],lo[equal],hi[equal]))
    opt=minimize(f,init,jac=jac,method='SLSQP',
                 bounds=Bounds(bounds_low,bounds_high),
                 constraints=constraints,
                 options={'maxiter':1500,'ftol':1e-12})
    if not opt.success or not np.isfinite(opt.x).all():
        raise RuntimeError(f'fund-aware multi-alpha optimisation did not converge: {opt.message}')
    w=np.asarray(opt.x[wi],dtype=float)
    pp=parts(opt.x)
    gross=float(np.abs(w).sum()+abs(pp['spy_position']))
    book=float(np.abs(w).sum())
    expo=B.T@w
    failures=[max(0,gross-policy.max_fund_gross),max(0,book-policy.max_book_gross),
              max(0,float(np.max(np.abs(w)))-policy.max_name_abs),
              max(0,pp['debit']-policy.max_segregated_debit),
              max(0,float(np.max(low-expo))),max(0,float(np.max(expo-high)))]
    if policy.dollar_neutral:failures.append(abs(float(w.sum())))
    if not policy.spy_shortable:failures.append(max(-pp['spy_position'],0))
    failures.extend(max(-w[i],0) for i,can_short in enumerate(eligible) if not can_short)
    if max(failures)>policy.tolerance:
        raise RuntimeError(f'post-solve exact constraints failed: {max(failures)}')
    # Aux variable optimality is explicitly checked: otherwise margin/stock
    # borrow financing could be misreported even with a feasible portfolio.
    if policy.margin_rate_annual>0 and abs(float(opt.x[debit])-pp['debit'])>policy.tolerance:
        raise RuntimeError('funding auxiliary does not match actual segregated debit')
    alpha_w=dict(packet['weights'])
    utility=float(pp['expected_excess']-policy.gamma*pp['variance']/2-
            pp['spread']-pp['impact']-pp['spy_spread']-pp['funding']-
            pp['stock_borrow']-pp['spy_short_borrow'])
    if abs(utility+f(opt.x))>1e-5:
        raise RuntimeError('objective-to-ledger mismatch; stop before reporting results')
    return dict(weights=w,net_spy=pp['spy_position'],
                fund_gross=gross,book_gross=book, factor_exposures=expo,
                predicted_fund_variance=pp['variance'],
                predicted_excess=pp['expected_excess'],
                predicted_utility_net_costs=utility,
                cost_breakdown={x:pp[x] for x in
                   ('spread','impact','spy_spread','funding','stock_borrow','spy_short_borrow')},
                long_notional=pp['long_notional'],segregated_debit=pp['debit'],
                approved_alphas=packet['approved'],shadow_alphas=packet['shadow'],
                blend_weights=alpha_w,source_corr=packet['pairwise_signal_corr'],
                solver_status=opt.message,max_constraint_error=max(failures))
