"""Coverage tables for the futures procurement assessment (PROCURE.md), parsed from vendors' published product pages.

Only market names, sectors and first/last dates are kept: product metadata, no prices of any market. The pages were
fetched once on 2026-11-25 with a generic browser User-Agent and kept outside the repository (their sha256 prefixes
are in PROCURE.json, `sources`). Pass the saved pages as arguments:

    python -I research/xasset/procure_coverage.py NORGATE_DCT_HTML PORTARA_DAILY_HTML PINNACLE_CLC_HTML \
        > research/xasset/procure_coverage.json

Sector mapping to the three non-equity classes of Moskowitz-Ooi-Pedersen (2012) Table 4 (COM, FI, FX) plus EQ
(equity indices, excluded from the candidate book because they duplicate the core) and OTHER (crypto, volatility,
dollar index, single-country index composites). Mini and micro duplicates of a full-size market are dropped.
"""
import html
import json
import re
import sys

MON = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"


def text(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d|td|th)>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return [re.sub(r"\s+", " ", x).strip() for x in t.split("\n")]


def is_dup(name):
    """A smaller copy of a full-size market listed by the same vendor (micro, mini-sized grains, mini gold)."""
    return bool(re.search(r"\bMicro\b|Mini-Sized|Gold Mini|24hr|S\. & P\. 500, Mini|Nasdaq, Mini|Dow Jones Mini|Mini Russell", name, re.I))


EQ = r"S\. & P\.|Dax|S&P|Nasdaq|Dow|Russell|Nikkei|TOPIX|FTSE|CAC|DAX|STOXX|Stoxx|SPI 200|Hang Seng|KOSPI|TSX|MSCI|Swiss Market|TecDAX|AEX|IBEX|MIB|China A50|Index - Mini"
FI = r"T-Note|T-Bond|T-Notes|T-Bonds|Treasury|Bund|BUND|BOBL|Bobl|SCHATZ|Schatz|BUXL|Buxl|OAT|BTP|Gilt|Govt|Bond|Bills|Federal Funds|Fed Funds|Eurodollar|Euribor|SONIA|CORRA|Sterling|Interbank|Swap|Euroyen|Muni"
FX = r"\$\$|Dollar$|Pound|Yen|Franc|Frank|Euro FX|Peso|Australian Dollar|Canadian Dollar|New Zealand|Japanese Yen|Swiss Frank|Euro, "
OTHER = r"Bitcoin|Ether|Volatility|US Dollar Index|Dollar Index|GSCI|Goldman|CRB"


def classify(name):
    if re.search(OTHER, name):
        return "OTHER"
    if re.search(FI, name):
        return "FI"
    if re.search(EQ, name):
        return "EQ"
    if re.search(FX, name):
        return "FX"
    return "COM"


def norgate(path):
    L = text(path)
    a = next(i for i, x in enumerate(L) if x.startswith("The symbols shown are for individual contracts"))
    m1, m2 = re.compile(rf"^{MON} (\d{{4}})$"), re.compile(rf"^\d{{1,2}} {MON} (\d{{4}})$")
    out = []
    for i in range(a, len(L) - 3):
        if m1.match(L[i + 1]) and m2.match(L[i + 2]):
            n = L[i]
            if not n or n in ("Day", "Night", "All Sessions Combined") or re.match(r"^[A-Z0-9]{1,6}$", n):
                continue
            out.append({"market": n, "first_contract": L[i + 1], "history_start": L[i + 2],
                        "start_year": int(m2.match(L[i + 2]).group(2)), "symbol": L[i + 3], "end": "current"})
    for r in out:
        r["class"] = classify(r["market"])
        r["duplicate"] = is_dup(r["market"])
    return out


def portara(path):
    L = text(path)
    d = re.compile(rf"^(\d{{4}}) {MON} \d{{2}}$")
    rows = {}
    for i in range(len(L) - 7):
        if d.match(L[i + 5]) and (d.match(L[i + 6]) or L[i + 6] == "Current") and L[i + 4] == "Futures":
            rows.setdefault(L[i], dict(symbol=L[i], desc=L[i + 1], sector=L[i + 2], exchange=L[i + 3],
                                       start=L[i + 5], end=L[i + 6]))
    smap = {"Grain": "COM", "Soft": "COM", "Metal": "COM", "Energy": "COM", "Meat": "COM",
            "Financial": "FI", "Currency": "FX", "Index": "EQ"}

    def norm(s):
        s = re.sub(r"\(.*?\)", "", s)
        s = re.sub(r"\b(Settlement|Combined|Globex|Pit|Day|All Sessions|ICE|Electronic|Composite|Session|Floor|"
                   r"Nymex|MGE|MIAX|HRSW)\b", "", s, flags=re.I)
        return re.sub(r"[^a-z0-9]", "", s.lower())

    markets = {}
    for r in rows.values():
        k = (norm(r["desc"]), r["sector"])
        y = int(r["start"][:4])
        if k not in markets or y < markets[k]["start_year"]:
            cls = smap.get(r["sector"], "OTHER")
            if re.search(r"Dollar Index|Bitcoin|Ether|VIX|Volatility", r["desc"]):
                cls = "OTHER"
            markets[k] = {"market": r["desc"], "exchange": r["exchange"], "sector": r["sector"], "class": cls,
                          "start_year": y, "end": r["end"], "duplicate": is_dup(r["desc"]),
                          "session_variants": 0}
        markets[k]["session_variants"] += 1
    return {"symbols_futures": len(rows), "markets": sorted(markets.values(), key=lambda m: (m["start_year"], m["market"]))}


def pinnacle(path):
    t = " ".join(text(path))
    t = t[t.find("ROLL DAY"):t.find("DM = Delivery Month")]
    t = re.sub(r"\s+", " ", t[len("ROLL DAY"):]) + " "
    by_base = {}
    for m in re.finditer(r"\s*(.+?) ((?:19|20)\d{2}) (.+?(?:MPDM|DM)) ", t):
        name = m.group(1).strip(" ,")
        # Day and Composite sessions of one market are one market: keep the earliest start
        base = re.sub(r",? *(Day|Composite) [Ss]ession.*$", "", name)
        y = int(m.group(2))
        if base not in by_base or y < by_base[base]["start_year"]:
            by_base[base] = {"market": base, "start_year": y, "class": classify(name), "duplicate": is_dup(name)}
    return sorted(by_base.values(), key=lambda m: (m["start_year"], m["market"]))


if __name__ == "__main__":
    ng, pt, pn = sys.argv[1:4]
    json.dump({"fetched": "2026-11-25",
               "norgate": {"url": "https://norgatedata.com/data-content-tables.php#futures", "markets": norgate(ng)},
               "portara": {"url": "https://portaracqg.com/historical-daily-futures-data/", **portara(pt)},
               "pinnacle_clc": {"url": "http://www.pinnacledata.com/clc.html", "markets": pinnacle(pn)}},
              sys.stdout, indent=1)
