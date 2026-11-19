"""Research-only fund-aware convex allocator; uses no broker or historical data.

A fixed SPY core s plus beta-hedged residual equity book w has actual SPY
exposure q=s-beta'w and fund gross |q|+||w||_1. The joint constraint is
implemented with an *exact linear epigraph* rather than smooth gross proxy.

The objective uses calibrated residual excess returns in holding-period units;
CORE's forecast is exogenous and its exposure is frozen as owner policy.
Financing and short collateral are deliberately not modeled here. Do not trade.
"""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, minimize


@dataclass(frozen=True)
class Config:
    gamma: float = 5.0
    max_fund_gross: float = 1.9
    max_book_gross: float = 0.6
    max_name_abs: float = 0.15
    aum: float = 10_000_000.0
    impact_k: float = 0.5
    spy_spread: float = 0.0005
    epsilon: float = 1e-9
    tolerance: float = 1e-7
    dollar_neutral: bool = True


def _vector(values, name, n=None):
    a = np.asarray(values, dtype=float)
    if a.ndim != 1 or not a.size or not np.isfinite(a).all() or (n is not None and len(a) != n):
        raise ValueError(f'{name}: expected aligned finite one-dimensional array')
    return a


def _num(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.floating, np.integer)) or not np.isfinite(value):
        raise ValueError(f'{name}: expected finite numeric scalar')
    return float(value)


def fund_gross(core, weights, beta):
    w = _vector(weights, 'weights')
    b = _vector(beta, 'beta', len(w))
    s = _num(core, 'core')
    q = s - float(b @ w)
    return float(abs(q)+np.abs(w).sum())


def solve(*, expected_residual_excess, residual_covariance, beta, residual_spy_cov,
          spy_expected_excess, spy_variance, core_spy, previous_weights,
          previous_net_spy, stock_half_spread, stock_daily_vol, stock_adv,
          config=Config()):
    """Constrained static one-period mean-variance forecast allocation.

    Joint whole-fund gross is bounded via abs epigraph variables u>=|w|,
    v>=|s-beta'w|, sum(u)+v <= max_fund_gross. This is convex for fixed core.

    Expected full-fund excess return = s*mu_spy + w'mu_residual;
    variance = s^2*var_spy + 2*s*c'w + w'Sigma_residual w.
    Costs: stock spread and sqrt impact (d^1.5), SPY turnover spread.
    Actual future net PnL, funding, borrow and margin are OUT OF SCOPE.
    """
    if not isinstance(config, Config):
        raise ValueError('Config required')
    vals = {k: _num(getattr(config, k), k) for k in
            ('gamma','max_fund_gross','max_book_gross','max_name_abs','aum',
             'impact_k','spy_spread','epsilon','tolerance')}
    if any(vals[k] <= 0 for k in ('gamma','max_fund_gross','max_book_gross',
                                'max_name_abs','aum','epsilon','tolerance')):
        raise ValueError('strictly positive risk/budgets/AUM/epsilon/tolerance required')
    if vals['impact_k'] < 0 or vals['spy_spread'] < 0 or type(config.dollar_neutral) is not bool:
        raise ValueError('invalid cost or neutrality assumption')
    m = _vector(expected_residual_excess, 'mu')
    n=len(m)
    b=_vector(beta, 'beta',n)
    c=_vector(residual_spy_cov, 'residual_spy_cov',n)
    old=_vector(previous_weights,'previous_weights',n)
    spr=_vector(stock_half_spread,'stock_half_spread',n)
    sig=_vector(stock_daily_vol,'stock_daily_vol',n)
    adv=_vector(stock_adv,'stock_adv',n)
    if (spr < 0).any() or (sig < 0).any() or (adv <= 0).any():
        raise ValueError('nonnegative spread/daily vol, strictly positive ADV required')
    spy_mu = _num(spy_expected_excess,'spy_expected_excess')
    spy_var = _num(spy_variance,'spy_variance')
    core = _num(core_spy,'core_spy')
    old_q = _num(previous_net_spy,'previous_net_spy')
    if spy_var <= 0 or abs(core) > config.max_fund_gross+config.tolerance:
        raise ValueError('invalid SPY variance or fixed core breaches fund gross')
    cov=np.asarray(residual_covariance,dtype=float)
    if cov.shape!=(n,n) or not np.isfinite(cov).all() or not np.allclose(cov,cov.T,rtol=0,atol=1e-11):
        raise ValueError('finite symmetric residual covariance required')
    # Factor/SPY joint covariance must be PSD: otherwise risk is not convex.
    joint=np.block([[cov, c[:,None]], [c[None,:],np.array([[spy_var]])]])
    if np.linalg.eigvalsh(joint).min() < -1e-10:
        raise ValueError('joint residual+SPY covariance must be PSD')
    if np.any(np.abs(old)>config.max_name_abs+config.tolerance):
        raise ValueError('previous per-name position exceeds supported bounds')
    k = config.impact_k * sig * np.sqrt(config.aum/adv)
    eps=config.epsilon
    s=core

    def parts(w):
        d=w-old
        q=s-float(b@w)
        dq=q-old_q
        soft=np.sqrt(d*d+eps*eps)-eps
        soft_spy=np.sqrt(dq*dq+eps*eps)-eps
        impact=(d*d+eps*eps)**0.75-eps**1.5
        return {
            'expected_full_excess':float(s*spy_mu+w@m),
            'risk_penalty':float(config.gamma*(s*s*spy_var+2*s*(c@w)+w@cov@w)/2),
            'stock_spread':float(spr@soft),
            'stock_impact':float(k@impact),
            'spy_turnover_spread':float(config.spy_spread*soft_spy),
        }

    def objective(z):
        v=parts(z[:n])
        return (-v['expected_full_excess']+v['risk_penalty']+v['stock_spread']+
                v['stock_impact']+v['spy_turnover_spread'])

    def gradient(z):
        w=z[:n]
        d=w-old
        den=d*d+eps*eps
        dq=s-float(b@w)-old_q
        grad=(-m+config.gamma*(cov@w+s*c) + spr*d/np.sqrt(den) +
              1.5*k*d*den**(-.25) - config.spy_spread*b*dq/np.sqrt(dq*dq+eps*eps))
        return np.r_[grad,np.zeros(n+1)]

    # Decision z=[w_0..w_n, u_0..u_n, v] where u_i>=abs(w_i) and
    # v>=abs(s-beta'w). Exact abs constraints are ALL LINEAR.
    nvar=2*n+1
    mat=[]; lower=[]; upper=[]
    for i in range(n):
        a=np.zeros(nvar);a[n+i]=1;a[i]=-1;mat.append(a);lower.append(0);upper.append(np.inf)
        a=np.zeros(nvar);a[n+i]=1;a[i]=1;mat.append(a);lower.append(0);upper.append(np.inf)
    a=np.zeros(nvar);a[-1]=1;a[:n]=b;mat.append(a);lower.append(s);upper.append(np.inf)
    a=np.zeros(nvar);a[-1]=1;a[:n]=-b;mat.append(a);lower.append(-s);upper.append(np.inf)
    a=np.zeros(nvar);a[n:]=1;mat.append(a);lower.append(-np.inf);upper.append(config.max_fund_gross)
    a=np.zeros(nvar);a[n:2*n]=1;mat.append(a);lower.append(-np.inf);upper.append(config.max_book_gross)
    constraints=[LinearConstraint(np.array(mat),np.array(lower),np.array(upper))]
    if config.dollar_neutral:
        a=np.zeros(nvar);a[:n]=1
        constraints.append(LinearConstraint(a.reshape(1,-1),0,0))
    bounds=Bounds(np.r_[np.full(n,-config.max_name_abs),np.zeros(n+1)],
                  np.r_[np.full(n,config.max_name_abs),np.full(n+1,np.inf)])
    # Start at a guaranteed feasible core-only portfolio. A currently breached
    # previous position can therefore be remedied; this is not broker execution.
    x0=np.r_[np.zeros(n),np.zeros(n),abs(s)]
    if fund_gross(s,old,b)<=config.max_fund_gross and np.abs(old).sum()<=config.max_book_gross and (not config.dollar_neutral or abs(old.sum())<config.tolerance):
        x0=np.r_[old,np.abs(old),abs(s-float(b@old))]
    res=minimize(objective,x0,jac=gradient,method='SLSQP',bounds=bounds,
                 constraints=constraints,options={'maxiter':1500,'ftol':1e-12})
    w=np.asarray(res.x[:n],dtype=float)
    q=s-float(b@w)
    gross=fund_gross(s,w,b)
    book_gross=float(np.abs(w).sum())
    violation=max(0,gross-config.max_fund_gross,book_gross-config.max_book_gross,
                  float(np.max(np.abs(w)))-config.max_name_abs,
                  abs(float(w.sum())) if config.dollar_neutral else 0.)
    if not res.success or not np.isfinite(res.x).all() or violation>config.tolerance:
        raise RuntimeError(f'fund-aware optimiser fails closed: {res.message}; violation={violation:.9g}')
    detail=parts(w)
    return {'weights':w,'net_spy':q,'beta_hedge':q-s,'book_beta':float(b@w),
            'fund_gross':gross,'book_gross':book_gross,'fund_gross_limit':config.max_fund_gross,
            'net_expected_quadratic_utility':float(-objective(res.x)),
            'expected_full_excess':detail['expected_full_excess'],
            'risk_full_variance':float(s*s*spy_var+2*s*(c@w)+w@cov@w),
            'cost_components':detail,'stock_turnover_one_way':float(np.abs(w-old).sum()/2),
            'spy_turnover_abs':abs(q-old_q),'max_violation':violation,'solver_message':res.message}
