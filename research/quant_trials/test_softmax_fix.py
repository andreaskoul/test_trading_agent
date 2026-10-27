"""Contract tests for the ported softmax fix (softmax_fix.py): fp64 agreement, zero-sum gradients, no collapse.

    python test_softmax_fix.py
"""

import torch
import torch.nn.functional as Fn

from softmax_fix import Margins, fixed_log_softmax, fixed_softmax, patched_softmax


def rows(margins, k=8, dtype=torch.float32, seed=0):
    """Rows whose top logit beats the log-sum-exp of the others by exactly each margin."""
    g = torch.Generator().manual_seed(seed)
    z = torch.randn(len(margins), k, generator=g, dtype=torch.float64)
    z[:, 0] = 0.0
    rest = torch.logsumexp(z[:, 1:], -1)
    z[:, 0] = rest + torch.tensor(margins, dtype=torch.float64)
    return z.to(dtype)


def test_matches_torch_below_cliff():
    z = rows([0.0, 1.0, 3.0, 8.0, 12.0])
    assert torch.allclose(fixed_softmax(z), torch.softmax(z, -1), atol=1e-7)
    assert torch.allclose(fixed_log_softmax(z), torch.log_softmax(z, -1), atol=1e-6)


def test_target_gradient_survives_the_cliff():
    """Hard-target CE on the top class: the gradient on the top logit is -(1 - q*) = -sigmoid(r); standard fp32 rounds
    it to 0 past ~16.6, the fix keeps it (relative error < 1e-4 vs the exact value) until exp underflow."""
    ms = [5.0, 16.0, 17.0, 20.0, 30.0, 40.0]
    for fn, should_survive in ((fixed_log_softmax, True), (lambda z, d: torch.log_softmax(z, d), False)):
        z = rows(ms).requires_grad_(True)
        (-fn(z, -1)[:, 0]).sum().backward()
        z64 = z.detach().double()                                   # exact: d(-log q*)/dz* = -sigmoid(r),
        ref = -torch.sigmoid(torch.logsumexp(z64[:, 1:], -1) - z64[:, 0])   # r = lse(others) - z* (fp64 also collapses)
        g = z.grad[:, 0].double()
        rel = ((g - ref).abs() / ref.abs())
        if should_survive:
            assert (rel < 1e-4).all(), rel
            assert (z.grad.sum(-1).abs() <= 1e-6 * z.grad.abs().sum(-1)).all()      # zero-sum
        else:
            assert (g[3:] == 0).all(), g                                            # the bug, as documented


def test_attention_like_gradient_matches_fp64():
    """Softmax used as weights (attention/gate): grad of sum_j q_j v_j matches fp64 at large margins."""
    ms = [2.0, 18.0, 25.0, 35.0]
    v = torch.randn(len(ms), 8, generator=torch.Generator().manual_seed(1), dtype=torch.float64)
    z = rows(ms).requires_grad_(True)
    (fixed_softmax(z, -1) * v.float()).sum().backward()
    z64 = z.detach().double().requires_grad_(True)              # the same fp32 inputs, in fp64
    (torch.softmax(z64, -1) * v).sum().backward()
    ref = z64.grad.clone()
    q = torch.softmax(z64.detach(), -1)                         # top entry without cancellation (fp64 also loses it
    ref[:, 0] = q[:, 0] * (q[:, 1:] * (v[:, :1] - v[:, 1:])).sum(-1)   # near margin 35): q* sum_j q_j (v* - v_j)
    rel = ((z.grad.double() - ref).abs() / ref.abs().clamp_min(1e-300))
    assert (rel < 1e-3).all(), rel


def test_patch_logs_margins_and_restores():
    mg = Margins()
    z = rows([1.0, 20.0])
    orig = torch.softmax
    with patched_softmax(mg):
        torch.softmax(z, -1)
        Fn.softmax(z, dim=-1)
        torch.nn.Softmax(dim=-1)(z)
        z.softmax(-1)
    assert torch.softmax is orig
    s = mg.summary()
    assert s["rows"] == 8 and s["gt_cliff"] == 4 and abs(s["max_margin"] - 20.0) < 1e-3, s


def test_masked_keys_are_not_margins():
    """Attention masks add -finfo.max: a row with one live key is skipped, masked keys never count as logits."""
    mg = Margins()
    z = torch.tensor([[0.0, 1.0, 2.0], [0.0, torch.finfo(torch.float32).min, torch.finfo(torch.float32).min]])
    with patched_softmax(mg):
        torch.softmax(z, -1)
    s = mg.summary()
    assert s["rows"] == 1 and s["max_margin"] < 2, s


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
