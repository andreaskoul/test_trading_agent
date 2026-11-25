"""Digitise the per-asset Sharpe-ratio bar charts used by LIT_PRIOR.md.

Reads only the published PDFs (not committed: copyright). Fetch them, check their sha256 against SOURCES below,
and run:

    python3 -I research/xasset/digitise.py MOP.pdf HOP.pdf TE.pdf > research/xasset/digitised.json

Method
* MOP 2012 Fig. 2 and HOP 2017 Exhibits 3-4 are vector drawings. Each bar is a filled rectangle; its height in PDF
  points is converted to a Sharpe ratio with the axis calibration (zero = bar baseline; scale from the tick marks or
  the tick-label glyph positions). Resolution is about 0.001.
* Babu et al. 2020 Fig. 2 Panels A-B are embedded JPEG images (825 px wide). Bars are found by colour; heights are
  converted with the axis spine (top and bottom tick values). Resolution about 0.003; JPEG blur makes it about
  ±0.01. Values are rounded to 2 decimals.
* Bar order is the x-axis label order read from the rendered page (labels are drawn as glyph outlines, not text).

Checks (each exits non-zero on failure)
* the bar count of each colour class equals the number of labels of that class;
* intermediate tick positions agree with the linear calibration (MOP);
* HOP Exhibit 3: mean of the 67 bars within 0.05 of the text's "average Sharpe ratio of approximately 0.4" (p. 18);
* MOP Fig. 2: every bar positive (text p. 236: "every single futures contract exhibits positive predictability");
* Babu et al.: median of Panel A within 0.015 of Table 2's 0.34, Panel B within 0.015 of 0.34.
"""
import hashlib
import json
import re
import statistics as st
import sys

import numpy as np
import pypdf
from PIL import Image
from io import BytesIO
from pypdf.generic import ContentStream, NameObject

SOURCES = {
    "MOP": "7682f8e97eb4b77591dc85e36731ff51ed031970cdde81678108734db9478379",
    "HOP": "7b286a9f6cf6925aa9610fc4dcecd15c26c58699c36502938c1e5ec35625b5af",
    "TE": "16e9b7b79e369e03b21c7d15e077f499c5af7015b2528358a4dcc57d2a7a3e0c",
}


def fail(msg):
    sys.stderr.write("CHECK FAILED: " + msg + "\n")
    sys.exit(1)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def filled_rects(path, page):
    """(cmyk colour, x0, x1, y0, y1) of every filled 2-point rectangle on a page, in page coordinates."""
    r = pypdf.PdfReader(path)
    p = r.pages[page - 1]

    def mul(a, b):
        return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3], a[2] * b[0] + a[3] * b[2],
                a[2] * b[1] + a[3] * b[3], a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]

    def tp(m, x, y):
        return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])

    ctm, stack, col, path_, out, glyph_pts = [1, 0, 0, 1, 0, 0], [], None, [], [], []
    for ops, op in ContentStream(p.get_contents(), r).operations:
        o = op.decode(errors="replace")
        if o == "q":
            stack.append((ctm[:], col))
        elif o == "Q":
            ctm, col = stack.pop()
        elif o == "cm":
            ctm = mul([float(v) for v in ops], ctm)
        elif o == "k":
            col = tuple(round(float(v), 3) for v in ops)
        elif o in ("rg", "g", "scn", "sc"):
            col = tuple(round(float(v), 3) for v in ops if not isinstance(v, NameObject))
        elif o == "re":
            x, y, w, h = (float(v) for v in ops)
            path_.append([tp(ctm, x, y), tp(ctm, x + w, y + h)])
        elif o == "m":
            path_.append([tp(ctm, *(float(v) for v in ops))])
        elif o == "l":
            path_[-1].append(tp(ctm, *(float(v) for v in ops)))
        elif o in ("f", "f*", "B", "b", "S", "n"):
            if o != "n":
                for sp in path_:
                    xs = [q[0] for q in sp]
                    ys = [q[1] for q in sp]
                    rec = (col, round(min(xs), 2), round(max(xs), 2), round(min(ys), 2), round(max(ys), 2), len(sp))
                    out.append(rec)
            path_ = []
    return out


def vector_bars(path, page, classes, names, zero, scale, width=(2.0, 3.2)):
    bars = [(x0, classes[c], y1) for (c, x0, x1, y0, y1, n) in filled_rects(path, page)
            if n == 2 and c in classes and abs(y0 - zero) < 0.02 and width[0] < x1 - x0 < width[1]]
    bars.sort()
    flat = [(c, n) for c, lst in names.items() for n in lst]
    if len(bars) != len(flat):
        fail(f"{path} p{page}: {len(bars)} bars, {len(flat)} labels")
    res = []
    for (x, c, y), (cl, nm) in zip(bars, flat):
        if c != cl:
            fail(f"{path} p{page}: colour class {c} where label class is {cl} ({nm})")
        res.append({"instrument": nm, "class": cl, "gross_sharpe": round((y - zero) / scale, 3)})
    return res


def raster_bars(img, zero_px, px_per_unit, pitch, names):
    a = np.asarray(img.convert("RGB")).astype(int)
    blue = (a[:, :, 2] > 120) & (a[:, :, 0] < 60) & (a[:, :, 1] < 130)
    blue[396:, :] = False
    cols = blue.sum(axis=0) > 0
    runs, x, W = [], 0, a.shape[1]
    while x < W:
        if cols[x]:
            s = x
            while x < W and cols[x]:
                x += 1
            runs.append((s, x - 1))
        x += 1
    found = []
    for s, e in runs:
        c = (s + e) // 2
        ys = np.where(blue[:, c])[0]
        top, bot = int(ys.min()), int(ys.max())
        v = (zero_px - top) / px_per_unit if top < zero_px - 1 else -(bot + 1 - zero_px) / px_per_unit
        found.append(((s + e) / 2, v))
    filled = [found[0]]
    for p in found[1:]:  # a bar shorter than one pixel is not detected: keep its slot, value None
        k = round((p[0] - filled[-1][0]) / pitch)
        for _ in range(1, k):
            filled.append((filled[-1][0] + pitch, None))
        filled.append(p)
    flat = [(c, n) for c, lst in names.items() for n in lst]
    if len(filled) != len(flat):
        fail(f"raster: {len(filled)} bar slots, {len(flat)} labels")
    return [{"instrument": n, "class": c, "gross_sharpe": (None if v is None else round(v, 2))}
            for (x, v), (c, n) in zip(filled, flat)]


def summary(rows):
    out = {}
    for c in dict.fromkeys(r["class"] for r in rows):
        v = [r["gross_sharpe"] for r in rows if r["class"] == c and r["gross_sharpe"] is not None]
        out[c] = {"n": len(v), "mean": round(st.mean(v), 3), "median": round(st.median(v), 3),
                  "min": min(v), "max": max(v)}
    return out


MOP_NAMES = {
    "Commodities": ["Aluminum", "Brent Oil", "Cattle", "Cocoa", "Coffee", "Copper", "Corn", "Cotton", "Crude Oil",
                    "Gas Oil", "Gold", "Heating Oil", "Hogs", "Natural Gas", "Nickel", "Platinum", "Silver",
                    "Soybeans", "Soy Meal", "Soy Oil", "Sugar", "Gasoline", "Wheat", "Zinc"],
    "Currencies": ["AUD-NZD", "AUD-USD", "EUR-JPY", "EUR-NOK", "EUR-SEK", "EUR-CHF", "EUR-GBP", "AUD-JPY",
                   "GBP-USD", "EUR-USD", "USD-CAD", "USD-JPY"],
    "Equities": ["ASX SPI 200", "DAX", "IBEX 35", "CAC 40", "FTSE/MIB", "TOPIX", "AEX", "FTSE 100", "S&P 500"],
    "Fixed Income": ["3 Yr Australian Bond", "10 Yr Australian Bond", "2 Yr Euro-Schatz", "5 Yr Euro-Bobl",
                     "10 Yr Euro-Bund", "30 Yr Euro-Buxl", "10 Yr CGB", "10 Yr JGB", "10 Yr Long Gilt",
                     "2 Yr US Treasury Note", "5 Yr US Treasury Note", "10 Yr US Treasury Note",
                     "30 Yr US Treasury Bond"],
}
HOP_EQ = ["Australia S&P/ASX 200", "Germany DAX", "Canada S&P/TSX 60", "Spain IBEX 35", "France CAC 40",
          "Italy FTSE MIB", "Japan Topix", "Netherlands AEX", "U.K. FTSE 100", "U.S. S&P 500", "U.S. Russell 2000"]
HOP3_NAMES = {
    "Equities": HOP_EQ,
    "Fixed Income": ["Australia 3-Yr Note", "Australia 10-Yr Bond", "Germany 2-Yr Note", "Germany 5-Yr Note",
                     "Germany 10-Yr Bond", "Germany 30-Yr Bond", "Canada 10-Yr Note", "France 10-Yr Bond",
                     "Italy 10-Yr Bond", "Japan 10-Yr Bond", "U.K. 10-Yr Bond", "U.S. 2-Yr Treasury Note",
                     "U.S. 5-Yr Treasury Note", "U.S. 10-Yr Treasury Note", "U.S. 20-Yr Treasury Bond"],
    "Currencies": ["USD AUD", "USD CAD", "USD EUR", "USD GBP", "USD JPY", "EUR JPY", "EUR NOK", "EUR SEK", "EUR CHF",
                   "EUR GBP", "JPY AUD", "AUD NZD"],
    "Commodities": ["Aluminum", "Brentoil", "Cattle", "Cocoa", "Coffee", "Copper", "Corn", "Cotton", "Crude",
                    "Gasoil", "Gold", "Heatoil", "Hogs", "Lard", "Natgas", "Nickel", "Oats", "Platinum", "Pork",
                    "Rye", "Shortribs", "Silver", "Soybeans", "Soymeal", "Soyoil", "Sugar", "Unleaded", "Wheat",
                    "Zinc"],
}
HOP4_NAMES = {
    "Equities": HOP_EQ,
    "Fixed Income": ["Germany 5-Yr Note", "Germany 10-Yr Bond", "Canada 10-Yr Note", "France 10-Yr Bond",
                     "Italy 10-Yr Bond", "U.K. 10-Yr Bond", "U.S. 2-Yr Treasury Note", "U.S. 5-Yr Treasury Note",
                     "U.S. 10-Yr Treasury Note", "U.S. 20-Yr Treasury Bond"],
    "Currencies": ["USD EUR", "USD GBP", "USD JPY", "EUR JPY", "EUR CHF", "EUR GBP"],
    "Commodities": ["Cattle", "Cocoa", "Corn", "Cotton", "Gold", "Hogs", "Lard", "Oats", "Pork", "Rye", "Shortribs",
                    "Silver", "Soybeans", "Soymeal", "Soyoil", "Sugar", "Wheat"],
}
TE_A_NAMES = {
    "Commodities": ["Aluminum", "Brent Crude Oil", "Live Cattle", "Cocoa", "Coffee", "Copper", "Corn", "Cotton",
                    "WTI Crude Oil", "Gasoil", "Gold", "Heating Oil", "Lean Hog", "Natural Gas", "Nickel", "Platinum",
                    "Silver", "Soybean", "Soybean Meal", "Soybean Oil", "Sugar", "RBOB Gasoline", "Wheat", "Zinc"],
    "Equities": ["SPI 200 Index", "DAX Index", "IBEX 35 Index", "CAC40 Index", "FTSE MIB Index", "Japan Topix Index",
                 "AEX Index", "FTSE100 Index", "S&P 500 Index"],
    "Fixed Income": ["Australia 3 Yr Bond", "Australia 10 Yr Bond", "Euro Schatz 2 Yr Bond", "Euro Bobl 5 Yr Bond",
                     "Euro Bund 10 Yr Bond", "Euro Buxl 30 Yr Bond", "Canada 10 Yr Bond", "Japan 10 Yr Bond",
                     "U.K. 10 Yr Gilt", "U.S. 2 Yr Treasury Note", "U.S. 5 Yr Treasury Note",
                     "U.S. 10 Yr Treasury Note", "U.S. 30 Yr Treasury Bond"],
    "Currencies": ["AUD vs. NZD", "AUD vs. USD", "EUR vs. JPY", "EUR vs. NOK", "EUR vs. SEK", "EUR vs. CHF",
                   "EUR vs. GBP", "JPY vs. AUD", "GBP vs. USD", "USD vs. EUR", "USD vs. CAD", "USD vs. JPY"],
}
TE_B_NAMES = {
    "Exotic commodities": ["S. African Wheat", "S. African White Maize", "S. African Yellow Maize", "Canola",
                           "EU Emissions", "Feeder Cattle", "German Power", "Iron Ore", "Lead", "Lumber", "Milk",
                           "Orange Juice", "Palm Oil", "Milling Wheat", "Rapeseed", "Rough Rice", "Robusta Coffee",
                           "Rubber", "TOCOM Crude", "UK Natural Gas", "White Sugar"],
    "Credit": ["Emerging Credit", "European - High Yield Credit", "European - IG Credit",
               "N. American - High Yield Credit", "N. American - IG Credit"],
    "Emerging equities": ["Ibovespa Index", "HSCEI China Index", "China A-Shares", "SGX CNX Nifty Index",
                          "KOSPI 200 Index", "South Africa All Share Index", "MSCI Taiwan Index"],
    "FI swaps": ["Australia 2 Yr FI Swap", "Germany 2 Yr FI Swap", "Canada 2 Yr FI Swap", "Japan 2 Yr FI Swap",
                 "Norway 2 Yr FI Swap", "New Zealand 2 Yr FI Swap", "Sweden 2 Yr FI Swap", "Switzerland 2 Yr FI Swap",
                 "United Kingdom 2 Yr FI Swap", "United States 2 Yr FI Swap", "Czech Republic 2 Yr FI Swap",
                 "Hong Kong 2 Yr FI Swap", "Hungary 2 Yr FI Swap", "Mexico 2 Yr FI Swap", "Poland 2 Yr FI Swap",
                 "South Africa 2 Yr FI Swap", "Singapore 2 Yr FI Swap"],
    "Emerging FX": ["BRL vs. USD", "COP vs. USD", "CLP vs. USD", "HUN vs. EUR", "IDR vs. USD", "INR vs. GBP",
                    "INR vs. USD", "ILS vs. USD", "KRW vs. JPY", "KRW vs. USD", "MXN vs. USD", "PHP vs. USD",
                    "PLN vs. EUR", "PLN vs. USD", "ZAR vs. AUD", "ZAR vs. EUR", "ZAR vs. GBP", "ZAR vs. USD",
                    "SGD vs. JPY", "SGD vs. USD", "TWD vs. JPY", "TWD vs. USD", "TRY vs. EUR", "TRY vs. USD"],
    "Vol futures": ["VSTOXX 1", "VSTOXX 2", "VSTOXX 3", "VIX 1", "VIX 2", "VIX 3", "VIX 4", "VIX 5"],
}


def main(mop, hop, te):
    for tag, pth in (("MOP", mop), ("HOP", hop), ("TE", te)):
        if sha(pth) != SOURCES[tag]:
            fail(f"{tag} sha256 differs from the registered file")
    out = {"sources_sha256": SOURCES}

    # MOP Fig. 2, PDF page 10 (journal p. 237). Ticks at x=132.7: centres 560.34 (0.0) ... 669.56 (1.2).
    ticks = {0.0: 560.34, 0.2: 578.55, 0.4: 596.765, 0.6: 614.98, 0.8: 633.14, 1.0: 651.35, 1.2: 669.56}
    scale = (ticks[1.2] - ticks[0.0]) / 1.2
    for v, y in ticks.items():
        if abs(ticks[0.0] + v * scale - y) > 0.05:
            fail(f"MOP tick {v} off the linear calibration")
    mop_cls = {(0.0, 0.0, 0.0, 0.785): "Commodities", (0.0, 0.0, 0.0, 0.0): "Currencies",
               (0.0, 0.0, 0.0, 1.0): "Equities", (0.0, 0.0, 0.0, 0.32): "Fixed Income"}
    m = vector_bars(mop, 10, mop_cls, MOP_NAMES, ticks[0.0], scale, width=(2.0, 3.0))
    if min(r["gross_sharpe"] for r in m) <= 0:
        fail("MOP: a non-positive bar, but the text says every contract is positive")
    out["MOP_fig2_1985_2009"] = {"rows": m, "summary": summary(m)}

    hop_cls = {(0.695, 0.719, 0.016, 0.0): "Equities", (0.746, 0.105, 1.0, 0.008): "Fixed Income",
               (0.668, 0.031, 0.371, 0.0): "Currencies", (0.0, 0.305, 0.844, 0.0): "Commodities"}
    # HOP Exhibit 3, PDF page 6 (printed p. 19). Baseline 436.66; tick-label glyphs 0.0 at 435.29, 1.2 at 663.26.
    h3 = vector_bars(hop, 6, hop_cls, HOP3_NAMES, 436.66, (663.26 - 435.29) / 1.2)
    mean67 = st.mean(r["gross_sharpe"] for r in h3)
    if abs(mean67 - 0.4) > 0.05:
        fail(f"HOP Ex. 3 mean {mean67:.3f} is not 'approximately 0.4'")
    out["HOP_ex3_1880_2016"] = {"rows": h3, "summary": summary(h3), "mean_all_67": round(mean67, 3)}
    # HOP Exhibit 4, PDF page 7 (printed p. 20). Baseline 450.23; glyphs 0.0 at 448.95, 1.4 at 659.03.
    h4 = vector_bars(hop, 7, hop_cls, HOP4_NAMES, 450.23, (659.03 - 448.95) / 1.4, width=(4.0, 4.8))
    out["HOP_ex4_1880_1984"] = {"rows": h4, "summary": summary(h4)}

    # Babu et al. Fig. 2, PDF page 7 (printed p. 58): two JPEGs. Spine rows 5..395.
    imgs = [Image.open(BytesIO(im.data)) for im in pypdf.PdfReader(te).pages[6].images]
    a = raster_bars(imgs[0], 330.0, 390 / 1.2, 13.55, TE_A_NAMES)   # axis 1.0 .. -0.2
    b = raster_bars(imgs[1], 297.5, 390 / 1.6, 9.43, TE_B_NAMES)    # axis 1.2 .. -0.4
    for tag, rows, printed in (("A", a, 0.34), ("B", b, 0.34)):
        med = st.median(r["gross_sharpe"] for r in rows if r["gross_sharpe"] is not None)
        if abs(med - printed) > 0.015:
            fail(f"TE panel {tag} median {med} vs Table 2 {printed}")
    out["TE_fig2A_1985_2017"] = {"rows": a, "summary": summary(a)}
    out["TE_fig2B_alt_assets_to_2017"] = {"rows": b, "summary": summary(b)}
    json.dump(out, sys.stdout, indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
