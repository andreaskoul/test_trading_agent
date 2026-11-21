"""Synthetic ex-ante objective comparison, not empirical research evidence."""
import numpy as np
import pytest
from research.nextgen.fund_aware.experiment import experiment,uniform_scale_to_fund_cap,score_policy


def test_scaling_bisection_both_regimes():
    beta=np.array([1.2,.8,1.2,.8]);w=np.array([-.15,.15,-.15,.15])
    result,scale=uniform_scale_to_fund_cap(1.3,w,beta,1.9)
    assert np.isclose(scale,5/6,atol=1e-10)
    assert np.isclose(np.abs(1.3-beta@result)+np.abs(result).sum(),1.9)
    result,scale=uniform_scale_to_fund_cap(.7,w,beta,1.9)
    assert np.isclose(scale,1.)
    with pytest.raises(ValueError):uniform_scale_to_fund_cap(2.0,w,beta,1.9)


def test_joint_can_only_beat_best_projection_under_same_objective():
    x=experiment(n_trials=12,seed=11)
    for core in x['core_scenarios'].values():
        assert core['mean_joint_vs_projected_utility']>=-1e-8
        assert core['max_baseline_gross_violation']<=1e-7
        assert core['max_joint_gross_violation']<=1e-7


def test_deterministic_stress():
    a=experiment(n_trials=10,seed=12)
    b=experiment(n_trials=10,seed=12)
    assert a==b


def test_invalid_experiment_setup():
    with pytest.raises(ValueError): experiment(n_trials=1)
    with pytest.raises(ValueError): experiment(seed=-1)


def test_forecast_error_falsification_reproducibility():
    from research.nextgen.fund_aware.experiment import forecast_error_falsification
    a=forecast_error_falsification(n_trials=20,seed=41,noise_levels=(0.,.04))
    b=forecast_error_falsification(n_trials=20,seed=41,noise_levels=(0.,.04))
    assert a==b
    assert len(a['results'])==4


def test_joint_utility_advantage_is_not_guaranteed_with_noisy_forecasts():
    from research.nextgen.fund_aware.experiment import forecast_error_falsification
    z=forecast_error_falsification(n_trials=60,seed=42,noise_levels=(0.,.04))
    for x in z['results'].values():
        assert x['mean_joint_minus_scaled_predicted_utility'] >=-1e-7
    # Policy choice under forecast error can be worse in true expected utility.
    high=z['results']['1.3|noise=0.04']
    assert high['mean_joint_minus_scaled_true_expected_utility'] < high['mean_joint_minus_scaled_predicted_utility']
