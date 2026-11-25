"""Conditional normal/HAC prospective power (not proof of economic edge).

Uses previously PUBLISHED SE as a hypothetical future scale; does not read a
backtest. Bonferroni m tests is conservative and not a substitute for logging
all future adaptive research decisions.
"""
import math
from scipy.stats import norm


def power_projection(*, delta_sr, historical_se, historical_weeks,
                     proposed_weeks=302, family_size=7,
                     one_sided_alpha=.05, target_power=.8):
    vals=(delta_sr,historical_se,historical_weeks,proposed_weeks,
          family_size,one_sided_alpha,target_power)
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in vals):
        raise ValueError('all inputs require finite numbers')
    if delta_sr <= 0 or historical_se <= 0 or historical_weeks < 3 or proposed_weeks < 3:
        raise ValueError('positive effect and SE; sample lengths >=3 required')
    if family_size < 1 or int(family_size) != family_size:
        raise ValueError('positive integer family size required')
    if not 0 < one_sided_alpha < .5 or not .5 < target_power < 1:
        raise ValueError('alpha <0.5; target power in (0.5,1)')
    cutoff=norm.isf(one_sided_alpha/family_size)
    se=historical_se*math.sqrt(historical_weeks/proposed_weeks)
    power=float(norm.sf(cutoff-delta_sr/se))
    detectable=float((cutoff+norm.ppf(target_power))*se)
    required=float(historical_weeks*(historical_se*(cutoff+norm.ppf(target_power))/delta_sr)**2)
    return {'proposed_weeks':int(proposed_weeks),'family_size':int(family_size),
            'nominal_one_sided_alpha':one_sided_alpha,
            'per_comparison_bonferroni_alpha':one_sided_alpha/family_size,
            'delta_sr_hypothesis':delta_sr,'se_under_sqrt_n_assumption':se,
            'approximate_power':power,
            'minimum_detectable_delta_sr_at_target_power':detectable,
            'required_weeks_at_target_power':required,
            'required_years_at_52w':required/52,
            'assumptions':'conditional independent forward sample, normal test, constant true effect and HAC variance scale; no adaptive reselection'}
