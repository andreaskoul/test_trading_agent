"""Section extraction from 10-K / 10-Q plain text (research/p8/text.py) for H5 and H2.

    python research/p8/sections.py validate   # §1 check: 50 overlap 10-Ks vs eloukas/edgar-corpus (>= 95% within 10%)

10-K: Item 1 (Business), Item 1A (Risk Factors), Item 7 (MD&A). 10-Q: Part I Item 2 (MD&A).
A section starts at its item heading and ends at the next item's heading. A table of contents repeats the
headings, so among all start matches the one giving the longest section (to the first end heading after it) is
taken (the usual rule; e.g. Loughran-McDonald's parsing notes). Content contract (CLAUDE.md rule 2): a section is
kept only with >= 250 words and, for MD&A (10-K Item 7, 10-Q Item 2), without "incorporated (herein) by
reference" in its first 1,000 characters (MD&A placed in an exhibit); otherwise it is an input defect, counted
missing. 10-Q fallback: without an "Item 2 ... Management's Discussion" heading, the MD&A runs from a "Management's
Discussion and Analysis" or "Financial Review" heading to Item 3, Item 4 or Part II.
"""
import gzip
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import edgar as ED                                               # noqa: E402
import pandas as pd                                              # noqa: E402
import prices as PX                                              # noqa: E402

SEP = r"[\s\.\:\-–—]*"
H = {
    "1": rf"item{SEP}1{SEP}(?!a\b)(?:\(?\w?\)?{SEP})?business",
    "1A": rf"item{SEP}1a{SEP}risk\s+factors",
    "1B": rf"item{SEP}1b{SEP}unresolved",
    "1C": rf"item{SEP}1c{SEP}cybersecurity",
    "2K": rf"item{SEP}2{SEP}(?:description\s+of\s+)?propert",
    "7": rf"item{SEP}7{SEP}management['’`s\s]*discussion",
    "7A": rf"item{SEP}7a{SEP}quantitative",
    "8": rf"item{SEP}8{SEP}(?:consolidated\s+)?financial\s+statements",
    "Q2": rf"item{SEP}2{SEP}management['’`s\s]*discussion",
    "Q3": rf"item{SEP}3{SEP}quantitative",
    "Q4": rf"item{SEP}4{SEP}(?:controls|mine)",
    # 10-Q fallback (Abbott-style filings title the MD&A without an item number)
    "QMDA": r"(?:management['’`s\s]*discussion\s+and\s+analysis|\n\s*financial\s+review\s*\n)",
    "QP2": r"part\s*ii\b[\s\.\:\-–—]*other\s+information",
}
# a heading starts a line: in-text cross-references ("... contained in Item 8. Financial Statements and
# Supplementary Data") must not end a section (they cut BD's and Cintas's MD&A to a few lines before this rule)
LINE = r"(?:^|\n)[ \t]*"
H_FREE = dict(H)                                          # unanchored: headings some filings put mid-line
H = {k: (v if k == "QMDA" else LINE + v) for k, v in H.items()}
SPEC = {"10-K": {"1": ("1", ["1A", "1B", "1C", "2K"]), "1A": ("1A", ["1B", "1C", "2K"]), "7": ("7", ["7A", "8"])},
        "10-Q": {"Q2": ("Q2", ["Q3", "Q4"])}}


def extract(text, form):
    """Line-anchored headings first; a section that fails is retried with unanchored headings."""
    a = _extract(text, form, H)
    if any(v is None for v in a.values()):
        b = _extract(text, form, H_FREE)
        a = {k: (v if v is not None else b[k]) for k, v in a.items()}
    return a


def _extract(text, form, H):
    low = text.lower()
    out = {}
    for name, (start, ends) in SPEC[form].items():
        best = ""
        for m in re.finditer(H[start], low):
            e = min((x.start() for k in ends for x in re.finditer(H[k], low[m.end():])), default=None)
            if e is None:
                continue
            seg = text[m.start(): m.end() + e]
            if len(seg) > len(best):
                best = seg
        if not best and name == "Q2":                         # fallback: MD&A heading without "Item 2"
            for m in re.finditer(H["QMDA"], low):
                e = min((x.start() for k in ("Q3", "Q4", "QP2") for x in re.finditer(H[k], low[m.end():])), default=None)
                if e is not None and len(text[m.start(): m.end() + e]) > len(best):
                    best = text[m.start(): m.end() + e]
        words = len(best.split())
        # MD&A moved to an exhibit (annual report) leaves only a cross-reference: an input defect for MD&A only
        exhibit = name in ("7", "Q2") and re.search(r"incorporated\s+(herein\s+)?by\s+reference", best[:1000], re.I)
        out[name] = best if words >= 250 and not exhibit else None
    return out


def load(cik, accession):
    p = os.path.join(ED.CACHE, "text", str(cik), accession + ".txt.gz")
    if not os.path.exists(p):
        return None
    with gzip.open(p, "rt") as h:
        return h.read()


def _ref_trim(b):
    """edgar-corpus keeps the next item's heading at the end of a section ("... Item 7a."): drop it."""
    return re.sub(r"(?is)\s*item\s*\d+[a-z]?\s*[\.\:]?\s*[^\n]{0,120}$", "", b.strip()) if re.search(
        r"(?is)item\s*\d+[a-z]?\s*[\.\:]?\s*[^\n]{0,120}$", b.strip()[-140:]) else b


def validate_html(year=2018, n=50, stored=False):
    """edgar-corpus's `year` is the fiscal period's year (78814_2018 discusses 2018 results: the 10-K filed in 2019),
    so filings are matched on the period, not the filing date.
    §1 parser check with like-for-like text: the 50 validation filings re-fetched as HTML and converted WITHOUT
    tables (edgar-corpus drops tables), the reference's trailing next-item heading removed; lengths in alphabetic
    words; boundaries by the first and last 8 alphabetic words."""
    from huggingface_hub import hf_hub_download
    import text as TX
    f = hf_hub_download("eloukas/edgar-corpus", f"{year}/test.jsonl", repo_type="dataset")
    ref = {int(json.loads(l)["cik"]): json.loads(l) for l in open(f)}
    F = [x for x in TX.filings() if x["form"] == "10-K" and (x["period"] or "")[:4] == str(year) and x["cik"] in ref]
    alpha = lambda s: re.findall(r"[a-z]{3,}", s.lower())
    rows, firms = [], set()
    for x in F:
        if len(firms) >= n:
            break
        if stored:                                         # the production text (tables kept), as H5 and H2 use it
            t = load(x["cik"], x["accession"])
            if t is None:
                continue
            s = extract(t, "10-K")
        else:
            b = TX.get(f"https://www.sec.gov/Archives/edgar/data/{x['cik']}/{x['accession'].replace('-', '')}/{x['doc']}")
            if b is None:
                continue
            s = extract(TX.to_text(b, tables=False), "10-K")
        r = ref[x["cik"]]
        added = False
        for ours, theirs in (("1A", "section_1A"), ("7", "section_7")):
            a, bb = s.get(ours), _ref_trim(r.get(theirs) or "")
            wa, wb = alpha(a or ""), alpha(bb)
            if a and len(wb) >= 250:
                # end agreement robust to page footers ("45 Table of Contents"): each side's last 8 alphabetic words
                # occur within the other's last 400 words
                tail = lambda w: " ".join(w[-8:])
                end_ok = tail(wb) in " ".join(wa[-400:]) or tail(wa) in " ".join(wb[-400:])
                rows.append({"cik": x["cik"], "section": ours, "ours": len(wa), "ref": len(wb),
                             "start_same": wa[:8] == wb[:8], "end_same": wa[-8:] == wb[-8:], "end_ok": end_ok})
                added = True
        if added:
            firms.add(x["cik"])
    D = pd.DataFrame(rows)
    D["within10"] = (D["ours"] - D["ref"]).abs() / D["ref"] <= 0.10
    out = [f"edgar-corpus check ({'production text, tables kept' if stored else 'tables removed on both sides'}), {year} 10-Ks: {len(D)} sections from {D['cik'].nunique()} filings",
           f"  alphabetic-word length within 10%: {D['within10'].mean():.1%} (§1 requires >= 95%)",
           f"  same first 8 words: {D['start_same'].mean():.1%}; same last 8 words: {D['end_same'].mean():.1%}; "
           f"end agrees (footer-robust): {D['end_ok'].mean():.1%}",
           f"  both boundaries agree: {(D['start_same'] & D['end_ok']).mean():.1%}"]
    print("\n".join(out))
    print(D[~(D["start_same"] & D["end_ok"])].to_string())
    D.to_csv(os.path.join(PX.OUT, "sections_validation.csv"), index=False)
    open(os.path.join(PX.OUT, "sections_validation.md"), "w").write("\n".join(out) + "\n")
    return D


def validate(year=2018, n=50):
    """§1 check against eloukas/edgar-corpus, same CIK and filing year, sections 1A and 7.

    Disclosure: the first run (2026-10-27) compared raw word counts and found 19/31 sections within 10%. Its section
    boundaries were identical to the reference's (start and end text checked on CIK 22356 and 60519); the gap was
    numeric table tokens, which edgar-corpus strips (6,166 vs 1,608 numeric tokens in one filing). The check is
    therefore made on alphabetic words (>= 3 letters, the unit H5 uses), plus a direct boundary check: the first and
    last 8 alphabetic words of the section must equal the reference's."""
    from huggingface_hub import hf_hub_download
    import text as TX
    f = hf_hub_download("eloukas/edgar-corpus", f"{year}/test.jsonl", repo_type="dataset")
    ref = {}
    for line in open(f):
        x = json.loads(line)
        ref[int(x["cik"])] = x
    F = [x for x in TX.filings() if x["form"] == "10-K" and (x["period"] or "")[:4] == str(year) and x["cik"] in ref]
    alpha = lambda s: re.findall(r"[a-z]{3,}", s.lower())
    rows = []
    for x in F:
        t = load(x["cik"], x["accession"])
        if t is None:
            continue
        s = extract(t, "10-K")
        r = ref[x["cik"]]
        for ours, theirs in (("1A", "section_1A"), ("7", "section_7")):
            a, b = s.get(ours), r.get(theirs) or ""
            wa, wb = alpha(a or ""), alpha(b)
            if a and len(wb) >= 250:
                rows.append({"cik": x["cik"], "section": ours, "ours": len(wa), "ref": len(wb),
                             "raw_ours": len(a.split()), "raw_ref": len(b.split()),
                             "start_same": wa[:8] == wb[:8], "end_same": wa[-8:] == wb[-8:]})
        if len({z["cik"] for z in rows}) >= n:
            break
    D = pd.DataFrame(rows)
    D["within10"] = (D["ours"] - D["ref"]).abs() / D["ref"] <= 0.10
    D["raw_within10"] = (D["raw_ours"] - D["raw_ref"]).abs() / D["raw_ref"] <= 0.10
    out = [f"edgar-corpus check, {year} 10-Ks: {len(D)} sections from {D['cik'].nunique()} filings",
           f"  alphabetic-word length within 10%: {D['within10'].mean():.1%} (§1 requires >= 95%)",
           f"  same first 8 words: {D['start_same'].mean():.1%}; same last 8 words: {D['end_same'].mean():.1%}",
           f"  (raw word count within 10%, tables included: {D['raw_within10'].mean():.1%})"]
    print("\n".join(out))
    print(D[~D["within10"]].to_string())
    D.to_csv(os.path.join(PX.OUT, "sections_validation.csv"), index=False)
    open(os.path.join(PX.OUT, "sections_validation.md"), "w").write("\n".join(out) + "\n")
    return D


if __name__ == "__main__":
    {"validate": validate, "validate_html": validate_html,
     "validate_stored": lambda: validate_html(stored=True)}[sys.argv[1]]()
