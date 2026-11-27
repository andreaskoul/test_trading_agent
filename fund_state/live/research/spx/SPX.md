# Forward S&P 500 paper books (PREREG_quant_transformers.md Amendment 4; never traded)

Records: 4 (first 2026-10-29, last 2026-11-19); prices to 2026-11-27. Book + the dynamic SPY sleeve, broker costs. Returns annualised (% per year) only from 26 weeks; the verdict is on weekly IC at each book's horizon (NW t), reviewed at 52 weeks; a book with IC < 0 and t < -1 at 26 weeks is retired.

| book          |   weeks |   cum_pct | pct_per_yr   | vs_spy_pct_yr   | vs_risk_matched_pct_yr   |   ic_weeks |      ic |     ic_t | status                                                |
|:--------------|--------:|----------:|:-------------|:----------------|:-------------------------|-----------:|--------:|---------:|:------------------------------------------------------|
| fw_master_h5  |       3 |   -9.1628 |              |                 |                          |          4 |  0.0181 |   0.2565 | running (4 of 26 IC weeks before the stop-rule check) |
| fw_master_h20 |       3 |  -11.4099 |              |                 |                          |          1 | -0.0924 | nan      | running (1 of 26 IC weeks before the stop-rule check) |
| fw_c2ft_h20   |       3 |  -14.012  |              |                 |                          |          1 | -0.3392 | nan      | running (1 of 26 IC weeks before the stop-rule check) |
| fw_ensemble   |       3 |  -12.9688 |              |                 |                          |          4 | -0.0862 |  -1.09   | running (4 of 26 IC weeks before the stop-rule check) |
| fw_ridge_h20  |       3 |  -12.9636 |              |                 |                          |          1 | -0.0132 | nan      | running (1 of 26 IC weeks before the stop-rule check) |
