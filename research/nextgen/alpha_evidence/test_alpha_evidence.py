"""Synthetic contracts and known-identity tests; no market data."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from math import exp, log
import numpy as np
import pytest
from scipy.special import logsumexp
from research.nextgen.alpha_evidence.core import (
    PairedOutcome, GatePolicy, evaluate)

REG=datetime(2026,12,1,tzinfo=timezone.utc)


def policy(**kw):
    return replace(GatePolicy(preregistered_at=REG,trial_id='SHA_PREDECLARED_A',family_id='FAM_7',registration_ref='SYNTHETIC_IMMUTABLE_REGISTRATION'),**kw)


def rows(gains, trial='SHA_PREDECLARED_A'):
    a=[]
    for j,g in enumerate(gains,1):
        d=REG+timedelta(days=7*j)
        e=d+timedelta(days=6)
        a.append(PairedOutcome(trial_id=trial,sequence=j,decision_at=d,
            period_end_at=e,available_at=e+timedelta(days=1),
            candidate_net_nav_return=float(g),control_net_nav_return=0.0,
            ledger_audit_ref=f'SYNTHETIC_LEDGER_HASH:{j}',matched_risk_ref='SYNTHETIC_RISK_MATCH'))
    return a


def run(gains, **opts):
    p=policy(**opts)
    a=rows(gains)
    return evaluate(a,policy=p,reviewed_at=a[-1].available_at+timedelta(hours=1))


def test_strong_gain_qualifies_only_for_review():
    z=run([.006]*125)
    assert z['historically_crossed']
    assert z['eligible_for_human_review']
    assert not z['automatically_approved_to_trade']
    assert z['anytime_valid_p_upper_bound']<=.05/7


def test_weak_gain_does_not_qualify():
    z=run([.001]*125)
    assert not z['eligible_for_human_review']


def test_regime_break_lapses_even_after_crossing():
    z=run([.006]*100+[-.008]*100)
    assert z['historically_crossed']
    assert z['evidence_lapsed_since_historical_crossing']
    assert not z['eligible_for_human_review']
    assert any(t['currently_eligible_for_review'] for t in z['path'])
    assert not z['path'][-1]['currently_eligible_for_review']


def test_log_e_exact_manual_hoeffding_mixture():
    gains=[.006,.008,-.005,.004,.003,.01]
    p=policy(family_size=1,min_periods=1,lambdas=(.1,.4,.8),hurdle_nav_per_period=0.)
    r=rows(gains)
    z=evaluate(r,policy=p,reviewed_at=r[-1].available_at+timedelta(hours=1))
    x=np.clip(np.array(gains)/p.clip_bound_nav,-1,1)
    lam=np.array(p.lambdas)
    exact=float(logsumexp(lam*x.sum()-len(x)*lam*lam/2)-log(len(lam)))
    assert abs(z['final_log_e_value']-exact)<1e-13


def test_single_outlier_cannot_authorize_review():
    z=run([200.0],min_periods=1)
    assert z['fraction_clipped']==1
    assert not z['eligible_for_human_review']


def test_negative_gain_does_not_pass():
    z=run([-.006]*100)
    assert z['final_log_e_value']<0
    assert not z['historically_crossed']


def test_stronger_multiplicity_gate_is_not_more_permissive():
    one=run([.004]*90,family_size=1)
    many=run([.004]*90,family_size=70)
    assert one['bonferroni_threshold_log_e']<many['bonferroni_threshold_log_e']
    assert not many['eligible_for_human_review'] or one['eligible_for_human_review']


def test_lookahead_hard_stop():
    a=rows([.004]*5)
    with pytest.raises(ValueError,match='unavailable future'):
        evaluate(a,policy=policy(),reviewed_at=a[0].available_at)


def test_pre_registration_prohibits_reused_history():
    a=rows([.004]*3)
    p=policy(preregistered_at=a[0].decision_at)
    with pytest.raises(ValueError,match='previously reused'):
        evaluate(a,policy=p,reviewed_at=a[-1].available_at+timedelta(days=1))


def test_missing_or_shuffled_week_rejected():
    a=rows([.006]*4)
    a.pop(1)
    with pytest.raises(ValueError,match='sequence gap'):
        evaluate(a,policy=policy(),reviewed_at=a[-1].available_at+timedelta(days=1))
    a=rows([.006]*4)
    a[0],a[1]=a[1],a[0]
    with pytest.raises(ValueError,match='sequence gap'):
        evaluate(a,policy=policy(),reviewed_at=a[-1].available_at+timedelta(days=1))


def test_unregistered_trial_rejected():
    a=rows([.004],trial='BAD_OTHER')
    with pytest.raises(ValueError,match='unregistered'):
        evaluate(a,policy=policy(),reviewed_at=a[0].available_at+timedelta(days=1))


def test_overlap_refused():
    a=rows([.003]*2)
    a[1]=replace(a[1],decision_at=a[0].period_end_at-timedelta(days=1))
    with pytest.raises(ValueError,match='overlapping'):
        evaluate(a,policy=policy(),reviewed_at=a[-1].available_at+timedelta(days=1))


def test_publication_order_must_be_monotone():
    a=rows([.003]*2)
    a[0]=replace(a[0],available_at=a[1].available_at)
    with pytest.raises(ValueError,match='increasing availability'):
        evaluate(a,policy=policy(),reviewed_at=a[-1].available_at+timedelta(days=1))


def test_bad_evidence_refs_rejected():
    a=rows([.003])
    with pytest.raises(ValueError,match='ledger audit'):
        replace(a[0],ledger_audit_ref='')
    with pytest.raises(ValueError,match='matched-risk'):
        replace(a[0],matched_risk_ref='')


def test_label_timestamps_must_order():
    a=rows([.003])
    with pytest.raises(ValueError,match='period end'):
        replace(a[0],period_end_at=a[0].decision_at)
    with pytest.raises(ValueError,match='period end'):
        replace(a[0],available_at=a[0].period_end_at-timedelta(seconds=1))


def test_raw_nav_return_invalid():
    a=rows([.003])
    for v in (-1,-1.2,float('nan'),float('inf')):
        with pytest.raises(ValueError):
            replace(a[0],candidate_net_nav_return=v)


def test_invalid_policy_fail_closed():
    for kw in ({'family_alpha':1.},{'family_alpha':0.},{'family_size':0},
               {'clip_bound_nav':0.},{'hurdle_nav_per_period':float('nan')},{'hurdle_nav_per_period':-.0001},
               {'min_periods':0},{'lambdas':(0.,)},{'lambdas':(.1,.1)},
               {'lambdas':(float('nan'),)}, {'lambdas':[.1,.2]},
               {'preregistered_at':REG.replace(tzinfo=None)}):
        with pytest.raises(ValueError):
            policy(**kw)


def test_zero_outcomes_is_not_approved():
    z=evaluate([],policy=policy(),reviewed_at=REG+timedelta(days=1))
    assert not z['eligible_for_human_review']
    assert z['anytime_valid_p_upper_bound']==1


def test_no_automatic_signal_approval_even_when_evidence_is_strong():
    z=run([.009]*90)
    assert z['eligible_for_human_review']
    assert z['automatically_approved_to_trade'] is False


def test_null_family_simulation_is_deterministic():
    from research.nextgen.alpha_evidence.simulate import run as simulate
    a=simulate(replicates=120,weeks=64,seed=42)
    b=simulate(replicates=120,weeks=64,seed=42)
    assert a==b
    assert a['scenarios']['null_family']['family_false_review_rate']<=.05


def test_simulation_strong_beats_weak_on_review_probability():
    from research.nextgen.alpha_evidence.simulate import run as simulate
    a=simulate(replicates=200,weeks=156,seed=555)
    assert a['scenarios']['one_strong']['true_candidate_review_rate']>.3
    assert a['scenarios']['one_weak']['true_candidate_review_rate']<.2


def test_simulation_regime_break_current_lapses():
    from research.nextgen.alpha_evidence.simulate import run as simulate
    a=simulate(replicates=200,weeks=156,seed=555)
    b=a['scenarios']['regime_break']
    assert b['true_candidate_ever_crossing_rate']>b['true_candidate_review_rate']


def test_error_model_uses_clipped_hurdle_not_raw_return_null():
    z=run([.0004]*100)
    assert z['paired_mean_raw_gain_nav']>0
    assert z['paired_mean_clipped_hurdle_adjusted']<0
    assert not z['eligible_for_human_review']


def test_persistent_mixture_breaks_unconditional_null_interpretation():
    from research.nextgen.alpha_evidence.simulate import run as simulate
    x=simulate(replicates=300,weeks=156,seed=137)
    warning=x['scenarios']['latent_regime_zero_unconditional']
    assert not warning['conditional_null_valid_in_design']
    assert warning['unconditional_null_false_review_warning']>.15


def test_predictably_heteroskedastic_conditional_null_still_low_false_rate():
    from research.nextgen.alpha_evidence.simulate import run as simulate
    x=simulate(replicates=300,weeks=156,seed=137)
    safe=x['scenarios']['conditional_heteroskedastic_null']
    assert safe['conditional_null_valid_in_design']
    assert safe['family_false_review_rate']<.05
