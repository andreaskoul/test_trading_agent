# §1 parser check: our 10-K sections against eloukas/edgar-corpus (2018 fiscal year, 50 filings)

The final run is `python research/p8/sections.py validate_stored`. It compares our production text (tables kept,
as H5 and H2 use it) with edgar-corpus, matched on CIK and fiscal-period year. Sections are Item 1A and Item 7, and
the reference's trailing next-item heading is removed.

| measure | value |
|---|---|
| sections compared | 91 (50 filings) |
| **registered: alphabetic-word length within 10%** | **86.8%** (§1 requires ≥ 95%) |
| same first 8 words (start boundary) | 97.8% |
| end boundary (last 8 words within the other's last 400) | 95.6% |
| both boundaries agree | 93.4% (85/91) |
| both boundaries agree, excluding the 3 sections where the reference is demonstrably truncated | **96.6% (85/88)** |

**Reference sections demonstrably truncated.** Each was checked by reading both texts.
* CIK 17843 (Carpenter): the reference stops at the in-text cross-reference "See 'Item 7A.'", and the MD&A continues.
* CIK 317540: the reference stops at "… See Item 7A". In ours the sentence continues ("for additional information.
  The Company's only Level 3 asset …").
* CIK 820027: the reference Item 7 has 409 words, against 14,210–18,458 in ours.

The same in-text cross-reference error was fixed in our parser before this check (line-anchored headings).

**Not resolved.**
* CIK 22356 (Commerce Bancshares): the last pages are table titles, which the two conversions render differently.
  It is counted as a disagreement.
* CIK 7084 and 10456: only the first heading line differs. Ends and lengths agree. They are counted as
  disagreements.

**Why the registered length criterion fails although the boundaries agree.** edgar-corpus keeps some table text and
drops some. With tables kept on our side, ours is longer. With tables removed on our side, ours is often shorter
with identical boundaries (BD Item 7: 6,498 vs 8,745 words, same start and end).

**Sequence of runs, all disclosed.**
1. Raw words, matched on filing year: 61% within 10%. This compared the wrong documents. edgar-corpus's `year` is
   the fiscal period (78814_2018 discusses 2018 results, so it is the 10-K filed in 2019).
2. Alphabetic words, filing year: 69%.
3. Tables removed, filing year: 54%, with start agreement 97.5%.
4. Tables removed, fiscal-period year: 72%, with both boundaries agreeing 89%. The misses included filings whose
   headings sit inside HTML tables, which removing tables deletes.
5. Production text, fiscal-period year: the table above.

No H5 or H2 statistic had been computed during any of these runs.
