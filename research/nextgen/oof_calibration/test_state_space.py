from dataclasses import replace
from datetime import timedelta
from math import isfinite
import numpy as np
import pytest

from research.nextgen.oof_calibration.core import walk_forward, predictive_loss
from research.nextgen.oof_calibration.synthetic import make_panel, comparative_study, DESIGN
from research.nextgen.oof_calibration.state_space import (
    StateSpaceConfig, state_space_walk_forward, _cross_section_slope)


def test_state_space_matured_only():
    rows,first=make_panel(scenario='stable',seed=45)
    result=state_space_walk_forward(rows,first_decision_at=first)
    x=next(p for p in result if p.decision_at==first)
    assert x.latest_training_target_available_at<first-timedelta(days=1)
    assert x.fitted_train_dates < DESIGN['train_dates']


def test_state_space_future_leak_mutation():
    rows,first=make_panel(scenario='stable',seed=45)
    d=first+timedelta(weeks=5)
    before=state_space_walk_forward(rows,first_decision_at=first)
    modified=[replace(r,target_excess=r.target_excess+1000) if r.decision_at>=d else r for r in rows]
    after=state_space_walk_forward(modified,first_decision_at=first)
    assert [p for p in before if p.decision_at==d]==[p for p in after if p.decision_at==d]


def test_state_space_unknown_future_labels_supported():
    rows,first=make_panel(scenario='stable',seed=8)
    modified=[replace(r,target_excess=None,target_available_at=None) if r.decision_at>=first else r for r in rows]
    p=state_space_walk_forward(modified,first_decision_at=first)
    assert p and all(isfinite(x.mu_unshrunk) for x in p)


def test_kalman_fast_regime_shift_vs_long_window():
    rows,first=make_panel(scenario='break',seed=8)
    p=state_space_walk_forward(rows,first_decision_at=first)
    l=walk_forward(rows,first_decision_at=first)
    tail_t=first+timedelta(weeks=DESIGN['evaluation_dates']-1)
    p_last=next(x for x in p if x.decision_at==tail_t)
    l_last=next(x for x in l if x.decision_at==tail_t)
    assert abs(p_last.slope)<abs(l_last.slope)


def test_point_in_time_permutation_invariance():
    rows,first=make_panel(scenario='stable',seed=8)
    a=state_space_walk_forward(rows,first_decision_at=first)
    b=state_space_walk_forward(list(reversed(rows)),first_decision_at=first)
    assert a==b


def test_cross_section_slope_fails_gracefully_on_ties():
    rows,first=make_panel(scenario='stable',seed=8)
    group=[replace(r,score=1.0) for r in rows if r.decision_at==first]
    assert _cross_section_slope(group) is None


def test_state_config_invalid():
    with pytest.raises(ValueError):StateSpaceConfig(min_names=2)
    with pytest.raises(ValueError):StateSpaceConfig(prior_variance=-1)
    with pytest.raises(ValueError):StateSpaceConfig(conservative_z=-1)


def test_exploratory_synthetic_study_reproducibility():
    a=comparative_study(replicates=3,seed=20261201)
    b=comparative_study(replicates=3,seed=20261201)
    assert a==b
    assert set(a['scenarios'])=={'stable','null','break'}


def test_exploratory_synthetic_study_bad_args():
    with pytest.raises(ValueError):comparative_study(replicates=1)
    with pytest.raises(ValueError):comparative_study(seed=-1)


def test_calibrator_does_not_use_past_partially_observed_date():
    rows,first=make_panel(scenario='stable',seed=13)
    past=first-timedelta(weeks=6)
    bad=next(r for r in rows if r.decision_at==past)
    modified=[replace(r,target_excess=None,target_available_at=None) if r==bad else r for r in rows]
    a=state_space_walk_forward(modified,first_decision_at=first)
    b=state_space_walk_forward(rows,first_decision_at=first)
    p=next(x for x in a if x.decision_at==first)
    q=next(x for x in b if x.decision_at==first)
    assert p.fitted_train_dates==q.fitted_train_dates-1


def test_mse_comparison_cannot_score_partial_outcomes():
    rows,first=make_panel(scenario='stable',seed=13)
    p=state_space_walk_forward(rows,first_decision_at=first)
    changed=[replace(r,target_excess=None,target_available_at=None) if r.decision_at==first else r for r in rows]
    with pytest.raises(ValueError):predictive_loss(changed,p)


def test_filter_uncertainty_propagates_without_new_outcomes():
    rows,first=make_panel(scenario='stable',seed=101)
    modified=[replace(r,target_excess=None,target_available_at=None) if r.decision_at>=first-timedelta(weeks=5) else r for r in rows]
    x=state_space_walk_forward(modified,first_decision_at=first)
    dates=sorted({p.decision_at for p in x})
    a=next(p for p in x if p.decision_at==dates[0])
    b=next(p for p in x if p.decision_at==dates[-1])
    assert a.fitted_train_dates==b.fitted_train_dates
    assert b.slope_standard_error > a.slope_standard_error
    assert a.slope==b.slope


def test_late_out_of_sequence_label_requires_replay():
    rows,first=make_panel(scenario='stable',seed=101)
    late_date=first-timedelta(weeks=1)
    altered=[replace(r,target_available_at=r.decision_at+timedelta(days=42))
             if r.decision_at==late_date else r for r in rows]
    with pytest.raises(ValueError,match='out-of-sequence'):
        state_space_walk_forward(altered,first_decision_at=first)
