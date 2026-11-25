"""Reproduce both synthetic calibration studies, never reading historical prices."""
import json
from .synthetic import study, comparative_study


def produce():
    return {
        'protocol':'OOF-01 synthetic demonstrations only, no trading Sharpe',
        'locked_stable_null_break':study(replicates=40,seed=20261119),
        'exploratory_adaptation_followup':comparative_study(replicates=40,seed=20261201),
    }


if __name__=='__main__':
    print(json.dumps(produce(),indent=2,allow_nan=False))
