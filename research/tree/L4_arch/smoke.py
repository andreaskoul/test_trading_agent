"""Smoke: 1 epoch per variant on the stage-1 window (data <= 2019), scores only on 3 validation Thursdays; timing."""
import os, time, numpy as np, arch as A
d = A.build("2019-12-31")
S = d["S"]
days = A.thursdays(S, np.where(S.year == 2017)[0])[-3:]       # inside the training data (no 2018-19 scores used)
for v in A.VARIANTS:
    ck = os.path.join(A.CACHE, "smoke", f"ck_{v}.pt")
    if os.path.exists(ck): os.remove(ck)
    t = time.time()
    st, out, info = A.fit(d, v, 0, 2018, days, ck, max_epochs=1)
    print(v, st, out.shape, np.isfinite(out).sum(1), info["hist"], f"{time.time()-t:.0f}s", flush=True)
