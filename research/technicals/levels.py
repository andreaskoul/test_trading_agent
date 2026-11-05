"""Technicals desk · the level map (draft Amendment 8). Deterministic, no LLM, no I/O.

Input: daily bars of one stock, a DataFrame indexed by session date with open, high, low, close, volume.
Prices are split-adjusted but NOT dividend-adjusted, so old levels and round numbers sit where traders saw
them. Every quantity at day t uses rows up to and including t only; a swing pivot is used only once the
bars that confirm it have closed.

A short is handled by mirroring prices (p -> -p, high <-> low): every rule is written once, for a long,
and `Chart(bars, side=-1)` applies it to a short. Distances are in ATR so the mirror is exact.

    ch = Chart(bars, side=+1)
    lm = ch.levels(t, event_day=..., extra=[...])      # dict: zones, anchors, event candle, AVWAPs, ...

Zones merge three kinds of evidence, clustered within ZONE_TOL x ATR:
* swing pivots (5-bar fractals; a 20-bar fractal counts double), weighted by recency and the volume at
  the turn (Osler 2000; Lo, Mamaysky & Wang 2000: levels from a smoothed price path, not hand-drawn);
* high-volume nodes of a 252-day volume-at-price profile (where holders' cost basis sits;
  Grinblatt & Han 2005);
* the 52-week high and low and the all-time high in the data (George & Hwang 2004).
News-stated prices (a deal price, an offering price, ...; the LLM technician's task 1) come in as `extra`.
"""

import math

import numpy as np
import pandas as pd

P = dict(
    ATR_N=14,             # Wilder ATR
    K_MINOR=5,            # fractal half-width of a swing pivot
    K_MAJOR=20,           # a pivot that is also a 20-bar fractal counts double
    LOOKBACK=252,         # sessions of history for pivots and the profile
    ZONE_TOL=0.5,         # cluster pivots within this many ATR
    HALF_LIFE=126,        # recency half-life of a pivot's weight, sessions
    BIN=0.25,             # volume-profile bin width, ATR
    HVN=1.5,              # a profile node is high-volume at this multiple of the mean bin volume
    LVN=0.5,              # ... and low-volume below this multiple
    STRONG=2.0,           # a zone is "strong" at this strength or more
    ANCHOR_W=2.0,         # strength of the 52-week high / low and the all-time high as zones
    RELVOL_N=20,          # relative volume: volume / mean of the previous 20 sessions
    MAX_BINS=400,         # profile bins are widened beyond BIN x ATR if the year's range needs more than this
)


def mirror(bars: pd.DataFrame) -> pd.DataFrame:
    """The short side's chart: prices negated, high and low swapped. Volume unchanged."""
    return pd.DataFrame({"open": -bars["open"], "high": -bars["low"], "low": -bars["high"], "close": -bars["close"],
                         "volume": bars["volume"]}, index=bars.index)


def round_step(price: float) -> tuple[float, float]:
    """Minor and major round-number steps for a share price (where stop and limit orders cluster; Osler 2003)."""
    p = abs(price)
    for lim, minor, major in ((10, 0.5, 1), (25, 1, 5), (50, 2.5, 10), (100, 5, 10), (250, 5, 50), (500, 10, 100),
                              (1000, 25, 100), (2500, 50, 500), (math.inf, 100, 1000)):
        if p < lim:
            return minor, major
    return 100, 1000


def round_levels(price: float, span: float) -> list[dict]:
    """Round numbers within +-span of price (signed prices allowed: a mirrored chart's levels are negated)."""
    s = 1 if price >= 0 else -1
    p = abs(price)
    minor, major = round_step(p)
    lo, hi = math.floor((p - span) / minor), math.ceil((p + span) / minor)
    out = []
    for i in range(max(lo, 1), hi + 1):
        r = i * minor
        if abs(r - p) <= span:
            out.append({"price": s * r, "major": abs(r / major - round(r / major)) < 1e-9})
    return sorted(out, key=lambda x: x["price"])


class Chart:
    """Precomputed series for one stock and one side; `levels(t)` is the point-in-time map."""

    def __init__(self, bars: pd.DataFrame, side: int = 1):
        assert side in (1, -1)
        b = bars[["open", "high", "low", "close", "volume"]].astype(float).sort_index()
        b = b[~b.index.duplicated(keep="last")].dropna(subset=["high", "low", "close"])
        self.side, self.raw = side, b
        self.b = b if side == 1 else mirror(b)
        b = self.b
        pc = b["close"].shift(1)
        tr = pd.concat([b["high"] - b["low"], (b["high"] - pc).abs(), (b["low"] - pc).abs()], axis=1).max(axis=1)
        self.atr = tr.ewm(alpha=1 / P["ATR_N"], adjust=False, min_periods=P["ATR_N"]).mean()
        self.relvol = b["volume"] / b["volume"].shift(1).rolling(P["RELVOL_N"], min_periods=10).mean()
        for n in (20, 21, 50, 200):
            setattr(self, f"sma{n}", b["close"].rolling(n, min_periods=n).mean())
        self.typical = (b["high"] + b["low"] + b["close"]) / 3
        sd20 = b["close"].rolling(20, min_periods=20).std()
        self.bbw = (4 * sd20 / self.atr)                     # band width in ATR, sign-free
        self.ix = {d: i for i, d in enumerate(b.index)}
        # swing pivots: bar i is a pivot high if its high is the max of [i-k, i+k]; known at bar i+k
        self.piv = []
        H, L, V = b["high"].to_numpy(), b["low"].to_numpy(), self.relvol.to_numpy()
        n = len(b)
        for kind, arr, fn in (("H", H, np.max), ("L", L, np.min)):
            for i in range(P["K_MINOR"], n - P["K_MINOR"]):
                w = arr[i - P["K_MINOR"]:i + P["K_MINOR"] + 1]
                if arr[i] != fn(w):
                    continue
                k2 = P["K_MAJOR"]
                major = i - k2 >= 0 and i + k2 < n and arr[i] == fn(arr[i - k2:i + k2 + 1])
                self.piv.append({"i": i, "known": i + P["K_MINOR"], "known_major": i + k2, "price": float(arr[i]),
                                 "kind": kind, "major": bool(major),
                                 "relvol": float(V[i]) if np.isfinite(V[i]) else 1.0})
        self.piv.sort(key=lambda x: x["known"])

    # ------------------------------------------------------------------ helpers
    def _i(self, t) -> int:
        t = pd.Timestamp(t)
        if t in self.ix:
            return self.ix[t]
        j = self.b.index.searchsorted(t, side="right") - 1
        if j < 0:
            raise KeyError(f"no bar on or before {t.date()}")
        return int(j)

    def avwap(self, start, t) -> float | None:
        """Anchored VWAP from the session `start` (inclusive) to t, on the daily typical price."""
        i0, i1 = self._i(start), self._i(t)
        if pd.Timestamp(self.b.index[i0]) < pd.Timestamp(start):
            i0 += 1
        if i0 > i1:
            return None
        v = self.b["volume"].iloc[i0:i1 + 1]
        if v.sum() <= 0:
            return float(self.typical.iloc[i0:i1 + 1].mean())
        return float((self.typical.iloc[i0:i1 + 1] * v).sum() / v.sum())

    def profile(self, i: int, atr: float) -> dict:
        """252-session volume-at-price: each session's volume spread evenly over its high-low range."""
        lo_i = max(0, i - P["LOOKBACK"] + 1)
        seg = self.b.iloc[lo_i:i + 1]
        if len(seg) < 20 or not atr or not np.isfinite(atr):
            return {"poc": None, "hvn": [], "lvn": [], "edges": None, "vol": None}
        base = float(seg["low"].min())
        w = max(P["BIN"] * atr, (float(seg["high"].max()) - base) / P["MAX_BINS"])     # a year's range over an
        nb = int(math.ceil((float(seg["high"].max()) - base) / w)) + 1                # unusually small ATR
        vol = np.zeros(nb)
        for lo, hi, v in zip(seg["low"].to_numpy(), seg["high"].to_numpy(), seg["volume"].to_numpy()):
            a, z = int((lo - base) // w), int((hi - base) // w)
            vol[a:z + 1] += v / (z - a + 1)
        sm = np.convolve(vol, np.ones(3) / 3, mode="same")
        mean = sm.mean() if sm.mean() > 0 else 1.0
        mids = base + (np.arange(nb) + 0.5) * w
        hvn = [{"price": float(mids[j]), "x": float(sm[j] / mean)} for j in range(nb)
               if sm[j] >= P["HVN"] * mean and sm[j] == sm[max(0, j - 2):j + 3].max()]
        lvn = [float(mids[j]) for j in range(nb) if sm[j] < P["LVN"] * mean]
        return {"poc": float(mids[int(np.argmax(sm))]), "hvn": hvn, "lvn": lvn, "base": base, "w": w, "sm": sm / mean}

    def air(self, lm: dict, a: float, z: float) -> float:
        """Share of the price path a -> z that crosses low-volume profile bins (0..1): 'clear air' above a long."""
        pr = lm.get("_profile") or {}
        if pr.get("sm") is None or z <= a:
            return 0.0
        j0 = max(0, int((a - pr["base"]) // pr["w"]))
        j1 = min(len(pr["sm"]) - 1, int((z - pr["base"]) // pr["w"]))
        if j1 < j0:
            return 1.0                                    # above the whole profile: nothing traded there for a year
        return float((pr["sm"][j0:j1 + 1] < P["LVN"]).mean())

    # ------------------------------------------------------------------ the map
    def levels(self, t, event_day=None, extra=None, anchors_from=None) -> dict:
        """The point-in-time level map at the close of session t (long frame; see `side`).

        event_day: the session the driving news first hit the price (the first session at or after
        `first_reported`). extra: news-stated price levels [{"name", "price" (real, unmirrored), "hard"}].
        anchors_from: extra AVWAP anchors {name: date}, e.g. the last earnings date."""
        i = self._i(t)
        b = self.b
        close, atr = float(b["close"].iloc[i]), float(self.atr.iloc[i])
        if not np.isfinite(atr) or atr <= 0:
            raise ValueError(f"no ATR yet on {b.index[i].date()}")
        d_t = b.index[i]
        lo_i = max(0, i - P["LOOKBACK"] + 1)
        # 1. evidence points: confirmed pivots in the lookback, profile nodes, anchors
        pts = []
        for p in self.piv:
            if p["known"] > i:
                break
            if p["i"] < lo_i:
                continue
            age = i - p["i"]
            w = 0.5 ** (age / P["HALF_LIFE"]) * (2.0 if p["major"] and p["known_major"] <= i else 1.0) \
                * float(np.clip(p["relvol"], 0.5, 3.0))
            pts.append({"price": p["price"], "w": w, "kind": p["kind"], "last": p["i"]})
        prof = self.profile(i, atr)
        for h in prof["hvn"]:
            pts.append({"price": h["price"], "w": min(h["x"], 3.0) / 1.5, "kind": "V", "last": i})
        hi52, lo52 = float(b["high"].iloc[lo_i:i + 1].max()), float(b["low"].iloc[lo_i:i + 1].min())
        ath = float(b["high"].iloc[:i + 1].max())
        anchors = [("52w_high", hi52), ("52w_low", lo52)] + ([("all_time_high", ath)] if ath > hi52 + 1e-9 else [])
        for name, px in anchors:
            pts.append({"price": px, "w": P["ANCHOR_W"], "kind": "A", "last": i, "anchor": name})
        # 2. cluster into zones
        pts.sort(key=lambda x: x["price"])
        zones, cur = [], []
        tol = P["ZONE_TOL"] * atr
        for p in pts:
            if cur and p["price"] - np.average([q["price"] for q in cur], weights=[q["w"] for q in cur]) > tol:
                zones.append(cur); cur = []
            cur.append(p)
        if cur:
            zones.append(cur)
        Z = []
        for k, zs in enumerate(zones):
            kinds = {q["kind"] for q in zs}
            s = sum(q["w"] for q in zs) * (1.25 if {"H", "L"} <= kinds else 1.0)       # role flip
            Z.append({"lo": min(q["price"] for q in zs), "hi": max(q["price"] for q in zs),
                      "mid": float(np.average([q["price"] for q in zs], weights=[q["w"] for q in zs])),
                      "strength": round(float(s), 3), "touches": sum(q["kind"] in "HL" for q in zs),
                      "highs": sum(q["kind"] == "H" for q in zs),
                      "kinds": "".join(sorted(kinds)), "anchors": [q["anchor"] for q in zs if q.get("anchor")],
                      "last": str(b.index[max(q["last"] for q in zs)].date()), "hard": False, "name": None})
        for x in extra or []:                                     # news-stated levels: hard, named
            px = float(x["price"]) * self.side
            Z.append({"lo": px, "hi": px, "mid": px, "strength": math.inf if x.get("hard") else P["STRONG"] * 2,
                      "touches": 0, "highs": 0, "kinds": "N", "anchors": [], "last": str(d_t.date()), "hard": bool(x.get("hard")),
                      "name": x.get("name")})
        Z.sort(key=lambda z: z["mid"])
        for k, z in enumerate(Z):
            z["id"] = f"Z{k + 1}"
            z["dist_atr"] = round((z["mid"] - close) / atr, 3)
        # 3. event candle and AVWAPs
        ev = None
        if event_day is not None:
            j = self._i(event_day)
            if pd.Timestamp(b.index[j]) < pd.Timestamp(event_day):
                j += 1
            if 1 <= j <= i:
                row, pc, a0 = b.iloc[j], float(b["close"].iloc[j - 1]), float(self.atr.iloc[j - 1])
                rng = float(row["high"] - row["low"])
                since = b.iloc[j:i + 1]
                gap = float(row["open"] - pc)
                ev = {"day": str(b.index[j].date()), "gap_atr": round(gap / a0, 3) if a0 else None,
                      "move_atr": round(float(row["close"] - pc) / a0, 3) if a0 else None,
                      "range_atr": round(rng / a0, 3) if a0 else None,
                      "clv": round(float(row["close"] - row["low"]) / rng, 3) if rng > 0 else 0.5,
                      "relvol": round(float(self.relvol.iloc[j]), 3) if np.isfinite(self.relvol.iloc[j]) else None,
                      "high": float(row["high"]), "low": float(row["low"]), "mid": float(row["high"] + row["low"]) / 2,
                      "prev_close": pc, "gap_filled": bool(gap > 0 and float(since["low"].min()) <= pc)
                      or bool(gap < 0 and float(since["high"].max()) >= pc),
                      "avwap": self.avwap(b.index[j], d_t), "sessions_since": int(i - j)}
        avw = {}
        hi_day = b["high"].iloc[lo_i:i + 1].idxmax()
        lo_day = b["low"].iloc[lo_i:i + 1].idxmin()
        for name, d0 in [("from_52w_high", hi_day), ("from_52w_low", lo_day)] + list((anchors_from or {}).items()):
            if d0 is not None and pd.Timestamp(d0) <= d_t:
                avw[name] = self.avwap(d0, d_t)
        if ev:
            avw["from_event"] = ev["avwap"]
        # 4. trend, extension, regime of the stock itself
        sma = {n: float(getattr(self, f"sma{n}").iloc[i]) for n in (20, 21, 50, 200)}
        sl50 = (sma[50] - float(self.sma50.iloc[i - 10])) / atr if i >= 10 and np.isfinite(self.sma50.iloc[i - 10]) else None
        sl200 = (sma[200] - float(self.sma200.iloc[i - 20])) / atr if i >= 20 and np.isfinite(self.sma200.iloc[i - 20]) else None
        bbw_hist = self.bbw.iloc[max(0, i - 251):i + 1].dropna()
        return {
            "date": str(d_t.date()), "side": self.side, "close": close, "atr": atr, "atr_pct": atr / abs(close),
            "zones": Z, "rounds": round_levels(close, 6 * atr),
            "poc": prof["poc"], "lvn_share": None, "_profile": prof,
            "sma20": sma[20], "sma50": sma[50], "sma200": sma[200],
            "ext_atr": round((close - sma[20]) / atr, 3) if np.isfinite(sma[20]) else None,
            "mad_atr": round((sma[21] - sma[200]) / atr, 3) if np.isfinite(sma[200]) else None,
            "slope50_atr": None if sl50 is None or not np.isfinite(sl50) else round(sl50, 3),
            "slope200_atr": None if sl200 is None or not np.isfinite(sl200) else round(sl200, 3),
            "hi52": hi52, "lo52": lo52, "ath": ath,
            "bbw_pct": float((bbw_hist <= bbw_hist.iloc[-1]).mean()) if len(bbw_hist) >= 60 else None,
            "relvol": float(self.relvol.iloc[i]) if np.isfinite(self.relvol.iloc[i]) else None,
            "event": ev, "avwap": avw,
        }

    def real(self, px: float | None) -> float | None:
        """A level of the (possibly mirrored) frame as a real share price."""
        return None if px is None else px * self.side


def public(lm: dict, ch: Chart) -> dict:
    """The map as stored in technicals.json: real prices, no internal arrays."""
    s = ch.side
    rp = lambda x: None if x is None else round(x * s, 4)
    z = [{**{k: v for k, v in q.items() if k not in ("lo", "hi", "mid")}, "lo": rp(q["hi"] if s < 0 else q["lo"]),
          "hi": rp(q["lo"] if s < 0 else q["hi"]), "mid": rp(q["mid"]),
          "strength": (None if q["strength"] == math.inf else q["strength"])} for q in lm["zones"]]
    ev = lm["event"]
    if ev:
        ev = {**ev, "high": rp(ev["low"] if s < 0 else ev["high"]), "low": rp(ev["high"] if s < 0 else ev["low"]),
              "mid": rp(ev["mid"]), "prev_close": rp(ev["prev_close"]), "avwap": rp(ev["avwap"])}
    return {**{k: v for k, v in lm.items() if k not in ("_profile", "zones", "event", "avwap", "rounds")},
            "close": rp(lm["close"]), "sma20": rp(lm["sma20"]), "sma50": rp(lm["sma50"]), "sma200": rp(lm["sma200"]),
            "hi52": rp(lm["lo52"] if s < 0 else lm["hi52"]), "lo52": rp(lm["hi52"] if s < 0 else lm["lo52"]),
            "ath": rp(lm["ath"]), "poc": rp(lm["poc"]), "zones": z, "event": ev,
            "avwap": {k: rp(v) for k, v in lm["avwap"].items()},
            "rounds": [{"price": rp(r["price"]), "major": r["major"]} for r in lm["rounds"]]}
