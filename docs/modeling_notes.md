# Modeling Notes

## Layers

- Layer 0: benchmark models used as permanent reference points.
- Layer 1: realtime data handling to remove revision and release-timing leakage.
- Layer 2: expanded models for horizon-specific recession probabilities.
- Layer 3: event-based evaluation focused on warning usefulness.
- Layer 4: reporting outputs for monitoring and investor interpretation.

## Benchmarks

- `yield_curve_logit` forecasts `within_12m` from the term spread.
- `yield_curve_inversion` applies a binary inversion rule on `10Y - 3M`.
- `hy_credit_logit` estimates `current_recession` from HY spreads.
- `sahm_rule` estimates current recession state from the unemployment gap.

## Expanded models

- Multivariate logistic models are run separately for `current_recession`, `within_3m`, `within_6m`, and `within_12m`.
- Regularized logistic models currently support elastic-net style shrinkage with configurable `alpha` and `l1_ratio`.
- A simple-average ensemble can combine configured benchmark and expanded members by target.
- Tree-based models are wired as an optional `scikit-learn` path and remain disabled by default.
- Forecast horizons are intentionally modeled separately rather than as one pooled target.

## Selection logic in reports

- Snapshot reports choose the best saved model per target using a simple ranking that prefers probability-scored models and then higher AUC / event performance.
- Realtime predictions remain evaluation artifacts and are not mixed into the latest-available investor snapshot.

## Known caveats

- Expanded forecast models can fall back to a dynamic holdout split when the configured early split is infeasible for the full feature set.
- V1 still uses a compact interpretable feature set rather than a wider macro panel.
- Current ensembles and tree-based models are deferred.
