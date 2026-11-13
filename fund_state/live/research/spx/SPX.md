# Forward S&P 500 paper books (PREREG_quant_transformers.md Amendment 4; never traded)

Records: 3 (first 2026-10-29, last 2026-11-12); prices to 2026-11-13. Book + the dynamic SPY sleeve, broker costs. Returns annualised (% per year) only from 26 weeks; the verdict is on weekly IC at each book's horizon (NW t), reviewed at 52 weeks; a book with IC < 0 and t < -1 at 26 weeks is retired.

| book          |   weeks |   cum_pct | pct_per_yr   | vs_spy_pct_yr   | vs_risk_matched_pct_yr   |   ic_weeks |       ic | ic_t   | status                                                |
|:--------------|--------:|----------:|:-------------|:----------------|:-------------------------|-----------:|---------:|:-------|:------------------------------------------------------|
| fw_master_h5  |       2 |    1.6809 |              |                 |                          |          2 |   0.1534 |        | running (2 of 26 IC weeks before the stop-rule check) |
| fw_master_h20 |       2 |    0.0145 |              |                 |                          |          0 | nan      |        | running (0 of 26 IC weeks before the stop-rule check) |
| fw_c2ft_h20   |       2 |   -2.6099 |              |                 |                          |          0 | nan      |        | running (0 of 26 IC weeks before the stop-rule check) |
| fw_ensemble   |       2 |   -2.0196 |              |                 |                          |          2 |   0.0846 |        | running (2 of 26 IC weeks before the stop-rule check) |
| fw_ridge_h20  |       2 |   -0.8805 |              |                 |                          |          0 | nan      |        | running (0 of 26 IC weeks before the stop-rule check) |
