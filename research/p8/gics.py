"""GICS hierarchy (sector > industry group > industry > sub-industry) for the P8 inference cluster (§1: "Industry =
the GICS industry, about 70 clusters").

    python research/p8/gics.py      # -> .cache/p8/gics.json and a match report

Source: the hierarchy table of Wikipedia's "Global Industry Classification Standard" article (MediaWiki API, wikitext),
which reproduces MSCI/S&P's published structure with its 8-digit codes. Firms carry their GICS sub-industry *name*
in data/raw/stocks/sp{500,400}_current.csv; names are matched to codes exactly after normalising case, '&'/'and'
and punctuation. An unmatched name is reported, never guessed.
"""
import json
import os
import re
import sys
import urllib.request

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices as PX                                              # noqa: E402

OUT = os.path.join(PX.CACHE, "gics.json")
# Sub-industries retired in the 2023 GICS revision whose industry is unchanged (MSCI/S&P, March 2023):
# 25504040 Specialty Stores sat in 255040 Specialty Retail, which still exists.
RETIRED = {"Specialty Stores": "255040"}


def clean(x):
    x = re.sub(r"\[\[([^|\]]*\|)?([^\]]*)\]\]", r"\2", x)
    x = re.sub(r"<[^>]*>|'''|''", "", x)
    return " ".join(x.replace("&amp;", "&").split()).strip(" |")


def norm(x):
    x = clean(x).lower().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", x).split())


def parse(wiki):
    """The table as one stream of cells (a rowspan puts a code and its name on separate lines): each 2/4/6/8-digit
    code cell is followed by its name cell."""
    i = wiki.find("{|")
    j = wiki.find("|}", i)
    toks = []
    for line in wiki[i:j].split("\n"):
        if not line.startswith("|") or line.startswith("|-") or line.startswith("{|"):
            continue
        line = re.sub(r'(rowspan|colspan)\s*=\s*"?\d+"?\s*\|', "", line)
        toks += [c.strip() for c in re.split(r"\|\|", line[1:]) if c.strip()]
    rows, cur, k = [], {}, 0
    while k < len(toks) - 1:
        m = re.fullmatch(r"(\d{2}|\d{4}|\d{6}|\d{8})", toks[k])
        if m:
            code, name = m.group(1), clean(toks[k + 1])
            lvl = {2: "sector", 4: "group", 6: "industry", 8: "sub"}[len(code)]
            cur[lvl] = (code, name)
            if lvl == "sub":
                rows.append({"sub_code": code, "sub": name, "industry_code": cur["industry"][0],
                             "industry": cur["industry"][1], "sector": cur["sector"][1]})
            k += 2
        else:
            k += 1
    return pd.DataFrame(rows)


def main():
    url = "https://en.wikipedia.org/w/api.php?action=parse&page=Global_Industry_Classification_Standard&prop=wikitext&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "p8-research/1.0"})
    wiki = json.load(urllib.request.urlopen(req, timeout=60))["parse"]["wikitext"]["*"]
    T = parse(wiki)
    assert all(T["sub_code"].str[:6] == T["industry_code"]), "sub-industry codes must nest in their industry"
    by = {norm(r.sub): r for r in T.itertuples()}
    firms = pd.concat([pd.read_csv(os.path.join(PX.ROOT, "data", "raw", "stocks", f))
                       for f in ("sp500_current.csv", "sp400_current.csv")]).drop_duplicates("Symbol")
    out, miss = {}, {}
    for r in firms.itertuples():
        s = getattr(r, "_4")
        x = by.get(norm(s))
        if x is None and s in RETIRED:                          # a sub-industry retired in 2023: its industry stands
            ind = T[T["industry_code"] == RETIRED[s]].iloc[0]
            out[r.Symbol] = {"sub": s, "sub_code": None, "retired_2023": True, "industry": ind.industry,
                             "industry_code": ind.industry_code, "sector": ind.sector}
            continue
        if x is None:
            miss[s] = miss.get(s, 0) + 1
            continue
        out[r.Symbol] = {"sub": x.sub, "sub_code": x.sub_code, "industry": x.industry, "industry_code": x.industry_code,
                         "sector": x.sector}
    json.dump({"source": url, "n_sub": len(T), "n_industry": T["industry_code"].nunique(), "firms": out,
               "unmatched": miss}, open(OUT, "w"), indent=0)
    print(f"GICS table: {len(T)} sub-industries, {T['industry_code'].nunique()} industries, "
          f"{T['sector'].nunique()} sectors; firms matched {len(out)} of {len(firms)}; unmatched names: {miss}")


if __name__ == "__main__":
    main()
