"""Prequential, anytime-valid *conditional bounded-mean* evidence gate.

Research only. Does NOT approve signals or compute Sharpe significance.
An e-process here is valid if, under the null, each CLIPPED/SHIFTED
paired gain has nonpositive conditional expectation given all information
available when that observation is revealed. This is stronger than an
unconditional Sharpe or zero-average-return null, particularly with regimes.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp, isfinite, log
import numpy as np
from scipy.special import logsumexp


def _utc(t, field):
    if not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None:
        raise ValueError(f'{field}: require timezone-aware timestamp')
    return t.astimezone(timezone.utc)


def _float(v, field):
    if isinstance(v, bool) or not isinstance(v, (int,float,np.integer,np.floating)) or not isfinite(v):
        raise ValueError(f'{field}: finite nonboolean numeric value required')
    return float(v)


@dataclass(frozen=True)
class GatePolicy:
    family_id: str
    trial_id: str
    preregistered_at: datetime
    registration_ref: str
    family_size: int = 7
    family_alpha: float = 0.05
    clip_bound_nav: float = 0.01
    hurdle_nav_per_period: float = 0.0005
    min_periods: int = 26
    lambdas: tuple[float,...] = (0.025,0.05,0.1,0.2,0.4,0.8)

    def __post_init__(self):
        if any(not isinstance(v,str) or not v.strip() for v in
               (self.family_id,self.trial_id,self.registration_ref)):
            raise ValueError('nonempty prospective trial, family and immutable-registration reference required')
        _utc(self.preregistered_at,'preregistered_at')
        if type(self.family_size) is not int or self.family_size<1 or type(self.min_periods) is not int or self.min_periods<1:
            raise ValueError('family size and min periods must be positive integers')
        alpha=_float(self.family_alpha,'family_alpha')
        bound=_float(self.clip_bound_nav,'clip_bound_nav')
        hurdle=_float(self.hurdle_nav_per_period,'hurdle_nav_per_period')
        if hurdle<0:
            raise ValueError('economically meaningful nonnegative hurdle required')
        if not 0<alpha<1 or not 0<bound<=1:
            raise ValueError('alpha in (0,1), bound in (0,1] required')
        if not isinstance(self.lambdas,tuple) or not self.lambdas or len(self.lambdas)>50:
            raise ValueError('fixed finite lambda mixture required')
        rates=tuple(_float(v,'lambda') for v in self.lambdas)
        if any(v<=0 or v>10 for v in rates) or len(set(rates))!=len(rates):
            raise ValueError('distinct positive fixed lambda mixture required')


@dataclass(frozen=True)
class PairedOutcome:
    """One *fully settled*, pre-registered, matched-risk portfolio comparison.

    Reconciliation / risk references MUST be independently checked externally:
    a nonempty string is a ledger manifest reference, not proof of validity.
    """
    trial_id: str
    sequence: int
    decision_at: datetime
    period_end_at: datetime
    available_at: datetime
    candidate_net_nav_return: float
    control_net_nav_return: float
    ledger_audit_ref: str
    matched_risk_ref: str

    def __post_init__(self):
        if type(self.sequence) is not int or self.sequence < 1:
            raise ValueError('sequence must be positive integer')
        if any(not isinstance(s,str) or not s.strip() for s in
               (self.trial_id,self.ledger_audit_ref,self.matched_risk_ref)):
            raise ValueError('trial id, ledger audit and matched-risk refs required')
        d,e,a=(_utc(getattr(self,name),name) for name in
               ('decision_at','period_end_at','available_at'))
        if not d<e<=a:
            raise ValueError('decision < period end <= outcome availability required')
        for name in ('candidate_net_nav_return','control_net_nav_return'):
            r=_float(getattr(self,name),name)
            if r<=-1:
                raise ValueError('NAV return <= -1 invalid for a continued funded strategy')


def evaluate(outcomes: list[PairedOutcome], *, policy: GatePolicy,
             reviewed_at: datetime):
    """Evaluate a fixed lambda-mixture Hoeffding test supermartingale.

    H0: E[X_t|F_{t-1}] <= 0, with X_t = clip((r_candidate-r_control-h)/B,
    -1,1) and *chronological revelation filtration* F.
    Hoeffding: E exp(lambda*X-lambda**2/2) <= 1 (lambda>=0).
    Fixed-mixture E_t = mean_lambdas exp(lambda*sum X - t*lambda**2/2).
    The maximum-to-date threshold m/alpha controls family-wise crossing by
    Bonferroni even for correlated trials *if the hypotheses and family were
    registered independently of this evaluation and the null holds*.
    """
    if not isinstance(policy,GatePolicy):
        raise ValueError('explicit immutable GatePolicy required')
    end=_utc(reviewed_at,'reviewed_at')
    if end<=_utc(policy.preregistered_at,'preregistered_at'):
        raise ValueError('review must postdate preregistration')
    if not isinstance(outcomes,list):
        raise TypeError('complete chronological list required')
    lam=np.array(policy.lambdas,float)
    logs=np.zeros(len(lam),dtype=float)
    logmax=0.0
    sum_x=0.0
    sum_raw=0.0
    capped=0
    track=[]
    previous_available=None
    previous_end=None
    crossed_at=None
    threshold=log(policy.family_size/policy.family_alpha)
    for i,o in enumerate(outcomes,1):
        if not isinstance(o,PairedOutcome) or o.trial_id!=policy.trial_id:
            raise ValueError('unregistered or invalid trial outcome')
        if o.sequence!=i:
            raise ValueError('sequence gap, shuffle or cherry-picked observation')
        a=_utc(o.available_at,'available_at')
        d=_utc(o.decision_at,'decision_at')
        p=_utc(o.period_end_at,'period_end_at')
        if d<=_utc(policy.preregistered_at,'preregistered_at'):
            raise ValueError('historical or previously reused decision; not prospective')
        if a>end:
            raise ValueError('unavailable future label; evaluate only matured outcomes')
        if previous_available is not None and a<=previous_available:
            raise ValueError('outcomes must be ordered by strictly increasing availability')
        if previous_end is not None and d<previous_end:
            raise ValueError('overlapping holding windows require a separate inference contract')
        previous_available,previous_end=a,p
        gain=o.candidate_net_nav_return-o.control_net_nav_return
        normalized=(gain-policy.hurdle_nav_per_period)/policy.clip_bound_nav
        x=float(np.clip(normalized,-1.0,1.0))
        capped+=abs(normalized)>1
        sum_x+=x
        sum_raw+=gain
        logs+=lam*x-0.5*lam*lam
        lse=float(logsumexp(logs)-log(len(logs)))
        logmax=max(logmax,lse)
        current_supported=i>=policy.min_periods and lse>=threshold
        ever_crossed=i>=policy.min_periods and logmax>=threshold
        if crossed_at is None and ever_crossed:
            crossed_at=i
        track.append({'sequence':i,'log_e_value':lse,
                      'max_log_e_value':logmax,'review_threshold_log_e':threshold,
                      'ever_crossed':ever_crossed,
                      'currently_eligible_for_review':current_supported})
    p_any=exp(-logmax) if logmax<700 else 0.0
    return {'trial_id':policy.trial_id,'family_id':policy.family_id,
            'registration_ref':policy.registration_ref,
            'family_size':policy.family_size,'n':len(outcomes),
            'paired_mean_raw_gain_nav':sum_raw/len(outcomes) if outcomes else None,
            'paired_mean_clipped_hurdle_adjusted':sum_x/len(outcomes) if outcomes else None,
            'fraction_clipped':capped/len(outcomes) if outcomes else None,
            'final_log_e_value':float(logsumexp(logs)-log(len(logs))),
            'max_log_e_value':logmax,
            'anytime_valid_p_upper_bound':p_any,
            'bonferroni_threshold_log_e':threshold,
            'first_historical_crossing_sequence':crossed_at,
            'historically_crossed':crossed_at is not None,
            'eligible_for_human_review':bool(track and track[-1]['currently_eligible_for_review']),
            'evidence_lapsed_since_historical_crossing':bool(crossed_at is not None and
                not track[-1]['currently_eligible_for_review']),
            'automatically_approved_to_trade':False,
            'scope':'clipped/hurdle-adjusted conditional mean only, NOT raw-mean or Sharpe significance',
            'path':track}
