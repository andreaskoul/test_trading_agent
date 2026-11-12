"""Branch M5: a small graph network over the 10-K text-neighbour graph, implemented in plain torch.

Node features: ranked characteristics (m5lib.base_design, optionally with hand-built peer features appended).
Layers: encoder Linear+ReLU, then L message-passing layers
    h <- h + ReLU(W_self h + W_nb AGG(h over live neighbours))
AGG = cosine-weighted mean ("sage") or attention over the neighbours and self ("gat"). Output Linear -> score.
graph=False is the control: the same network with every edge removed (AGG = 0), i.e. a per-node MLP.
Loss: squared error on the per-date ranked y5 (eligible names). Trained on Thursdays up to train_end, fixed epochs
(no validation-based stopping).
"""
import numpy as np
import torch
import torch.nn as nn

import m5lib

torch.set_num_threads(3)


class Net(nn.Module):
    def __init__(self, F, H=32, L=1, agg="sage", graph=True, drop=0.1):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(F, H), nn.ReLU())
        self.self_ = nn.ModuleList([nn.Linear(H, H) for _ in range(L)])
        self.nb = nn.ModuleList([nn.Linear(H, H, bias=False) for _ in range(L)])
        if agg == "gat":
            self.att = nn.ModuleList([nn.Linear(2 * H, 1) for _ in range(L)])
        self.out = nn.Linear(H, 1)
        self.agg, self.graph, self.drop = agg, graph, nn.Dropout(drop)

    def aggregate(self, h, NB, W, layer):
        # h (B,N,H); NB (B,N,10) long; W (B,N,10) live weights (0 = dead edge)
        B, N, H = h.shape
        hn = torch.gather(h, 1, NB.reshape(B, -1, 1).expand(-1, -1, H)).reshape(B, N, 10, H)
        if self.agg == "sage":
            s = W.sum(2, keepdim=True)
            return (W.unsqueeze(-1) * hn).sum(2) / s.clamp_min(1e-6)
        # attention over live neighbours plus self
        cand = torch.cat([h.unsqueeze(2), hn], 2)                                   # (B,N,11,H)
        live = torch.cat([torch.ones_like(W[:, :, :1]), (W > 0).float()], 2)
        e = self.att[layer](torch.cat([h.unsqueeze(2).expand_as(cand), cand], -1)).squeeze(-1)
        e = torch.nn.functional.leaky_relu(e, 0.2).masked_fill(live == 0, -1e9)
        a = torch.softmax(e, 2)
        return (a.unsqueeze(-1) * cand).sum(2)  # includes the self term

    def forward(self, x, NB, W):
        h = self.enc(x)
        for l in range(len(self.self_)):
            m = self.self_[l](h)
            if self.graph:
                m = m + self.nb[l](self.aggregate(h, NB, W, l))
            h = h + self.drop(torch.relu(m))
        return self.out(h).squeeze(-1)


def make(base="C24", peer_cols=None, H=32, L=1, agg="sage", graph=True, epochs=15, lr=1e-3, wd=1e-4, batch=8,
         drop=0.1, uniform=False):
    def design(D):
        X, ok = m5lib.base_design(D, base)
        if peer_cols is not None:
            P, _ = m5lib.peer_design(D, base, cols=peer_cols, gap=True)
            X = np.concatenate([X, P], 2)
        return X, ok

    def fit_predict(D, te, rows, seed):
        torch.manual_seed(seed)
        np.random.seed(seed)
        X, ok = design(D)
        S = D["S"]
        tr = np.where((S.weekday == 3) & (np.arange(len(S)) <= te))[0]
        y, m = m5lib.ranked_target(D, te, tr, ok)
        keep = m.sum(1) >= 50
        tr, y, m = tr[keep], y[keep], m[keep]
        NB, W = m5lib.edges(D, tr, ok, uniform)
        Xt, yt, mt = torch.from_numpy(X[tr]), torch.from_numpy(y), torch.from_numpy(m.astype(np.float32))
        NBt, Wt = torch.from_numpy(NB), torch.from_numpy(W)
        net = Net(X.shape[2], H, L, agg, graph, drop)
        opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=wd)
        g = torch.Generator().manual_seed(seed)
        for ep in range(epochs):
            net.train()
            perm = torch.randperm(len(tr), generator=g)
            for i in range(0, len(tr), batch):
                b = perm[i:i + batch]
                p = net(Xt[b], NBt[b], Wt[b])
                loss = (((p - yt[b]) ** 2) * mt[b]).sum() / mt[b].sum()
                opt.zero_grad()
                loss.backward()
                opt.step()
        net.eval()
        NBp, Wp = m5lib.edges(D, rows, ok, uniform)
        with torch.no_grad():
            p = net(torch.from_numpy(X[rows]), torch.from_numpy(NBp), torch.from_numpy(Wp)).numpy()
        return np.where(ok[rows], p, np.nan)

    return fit_predict
