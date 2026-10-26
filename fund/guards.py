"""Guardrails for desks that feed documents to an LLM (research desks now; champion desks only through a new protocol).

Written after the R5 incidents of 2026-10-15/16 (CLAUDE.md, "Data and LLM guardrails"):
* 7 of 20 thesis cards were built from the 8-K cover page instead of the EX-99.1 press release, because the exhibit
  was chosen by file name. One failed loudly; six passed as "ok" with cards the document did not support.
* One firm lost 2 of 3 ledger passes to transport errors (a dropped connection, a time-out), and nothing retried them.

Every guard here turns a silent failure into a typed status:
* typed_exhibit  - pick a filing document by its declared SEC type (the -index.htm table), never by file name
* release_check  - the content contract for an earnings press release; a cover page or a stub is an input defect
* grounding      - the share of a card's numbers that appear in its source; a card that invents numbers is rejected
* guarded_llm    - an LLM call that logs every rejected answer and transport error, and gets one repair turn
* quality_gate   - a run-level gate: input defects and failures above a share fail the run, after its records are saved
"""

import json
import re

from common import llm

# ----------------------------------------------------------------------------- inputs: which document, and is it one
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
HREF = re.compile(r'href="([^"]+)"', re.I)


def filing_documents(index_html):
    """Rows of an SEC filing index page (<accession>-index.htm): [{seq, description, name, type, size}]."""
    out = []
    for m in ROW.finditer(index_html):
        cells = CELL.findall(m.group(1))
        if len(cells) < 4:
            continue
        href = HREF.search(cells[2])
        name = href.group(1).rsplit("/", 1)[-1] if href else re.sub(r"<[^>]+>|&nbsp;", " ", cells[2]).split()[0:1]
        name = name if isinstance(name, str) else (name[0] if name else "")
        name = name.split("?")[0]
        if name.startswith("ix?doc="):
            name = name.split("=", 1)[1].rsplit("/", 1)[-1]
        clean = lambda c: re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;", " ", c)).strip()
        out.append({"seq": clean(cells[0]), "description": clean(cells[1]), "name": name, "type": clean(cells[3]),
                    "size": clean(cells[4]) if len(cells) > 4 else ""})
    return out


def typed_exhibit(docs, prefer=("EX-99.1", "EX-99.01", "EX-99")):
    """The earnings-release exhibit by its declared type: EX-99.1 first, then any EX-99.x in filing order.
    Never the primary 8-K. Returns (doc, how) or (None, reason)."""
    if not docs:
        return None, "no filing index"
    for want in prefer:
        hit = [d for d in docs if d["type"].upper() == want and d["name"].lower().endswith((".htm", ".html", ".txt"))]
        if hit:
            return hit[0], f"type {want}"
    ex = [d for d in docs if d["type"].upper().startswith("EX-99") and d["name"].lower().endswith((".htm", ".html", ".txt"))]
    if ex:
        return ex[0], f"type {ex[0]['type']}"
    return None, "no EX-99 exhibit in the filing"


MARKERS = [r"net income", r"(diluted|per) share|\beps\b", r"\brevenues?\b|net sales|total sales|net interest income",
           r"\b(first|second|third|fourth)[- ]quarter\b|\bq[1-4]\b|three months ended", r"operating (income|margin)|pre-tax|income before"]


def release_check(text, min_chars=2000, min_markers=3):
    """Content contract for an earnings press release. Returns None if it holds, else the defect."""
    if len(text) < min_chars:
        return f"too short for a press release ({len(text)} characters)"
    head = text[:2500]
    if re.search(r"FORM 8-K", head) and re.search(r"Item\s*2\.02|Results of Operations and Financial Condition", head, re.I):
        return "8-K cover page, not the press release"
    hits = [m for m in MARKERS if re.search(m, text[:20000], re.I)]
    if len(hits) < min_markers:
        return f"only {len(hits)} of {len(MARKERS)} earnings-release markers"
    return None


# ----------------------------------------------------------------------------- outputs: does the answer rest on the input
NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


def numbers(s):
    """Numeric tokens worth checking: two or more significant digits, years excluded."""
    out = set()
    for x in NUM.findall(str(s or "")):
        v = x.replace(",", "").rstrip(".")
        if len(v.replace(".", "").lstrip("0")) < 2 or re.fullmatch(r"(19|20)\d\d", v):
            continue
        out.add(v)
    return out


def grounding(claims_text, source_text, min_numbers=3, min_share=0.6):
    """Share of the claims' numbers found in the source. Returns (ok, stats). With fewer than `min_numbers` numbers
    the card cannot be checked this way and is accepted (stats say so)."""
    cn, sn = numbers(claims_text), numbers(source_text)
    found = sorted(cn & sn)
    share = len(found) / len(cn) if cn else None
    ok = len(cn) < min_numbers or share >= min_share
    return ok, {"numbers": len(cn), "found": len(found), "share": share, "missing": sorted(cn - sn)[:10]}


# ----------------------------------------------------------------------------- the call
def guarded_llm(system, user, check, temperature=0.0, repair=True):
    """common.llm with a log of every rejected answer, and one repair turn when the last failure was a schema
    rejection. Returns (status, out, meta, err, log); log = {"attempts": [...], "repaired": bool}."""
    attempts = []

    def chk(o):
        e = check(o) if check else None
        if e:
            attempts.append({"kind": "schema", "error": e, "raw": json.dumps(o, ensure_ascii=False)[:1500]})
        return e

    st, out, meta, err = llm(system, user, chk, temperature=temperature)
    if st != "ok" and (not attempts or attempts[-1]["error"] != err):
        attempts.append({"kind": "transport", "error": err})
    repaired = False
    if st != "ok" and repair and attempts and attempts[-1]["kind"] == "schema":
        user2 = (user + "\n\nYOUR PREVIOUS ANSWER WAS REJECTED BY THE VALIDATOR: " + attempts[-1]["error"]
                 + ". Answer again from the same material, as JSON only, in exactly the required format.")
        st, out, meta, err = llm(system, user2, chk, temperature=temperature, tries=2)
        if st != "ok" and (not attempts or attempts[-1]["error"] != err):
            attempts.append({"kind": "transport", "error": err})
        repaired = st == "ok"
    return st, out, meta, err, {"attempts": attempts, "repaired": repaired}


# ----------------------------------------------------------------------------- the run
FAILED = ("card_failed", "card_ungrounded", "ledger_failed", "error")
DEFECT = ("input_defect", "no_release_found")


def quality_gate(statuses, max_bad_share=0.25, min_n=4):
    """Counts by status class and whether the run passes: (input defects + failures) / attempted <= max_bad_share.
    Skips (already reported) are not attempted. Small runs (< min_n attempted) always pass, but are still counted."""
    from collections import Counter
    c = Counter(statuses)
    attempted = sum(v for k, v in c.items() if k != "already_reported")
    bad = sum(v for k, v in c.items() if k in FAILED or k in DEFECT)
    share = bad / attempted if attempted else 0.0
    ok = attempted < min_n or share <= max_bad_share
    return ok, {"counts": dict(c), "attempted": attempted, "bad": bad, "bad_share": round(share, 3), "threshold": max_bad_share}
