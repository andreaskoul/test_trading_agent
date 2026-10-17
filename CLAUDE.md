# Guardrails for work on this repository

A paper-traded fund (`fund/`, Protocol 7, frozen) plus pre-registered research (`reports/research/`). Every rule
below comes from an incident; the incident log is `fund/CHANGELOG.md`. Read this before changing a desk, a job or
a research script.

## Inputs: know exactly what you feed in

1. **Choose documents and data by declared, typed fields, never by name or position.**
   * SEC filings: the `Type` column of `<accession>-index.htm` (`fund/guards.py: typed_exhibit`).
   * APIs: their documented fields.
   * If the typed field is missing, the result is a typed defect, never a guess. (2026-10-15/16: a file-name rule fed
     7 of 20 R5 cards an 8-K cover page.)
2. **Every input has a content contract checked before use**: size, required markers, not boilerplate
   (`guards.release_check` is the pattern). A failure is an `input_defect`: no LLM call, counted as missing.
3. **Coverage is checked against what was expected, not against zero.** (2026-10-08: 299 of 500 prices, caught by
   a person.)
4. **Anything a source can revise later is frozen at first use**, and recorded days are never recomputed.
   (2026-10-14: a late-published T-bill rate moved recorded NAVs.)

## LLM calls: "ok" must mean grounded

5. Research desks call the model through `guards.guarded_llm`. It:
   * validates the JSON schema;
   * logs every rejected raw answer and the serving provider;
   * gives at most one repair turn.

   Champion desks keep `common.llm` until a protocol changes them.
6. **Check outputs against their inputs.**
   * Numbers and quotes must appear in the source (`guards.grounding`).
   * An empty or generic answer from a thin input is a defect, not a result.
7. **Transport is unreliable** (providers are unpinned). Re-run a failed pass once within the time budget. Never
   let one surviving pass stand in for a median.
8. No prices in prompts for research desks. Temperature 0. Fixed schemas.

## Runs and records: fail loudly, after saving

9. **Every batch has a quality gate** (`guards.quality_gate`):
   * save and commit the records first;
   * then exit non-zero, so the runner opens an issue and texts the owner.
10. **Data-saving steps never end in silence.** Push loops fail after their retries (`if [ -z "$pushed" ]; then …
    exit 1`). There is no `|| true` on anything that writes a record.
11. **Dry runs are inspected for content, not status.** Open a sample of outputs next to their source documents.
    (The 2026-10-14 dry run reported `ok` on cover-page cards.)
12. **Every failure class found gets a contract test on a real fixture** in `fund/tests/`. Run them before any
    merge that touches a desk:

    ```
    python fund/tests/test_guards.py
    python fund/tests/test_levels.py
    ```

## Discipline

13. **The traded fund is frozen.** Only operational fixes, each with a CHANGELOG line that answers "could this
    change a decision?". Anything else is a new protocol.
14. **Research records are append-only and pre-registered.**
    * A fix is a dated amendment in the pre-registration, with mechanical criteria, written before outcomes are
      examined.
    * Nothing is back-filled or overwritten.
    * R5 records live on `research-data`, never `fund-data`.
15. **Never merge to `main`:**
    * Wed 21:00 → Thu 17:30 UTC;
    * 15:30–17:30 UTC on Mon, Tue, Wed and Fri;
    * 20:30–02:00 UTC daily.

    Safe windows: weekends, and Mon, Tue, Fri 02:00–15:30. `main` is merged by the owner.
16. **Secrets:** never open, source or print the runner's key file. Run key-needing commands through the
    redacting wrapper (`python3 ~/.claude/hooks/with_secrets.py '<command>'`), and keep those commands free of
    other file edits.
17. **Instruments and hedges** (SPY, sector ETFs, net exposure) are the owner's strategic policy, stated as
    policy. They are not tested or optimised. The S&P 500 is a yardstick, not a design input.
