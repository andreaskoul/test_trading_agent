"""Reproduce both frozen synthetic scenarios; never reads market-data cache."""
import json
from .experiment import experiment, forecast_error_falsification


def produce():
    return {'selection':'exploratory synthetic fund-gross architecture experiment',
            'exact_cap_vs_uniform_projection':experiment(n_trials=120,seed=20261119),
            'independent_synthetic_true_mu_falsification':forecast_error_falsification(
                n_trials=240,seed=20261201,noise_levels=(0.0,.012,.04)),
            'not_measured':['actual historical Sharpe','broker financing','market data','real MASTER calibration']}


if __name__=='__main__':
    print(json.dumps(produce(),indent=2,allow_nan=False))
