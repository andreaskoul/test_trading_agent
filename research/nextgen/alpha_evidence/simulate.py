"""Locked synthetic family-wise test of the evidence gate, not a market backtest."""
from math import log, sqrt
from datetime import datetime,timezone
import numpy as np
from scipy.special import logsumexp
from .core import GatePolicy


def run(*, replicates=1200, weeks=156, correlation=0.8, seed=20261119,
        noise_sigma_nav=0.006, weak_gain_nav=0.001,
        strong_gain_nav=0.004, policy=None):
    if policy is None:
        policy=GatePolicy(family_id='SYNTHETIC_FAMILY',trial_id='SYNTHETIC_TRIAL',
            preregistered_at=datetime(2026,11,19,tzinfo=timezone.utc),
            registration_ref='SYNTHETIC_PREDECLARED_SIMULATION_PROTOCOL')
    if not isinstance(policy,GatePolicy):
        raise ValueError('GatePolicy required')
    if any(type(v) is not int for v in (replicates,weeks,seed)) or replicates<100 or weeks<policy.min_periods or seed<0:
        raise ValueError('replicates >=100, weeks >=min_periods, integer nonnegative seed')
    if not 0<=correlation<1 or not np.isfinite(correlation) or not np.isfinite(noise_sigma_nav) or noise_sigma_nav<=0:
        raise ValueError('valid correlation [0,1), positive noise sigma required')
    if not np.isfinite([weak_gain_nav,strong_gain_nav]).all() or weak_gain_nav<0 or strong_gain_nav<weak_gain_nav:
        raise ValueError('finite ordered null/weak/strong alternatives required')
    rng=np.random.default_rng(seed)
    m=policy.family_size
    lam=np.array(policy.lambdas,float)
    threshold=log(m/policy.family_alpha)
    out={}
    for scenario in ('null_family','conditional_heteroskedastic_null','one_weak','one_strong','regime_break','latent_regime_zero_unconditional'):
        # Correlated across proposed models within a week, iid over time.
        common=rng.normal(size=(replicates,weeks,1))
        independent=rng.normal(size=(replicates,weeks,m))
        noise=noise_sigma_nav*(sqrt(correlation)*common+sqrt(1-correlation)*independent)
        delta=noise.copy()
        if scenario=='conditional_heteroskedastic_null':
            # Predictable volatility depends only on earlier realised shocks.
            # New Gaussian innovation is mean-zero conditional on prior history.
            lagged=np.concatenate([np.zeros((replicates,1,1)),
                                   common[:,:-1,:]],axis=1)
            delta*=0.3+0.7*np.minimum(np.abs(lagged),2.0)
        if scenario=='one_weak':
            delta[:,:,0]+=weak_gain_nav
        elif scenario=='one_strong':
            delta[:,:,0]+=strong_gain_nav
        elif scenario=='regime_break':
            delta[:,:weeks//2,0]+=strong_gain_nav
            delta[:,weeks//2:,0]-=weak_gain_nav
        elif scenario=='latent_regime_zero_unconditional':
            # Mean zero across paths; persistent +/- regime learned from early
            # outcomes invalidates conditional-mean H0 for later observations.
            latent=rng.choice(np.array([-1,1]),size=replicates)
            delta[:,:,0]+=latent[:,None]*strong_gain_nav
        scaled=np.clip((delta-policy.hurdle_nav_per_period)/policy.clip_bound_nav,-1,1)
        cs=scaled.cumsum(axis=1)
        horizon=np.arange(1,weeks+1)
        # shape rep x week x candidates x mixture-L
        log_components=cs[:,:,:,None]*lam[None,None,None,:] - horizon[None,:,None,None]*lam[None,None,None,:]**2/2
        log_e=logsumexp(log_components,axis=3)-log(len(lam))
        historical=np.maximum.accumulate(log_e,axis=1)>=threshold
        current=log_e>=threshold
        historical[:,:policy.min_periods-1,:]=False
        current[:,:policy.min_periods-1,:]=False
        final=current[:,-1,:]
        ever=historical[:,-1,:]
        true_valid=bool(scenario!='null_family')
        out[scenario]={
            'family_false_review_rate':float((final.any(axis=1)).mean()) if not true_valid else float((final[:,1:].any(axis=1)).mean()),
            'true_candidate_review_rate':float(final[:,0].mean()) if true_valid else None,
            'true_candidate_ever_crossing_rate':float(ever[:,0].mean()) if true_valid else None,
            'true_candidate_lapsed_evidence_rate':float(np.mean(ever[:,0]&(~final[:,0]))) if true_valid else None,
            'conditional_null_valid_in_design':scenario in ('null_family','conditional_heteroskedastic_null'),
            'unconditional_null_false_review_warning':float(final[:,0].mean()) if scenario=='latent_regime_zero_unconditional' else None,
            'mean_final_clipped_increment_candidate_0':float(scaled[:,:,0].mean()),
            'mean_max_log_e_candidate_0':float(log_e[:,:,0].max(axis=1).mean()),
        }
    return {'design':'synthetic correlated Gaussian matched-pair increments with fixed clipped e-process family gate',
            'seed':seed,'replicates':replicates,'weeks':weeks,'candidate_family_size':m,
            'candidate_weekly_correlation':correlation,'noise_sigma_weekly_nav':noise_sigma_nav,
            'weak_increment_weekly_nav':weak_gain_nav,'strong_increment_weekly_nav':strong_gain_nav,
            'evidence_policy':{'clip_bound_nav':policy.clip_bound_nav,'hurdle_nav':policy.hurdle_nav_per_period,
                               'lambda_grid':list(policy.lambdas),'alpha_family':policy.family_alpha,
                               'min_weeks':policy.min_periods},
            'scenarios':out,
            'limitations':'persistent latent regime violates conditional null although unconditional mean is zero; no Sharpe or real fund backtest'}

if __name__=='__main__':
    import json
    print(json.dumps(run(),indent=2,allow_nan=False))
