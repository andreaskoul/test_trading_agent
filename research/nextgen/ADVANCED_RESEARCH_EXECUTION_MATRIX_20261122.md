# Combined advanced quantitative research — execution matrix (22 November 2026)

Source stack: #188 (research/joint_state) -> #189 (research/joint_geometry) -> #191 (research/coupled_risk). The terminal branch research/coupled-factor-tail-risk-20261122 contains **all three complete suites** in one checkout. Each suite is research-only, with no main, fund, brokerage, caches, or H9 forward change.

## Setup and review

Start with the three README.md and SPEC.md files. All research labels must end on or before 2019-12-31; 2020–26 already inspected windows may not be reused for model choice.

    git fetch origin research/coupled-factor-tail-risk-20261122
    git worktree add --detach ../joint-advanced-lab FETCH_HEAD
    cd ../joint-advanced-lab
    python3.12 -m venv /private/tmp/joint-advanced-venv
    source /private/tmp/joint-advanced-venv/bin/activate
    python -m pip install -r research/nextgen/joint_state/requirements-base.txt
    python -m pip install -r research/nextgen/joint_state/requirements-advanced.txt
    python -m pip install -r research/nextgen/joint_geometry/requirements-manifold.txt
    python -m pytest -q research/nextgen/joint_state/tests research/nextgen/joint_geometry/tests research/nextgen/coupled_risk/tests

Use a compatible isolated PyMC/ArviZ environment for full posterior NUTS and install CVXPY separately if needed. Monitor CPU/RAM and swap; no artificial cap on valuable compute. The advanced dependencies are not needed for standalone coupled_risk.

    export HF="/absolute/path/to/riskfield/.cache/riskfield/hf.npz"
    export DEV="/absolute/path/to/.cache/tree/dev.npz"

    python -m research.nextgen.joint_state.runner check --hf-cache "$HF" --alpha-cache "$DEV"
    python -m research.nextgen.joint_geometry.runner check --hf-cache "$HF" --alpha-cache "$DEV"
    python -m research.nextgen.coupled_risk.runner check --hf-cache "$HF" --alpha-cache "$DEV"

All outputs must be in new folders external to the repository and caches. Never bypass a provenance, cutoff, coverage or label-maturity failure.

## A: established factor risk and Bayesian SV (#188)

    OPENBLAS_NUM_THREADS=3 python -m research.nextgen.joint_state.runner risk \
      --hf-cache "$HF" --models poet heavy realized_garch bayes_sv \
      --factors 3 --lookback 252 --step 42 --draws 700 \
      --out "$HOME/ResearchData/adv_joint/risk_01"

## B: geometry, diffusion regimes, geometric MASTER efficacy (#189)

    OPENBLAS_NUM_THREADS=3 python -m research.nextgen.joint_geometry.runner covariance \
      --hf-cache "$HF" --rank 4 --out "$HOME/ResearchData/adv_joint/geometry_cov_01"

    OPENBLAS_NUM_THREADS=3 python -m research.nextgen.joint_geometry.runner states \
      --hf-cache "$HF" --rank 4 --states 3 --dimension 3 \
      --out "$HOME/ResearchData/adv_joint/geometry_states_01"

    OPENBLAS_NUM_THREADS=3 python -m research.nextgen.joint_geometry.runner alpha \
      --hf-cache "$HF" --alpha-cache "$DEV" --rank 4 \
      --out "$HOME/ResearchData/adv_joint/geometry_alpha_01"

## C: coupled factor volatility and heavy tails (#191)

    OPENBLAS_NUM_THREADS=3 python -m research.nextgen.coupled_risk.runner run \
      --hf-cache "$HF" --alpha-cache "$DEV" \
      --models poet matrix_heavy dcc t_score particle_sv \
      --factors 3 --lookback 252 --particles 1000 --step 21 \
      --out "$HOME/ResearchData/adv_joint/coupled_risk_01"

The t_score filter is Student-t robust and score-inspired, not exact Fisher-scaled GAS. The particle filter couples latent log-variance innovations, but keeps factor-return correlation fixed within a fitting window; DCC measures correlation dynamics separately. Inspect particle ESS and nine fixed model weights; if SMC degenerates, repeat stability checks with more particles (e.g. 2000–5000) before trusting results. Do not tune on previously inspected 2020–26 returns.

## D: filtered state changes and conditional MASTER alpha (#188)

    python -m research.nextgen.joint_state.runner regimes --hf-cache "$HF" \
      --models hmm hsmm bocpd --out "$HOME/ResearchData/adv_joint/regimes_01"

    python -m research.nextgen.joint_state.runner alpha --alpha-cache "$DEV" \
      --models constant kalman state_regression moe bayesian \
      --refit-every 13 --draws 700 --device cpu \
      --out "$HOME/ResearchData/adv_joint/master_alpha_01"

## E: decision-layer robust stochastic MPC (#188 and #189)

    python -m research.nextgen.joint_state.runner optimize \
      --hf-cache "$HF" --alpha-cache "$DEV" --origin 2019-11-01 \
      --forecaster heavy --factors 3 --lookback 252 --scenarios 1000 \
      --horizon 4 --financing segregated \
      --out "$HOME/ResearchData/adv_joint/mpc_01"

    python -m research.nextgen.joint_geometry.runner control \
      --hf-cache "$HF" --alpha-cache "$DEV" --rank 4 \
      --out "$HOME/ResearchData/adv_joint/geometry_mpc_01"

The MPC results are only predictive decision and feasibility diagnostics; no backtested or live performance improvement can be inferred from solver objectives.

## Comparison and promotion criteria

    python -m research.nextgen.joint_state.runner compare \
      --risk-results "$HOME/ResearchData/adv_joint/risk_01" \
      --regime-results "$HOME/ResearchData/adv_joint/regimes_01" \
      --alpha-results "$HOME/ResearchData/adv_joint/master_alpha_01" \
      --out "$HOME/ResearchData/adv_joint/paired_01"

Each research suite has a different forecast target. Cross-suite ranking is permitted ONLY after aligning identical origin dates, identical portfolio weights, realized outcomes, and loss definitions. Risk: matched next-five-session portfolio QLIKE, calibration, tails and crisis years. Alpha: weekly MASTER residual slope MSE/negative log predictive density with completed labels. Regimes: filtered sequential predictive likelihood, not hindsight state accuracy. Policy: strictly matched whole-fund capital and financing, net trading/borrow/cash and cash-excess Sharpe, separately tested. Use year-level breakdown, paired HAC/block bootstrap, train-only model selection and full previous 162+ trial inventory. Never treat 300 names times 300 weeks as independent market-state samples.

Existing HF intraday data are current constituent biased. The optional coupled_risk MASTER portfolio is an unhedged risk *proxy*, not a validated production MASTER fund. A truly accurate historical fund backtest requires independent PIT membership and exact timing of core, stock positions and beta/SPY hedge.

## Status

#188 PR describes 42 passing engineering tests and one optional CVXPY skip.
#189 PR describes 53 passing engineering tests and one optional CVXPY skip.
#191 new extension: 26 locally passed tests, plus a 2-origin engineering end-to-end fixture that completed every risk model without inventing significance. Source Git blob SHAs match the locally tested bytes.
No private local-cache model run has occurred for this extended suite. No net fund improvement is established. Main/production/trades and locked H9 forward records remain unchanged.
