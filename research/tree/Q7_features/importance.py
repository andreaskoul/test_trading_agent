"""Declared diagnostic (b): permutation importance of the 9 added inputs in F1 (seed 0 models, one per validation
year). For each year: IC of the model on that year's Thursdays (y5), then the mean drop when one added input (or all
9 together) is shuffled across names within each row. 3 shuffles each. Writes IMPORTANCE.json."""
import json
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "3")
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import model as M  # noqa: E402

H = M.harness


def ic_rows(p, D, rows):
    return float(np.nanmean(H.weekly_ic(p, D, rows)))


def main():
    D = H.load()
    X = M.features(D, "F")
    n0 = X.shape[2] - len(M.ADDED)
    groups = {k: [n0 + i] for i, k in enumerate(M.ADDED)}
    groups["all_added"] = list(range(n0, X.shape[2]))
    ok = D["elig"] & np.isfinite(D["Z"]).all(2)
    out = {k: [] for k in groups}
    base_by, trees = {}, {}
    rng = np.random.default_rng(0)
    for y in H.VAL_YEARS:
        te, rows = H.train_end(D, y), H.thursdays(D, y)
        Dm = dict(D)
        y5 = D["y5"].copy()
        y5[te + 1:] = np.nan
        Dm["y5"] = y5
        _, mdl, ntree = M.hgb(Dm, te, rows, 0, "F", 5, return_model=True)
        trees[y] = ntree
        Xp = X[rows].copy()

        def pred(Z):
            p = mdl.predict(Z.reshape(-1, Z.shape[2])).reshape(Z.shape[:2]).astype(np.float64)
            p[~ok[rows]] = np.nan
            full = np.full(D["y5"].shape, np.nan)
            full[rows] = p
            return full
        base = ic_rows(pred(Xp), D, rows)
        base_by[y] = base
        for k, cols in groups.items():
            drops = []
            for _ in range(3):
                Z = Xp.copy()
                for i in range(len(rows)):
                    idx = np.where(ok[rows[i]])[0]
                    perm = rng.permutation(idx)
                    for c in cols:
                        Z[i, idx, c] = Xp[i, perm, c]
                drops.append(base - ic_rows(pred(Z), D, rows))
            out[k].append(float(np.mean(drops)))
        print(y, base, ntree, {k: round(v[-1], 4) for k, v in out.items()}, flush=True)
    res = {"note": __doc__, "base_ic_by_year": base_by, "trees_by_year": trees,
           "mean_ic_drop": {k: float(np.mean(v)) for k, v in out.items()},
           "ic_drop_by_year": {k: dict(zip(map(str, H.VAL_YEARS), v)) for k, v in out.items()},
           "years_drop_positive": {k: int(sum(x > 0 for x in v)) for k, v in out.items()}}
    json.dump(res, open(os.path.join(HERE, "IMPORTANCE.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
