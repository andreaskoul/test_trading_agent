"""Smoke 2: resume a 1-epoch checkpoint for one more epoch (concurrency timing when two run at once)."""
import os, sys, time, numpy as np, arch as A
v = sys.argv[1]
d = A.build("2019-12-31")
S = d["S"]
days = A.thursdays(S, np.where(S.year == 2017)[0])[-3:]
ck = os.path.join(A.CACHE, "smoke", f"ck_{v}.pt")
st, out, info = A.fit(d, v, 0, 2018, days, ck, max_epochs=2)
print(v, st, info["hist"], flush=True)
