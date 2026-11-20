# Forward S&P 500 paper books (PREREG_quant_transformers.md Amendment 4; never traded)

Records: 4 (first 2026-10-29, last 2026-11-19); prices to 2026-11-20. Book + the dynamic SPY sleeve, broker costs. Returns annualised (% per year) only from 26 weeks; the verdict is on weekly IC at each book's horizon (NW t), reviewed at 52 weeks; a book with IC < 0 and t < -1 at 26 weeks is retired.

| book          |   weeks |   cum_pct | pct_per_yr   | vs_spy_pct_yr   | vs_risk_matched_pct_yr   |   ic_weeks |       ic | ic_t   | status                                                |
|:--------------|--------:|----------:|:-------------|:----------------|:-------------------------|-----------:|---------:|:-------|:------------------------------------------------------|
| fw_master_h5  |       3 |   -9.1628 |              |                 |                          |          3 |   0.1345 |        | running (3 of 26 IC weeks before the stop-rule check) |
| fw_master_h20 |       3 |  -11.4099 |              |                 |                          |          0 | nan      |        | running (0 of 26 IC weeks before the stop-rule check) |
| fw_c2ft_h20   |       3 |  -14.012  |              |                 |                          |          0 | nan      |        | running (0 of 26 IC weeks before the stop-rule check) |
| fw_ensemble   |       3 |  -12.9688 |              |                 |                          |          3 |   0.0302 |        | running (3 of 26 IC weeks before the stop-rule check) |
| fw_ridge_h20  |       3 |  -12.9636 |              |                 |                          |          0 | nan      |        | running (0 of 26 IC weeks before the stop-rule check) |
