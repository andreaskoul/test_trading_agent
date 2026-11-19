from dataclasses import replace
from datetime import datetime,timedelta,timezone
from copy import deepcopy
import numpy as np
import pytest

from research.nextgen.oof_calibration.core import (
    ScoreObservation, CalibrationConfig, walk_forward, predictive_loss, _fit, _rank_scores)
from research.nextgen.oof_calibration.synthetic import make_panel, single_experiment, DESIGN


def small(**kwargs):
    return ScoreObservation(security_id='PIT_A', decision_at=datetime(2019,1,10,tzinfo=timezone.utc),
        score_available_at=datetime(2019,1,10,tzinfo=timezone.utc)-timedelta(minutes=1),
        upstream_train_target_end_at=datetime(2019,1,1,tzinfo=timezone.utc),
        target_end_at=datetime(2019,1,17,tzinfo=timezone.utc),
        target_available_at=datetime(2019,1,18,tzinfo=timezone.utc),
        score=1.0,target_excess=0.03,**kwargs)


def test_pit_contract_accepts_valid_record():
    assert small().eligible


def test_pit_contract_fails_future_score():
    x=small()
    with pytest.raises(ValueError,match='model training'):
        replace(x,score_available_at=x.decision_at)


def test_pit_contract_fails_future_model_training():
    x=small()
    with pytest.raises(ValueError,match='model training'):
        replace(x,upstream_train_target_end_at=x.decision_at)


def test_pit_contract_fails_missing_eligibility_type():
    with pytest.raises(ValueError,match='eligible'):
        replace(small(),eligible=1)


def test_pit_contract_rejects_unknown_label_with_available_timestamp():
    x=small()
    with pytest.raises(ValueError,match='unknown target'):
        replace(x,target_excess=None)


def test_pit_contract_rejects_target_available_before_end():
    x=small()
    with pytest.raises(ValueError,match='realised target'):
        replace(x,target_available_at=x.decision_at)


def test_pit_contract_missing_timezone():
    x=small()
    with pytest.raises(ValueError,match='timezone'):
        replace(x,decision_at=x.decision_at.replace(tzinfo=None))


def test_rank_ties_are_centered():
    t=small()
    group=[replace(t,security_id=str(i),score=s) for i,s in enumerate([3,4,4,9])]
    ranks=_rank_scores(group)
    np.testing.assert_allclose(ranks,[-1,0,0,1]) # Need check rankdata ranks 1,2.5,2.5,4 => -1,0,0,1


def test_no_prior_labels_gives_zero_forecast():
    r,first=make_panel(scenario='stable',seed=14)
    earlier=first-timedelta(weeks=DESIGN['train_dates']-1)
    p=walk_forward(r,first_decision_at=earlier)
    early=[x for x in p if x.decision_at==earlier]
    assert len(early)==DESIGN['n_names']
    assert all(x.mu_conservative==0 and x.mu_unshrunk==0 for x in early)


def test_no_target_lookahead_mutation():
    r,first=make_panel(scenario='stable',seed=5)
    x=walk_forward(r,first_decision_at=first)
    d=first+timedelta(weeks=4)
    original=[v for v in x if v.decision_at==d]
    changed=[replace(o,target_excess=o.target_excess+10.0*(1 if j%2==0 else -1))
             if o.decision_at >= d else o for j,o in enumerate(r)]
    future=walk_forward(changed,first_decision_at=first)
    assert [v for v in future if v.decision_at==d]==original


def test_no_leak_from_target_availability_after_cutoff():
    r,first=make_panel(scenario='stable',seed=6)
    base=walk_forward(r,first_decision_at=first)
    row=next(o for o in r if o.decision_at<first and o.target_available_at>=first-timedelta(days=1))
    updated=[replace(o,target_excess=1000) if o==row else o for o in r]
    new=walk_forward(updated,first_decision_at=first)
    assert [z for z in base if z.decision_at==first]==[z for z in new if z.decision_at==first]


def test_uses_strict_embargo_on_labels():
    r,first=make_panel(scenario='stable',seed=6)
    x=walk_forward(r,first_decision_at=first)
    z=next(y for y in x if y.decision_at==first)
    assert z.latest_training_target_available_at<first-timedelta(days=1)


def test_duplicate_stable_identifier_rejected():
    r,first=make_panel(scenario='stable',seed=2)
    with pytest.raises(ValueError,match='duplicate'):
        walk_forward(r+[r[0]],first_decision_at=first)


def test_permutation_invariance():
    r,first=make_panel(scenario='stable',seed=8)
    a=walk_forward(r,first_decision_at=first)
    b=walk_forward(list(reversed(r)),first_decision_at=first)
    sa=sorted(a,key=lambda x:(x.decision_at,x.security_id))
    sb=sorted(b,key=lambda x:(x.decision_at,x.security_id))
    assert sa==sb


def test_unlabeled_decision_date_can_be_predicted():
    r,first=make_panel(scenario='stable',seed=8)
    no_label=[replace(o,target_excess=None,target_available_at=None) if o.decision_at>=first else o for o in r]
    output=walk_forward(no_label,first_decision_at=first)
    assert output and all(np.isfinite(x.mu_conservative) for x in output)


def test_partial_missing_labels_fail_in_evaluation():
    r,first=make_panel(scenario='stable',seed=4)
    p=walk_forward(r,first_decision_at=first)
    o=next(o for o in r if o.decision_at==first)
    changed=[replace(x,target_excess=None,target_available_at=None) if x==o else x for x in r]
    with pytest.raises(ValueError,match='missing outcome'):
        predictive_loss(changed,p)


def test_ineligible_security_is_not_in_rank_universe():
    r,first=make_panel(scenario='stable',seed=4)
    group=next(x for x in r if x.decision_at==first)
    changed=[replace(x,eligible=False) if x==group else x for x in r]
    out=walk_forward(changed,first_decision_at=first)
    assert all(not (v.security_id==group.security_id and v.decision_at==first) for v in out)


def test_zero_score_variation_has_no_alpha():
    r,first=make_panel(scenario='stable',seed=4)
    changed=[replace(x,score=1.0) for x in r]
    z=walk_forward(changed,first_decision_at=first)
    assert all(x.mu_unshrunk==0 and x.mu_conservative==0 for x in z)


def test_invalid_config_and_no_evaluation_labels():
    with pytest.raises(ValueError): CalibrationConfig(hac_lags=28)
    r,first=make_panel(scenario='null',seed=3)
    unlabeled=[replace(x,target_excess=None,target_available_at=None) for x in r]
    p=walk_forward(unlabeled,first_decision_at=first)
    with pytest.raises(ValueError):predictive_loss(unlabeled,p)


def test_stable_signal_outperforms_zero_on_synthetic():
    x=single_experiment('stable',seed=20261119)
    assert x['mse_raw']<x['mse_zero']


def test_null_gate_shrinks_against_raw():
    x=single_experiment('null',seed=20261119)
    assert x['mse_conservative']<=x['mse_raw']*1.01
