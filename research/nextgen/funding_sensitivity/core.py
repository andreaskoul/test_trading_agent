"""Read-only structural financing stress for a SPY core + beta-hedged stock book.

Every output is a CONDITIONAL scenario, not an Alpaca debit balance or empirical
backtest result. Rates are explicit user-supplied decimal annual simple rates.
Positions are fractions of beginning-period fund NAV and assumed unchanged
within an interval. Research only; no broker/API/network access.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class FundingScenario:
    margin_rate: float
    legacy_margin_rate: float
    days: float
    stock_borrow_rates: tuple[float, ...]
    stock_shortable: tuple[bool, ...]
    spy_borrow_rate: float = 0.0
    spy_shortable: bool = True
    short_rebate_rate: float = 0.0
    idle_cash_yield_rate: float = 0.0
    day_count: float = 360.0


def _rate(x, name):
    if isinstance(x, bool) or not isinstance(x, (int, float, np.integer, np.floating)) or not isfinite(x) or x < 0:
        raise ValueError(f'{name}: expected finite nonnegative annual simple rate')
    return float(x)


def _vector(x, name, n=None):
    try:
        a = np.asarray(x, dtype=float)
    except (ValueError, TypeError) as exc:
        raise ValueError(f'{name}: expected finite vector') from exc
    if a.ndim != 1 or not len(a) or not np.all(np.isfinite(a)) or (n is not None and len(a) != n):
        raise ValueError(f'{name}: expected finite aligned one-dimensional vector')
    return a


def evaluate(core_spy_weight: float, stock_weights: Sequence[float],
             stock_betas: Sequence[float], scenario: FundingScenario) -> dict:
    """Compare legacy net-notional debit with a segregated-short-proceeds scenario.

    This is a scenario of *cash financing* conditional on every input. It is
    not a Reg-T, portfolio-margin or broker end-of-day settlement model.

    Legacy: debit=max(core_spy+hedge+sum(stock_weights)-1,0)
    Segregated-short-proceeds counterfactual:
        debit=max(long_stock+long_net_SPY-1,0)
        short_sale_notional=short_stock+short_net_SPY
    Net charges include explicit stock borrow, short rebate and free-cash
    credits, which must not be confused with broker-specific eligibility.
    """
    if not isinstance(scenario, FundingScenario):
        raise ValueError('explicit FundingScenario required')
    core = float(core_spy_weight)
    if not isfinite(core):
        raise ValueError('finite core required')
    w = _vector(stock_weights, 'stock_weights')
    beta = _vector(stock_betas, 'stock_betas', len(w))
    rates = _vector(scenario.stock_borrow_rates, 'stock_borrow_rates', len(w))
    if np.any(rates < 0):
        raise ValueError('borrow rates must be nonnegative')
    availability = tuple(scenario.stock_shortable)
    if len(availability) != len(w) or any(type(x) not in (bool, np.bool_) for x in availability):
        raise ValueError('every security must have explicit boolean shortability')
    for name in ('margin_rate', 'legacy_margin_rate', 'spy_borrow_rate',
                 'short_rebate_rate', 'idle_cash_yield_rate'):
        _rate(getattr(scenario, name), name)
    days, basis = float(scenario.days), float(scenario.day_count)
    if not isfinite(days) or days <= 0 or not isfinite(basis) or basis <= 0:
        raise ValueError('positive finite duration and day-count basis required')
    hedge = -float(beta @ w)
    spy = core + hedge
    short_stock = np.clip(-w, 0.0, None)
    long_stock = np.clip(w, 0.0, None)
    if any(short_stock[i] > 1e-14 and not availability[i] for i in range(len(w))):
        raise ValueError('unavailable short stock position: fail closed')
    if spy < -1e-14 and not scenario.spy_shortable:
        raise ValueError('unavailable short SPY position: fail closed')
    long_notional = float(max(spy, 0.0) + long_stock.sum())
    short_notional = float(max(-spy, 0.0) + short_stock.sum())
    net_notional = float(core + hedge + w.sum())
    # Self-financing identity, independent of market data.
    if not np.isclose(long_notional-short_notional, net_notional, atol=1e-12, rtol=0):
        raise ArithmeticError('position financing identity failed')
    legacy_debit = max(net_notional-1.0, 0.0)
    segregated_debit = max(long_notional-1.0, 0.0)
    free_cash = max(1.0-long_notional, 0.0)
    margin_charge = segregated_debit * scenario.margin_rate * days/basis
    legacy_charge = legacy_debit * scenario.legacy_margin_rate * days/basis
    borrow_charge = (float(short_stock @ rates) + max(-spy,0.0)*scenario.spy_borrow_rate)*days/basis
    rebate = short_notional * scenario.short_rebate_rate * days/basis
    idle_credit = free_cash * scenario.idle_cash_yield_rate * days/basis
    conditional_financing_charge = margin_charge + borrow_charge - rebate - idle_credit
    gross = float(abs(spy) + abs(w).sum())
    return {
        'core_spy': core, 'spy_beta_hedge': hedge,
        'net_spy_position': spy, 'stocks_long': float(long_stock.sum()),
        'stocks_short': float(short_stock.sum()),
        'gross_nav': gross, 'long_notional_nav': long_notional,
        'short_notional_nav': short_notional,
        'net_notional_nav': net_notional,
        'legacy_net_debit_nav': legacy_debit,
        'segregated_short_debit_nav': segregated_debit,
        'financing_debit_gap_nav': segregated_debit-legacy_debit,
        'free_cash_nav': free_cash,
        'legacy_funding_cost_nav_period': legacy_charge,
        'scenario_margin_cost_nav_period': margin_charge,
        'scenario_borrow_cost_nav_period': borrow_charge,
        'scenario_rebate_nav_period': rebate,
        'scenario_cash_credit_nav_period': idle_credit,
        'scenario_net_financing_cost_nav_period': conditional_financing_charge,
        'extra_cost_nav_period': conditional_financing_charge-legacy_charge,
        'extra_cost_nav_per_360d_fixed_holdings':
            (conditional_financing_charge-legacy_charge)*360.0/days,
        'assumption': 'hypothetical segregated short proceeds, static positions, not broker-settled cash',
    }


def fixed_vol_sharpe_shift(raw_return_vol_ratio: float, annual_vol_fraction: float,
                           annual_extra_cost_nav: float) -> float:
    """Illustrative first-order delta, NOT recomputed annualised/excess Sharpe.

    Holds measured volatility constant, assumes cost is a deterministic annual
    arithmetic return shift, and uses the same (legacy raw) ratio convention.
    """
    ratio = float(raw_return_vol_ratio)
    v = float(annual_vol_fraction)
    d = float(annual_extra_cost_nav)
    if not all(map(isfinite,(ratio,v,d))) or v <= 0:
        raise ValueError('finite ratio/cost and positive annual volatility required')
    return float(ratio - d/v)
