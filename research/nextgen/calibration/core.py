"""Research-only exact mean-variance estimation-error identities.

The derived identities apply ONLY to unconstrained quadratic mean-variance
utility with known fixed SPD covariance and unbiased zero-mean forecasts.
They do not apply as equalities to the fund's gross/beta/cost constraints.
"""
from dataclasses import dataclass
from math import isfinite
import numpy as np


@dataclass(frozen=True)
class CalibrationRisk:
    signal_strength: float
    forecast_noise_strength: float
    forecast_to_signal_ratio: float
    optimal_shrink: float
    oracle_utility: float
    unshrunk_expected_utility: float
    shrunk_expected_utility: float
    predicted_unshrunk_regret: float


def _spd(a, n, label):
    a = np.asarray(a, dtype=float)
    if a.shape != (n,n) or not np.isfinite(a).all():
        raise ValueError(f'{label}: finite aligned square matrix required')
    if not np.allclose(a, a.T, rtol=0, atol=1e-12):
        raise ValueError(f'{label}: symmetric matrix required')
    if np.linalg.eigvalsh(a).min() <= 0:
        raise ValueError(f'{label}: strictly positive definite required')
    return a


def characterize(true_mu, covariance, forecast_noise_covariance, risk_aversion=5.0):
    """E[true quadratic utility] of lambda*Sigma^-1*forecast/risk_aversion.

    True forecast = mu + epsilon, E epsilon = 0, E eps eps' = Omega.
    A=mu' Sigma^-1 mu, B=tr(Sigma^-1 Omega), optimal lambda=A/(A+B).
    E U(lambda)=lambda*A/gamma - lambda^2*(A+B)/(2 gamma).
    If A=0, best shrink is zero; B can be nonzero.
    """
    m = np.asarray(true_mu,dtype=float)
    if m.ndim != 1 or m.size == 0 or not np.isfinite(m).all():
        raise ValueError('true_mu: finite 1D vector required')
    n = len(m)
    S = _spd(covariance,n,'covariance')
    O = np.asarray(forecast_noise_covariance,dtype=float)
    if O.shape != (n,n) or not np.isfinite(O).all() or not np.allclose(O,O.T,rtol=0,atol=1e-12):
        raise ValueError('forecast noise covariance must be finite symmetric')
    if np.linalg.eigvalsh(O).min() < -1e-12:
        raise ValueError('forecast noise covariance must be positive semidefinite')
    gamma = float(risk_aversion)
    if not isfinite(gamma) or gamma <= 0:
        raise ValueError('risk aversion must be finite positive')
    A = float(m @ np.linalg.solve(S,m))
    B = float(np.trace(np.linalg.solve(S,O)))
    if A < -1e-12 or B < -1e-12:
        raise ArithmeticError('impossible negative risk-weighted strengths')
    A, B = max(A,0.0), max(B,0.0)
    lam = A/(A+B) if A+B > 0 else 0.0
    return CalibrationRisk(
        signal_strength=A,
        forecast_noise_strength=B,
        forecast_to_signal_ratio=B/A if A > 0 else (float('inf') if B>0 else 0.0),
        optimal_shrink=lam,
        oracle_utility=A/(2*gamma),
        unshrunk_expected_utility=(A-B)/(2*gamma),
        shrunk_expected_utility=A*A/(2*gamma*(A+B)) if A+B > 0 else 0.0,
        predicted_unshrunk_regret=B/(2*gamma),
    )


def realized_utility(true_mu,covariance,weights,risk_aversion):
    mu=np.asarray(true_mu,dtype=float)
    w=np.asarray(weights,dtype=float)
    if mu.ndim != 1 or w.shape != mu.shape or not np.isfinite(mu).all() or not np.isfinite(w).all():
        raise ValueError('aligned finite vectors required')
    S=_spd(covariance,len(mu),'covariance')
    gamma=float(risk_aversion)
    if not isfinite(gamma) or gamma <= 0:
        raise ValueError('invalid risk aversion')
    return float(mu@w-gamma/2*w@S@w)


def simulate(*, ratios=(0.25,1.0,4.0,16.0), draws=20000, seed=20261119,
             n_assets=24, gamma=5.0):
    """Pre-specified Gaussian Monte Carlo check against analytic identities.

    Noise covariance proportional to return covariance. Exactly no fund data.
    A different random stream is used across noise ratios, always same true mu.
    """
    if isinstance(draws,bool) or not isinstance(draws,int) or draws<500:
        raise ValueError('draws must be integer >=500')
    if isinstance(seed,bool) or not isinstance(seed,int) or seed<0:
        raise ValueError('seed must be nonnegative integer')
    if isinstance(n_assets,bool) or not isinstance(n_assets,int) or not 2<=n_assets<=200:
        raise ValueError('n_assets outside supported range')
    ratios=np.asarray(ratios,dtype=float)
    if ratios.ndim!=1 or ratios.size==0 or not np.isfinite(ratios).all() or (ratios<0).any():
        raise ValueError('ratios require finite nonnegative values')
    rng=np.random.default_rng(seed)
    X=rng.normal(size=(n_assets,4))*0.004
    S=X@X.T+np.diag((0.015+0.005*rng.random(n_assets))**2)
    mu=np.linspace(-0.002,0.002,n_assets)
    A=float(mu@np.linalg.solve(S,mu))
    w0=np.linalg.solve(S,mu)/gamma
    oracle=realized_utility(mu,S,w0,gamma)
    out=[]
    for ratio in ratios:
        omega=S*(ratio*A/n_assets)
        info=characterize(mu,S,omega,gamma)
        noise=rng.standard_normal((draws,n_assets))@np.linalg.cholesky(omega).T if ratio>0 else np.zeros((draws,n_assets))
        forecast=mu[None,:]+noise
        w=np.linalg.solve(S,forecast.T).T/gamma
        w_sh=info.optimal_shrink*w
        def stats(weights):
            pay=weights@mu-.5*gamma*np.einsum('ij,jk,ik->i',weights,S,weights,optimize=True)
            return float(pay.mean()), float(pay.std(ddof=1)/np.sqrt(draws))
        u_raw,se_raw=stats(w)
        u_sh,se_sh=stats(w_sh)
        out.append({
            'noise_to_signal':float(ratio), 'theoretical_optimal_shrink':info.optimal_shrink,
            'oracle_utility':oracle,
            'theory_unshrunk_utility':info.unshrunk_expected_utility,
            'mc_unshrunk_utility':u_raw,
            'mc_se_unshrunk':se_raw,
            'theory_shrunk_utility':info.shrunk_expected_utility,
            'mc_shrunk_utility':u_sh,
            'mc_se_shrunk':se_sh,
            'unshrunk_negative_expected_utility':info.unshrunk_expected_utility<0,
            'theory_to_oracle_raw':info.unshrunk_expected_utility/oracle,
            'theory_to_oracle_shrunk':info.shrunk_expected_utility/oracle,
        })
    return {'design':'synthetic unconstrained Gaussian quadratic utility, known Sigma and mu',
            'n_assets':n_assets,'draws':draws,'seed':seed,'gamma':gamma,
            'per_ratio':out,
            'limitations':'no optimizer constraints, transaction costs, or market backtest; known true mu is oracle-only'}
