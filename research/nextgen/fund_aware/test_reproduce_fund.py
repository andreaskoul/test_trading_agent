from unittest.mock import patch
from research.nextgen.fund_aware.reproduce import produce


def test_reproducibility_protocol_uses_locked_design():
    with patch('research.nextgen.fund_aware.reproduce.experiment',return_value={'stage':1}) as a, \
         patch('research.nextgen.fund_aware.reproduce.forecast_error_falsification',return_value={'stage':2}) as b:
        z=produce()
    a.assert_called_once_with(n_trials=120,seed=20261119)
    b.assert_called_once_with(n_trials=240,seed=20261201,noise_levels=(0.0,.012,.04))
    assert z['exact_cap_vs_uniform_projection']=={'stage':1}
    assert z['independent_synthetic_true_mu_falsification']=={'stage':2}
