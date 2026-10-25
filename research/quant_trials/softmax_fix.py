"""The softmax fix of Barron, Gnanapragasam & Tschannen (arXiv 2610.31642), ported to PyTorch, and the F1 diagnostic
(PREREG_quant_transformers.md Amendment 3).

    python softmax_fix.py diagnose master   # MASTER h5, the 2013 refit window (training + validation only), 5 seeds
    python softmax_fix.py diagnose tft      # TFT h10, the 2013 refit window, seed 0
    python softmax_fix.py diagnose chronos2_ft  # Chronos-2 fine-tuned on the 2013 refit window (eager attention)
    python softmax_fix.py ab master         # F2, only if F1's rule is crossed: validation IC, standard vs fixed

Why it might matter: in fp32 a softmax row whose top logit beats the log-sum-exp of the rest by more than ~16.6 has
its top probability rounded to 1, so the gradient through that entry is lost (Softmax Collapse). None of our models
trains on cross-entropy (MASTER: MSE; TFT, Chronos-2: quantile losses); softmax sits only in attention and in
MASTER's feature gate. F1 logs every softmax row's margin; the fix is applied (F2) only where margins reach the
cliff. Timestral is inference-only, where the collapse does not change a forecast.
"""

import contextlib
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn.functional as Fn

import panel as P

CLIFF_FP32, RULE_MARGIN, RULE_SHARE = 16.6, 15.0, 0.001       # Amendment 3: under 0.1% of rows above 15 -> no-op
LOG = os.path.join(P.CACHE, "logs", "softmax_diag.json")


# ----------------------------------------------------------------------------------------------- the fix (torch)
def fixed_log_softmax(z, dim=-1):
    """log softmax(z) with the max-excluded log-sum-exp and softplus (paper, sec. 3).

    With z* the row maximum and r = logsumexp_{j != *}(z_j - z*), log q_j = (z_j - z*) - softplus(r) and
    log q_* = -softplus(r). The max entry's log-probability holds no z* - z* term, so autograd gives its gradient as
    the negative sum of the others' and nothing rounds against 1."""
    idx = z.argmax(dim, keepdim=True)
    top = torch.zeros_like(z, dtype=torch.bool).scatter_(dim, idx, True)
    d = z - z.gather(dim, idx)
    d = torch.where(top, torch.zeros_like(d), d)                  # the max entry: a constant 0, no z* - z* path
    r = torch.logsumexp(d.masked_fill(top, float("-inf")), dim, keepdim=True)
    if z.shape[dim] == 1:
        r = torch.full_like(r, float("-inf"))
    return d - Fn.softplus(r)


def fixed_softmax(z, dim=-1):
    return fixed_log_softmax(z, dim).exp()


# ------------------------------------------------------------------------------------------- margin diagnostics
class Margins:
    """Per call site: rows seen, rows with margin > 15 and > 16.6, max margin. Every `every`-th call is measured."""

    def __init__(self, every=1):
        self.every, self.calls, self.sites = every, 0, {}

    def add(self, x, dim):
        self.calls += 1
        if self.calls % self.every:
            return
        with torch.no_grad():
            z = x.detach().float().movedim(dim, -1).reshape(-1, x.shape[dim])
            z = z[torch.isfinite(z).any(-1)]
            if z.shape[-1] < 2 or not len(z):
                return
            top, i = z.max(-1, keepdim=True)
            rest = z.scatter(-1, i, float("-inf"))
            m = (top - torch.logsumexp(rest, -1, keepdim=True)).squeeze(-1)
            m = m[torch.isfinite(m)]
            if not len(m):
                return
            f = sys._getframe(1)                                  # the first caller outside torch and this file
            while f.f_back and (f.f_code.co_filename == __file__ or f"{os.sep}torch{os.sep}" in f.f_code.co_filename):
                f = f.f_back
            key = f"{os.path.basename(f.f_code.co_filename)}:{f.f_lineno} (n={x.shape[dim]})"
            s = self.sites.setdefault(key, {"rows": 0, "gt10": 0, "gt15": 0, "gt_cliff": 0, "max": -np.inf})
            s["rows"] += int(len(m))
            s["gt10"] += int((m > 10).sum())                      # descriptive: fp32 top-gradient error ~0.2% here
            s["gt15"] += int((m > RULE_MARGIN).sum())
            s["gt_cliff"] += int((m > CLIFF_FP32).sum())
            s["max"] = max(s["max"], float(m.max()))

    def summary(self):
        rows = sum(s["rows"] for s in self.sites.values())
        gt15 = sum(s["gt15"] for s in self.sites.values())
        return {"rows": rows, "gt10": sum(s["gt10"] for s in self.sites.values()), "gt15": gt15, "share_gt15": gt15 / max(rows, 1),
                "gt_cliff": sum(s["gt_cliff"] for s in self.sites.values()),
                "max_margin": max([s["max"] for s in self.sites.values()] or [float("nan")]),
                "noop": gt15 / max(rows, 1) < RULE_SHARE, "sites": self.sites}


@contextlib.contextmanager
def patched_softmax(margins=None, fixed=False):
    """Route torch.softmax, F.softmax, Tensor.softmax (and nn.Softmax, which calls F.softmax) through a logger and,
    with fixed=True, through fixed_softmax."""
    orig = torch.softmax, Fn.softmax, torch.Tensor.softmax

    def sm(x, dim=None, *a, dtype=None, **k):
        dim = -1 if dim is None else dim
        if dtype is not None:
            x = x.to(dtype)
        if margins is not None:
            margins.add(x, dim)
        return fixed_softmax(x, dim) if fixed else orig[0](x, dim)

    torch.softmax, Fn.softmax = sm, sm
    torch.Tensor.softmax = lambda self, dim=None, *a, **k: sm(self, dim, *a, **k)
    try:
        yield margins
    finally:
        torch.softmax, Fn.softmax, torch.Tensor.softmax = orig


# ------------------------------------------------------------------------------------------------------ commands
def _setup():
    import sp500_transformers as X
    import sp500_test as T
    d = T.build()
    return X, d, X.sectors(d), X.market(d)


def diagnose(model):
    X, d, sector, M = _setup()
    S = d["S"]
    out = {}                                                       # merged into LOG at the end (parallel runs)
    t0 = time.time()
    if model == "master":
        h, cfg = 5, X.FINAL["master_h5"]
        tr, va, train, _ = X.windows(S, 2013, h)
        res = {}
        for s_ in X.SEEDS["master"]:
            mg = Margins()
            with patched_softmax(mg):
                _, info = X.master_fit_predict(d, d[f"y{h}"], tr, va, X.thursdays(S, va), cfg, s_, M)
            res[f"seed{s_}"] = {**mg.summary(), **info}
            X.log("master seed", s_, json.dumps(res[f"seed{s_}"], default=float))
        out["master_h5"] = res
    elif model == "tft":
        h, cfg = 10, X.FINAL["tft_h10"]
        tr, va, train, _ = X.windows(S, 2013, h)
        mg = Margins(every=5)
        with patched_softmax(mg):
            X.tft_fit_predict(d, h, tr, va, X.thursdays(S, va)[:5], cfg, 0, sector)
        out["tft_h10"] = mg.summary()
    elif model == "chronos2_ft":
        import pandas as pd
        q = int(np.searchsorted(S, pd.Timestamp("2013-01-01")))
        mg = Margins(every=20)
        from chronos import Chronos2Pipeline
        orig = Chronos2Pipeline.from_pretrained

        def eager(*a, **k):                                        # eager attention: softmax visible to the logger
            p = orig(*a, **k)
            p.model.config._attn_implementation = "eager"
            return p
        Chronos2Pipeline.from_pretrained = eager
        try:
            with patched_softmax(mg):
                X.chronos_finetune(d, q - 1 - max(X.HS), 2013, out_dir=os.path.join(P.CACHE, "softmax_diag_c2ft"))
        finally:
            Chronos2Pipeline.from_pretrained = orig
        out["chronos2_ft"] = mg.summary()
    else:
        sys.exit(f"unknown model {model}")
    out.setdefault("_meta", {})[model] = {"sec": round(time.time() - t0), "rule": f"share(margin>{RULE_MARGIN}) < "
                                                                                  f"{RULE_SHARE} -> no-op"}
    _merge(out)
    X.log("written", LOG, json.dumps({k: v for k, v in out.items() if k != "_meta"}, default=float)[:2000])


def _merge(out):
    """Read-merge-write under an exclusive lock, so diagnostics running in parallel never drop each other's keys."""
    import fcntl
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        cur = json.load(open(LOG)) if os.path.exists(LOG) else {}
        for k, v in out.items():
            cur[k] = {**cur.get(k, {}), **v} if k == "_meta" else v
        json.dump(cur, open(LOG + ".tmp", "w"), indent=1, default=float)
        os.replace(LOG + ".tmp", LOG)


def ab(model):
    """F2 (only if F1's rule is crossed): validation IC of the 2013 window, 5 seeds, standard vs fixed softmax."""
    diag = json.load(open(LOG))
    key = {"master": "master_h5"}[model]
    if all(v.get("noop", True) for v in diag[key].values() if isinstance(v, dict)):
        sys.exit(f"F1 rule not crossed for {key}: the fix is a numerical no-op; F2 does not run (Amendment 3)")
    X, d, sector, M = _setup()
    S, h, cfg = d["S"], 5, X.FINAL["master_h5"]
    tr, va, train, _ = X.windows(S, 2013, h)
    res = {"standard": [], "fixed": []}
    for s_ in X.SEEDS["master"]:
        for arm in res:
            with patched_softmax(None, fixed=(arm == "fixed")):
                res[arm].append(X.master_fit_predict(d, d[f"y{h}"], tr, va, [], cfg, s_, M)[1]["val_ic"])
    dlt = np.array(res["fixed"]) - np.array(res["standard"])
    diag["ab_master_h5"] = {**res, "delta_mean": float(dlt.mean()), "delta_se": float(dlt.std(ddof=1) / np.sqrt(len(dlt))),
                            "material": bool(dlt.mean() > 2 * dlt.std(ddof=1) / np.sqrt(len(dlt)))}
    _merge({"ab_master_h5": diag["ab_master_h5"]})
    print(json.dumps(diag["ab_master_h5"], indent=1))


if __name__ == "__main__":
    {"diagnose": diagnose, "ab": ab}[sys.argv[1]](sys.argv[2])
