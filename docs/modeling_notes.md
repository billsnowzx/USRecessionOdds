# Modeling Notes

## Layers

- Layer 0: benchmark models used as permanent reference points
- Layer 1: realtime data handling to reduce revision and release-timing leakage
- Layer 2: expanded models for horizon-specific recession probabilities
- Layer 3: event-based evaluation focused on warning usefulness
- Layer 4: investor-facing reporting with governed snapshot selection

## Benchmarks

- `yield_curve_logit` forecasts `within_12m` from the term spread
- `yield_curve_inversion` applies a binary inversion rule on `10Y - 3M`
- `hy_credit_logit` estimates `current_recession` from HY spreads
- `sahm_rule` estimates current recession state from the unemployment gap

## Expanded models

- Separate models are fit for `current_recession`, `within_3m`, `within_6m`, and `within_12m`
- Multivariate and regularized logistic models use the compact configured feature set
- Tree models are optional and disabled by default
- Ensembles average eligible calibrated member probabilities by target
- Forecast horizons are modeled separately rather than pooled

## Calibration and training policy

- Expanded probability models use deterministic Platt-style calibration
- Calibration uses a trailing validation slice from the training window when enough history exists
- The saved prediction files retain `raw_score`, `calibrated_score`, and the investor-facing `score`
- Expanded models are skipped when the configured fixed split does not leave enough history or class variation
- Dynamic holdout fallback is no longer the default investor path

## Snapshot selection logic

- Reporting builds separate `latest_available` and `realtime` snapshots
- Expanded models are eligible for auto-selection only if they pass configured quality gates
- Current gates use AUC, episode recall, ECE for probability models, and target-specific false-alarm streak caps
- If no expanded model passes for a target, the snapshot falls back to the best benchmark and records the reason

## Current caveats

- The feature set is still compact and intentionally interpretable
- Some expanded models remain too weak or too unstable to pass the snapshot gates consistently
- Realtime and latest-available views can diverge materially, especially when macro release lags bite
- Tree models are still an optional experimental path, not a default investor-facing model family
