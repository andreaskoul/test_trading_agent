"""Reproduce the predeclared 162-candidate synthetic Monte Carlo comparison."""
import json
from .core import run


def produce():
    return [run(n_candidates=162,weeks=302,repetitions=1000,
                strategy_correlation=rho,population_sharpe=.6,
                screening_threshold=1.0,seed=20261119)
            for rho in (0.0,0.8,0.95)]


if __name__ == '__main__':
    print(json.dumps(produce(), indent=2, allow_nan=False))
