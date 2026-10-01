# Amendment 6 branch dry run

Run https://github.com/andreaskoul/test_trading_agent/actions/runs/36926866249, commit 4686df2, 2026-10-01T21:21:50Z

## Context archive, run 1 (all sources)
```
context fred: {'ok': True, 'fetched': 954} (1 s)
context kalshi: {'ok': True, 'fetched': 646} (4 s)
context gpr: {'ok': True, 'fetched': 27550} (4 s)
context gdelt: {'ok': False, 'fetched': 602, 'note': '19 failed: ["tariffs/timelinevol: <HTTPError 429: \'Too Many Requests\'>", "tariffs/timelinetone: <HTTPError 429: \'Too Many Requests\'>", "export_controls/timelinevol: <HTTPError 429: \'Too Many Requests\'>"]'} (488 s)
context finnhub: {'ok': True, 'fetched': 100} (0 s)
context edgar: {'ok': True, 'fetched': 1565} (147 s)
context archive 2026-10-01: fetched 31417, new 31417 {'edgar': 1565, 'finnhub': 100, 'fred': 954, 'gdelt': 602, 'gpr': 27550, 'kalshi': 646}; sources ok 5/6
real	10m48.742s
```
## Context archive, run 2 (kalshi, gpr, fred, finnhub)
```
context fred: {'ok': True, 'fetched': 954} (1 s)
context kalshi: {'ok': True, 'fetched': 646} (4 s)
context gpr: {'ok': True, 'fetched': 27550} (4 s)
context finnhub: {'ok': True, 'fetched': 100} (0 s)
context archive 2026-10-01: fetched 29250, new 70 {'kalshi': 70}; sources ok 4/4
```
