# Amendment 6 branch dry run

Run https://github.com/andreaskoul/test_trading_agent/actions/runs/36928658865, commit 3b2b436, 2026-10-01T21:37:44Z

## Context archive, run 1 (all sources)
```
context fred: {'ok': True, 'fetched': 954} (1 s)
context kalshi: {'ok': True, 'fetched': 646} (4 s)
context gpr: {'ok': True, 'fetched': 27550} (4 s)
context gdelt: {'ok': False, 'fetched': 344, 'note': 'best effort, 4/26 queries: failed ["export_controls/timelinetone: <HTTPError 429: \'Too Many Requests\'>", "sanctions/timelinevol: <HTTPError 429: \'Too Many Requests\'>"]'} (499 s)
context finnhub: {'ok': True, 'fetched': 100} (0 s)
context edgar: {'ok': True, 'fetched': 1567} (151 s)
context archive 2026-10-01: fetched 31161, new 295 {'edgar': 2, 'gdelt': 258, 'kalshi': 35}; sources ok 5/6
real	11m5.073s
```
## Context archive, run 2 (kalshi, gpr, fred, finnhub)
```
context fred: {'ok': True, 'fetched': 954} (1 s)
context kalshi: {'ok': True, 'fetched': 646} (4 s)
context gpr: {'ok': True, 'fetched': 27550} (3 s)
context finnhub: {'ok': True, 'fetched': 100} (0 s)
context archive 2026-10-01: fetched 29250, new 51 {'finnhub': 2, 'kalshi': 49}; sources ok 4/4
```
