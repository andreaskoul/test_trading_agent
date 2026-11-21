"""Joint posterior-predictive scenario sampler for risk/alpha -> robust MPC.

No prices fetched or future return arrays consumed. The source forecast
bundle is required to state its as-of date, training cutoff, factor/risk
model vintage and uncertainty. These contracts do not *prove* PIT lineage;
actual source hashes and data acquisition logs still require audit.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import numpy as np
from .covariance import psd


def sample_multivariate_t(mu, cov, scenarios=1024, df=6.,seed=20261121,
                          posterior_std=None, across_horizon_rho=.0):
    """H x (N+1) expected return and SPD covariance -> M x H x (N+1).

    Student-t scaling normalised to unit variance, independent across weeks
    unless specified temporal AR(1) correlation. Parameter uncertainty adds
    a draw of uncertain mu per scenario (persistent across all H weeks).
    """
    m=np.asarray(mu,float);C=np.asarray(cov,float)
    if m.ndim!=2 or C.shape!=(m.shape[1],m.shape[1]) or not np.isfinite(m).all() or not np.isfinite(C).all():
        raise ValueError('invalid expected returns/covariance')
    if scenarios<20 or df<=2 or not -.98<across_horizon_rho<.98:
        raise ValueError('invalid scenario count, degrees of freedom or autocorrelation')
    s=np.zeros_like(m) if posterior_std is None else np.asarray(posterior_std,float)
    if s.shape!=m.shape or np.any(s<0) or not np.isfinite(s).all():raise ValueError('uncertainty input')
    C=psd(C)
    L=np.linalg.cholesky(C)
    rng=np.random.default_rng(seed)
    M,H,N=scenarios,*m.shape
    draws=rng.standard_normal((M,H,N))
    if across_horizon_rho:
        for t in range(1,H):draws[:,t]=across_horizon_rho*draws[:,t-1]+np.sqrt(1-across_horizon_rho**2)*draws[:,t]
    innovations=draws@L.T
    variance_scale=np.sqrt((df-2)/rng.chisquare(df,size=(M,H,1)))
    alpha_param=rng.normal(size=(M,1,N))*s[None,:,:]
    return (m[None,:,:]+alpha_param+innovations*variance_scale).astype(np.float64)


def validate_forecast_asof(asof,fit_end,maturity_end,validation_end='2019-12-31'):
    dates=[str(x)[:10] for x in (asof,fit_end,maturity_end)]
    if any(len(d)!=10 or d[4]!='-' or d[7]!='-' for d in dates):raise ValueError('date format YYYY-MM-DD')
    if dates[1]>dates[0] or dates[2]>dates[0]:raise ValueError('STOP: model uses information after forecast as-of')
    if any(d>validation_end for d in dates):raise ValueError('STOP: development-only experiment read 2020+ period')


def build_bundle(forecast_npz,out_path,scenarios=1024,df=6,seed=20261121):
    """Read model forecast NPZ and generate simulation-only MPC input NPZ.

    Required arrays: mu(H,N+1), cov(N+1,N+1), previous(N), beta(N),
    core scalar, hedge_prev scalar, alpha_std(H,N+1),
    asof/fit_end/label_maturity_end strings. Optional ADV and spread.
    Last asset is SPY. Keeps only model estimates and no realised future R.
    """
    source=Path(forecast_npz);out=Path(out_path)
    if out.exists():raise FileExistsError('NO OVERWRITE: '+str(out))
    with np.load(source,allow_pickle=False) as z:
        names={'mu','cov','previous','beta','core','hedge_prev','alpha_std','asof','fit_end','label_maturity_end'}
        if not names<=set(z.files):raise ValueError('STOP: missing '+str(names-set(z.files)))
        data={k:z[k] for k in names}
        for key in ('half_spread_bp','adv_max_weight_change'):
            if key in z.files:data[key]=z[key]
    dates=[str(data[k].item()) for k in ('asof','fit_end','label_maturity_end')]
    validate_forecast_asof(*dates)
    mu=data['mu'];cov=data['cov'];std=data['alpha_std']
    if mu.ndim!=2 or mu.shape[1]!=len(data['previous'])+1 or std.shape!=mu.shape:
        raise ValueError('STOP: model expected return/stock dimensions inconsistent')
    res=sample_multivariate_t(mu,cov,scenarios,df,seed,std)
    # Optimizer target mu excludes SPY column, which remains in scenarios.
    dest=dict(mu=mu[:,:-1],scenarios=res,previous=data['previous'],beta=data['beta'],
              core=data['core'],hedge_prev=data['hedge_prev'],alpha_posterior_std=std[:,:-1],
              asof=data['asof'],fit_end=data['fit_end'],label_maturity_end=data['label_maturity_end'],
              forecast_source_sha256=np.array(hashlib.sha256(source.read_bytes()).hexdigest()))
    for k in ('half_spread_bp','adv_max_weight_change'):
        if k in data:dest[k]=data[k]
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('xb') as f:np.savez_compressed(f,**dest)
    return {'forecast_sha256':dest['forecast_source_sha256'].item(),
            'asof':dates[0],'scenarios':scenarios,'H':mu.shape[0],'N_stocks':mu.shape[1]-1}
