"""Branch Q5_rl (Layer 3, Amendment 6): reinforcement-learned portfolio construction on fixed signals.
Development data 2013-2019 only (harness.load() and the saved Q4 signals).

Book convention = M1 simulate: weights w_t chosen on Thursday t from data <= t, entered at the next close, held 5
sessions, earn w_t . y5_t, cost 5 bp x sum|w_t - w_{t-1}|; names leave (traded out, cost charged) when not in M1's
mask. y5 is the beta-hedged residual return, so every book here carries an implicit SPY leg of -sum_i w_i beta_i
(the harness convention; the hedge leg's own cost is not charged, as for the controls). Every book is dollar-neutral
by construction (long side and short side normalised to equal gross) and gross <= 1.

Policies (all causal; per-week inputs from data <= t):
* rrl    Moody-Saffell recurrent policy, 13 parameters: a smooth no-trade band on the signal's cross-sectional
         percentile p (entry at |p - .5| > k, held names keep their side while |p - .5| > k - h; held = recurrent
         input from the previous book), size tilt by name vol^-theta_v and signal strength, sides 0.5, then
         book exposure e_t = sigmoid(b0 + beta . x_t) <= 1 from 8 market-state inputs x_t. Initialised AT the
         control band (k .4, h .1). Trained by (a) batch net Sharpe with full backpropagation through the recurrence
         ("rrl_bs") or (b) online differential Sharpe ratio, Moody-Saffell 1998/2001 ("rrl_dsr").
* ppo    PPO (clipped surrogate, GAE) on a 3-d action per week: trade rate tau toward the band target, exit width h,
         exposure e, each a linear-Gaussian function of x_t; reward = differential Sharpe ratio of the week's net.
* eiie   Jiang et al. (2017) per-asset shared network (5 inputs -> 16 -> 16 -> 1, tanh): the same network scores every
         name from (percentile, last week's percentile, held weight, log vol ratio, beta); centred and L1-normalised
         to gross 1 (dollar-neutral), times the exposure head. Trained with a portfolio-vector memory (previous
         weights read from memory, no gradient) on random 26-week mini-batches, objective net Sharpe ("eiie_pvm").
* e2e    The same network trained by full backpropagation through the whole sequence on net Sharpe (Zhang, Zohren and
         Roberts 2020 style), the non-RL baseline ("e2e").

Market state x_t (8): market 20- and 120-session return, log 21-session realised vol, drawdown from the 252-session
high (all standardised by their 2010-2012 Thursday mean/sd, before any validation week), log cross-sectional
dispersion of 5-session residual returns (same standardisation), the signal's mean realised rank IC over the last 13
and 52 weeks whose y5 had ended (rows[k] <= t - 7), and the week-on-week rank autocorrelation of the signal ((ac - .5) x 3).

Walk-forward: for year y in 2014-2019 the policy is trained on the weeks with rows[j] <= harness.train_end(D, y), then
run through year y starting from the book actually held at the end of y-1 (2013 holds the control band book; the
switch cost is charged). Fixed split: trained once on 2013-2016, run through 2017-2019.
"""
import os
import sys

for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(v, "3")

import importlib.util
import json
import time

import numpy as np
import pandas as pd
import torch

torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "3")))
torch.set_default_dtype(torch.float64)

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(TREE))
sys.path.insert(0, TREE)
import harness  # noqa: E402

PREDS = os.path.join(ROOT, ".cache", "tree", "preds", "Q5_rl")
Q4PREDS = os.path.join(ROOT, ".cache", "tree", "preds", "Q4_portfolio")
os.makedirs(PREDS, exist_ok=True)
COST = harness.COST


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


m1 = _mod("m1lib_q5", os.path.join(TREE, "M1_dyntrade", "lib.py"))
q4 = _mod("q4lib_q5", os.path.join(TREE, "Q4_portfolio", "lib.py"))


# ---------------------------------------------------------------- inputs
def signals(D):
    return {"master": D["master_h5_ref"].astype(np.float64),
            "trees": np.load(os.path.join(Q4PREDS, "sig_trees.npy")),
            "ipca": np.load(os.path.join(Q4PREDS, "sig_ipca.npy"))}


def market_state_raw(D, t):
    rm = np.nan_to_num(D["rm"].astype(np.float64))
    L = np.cumsum(rm)
    f1 = L[t] - L[t - 20]
    f2 = L[t] - L[t - 120]
    f3 = np.log(np.std(rm[t - 20:t + 1], ddof=1) * np.sqrt(252) + 1e-6)
    f4 = L[t] - L[t - 251:t + 1].max()
    e5 = np.nansum(D["e"][t - 4:t + 1].astype(np.float64), 0)
    el = D["elig"][t] & np.isfinite(D["e"][t])
    f5 = np.log(np.std(e5[el]) + 1e-6)
    return np.array([f1, f2, f3, f4, f5])


_MS = {}


def market_norm(D):
    if "mu" not in _MS:
        S = D["S"]
        ref = np.where((S.weekday == 3) & (S.year >= 2010) & (S.year <= 2012))[0]
        X = np.array([market_state_raw(D, t) for t in ref])
        _MS["mu"], _MS["sd"] = X.mean(0), X.std(0)
    return _MS["mu"], _MS["sd"]


def prep(D, s):
    """All per-week inputs for one signal on M1's validation rows (identical for the three signals)."""
    rows = m1.val_rows(D, s)
    T, n = len(rows), s.shape[1]
    M = np.zeros((T, n), bool)
    P = np.zeros((T, n))                 # percentile - 0.5 on the mask, 0 off
    Y = np.zeros((T, n))
    V = np.ones((T, n))                  # log(vol / median vol)
    B = np.zeros((T, n))                 # beta - 1
    for j, t in enumerate(rows):
        m = m1.mask(s, D, t)
        M[j] = m
        P[j, m] = pd.Series(s[t][m]).rank(pct=True).to_numpy() - 0.5
        Y[j] = np.where(m, np.nan_to_num(D["y5"][t]), 0.0)
        vol = m1.resid_vol(D, t)
        V[j] = np.where(m, np.log(vol / np.median(vol[m])), 0.0)
        b = D["beta"][t].astype(np.float64)
        B[j] = np.where(m & np.isfinite(b), b - 1, 0.0)
    Pprev = np.zeros((T, n))
    Pprev[1:] = P[:-1]
    ic = harness.weekly_ic(s, D, rows)
    ac = m1.autocorr(s, D, rows)
    mu, sd = market_norm(D)
    X = np.zeros((T, 8))
    for j, t in enumerate(rows):
        X[j, :5] = (market_state_raw(D, t) - mu) / sd
        known = [k for k in range(j) if rows[k] <= t - 7 and np.isfinite(ic[k])]
        X[j, 5] = (np.mean(ic[known[-13:]]) - 0.02) * 20 if known else 0.0
        X[j, 6] = (np.mean(ic[known[-52:]]) - 0.02) * 20 if known else 0.0
        X[j, 7] = (ac[j] - 0.5) * 3 if np.isfinite(ac[j]) else 0.0
    X = np.clip(X, -4, 4)
    years = D["S"][rows].year.to_numpy()
    te = {y: int(np.sum(rows <= harness.train_end(D, y))) for y in range(2014, 2020)}   # train on j < te[y]
    first = {y: int(np.argmax(years == y)) for y in range(2013, 2020)}
    tt = lambda a: torch.as_tensor(a, dtype=torch.float64)
    return {"rows": rows, "years": years, "te": te, "first": first, "M": M, "P": P, "Y": Y, "V": V, "B": B,
            "Pprev": Pprev, "X": X, "ic": ic,
            "tM": tt(M.astype(float)), "tP": tt(P), "tY": tt(Y), "tV": tt(V), "tB": tt(B), "tPp": tt(Pprev), "tX": tt(X)}


# ---------------------------------------------------------------- shared pieces (torch, batch dim first)
def sides_t(a, eps=1e-12):
    pos, neg = torch.relu(a), torch.relu(-a)
    return 0.5 * pos / (pos.sum(-1, keepdim=True) + eps) - 0.5 * neg / (neg.sum(-1, keepdim=True) + eps)


def wbar(m):
    """Weight of one name in an equal-weighted decile side (0.5 / (0.1 n))."""
    return 0.5 / (0.1 * m.sum(-1, keepdim=True).clamp(min=1))


def sharpe_t(R, dim=0):
    return R.mean(dim) / (R.std(dim) + 1e-9) * np.sqrt(52)


# ---------------------------------------------------------------- RRL parametric policy
RRL_NP = 13       # phi: k, h, theta_v, theta_p, b0, beta[8]


def rrl_init(nb, seed, noise=0.05):
    g = torch.Generator().manual_seed(seed)
    phi = torch.zeros(nb, RRL_NP)
    phi[:, 4] = 3.0                                         # exposure sigmoid(3) = .95 at x = 0
    phi = phi + noise * torch.randn(nb, RRL_NP, generator=g) * torch.tensor([1, 1, 1, 1, 0] + [1] * 8)
    return phi


def rrl_step(phi, p, m, v, x, prev_u, s=0.02):
    """phi (nb, 13); p, m, v (n,); x (8,); prev_u (nb, n) unscaled book. Returns unscaled book u and exposure e."""
    k = 0.4 + 0.1 * phi[:, 0:1]
    h = torch.relu(0.1 + 0.1 * phi[:, 1:2])
    sg = torch.sign(p)[None]
    q = torch.clamp(prev_u * sg / (0.5 * wbar(m[None])), 0, 1)        # 1 if held on the side the signal now points
    a = sg * torch.sigmoid((p.abs()[None] - k + h * q) / s) * m[None]
    a = a * torch.exp(-phi[:, 2:3] * v[None] + phi[:, 3:4] * 10 * (p.abs()[None] - 0.4))
    u = sides_t(a)
    e = torch.sigmoid(phi[:, 4:5] + (phi[:, 5:] * x[None]).sum(-1, keepdim=True))
    return u, e


# ---------------------------------------------------------------- EIIE shared network
class EIIE(torch.nn.Module):
    def __init__(self, seed, hid=16):
        super().__init__()
        torch.manual_seed(seed)
        self.f = torch.nn.Sequential(torch.nn.Linear(5, hid), torch.nn.Tanh(), torch.nn.Linear(hid, hid), torch.nn.Tanh(),
                                     torch.nn.Linear(hid, 1))
        self.g = torch.nn.Linear(8, 1)
        with torch.no_grad():
            self.g.weight.mul_(0.1)
            self.g.bias.fill_(3.0)

    def step(self, p, pp, m, v, b, x, prev_u):
        """prev_u (nb, n). Returns u (nb, n) gross 1 dollar-neutral, e (nb, 1)."""
        nb = prev_u.shape[0]
        hq = torch.clamp(prev_u / wbar(m[None]), -2, 2)
        f = torch.stack([2 * p[None].expand(nb, -1), 2 * pp[None].expand(nb, -1), hq, v[None].expand(nb, -1),
                         b[None].expand(nb, -1)], -1)
        sc = self.f(f).squeeze(-1)
        mm = m[None]
        c = (sc - (sc * mm).sum(-1, keepdim=True) / mm.sum(-1, keepdim=True).clamp(min=1)) * mm
        u = c / (c.abs().sum(-1, keepdim=True) + 1e-12)
        e = torch.sigmoid(self.g(x[None])).expand(nb, 1)
        return u, e


# ---------------------------------------------------------------- differentiable simulation
def run_seq(step, Pd, j0, j1, prev_u, prev_w):
    """Runs step(j, prev_u) -> (u, e) over weeks j0..j1-1. Returns net R (L, nb), W (L, nb, n), last u and w."""
    Rs, Ws = [], []
    for j in range(j0, j1):
        u, e = step(j, prev_u)
        w = e * u
        R = (w * Pd["tY"][j][None]).sum(-1) - COST * (w - prev_w).abs().sum(-1)
        Rs.append(R), Ws.append(w)
        prev_u, prev_w = u, w
    return torch.stack(Rs), torch.stack(Ws), prev_u, prev_w


def rrl_stepper(phi, Pd):
    return lambda j, pu: rrl_step(phi, Pd["tP"][j], Pd["tM"][j], Pd["tV"][j], Pd["tX"][j], pu)


def eiie_stepper(net, Pd):
    return lambda j, pu: net.step(Pd["tP"][j], Pd["tPp"][j], Pd["tM"][j], Pd["tV"][j], Pd["tB"][j], Pd["tX"][j], pu)


# ---------------------------------------------------------------- trainers; each returns snapshots {length: policy}
def train_rrl_bs(Pd, jend, seeds, lengths, lr=0.02):
    """Batch net Sharpe, full BPTT through the recurrence, weeks 0..jend-1. Seeds in the batch dim."""
    nb, n = len(seeds), Pd["tY"].shape[1]
    phi = torch.cat([rrl_init(1, s) for s in seeds]).requires_grad_(True)
    opt = torch.optim.Adam([phi], lr=lr)
    snaps = {}
    for it in range(1, max(lengths) + 1):
        z = torch.zeros(nb, n)
        R, _, _, _ = run_seq(rrl_stepper(phi, Pd), Pd, 0, jend, z, z)
        loss = -sharpe_t(R[1:]).sum()
        opt.zero_grad()
        loss.backward()
        opt.step()
        if it in lengths:
            snaps[it] = phi.detach().clone()
    return snaps


def rrl_freeze(phi, part):
    """Post-hoc ablations. part="exposure": exposure fixed at 1 (b0 = 30, beta = 0), only the book shape learns;
    part="book": book fixed at the control band (k .4, h .1, no tilts), only the exposure head learns."""
    phi = phi.clone()
    if part == "exposure":
        phi[:, 4], phi[:, 5:] = 30.0, 0.0
        free = torch.tensor([1.0] * 4 + [0.0] * 9)
    else:
        phi[:, :4] = 0.0
        free = torch.tensor([0.0] * 4 + [1.0] * 9)
    return phi, free


def fixed_band(nb, h):
    """The unlearned smooth band with exit width h and exposure 1 (reference rule)."""
    phi = torch.zeros(nb, RRL_NP)
    phi[:, 1], phi[:, 4] = (h - 0.1) / 0.1, 30.0
    return phi


def train_rrl_dsr(Pd, jend, seeds, lengths, lr=0.01, eta=0.04, freeze=None):
    """Online differential Sharpe ratio (Moody-Saffell): one gradient step per week, sequential passes over the
    training weeks; previous book detached (one-step truncated recurrent derivative). Batch dim = seeds."""
    nb, n = len(seeds), Pd["tY"].shape[1]
    phi = torch.cat([rrl_init(1, s) for s in seeds])
    free = torch.ones(RRL_NP)
    if freeze:
        phi, free = rrl_freeze(phi, freeze)
    phi.requires_grad_(True)
    phi.register_hook(lambda g: g * free)
    opt = torch.optim.Adam([phi], lr=lr)
    snaps = {}
    for ep in range(1, max(lengths) + 1):
        A, Bm = torch.full((nb,), 0.0004), torch.full((nb,), 0.0004 ** 2 + 0.009 ** 2)
        pu, pw = torch.zeros(nb, n), torch.zeros(nb, n)
        for j in range(jend):
            u, e = rrl_step(phi, Pd["tP"][j], Pd["tM"][j], Pd["tV"][j], Pd["tX"][j], pu)
            w = e * u
            R = (w * Pd["tY"][j][None]).sum(-1) - COST * (w - pw).abs().sum(-1)
            dA, dB = R - A, R * R - Bm
            Dt = (Bm * dA - 0.5 * A * dB) / (Bm - A * A).clamp(min=1e-10) ** 1.5
            if j > 0:
                opt.zero_grad()
                (-Dt.sum()).backward()
                opt.step()
            Rd = R.detach()
            A, Bm = A + eta * (Rd - A), Bm + eta * (Rd * Rd - Bm)
            pu, pw = u.detach(), w.detach()
        if ep in lengths:
            snaps[ep] = phi.detach().clone()
    return snaps


def train_e2e(Pd, jend, seed, lengths, lr=0.01, wd=1e-4):
    net = EIIE(seed)
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=wd)
    n = Pd["tY"].shape[1]
    snaps = {}
    for it in range(1, max(lengths) + 1):
        z = torch.zeros(1, n)
        R, _, _, _ = run_seq(eiie_stepper(net, Pd), Pd, 0, jend, z, z)
        loss = -sharpe_t(R[1:, 0])
        opt.zero_grad()
        loss.backward()
        opt.step()
        if it in lengths:
            snaps[it] = {k: v.clone() for k, v in net.state_dict().items()}
    return snaps


def train_eiie_pvm(Pd, jend, seed, lengths, lr=0.01, wd=1e-4, win=26):
    """Jiang et al. online stochastic batch learning with a portfolio-vector memory: previous weights come from the
    memory (no gradient), every week of a random 26-week window is computed in parallel, the memory is overwritten
    with the new weights; objective net Sharpe of the window."""
    net = EIIE(seed)
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=wd)
    rng = np.random.default_rng(seed)
    n = Pd["tY"].shape[1]
    with torch.no_grad():
        z = torch.zeros(1, n)
        _, W0, _, _ = run_seq(eiie_stepper(net, Pd), Pd, 0, jend, z, z)
        PVU = W0[:, 0] / W0[:, 0].abs().sum(-1, keepdim=True).clamp(min=1e-12)       # unscaled book memory
        PVW = W0[:, 0].clone()
    snaps = {}
    win = min(win, jend - 1)
    for it in range(1, max(lengths) + 1):
        a = int(rng.integers(1, jend - win + 1))
        js = np.arange(a, a + win)
        pu, pw = PVU[js - 1], PVW[js - 1]
        us, es = [], []
        for i, j in enumerate(js):                       # parallel in spirit: each week reads the memory, not its window neighbour
            u, e = net.step(Pd["tP"][j], Pd["tPp"][j], Pd["tM"][j], Pd["tV"][j], Pd["tB"][j], Pd["tX"][j], pu[i:i + 1])
            us.append(u[0]), es.append(e[0])
        U, E = torch.stack(us), torch.stack(es)
        Wn = E * U
        R = (Wn * Pd["tY"][js]).sum(-1) - COST * (Wn - pw).abs().sum(-1)
        loss = -sharpe_t(R)
        opt.zero_grad()
        loss.backward()
        opt.step()
        PVU[js], PVW[js] = U.detach(), Wn.detach()
        if it in lengths:
            snaps[it] = {k: v.clone() for k, v in net.state_dict().items()}
    return snaps


# ---------------------------------------------------------------- PPO on (trade rate, exit width, exposure)
def band_target(p, m, prev_u, h, k=0.4):
    """Hard band target (numpy, batch): enter at |p| > k, keep a held name while |p| > k - h on its side."""
    sg = np.sign(p)[None]
    held = (prev_u * sg) > 0
    a = sg * m[None] * ((np.abs(p)[None] > k) | (held & (np.abs(p)[None] > k - h[:, None])))
    pos, neg = np.maximum(a, 0), np.maximum(-a, 0)
    return 0.5 * pos / np.maximum(pos.sum(1, keepdims=True), 1e-12) - 0.5 * neg / np.maximum(neg.sum(1, keepdims=True), 1e-12)


def sides_np(a):
    pos, neg = np.maximum(a, 0), np.maximum(-a, 0)
    return 0.5 * pos / np.maximum(pos.sum(-1, keepdims=True), 1e-12) - 0.5 * neg / np.maximum(neg.sum(-1, keepdims=True), 1e-12)


def ppo_env_step(Pd, j, act, prev_u, prev_w):
    """act (nb, 3) squashed actions in (0,1): tau, h/0.4, e."""
    m, p = Pd["M"][j], Pd["P"][j]
    tau, h, e = act[:, 0:1], act[:, 1] * 0.4, act[:, 2:3]
    tgt = band_target(p, m, prev_u, h)
    u = sides_np(np.where(m[None], (1 - tau) * prev_u + tau * tgt, 0.0))
    w = e * u
    R = (w * Pd["Y"][j][None]).sum(1) - COST * np.abs(w - prev_w).sum(1)
    return u, w, R


class PPOPolicy(torch.nn.Module):
    def __init__(self, seed):
        super().__init__()
        torch.manual_seed(seed)
        self.mu = torch.nn.Linear(9, 3)
        self.v = torch.nn.Linear(9, 1)
        with torch.no_grad():
            self.mu.weight.mul_(0.1)
            self.mu.bias.copy_(torch.tensor([2.0, 0.0, 3.0]))   # tau .88, h .2 (band .1 is h/0.4 = .25), e .95
        self.logstd = torch.nn.Parameter(torch.full((3,), -0.5))

    def obs(self, x, dsr_a):
        return torch.cat([x, dsr_a], -1)


def train_ppo(Pd, jend, seed, lengths, n_env=16, ep_len=52, lr=0.01, gamma=0.9, lam=0.9, clip=0.2, eta=0.04,
              ctl_book=None):
    rng = np.random.default_rng(seed)
    pol = PPOPolicy(seed)
    opt = torch.optim.Adam(pol.parameters(), lr=lr)
    ep_len = min(ep_len, jend - 2)
    snaps = {}
    for it in range(1, max(lengths) + 1):
        starts = rng.integers(1, jend - ep_len + 1, n_env)
        pu = ctl_book[starts - 1].copy()
        pw = pu.copy()
        A, Bm = np.full(n_env, 0.0004), np.full(n_env, 0.0004 ** 2 + 0.009 ** 2)
        obs, acts, logps, rews, vals = [], [], [], [], []
        for i in range(ep_len):
            js = starts + i
            o = torch.as_tensor(np.column_stack([Pd["X"][js], A * 1000]))
            with torch.no_grad():
                mu, v = pol.mu(o), pol.v(o)[:, 0]
                dist = torch.distributions.Normal(mu, pol.logstd.exp())
                a = mu + pol.logstd.exp() * torch.as_tensor(rng.standard_normal((n_env, 3)))
                lp = dist.log_prob(a).sum(-1)
            sq = torch.sigmoid(a).numpy()
            R = np.zeros(n_env)
            nu, nw = np.zeros_like(pu), np.zeros_like(pw)
            for b in range(n_env):          # weeks differ by env
                u_, w_, R_ = ppo_env_step(Pd, js[b], sq[b:b + 1], pu[b:b + 1], pw[b:b + 1])
                nu[b], nw[b], R[b] = u_[0], w_[0], R_[0]
            dA, dB = R - A, R * R - Bm
            Dt = (Bm * dA - 0.5 * A * dB) / np.maximum(Bm - A * A, 1e-10) ** 1.5
            A, Bm = A + eta * (R - A), Bm + eta * (R * R - Bm)
            pu, pw = nu, nw
            obs.append(o), acts.append(a), logps.append(lp), rews.append(torch.as_tensor(Dt * eta)), vals.append(v)
        rews, vals = torch.stack(rews), torch.stack(vals)
        rews = rews / (rews.std() + 1e-9)
        adv = torch.zeros_like(rews)
        last = torch.zeros(n_env)
        for i in reversed(range(ep_len)):
            nv = vals[i + 1] if i + 1 < ep_len else torch.zeros(n_env)
            delta = rews[i] + gamma * nv - vals[i]
            last = delta + gamma * lam * last
            adv[i] = last
        ret = adv + vals
        O, Ac, LP = torch.cat(obs), torch.cat(acts), torch.cat(logps)
        AD, RT = adv.reshape(-1), ret.reshape(-1)
        AD = (AD - AD.mean()) / (AD.std() + 1e-9)
        for _ in range(4):
            dist = torch.distributions.Normal(pol.mu(O), pol.logstd.exp())
            lp = dist.log_prob(Ac).sum(-1)
            ratio = (lp - LP).exp()
            l1 = -torch.min(ratio * AD, ratio.clamp(1 - clip, 1 + clip) * AD).mean()
            l2 = ((pol.v(O)[:, 0] - RT) ** 2).mean()
            opt.zero_grad()
            (l1 + 0.5 * l2 - 0.001 * dist.entropy().sum(-1).mean()).backward()
            opt.step()
        if it in lengths:
            snaps[it] = {k: v.clone() for k, v in pol.state_dict().items()}
    return snaps


def ppo_run(state, Pd, j0, j1, prev_u, prev_w):
    """Deterministic (mean-action) run; numpy. prev_u, prev_w (n,)."""
    pol = PPOPolicy(0)
    pol.load_state_dict(state)
    A, Bm = 0.0004, 0.0004 ** 2 + 0.009 ** 2
    Rs, Ws = [], []
    pu, pw = prev_u[None], prev_w[None]
    for j in range(j0, j1):
        o = torch.as_tensor(np.concatenate([Pd["X"][j], [A * 1000]]))[None]
        with torch.no_grad():
            sq = torch.sigmoid(pol.mu(o)).numpy()
        pu, pw, R = ppo_env_step(Pd, j, sq, pu, pw)
        A, Bm = A + 0.04 * (R[0] - A), Bm + 0.04 * (R[0] ** 2 - Bm)
        Rs.append(R[0]), Ws.append(pw[0])
    return np.array(Rs), np.array(Ws), pu[0], pw[0]


# ---------------------------------------------------------------- controls
def control_band(D, s, Pd):
    return m1.build("band", s, D, Pd["rows"])


def control_mvnl_nt(D, s, Pd, name):
    p = os.path.join(PREDS, f"_W_mvnl_nt_{name}.npy")
    if os.path.exists(p):
        return np.load(p)
    W = q4.build({"target": "mvnl", "nt": 2.0}, s, D, Pd["rows"])[0]
    np.save(p, W)
    return W


def net_of(W, Pd):
    """Weekly net of a weight panel W (T, n), M1 convention (prev = previous row's weights)."""
    prev = np.vstack([np.zeros((1, W.shape[1])), W[:-1]])
    return (W * Pd["Y"]).sum(1) - COST * np.abs(W - prev).sum(1), np.abs(W - prev).sum(1) / 2


# ---------------------------------------------------------------- metrics
nw_t, max_dd = q4.nw_t, q4.max_dd


def shp(x):
    return float(x.mean() / x.std(ddof=1) * np.sqrt(52)) if len(x) > 2 and x.std() > 0 else float("nan")


def stats(net, turn, years, gross):
    a, b = years <= 2016, years >= 2017
    return {"net_pct_per_year": float(52 * net.mean() * 100), "net_sharpe": shp(net), "gross_sharpe": shp(gross),
            "gross_pct_per_year": float(52 * gross.mean() * 100), "max_drawdown": max_dd(net),
            "turnover": float(turn.mean()), "vol_pct_per_year": float(net.std(ddof=1) * np.sqrt(52) * 100),
            "by_period": {"2014-2016": {"net_sharpe": shp(net[a]), "net_pct_per_year": float(52 * net[a].mean() * 100),
                                        "max_drawdown": max_dd(net[a])},
                          "2017-2019": {"net_sharpe": shp(net[b]), "net_pct_per_year": float(52 * net[b].mean() * 100),
                                        "max_drawdown": max_dd(net[b])}},
            "by_year_net_pct": {int(y): float(52 * net[years == y].mean() * 100) for y in np.unique(years)}}


def versus(net, ctl, years):
    d = net - ctl
    vm = net * ctl.std(ddof=1) / net.std(ddof=1)
    dv = vm - ctl
    return {"diff_pct_per_year": float(52 * d.mean() * 100), "t_nw4": nw_t(d) if np.abs(d).sum() > 0 else 0.0,
            "diff_2014_2016": float(52 * d[years <= 2016].mean() * 100),
            "diff_2017_2019": float(52 * d[years >= 2017].mean() * 100),
            "volmatched_diff_pct_per_year": float(52 * dv.mean() * 100), "volmatched_t_nw4": nw_t(dv) if np.abs(dv).sum() > 0 else 0.0,
            "max_drawdown_at_control_vol": max_dd(vm), "control_net_sharpe": shp(ctl), "control_max_drawdown": max_dd(ctl)}
