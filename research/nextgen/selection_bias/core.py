"""Controlled Gaussian *synthetic* research search and false-winner stress.

There are no historical securities, no return files, and no OOS inference here.
No empirical Sharpe estimates, market-data or strategy parameters are consumed.
"""
from math import sqrt, isfinite
import numpy as np


def iid_sharpe_se(annual_sharpe, weeks, periods_per_year=52):
    """First-order iid normal approximation to annual Sharpe sampling SE."""
    s, n, k = float(annual_sharpe), int(weeks), float(periods_per_year)
    if not all(map(isfinite,(s,k))) or not isinstance(weeks,int) or weeks < 3 or k <= 0:
        raise ValueError('finite Sharpe, integer weeks >=3 and positive year scale required')
    return sqrt((k + s*s/2)/n)


def run(*, n_candidates=162, weeks=302, repetitions=1000,
        strategy_correlation=0.8, population_sharpe=0.6,
        screening_threshold=1.0, seed=20261119):
    """IID normal equal-alpha, equal-vol candidate models with common shocks.

    All models have the same population annual Sharpe. The winner of an
    in-sample search is then evaluated against a newly sampled independent
    period of equal length, with no re-selection. Correlations within a weekly
    candidate family are fixed by one-factor Gaussian innovations. This
    isolates *selection bias*; it does not test an alpha strategy.
    """
    if any(isinstance(x,bool) or not isinstance(x,(int,np.integer)) for x in
           (n_candidates,weeks,repetitions,seed)):
        raise ValueError('counts and seed must be integer')
    if not 1 <= n_candidates <= 2000 or weeks < 52 or repetitions < 100 or seed < 0:
        raise ValueError('sample/candidate counts or seed invalid')
    rho, true_sr, threshold = map(float,(strategy_correlation,population_sharpe,screening_threshold))
    if not all(map(isfinite,(rho,true_sr,threshold))) or not 0 <= rho < 1:
        raise ValueError('finite quantities and 0<=correlation<1 required')
    k = sqrt(52)
    weekly_sigma = 0.02
    weekly_mu = true_sr*weekly_sigma/k
    rng = np.random.default_rng(int(seed))
    # Do not generate information about external observations: all are simulated.
    best_insample=np.empty(repetitions,dtype=float)
    best_forward=np.empty(repetitions,dtype=float)
    sqrt_c, sqrt_i = sqrt(rho), sqrt(1-rho)
    for j in range(repetitions):
        common = rng.standard_normal((weeks,1))
        idiosyncratic = rng.standard_normal((weeks,n_candidates))
        r=weekly_mu+weekly_sigma*(sqrt_c*common+sqrt_i*idiosyncratic)
        sr=k*r.mean(axis=0)/r.std(axis=0,ddof=1)
        chosen=int(np.argmax(sr))
        best_insample[j]=sr[chosen]
        # The selected strategy's *future* is independent of its selection.
        fwd=weekly_mu+weekly_sigma*(sqrt_c*rng.standard_normal(weeks)+sqrt_i*rng.standard_normal(weeks))
        best_forward[j]=k*fwd.mean()/fwd.std(ddof=1)
    selected_above=best_insample>threshold
    return {
        'method':'synthetic iid normal equal-alpha one-factor correlated family',
        'n_candidates':int(n_candidates),'weeks_per_period':int(weeks),
        'repetitions':int(repetitions),'candidate_correlation':rho,
        'population_annual_sharpe':true_sr,'screening_threshold':threshold,
        'seed':int(seed),
        'mean_selected_insample_sharpe':float(best_insample.mean()),
        'mean_selected_forward_sharpe':float(best_forward.mean()),
        'mean_selection_optimism':float((best_insample-best_forward).mean()),
        'fraction_selected_insample_above_threshold':float(selected_above.mean()),
        'fraction_selected_insample_above_threshold_but_population_below':
            float(selected_above.mean()) if true_sr<threshold else 0.0,
        'iid_first_order_sharpe_se':iid_sharpe_se(true_sr,weeks),
        'monte_carlo_se_of_above_threshold_fraction':float(sqrt(selected_above.mean()*(1-selected_above.mean())/repetitions)),
        'note':'This is not a trading backtest, calibrated model of research history, statistical significance test, or predictive edge.',
    }
