"""Quant trials · post-hoc second look at 2022-2025 with the tuning fix (NOT confirmatory).

The Stage-2 read (CONFIRM.md, prereg 8de9271) found the GBRT candidate nearly untrained: MSE early stopping kept
1-30 trees (1 in every seed for 2023). This reruns Q1-Q3 with the selection objective switched to validation rank
IC (ridge_ic, gbrt_ic; trees floor 25), everything else as pre-registered. 2022-25 has already been seen, so these
numbers are a diagnostic of the fix, not evidence.
"""

import json
import os
import re

import confirm as C
import panel as P

spec = json.loads(re.search(r"```json\n(.*?)\n```", open(C.PREREG).read(), re.S).group(1))
cands = []
for c in spec["candidates"]:
    c = dict(c)
    c["model"] = {"ridge": "ridge_ic", "gbrt": "gbrt_ic"}[c["model"]]
    cands.append(c)
C.evaluate(cands, "posthoc", "S2b", os.path.join(P.REPORT, "POSTHOC.md"), os.path.join(P.REPORT, "posthoc.csv"),
           "# Quant trials · post-hoc 2022-2025 rerun with IC-based tuning (NOT confirmatory)\n\n"
           "2022-2025 was already read once (CONFIRM.md). This rerun fixes model selection (validation rank IC "
           "instead of MSE; trees floor 25) and is a diagnostic only.\n\n")
