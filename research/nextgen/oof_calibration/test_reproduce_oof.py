from unittest.mock import patch
from research.nextgen.oof_calibration.reproduce import produce


def test_reproduce_exact_two_stages():
    with patch('research.nextgen.oof_calibration.reproduce.study',return_value={'stage':1}) as a, \
         patch('research.nextgen.oof_calibration.reproduce.comparative_study',return_value={'stage':2}) as b:
        result=produce()
    assert result['locked_stable_null_break']=={'stage':1}
    assert result['exploratory_adaptation_followup']=={'stage':2}
    a.assert_called_once_with(replicates=40,seed=20261119)
    b.assert_called_once_with(replicates=40,seed=20261201)
