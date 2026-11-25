# EV-01: prospective evidence for incremental alpha — tested before decision

19 November 2026. **Research-only; no historical data, trading, NAV or Sharpe results were used.**

## Why this study now (no restart)

The existing research branch has merged the NAV measurement, PIT contract, inference, and cost-aware optimiser primitives. The six other open research drafts (#176–#181) extend accounting, financing, overfitting, calibration and fund gross. Draft #182 MULTI-01 already implements a source registry and factor-aware fund-level optimizer, stacked on #181. It requires independent evidence references for approving an additional alpha, but a reference string does not prove a net economic advantage.

MULTI-01's already-run synthetic trial found a *spurious misapproved alpha* reduced true expected utility despite an optimistic predicted improvement. EV-01 tests a standalone evidence-review procedure without changing MULTI-01 or any other workstream.

## Explicit mathematical hypothesis

For a forward, mature, fully settled, matched-risk shadow candidate and incumbent control, define fractional NAV incremental return g_t = r_candidate,t - r_control,t. Freeze an economic hurdle h>=0 and a clipping scale B>0 before observing any evaluation outcome. Define X_t = clip((g_t-h)/B,-1,1).

The **actual null** is E[X_t | F_{t-1}] <= 0 at every sequential outcome disclosure. It is **not** the null of equal raw Sharpe, zero average raw return, or zero unconditional alpha. Under this conditional and bounded null, for every fixed lambda>0,

    E_t(lambda) = exp(lambda * sum_{i<=t} X_i - t*lambda^2/2)

is a nonnegative test supermartingale by Hoeffding's lemma. A precommitted equal mixture of those processes is also a test supermartingale. Ville's inequality and Bonferroni across m preregistered candidate trials justify a family-wise probability bound alpha when testing ever crossing E_t >= m/alpha. For m=7 and alpha=.05 the log threshold is log(140).

The exact prerequisite **conditional null** is strong in financial settings with regime persistence and adaptive model search. Zero *unconditional* expected gain does not imply it. Clipping also changes the tested estimand. The method therefore provides supplementary evidence, not a validated Sharpe improvement and not a complete alpha admission policy.

The implementation separately reports historical ever-crossing and **current** evidence sufficiency. If an alpha once crossed but later log evidence drops below the threshold, current eligibility lapses. Nonetheless such a flag cannot establish current performance: a hidden regime may persist and invalidate the null. The code *always* returns automatically_approved_to_trade = false.

## Scientific data contract

Inputs require an explicitly registered prospective trial and family, registration reference and timestamp, unique and sequential observations, decision time before end before availability, completely available outcomes as of review time, nonoverlapping comparison windows, and references to externally reviewed NAV ledgers and matched-risk checks. Invalid/missing metadata fails closed. **Nonempty reference strings are NOT cryptographic or independent proof of correctness**; full audit is external. The fixed prospective family size must include all genuinely tested hypotheses rather than only winners.

## Experiments performed in this session

Initial locked simulation parameters: 1,200 independent Monte Carlo runs *per scenario*; 156 weekly observations (3 years), seven contemporaneously 80%-correlated candidate noises, weekly innovation sigma=.006 NAV, fixed h=.0005 NAV, clip B=.01 NAV, min 26 periods, mixture lambdas=(.025,.05,.1,.2,.4,.8), family alpha=.05, seed 20261119. Synthetic true incremental gains in the alternative are .001 (weak) or .004 (strong) weekly NAV. We evaluated all-null, one weak, one strong, and a strong-then-broken signal.

**Exploratory modifications after inspecting the initial output:** an early version retained an ever-crossed candidate as forever review-eligible. That was corrected to require *current* threshold support. Added the predictable-heteroskedastic conditional null, persistent +/- latent-regime unconditional-null counterexample, and zero-hurdle boundary check. These are explicitly responsive falsifications, NOT new untouched confirmatory findings.

| Scenario | Current-review rate (1200 replications) | Ever-crossed | H0 conditional validity |
| --- | ---: | ---: | --- |
| Seven iid conditionally-null alphas | 0.0% | 0.0% | yes |
| Seven predictably-heteroskedastic conditionally-null alphas | 0.0% | 0.0% | yes |
| One weak .10%/week alpha | 0.0% | 0.0% | alternative |
| One strong .40%/week alpha | 64.83% | 69.92% | alternative |
| Strong then breaks at halfway | 0.0% | 6.67% | alternative |
| Random persistent +/-.40% weekly latent state, unconditional mean ZERO | **33.33%** | 36.42% | **NO**, conditional null invalid |

With zero hurdle, the persistent hidden-regime current review rate was **48.08%**. These numbers are hypothetical Monte Carlo probabilities, not live performance. The last scenario is a demonstration of **assumption failure**: no contradiction of the supermartingale theorem. The zero rates from 1,200 samples also do not prove the false-review probability is actually zero. The strong simulated +.4% NAV *weekly* effect is very large for an incremental liquid equity sleeve; a weak .1% alpha cannot be reliably detected under these settings even after 156 weeks. This indicates severe power challenges.

## Tests and implementation evidence

- **25 new tests pass**: exact independent mixture identity, optional stopping/current-versus-ever and regime-break expiry, multiplicity, preregistration, chronology/availability, invalid cash returns, source audit references, nulls, adversarial outlier clipping, weak/strong synthetic power.
- **94% statement coverage** across this module's two source files. Coverage measured on the separate module only.
- With the four already-merged nextgen components: **62 passed, 8 subtests**.
- Full local cross-workstream compatibility INCLUDING still-unmerged PRs #176–#182: **244 passed, 32 subtests**. These PRs were **not merged**, and the test was performed in an isolated local reconstruction, **not GitHub Actions CI**.
- An import collision due to a generic test_core filename was found during the combined test run and resolved with the unique test_alpha_evidence.py filename.
- Exact three Python Git blob hashes were checked against the executed local source.
- Reproduce from repository root: python -m pytest -q research/nextgen/alpha_evidence, and python -m research.nextgen.alpha_evidence.simulate.

## Decision and next stage

**Accept as an isolated supplementary, human-reviewed research monitor; reject automatic alpha admission and any claim that it proves mean/Sharpe improvement.** This decision followed adversarial tests, including the high false-review rate under the zero-unconditional-mean persistent regime.

Next steps: obtain genuinely new PIT OOF predictions, matched-risk shadow portfolio outcomes, independently reconciled broker financing and borrow costs, and an immutable preregistered trial family; independently assess conditional-null plausibility across regimes. Do not repurpose 2013–2026 historical results as an untouched holdout. Do not trade or change the 200-day core, fund gross policy, fund code or broker execution.

## Academic and practitioner context

- Ramdas, Grünwald, Vovk, Shafer, Game-Theoretic Statistics and Safe Anytime-Valid Inference, https://arxiv.org/abs/2210.01948.
- Waudby-Smith and Ramdas, Estimating means of bounded random variables by betting, JRSS B, https://doi.org/10.1093/jrsssb/qkad009.
- Gârleanu and Pedersen, Dynamic Trading with Predictable Returns and Transaction Costs, Journal of Finance, https://doi.org/10.1111/jofi.12080.
- AQR practitioner work on signal decay and execution cost, https://www.aqr.com/insights/research/journal-article/dynamic-trading-with-predictable-returns-and-transactions-costs.
- Quantitative Finance Stack Exchange, Combining alphas for mean variance optimizer, https://quant.stackexchange.com/questions/79899/combining-alphas-for-mean-variance-optimizer. Discussion is not empirical validation.
