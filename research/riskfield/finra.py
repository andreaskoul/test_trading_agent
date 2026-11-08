"""Risk-field round 10: FINRA Reg SHO daily short-sale volume (off-exchange, FINRA trade reporting facilities).

    python research/riskfield/finra.py download   # -> .cache/riskfield/finra_short.parquet (date, ticker, short, total)

Files (free, https://cdn.finra.org/equity/regsho/daily/):
* CNMSshvol<YYYYMMDD>.txt (consolidated NMS) from 2018-08-01;
* before that, the per-facility files FNSQ (FINRA/Nasdaq TRF), FNYX (FINRA/NYSE TRF), FNQC (FINRA/Nasdaq TRF Chicago)
  and FORF (ORF), summed. A missing facility file is absent, not an error; a day with none is reported.

Content contract: header "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market", the file's date equals the
requested date, ShortVolume <= TotalVolume. Only the tickers of this study's universes are kept.
"""
import io
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import panel as PN                                                                    # noqa: E402

OUT = os.path.join(PN.CACHE, "finra_short.parquet")
BASE = "https://cdn.finra.org/equity/regsho/daily/{}shvol{}.txt"
UA = "research fund-bot@users.noreply.github.com"
HEAD = "Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market"


def universe():
    px = pd.read_parquet(os.path.join(PN.QT, "sp500_close.parquet"))
    s400 = pd.read_csv(os.path.join(PN.ROOT, "data", "raw", "stocks", "sp400_current.csv"))
    col = "Symbol" if "Symbol" in s400.columns else s400.columns[0]
    return set(px.columns) | set(s400[col].astype(str))


def one(args):
    fac, d = args
    try:
        req = urllib.request.Request(BASE.format(fac, d.strftime("%Y%m%d")), headers={"User-Agent": UA})
        t = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return (fac, d, None, e.code)
    except Exception as e:                                               # noqa: BLE001 (transport: one retry)
        try:
            t = urllib.request.urlopen(urllib.request.Request(BASE.format(fac, d.strftime("%Y%m%d")), headers={"User-Agent": UA}),
                                       timeout=60).read().decode("utf-8", "replace")
        except Exception:                                                # noqa: BLE001
            return (fac, d, None, type(e).__name__)
    if not t.startswith(HEAD):
        return (fac, d, None, "bad header")
    x = pd.read_csv(io.StringIO(t), sep="|", dtype={"Date": str, "Symbol": str}, usecols=["Date", "Symbol", "ShortVolume", "TotalVolume"])
    x = x[x.Date == d.strftime("%Y%m%d")]                               # drops the trailer line and any wrong date
    return (fac, d, x, None)


def download():
    keep = universe()
    days = pd.bdate_range("2012-01-03", "2025-12-31")
    jobs = [("CNMS", d) for d in days if d >= pd.Timestamp("2018-08-01")] + \
           [(f, d) for d in days if d < pd.Timestamp("2018-08-01") for f in ("FNSQ", "FNYX", "FNQC", "FORF")]
    parts, missing = [], {}
    with ThreadPoolExecutor(8) as ex:
        for fac, d, x, err in ex.map(one, jobs):
            if x is None:
                missing.setdefault(d, []).append(f"{fac}:{err}")
                continue
            x = x[x.Symbol.isin(keep)]
            parts.append(x.assign(fac=fac))
    D = pd.concat(parts, ignore_index=True)
    D = D[D.ShortVolume <= D.TotalVolume]
    D["date"] = pd.to_datetime(D.Date, format="%Y%m%d")
    G = D.groupby(["date", "Symbol"])[["ShortVolume", "TotalVolume"]].sum().reset_index()
    G.columns = ["date", "ticker", "short", "total"]
    G.to_parquet(OUT)
    have = set(G.date)
    none = [d for d in days if d not in have]
    print(f"rows {len(G)}, tickers {G.ticker.nunique()}, days with data {len(have)} of {len(days)} weekdays; "
          f"weekdays with no file (holidays or gaps): {len(none)}; first {G.date.min().date()} last {G.date.max().date()}")
    per = G.groupby(G.date.dt.year).ticker.nunique()
    print("tickers per year:", per.to_dict())


if __name__ == "__main__":
    {"download": download}[sys.argv[1]]()
