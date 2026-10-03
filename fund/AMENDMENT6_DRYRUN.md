# Amendment 6 branch tests

Run https://github.com/andreaskoul/test_trading_agent/actions/runs/37109300384, commit 9b8e07b, 2026-10-03T08:22:20Z

## Mock: champion decisions, main vs branch; Amendment 6 desks in mock
```
screen.json: DIFFERENT
  screen cells differing: 5242 of 11500 ; columns: {'mom12_1': 498, 'lowvol': 493, 'high52': 500, 'ridge_bp': 500, 'beta60': 8, 'beta252w': 500, 'beta_hedge': 500, 'ret_12_1_pct': 186, 'pct_below_52w_high': 49, 'vol60_ann_pct': 8, 'news_7d': 500, 'attention_z': 500, 'attention_shock': 500, 'latest_headlines': 500} ; tickers: ['A', 'AAPL', 'ABBV', 'ABNB', 'ABT', 'ACGL', 'ACN', 'ADBE', 'ADI', 'ADM', 'ADP', 'ADSK']
ideation.json: IDENTICAL
research.json: IDENTICAL
analysts.json: IDENTICAL
redteam.json: IDENTICAL
book.json: DIFFERENT
fx.json: IDENTICAL
book.json, branch pm_risk on main's inputs vs main: IDENTICAL
shadow ok
macro_desk ok
neighbours ok
shadow_info ok
c2_selfconsistency {'FICO': 0.1, 'MRNA': 0.1, 'PCG': 0.1, 'CHTR': 0.1, 'AXON': 0.1, 'TTD': 0.1, 'CRM': 0.05, 'NFLX': 0.05, 'INTC': -0.09, 'MPWR': -0.09, 'AMD': 
c3_textonly {} ['no views: flat']
c8_informed {'FICO': 0.05, 'MRNA': 0.05, 'PCG': 0.05, 'CHTR': 0.05, 'AXON': 0.05, 'TTD': 0.05, 'CRM': 0.025, 'NFLX': 0.025, 'INTC': -0.05, 'MPWR': -0.05, 'AMD':
c9_ranker {'FICO': 0.05, 'MRNA': 0.05, 'PCG': 0.05, 'CHTR': 0.05, 'AXON': 0.05, 'TTD': 0.05, 'CRM': 0.025, 'NFLX': 0.025, 'INTC': -0.05, 'MPWR': -0.05, 'AMD': -
score ok
```
## Real-call test (dry run, live week 2026-09-30)

<details><summary>log tail</summary>

```
    response.raise_for_status()
  File "/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/site-packages/httpx2/_models.py", line 827, in raise_for_status
    raise HTTPStatusError(message, request=request, response=self)
httpx2.HTTPStatusError: Client error '401 Unauthorized' for url 'https://huggingface.co/api/whoami-v2'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/site-packages/huggingface_hub/hf_api.py", line 2239, in _inner_whoami
    hf_raise_for_status(r)
  File "/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/site-packages/huggingface_hub/utils/_http.py", line 976, in hf_raise_for_status
    raise _format(HfHubHTTPError, str(e), response) from e
huggingface_hub.errors.HfHubHTTPError: Client error '401 Unauthorized' for url 'https://huggingface.co/api/whoami-v2' (Request ID: Root=1-6ac0bb3b-064c42670985159369fed100;1dde6923-5905-4503-8934-6525b57edd9a)
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401

Invalid username or password.

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/home/runner/work/test_trading_agent/test_trading_agent/fund/neighbours.py", line 51, in <module>
    repo = f"{api.whoami()['name']}/fund-news-archive"
              ^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/site-packages/huggingface_hub/utils/_validators.py", line 89, in _inner_fn
    return fn(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/site-packages/huggingface_hub/hf_api.py", line 2226, in whoami
    output = self._inner_whoami(token=token)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/hostedtoolcache/Python/3.11.16/x64/lib/python3.11/site-packages/huggingface_hub/hf_api.py", line 2255, in _inner_whoami
    raise HfHubHTTPError(error_message, response=e.response) from e
huggingface_hub.errors.HfHubHTTPError: Invalid user token. The token from HF_TOKEN environment variable is invalid. Note that HF_TOKEN takes precedence over `hf auth login`.

real	0m30.337s
user	0m0.928s
sys	0m0.630s
REAL TEST FAILED
context archive unavailable (HfHubHTTPError('Invalid user token. The token from HF_TOKEN environment variable is invalid. Note that HF_TOKEN takes precedence over `hf auth login`.')); working without it
review context 2026-10-03: 19 held names; releases []; GPR spikes []; 0 names with new 8-Ks
```
</details>
