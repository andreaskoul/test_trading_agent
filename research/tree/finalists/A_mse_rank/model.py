"""Holdout finalist: A configuration mse_rank (small MLP, squared error on the cross-sectionally ranked target).
Wraps research/tree/A_loss/losslib.py unchanged, with the configuration as logged in run.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "A_loss"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import losslib  # noqa: E402

fit_predict = losslib.make(loss="mse_rank")
