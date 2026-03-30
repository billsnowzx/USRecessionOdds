# USRecessionOdds — Implementation Spec

## Objective

Upgrade `USRecessionOdds` from a baseline replication project into a robust, pseudo-real-time U.S. recession probability platform suitable for research, monitoring, and investor decision support.

The upgraded system must:

1. Preserve the current baseline models and existing CLI/report pipeline.
2. Add pseudo-real-time data support using vintage-aware macro data and release-lag logic.
3. Support separate nowcast and forward recession forecast models.
4. Expand the model stack beyond single-indicator baselines.
5. Improve evaluation with event-based recession warning metrics.
6. Produce clearer investor-facing outputs.
7. Strengthen software engineering, testing, and maintainability.

---

## Product Requirements

### Core capabilities
The final system should be able to:

- Build a monthly recession-risk panel using only data available as of each forecast date.
- Estimate and compare multiple recession models.
- Generate:
  - `P(recession now)`
  - `P(recession within 3 months)`
  - `P(recession within 6 months)`
  - `P(recession within 12 months)`
- Run expanding-window pseudo-real-time backtests.
- Archive all historical predictions by as-of date.
- Evaluate models using both standard classification metrics and recession-event metrics.
- Generate current-state and historical reports for research and investor use.

### Non-goals
This phase should **not** prioritize:
- global recession models
- high-frequency intraday forecasting
- full web app deployment
- live trading integration

---

## Design Principles

1. **Backward compatible**
   Keep the current baseline workflows working unless new modes are explicitly selected.

2. **Config driven**
   Extend existing YAML-based configuration instead of hardcoding model/data choices.

3. **No look-ahead leakage**
   Every backtest must use only information available at the forecast date.

4. **Modular architecture**
   Data, models, backtests, metrics, and reporting should remain cleanly separated.

5. **Benchmark first**
   Existing baseline models remain the benchmark layer and should never be removed.

6. **Research-grade reproducibility**
   Outputs should be deterministic, archived, and testable.

---

## Existing Benchmark Layer

Retain the current benchmark models as Layer 0:

1. Yield curve logit
2. 10Y–3M inversion rule
3. High-yield spread logit
4. Sahm-style unemployment rule

These models should remain runnable through the existing CLI and continue to appear in reports as the baseline comparison set.

---

## Target Architecture

### Layer 0 — Benchmark models
Purpose: preserve current replication baseline.

### Layer 1 — Real-time data layer
Purpose: ensure historical tests are realistic and free from revision bias.

### Layer 2 — Expanded model layer
Purpose: improve recession probability estimation using richer inputs.

### Layer 3 — Evaluation layer
Purpose: judge models in ways that reflect actual recession warning usefulness.

### Layer 4 — Reporting layer
Purpose: produce outputs that are useful for research and investment interpretation.

---

# Phase 1 — Pseudo-real-time data system

## Goal
Eliminate revision and release-timing bias from backtests.

## Deliverables

### 1. Vintage-aware data support
Add support for vintage-aware macro data where applicable.

New module:
```text
src/recession_risk/data/vintages.py
```

Responsibilities:

- fetch vintage data where available
- cache vintage observations locally
- expose an as-of query interface

Suggested interface:

```python
def get_series_asof(series_id: str, as_of_date: str) -> pd.Series:
    ...
```

---

### 2. Release lag logic

Add release calendar logic so the system knows when each macro observation became usable.

New module:

```text
src/recession_risk/data/release_calendar.py
```

Responsibilities:

- define release lag assumptions by series
- determine whether a given observation is observable as of a forecast date

Suggested interface:

```python
def get_available_date(series_id: str, observation_date: str) -> str:
    ...
```

---

### 3. Real-time monthly panel constructor

Add a panel builder that creates features using only information available as of each forecast date.

New module:

```text
src/recession_risk/data/realtime_panel.py
```

Responsibilities:

- construct monthly feature matrix with no look-ahead leakage
- track forecast date, source observation date, and vintage date used
- align market and macro series consistently

Output should include metadata columns such as:

```text
forecast_date
feature_date_used
series_vintage_date
```

---

### 4. Real-time backtest runner

Add a month-by-month expanding-window pseudo-real-time runner.

New module:

```text
src/recession_risk/backtest/realtime_runner.py
```

Responsibilities:

- iterate across forecast dates
- fit only on information available through each forecast date
- generate archived probability history for each model and horizon

Primary output:

```text
outputs/backtests/realtime_predictions.csv
```

---

### 5. Config support for data mode

Add a `data_mode` switch.

Example:

```yaml
data_mode: realtime   # or latest_available

realtime:
  use_vintages: true
  release_lags: true
  estimation_window: expanding
```

---

## Acceptance criteria for Phase 1

- Existing non-realtime mode continues to work.
- Realtime mode can be toggled via config or CLI.
- Backtests in realtime mode do not use future revisions or unreleased data.
- Forecast histories are saved by as-of date.

---

# Phase 2 — Expanded model layer

## Goal

Move from single-indicator baselines to a broader recession-forecast framework.

## Deliverables

### 1. Multivariate logistic regression

New module:

```text
src/recession_risk/models/logit_multivariate.py
```

Requirements:

- support separate models for:
  - `within_3m`
  - `within_6m`
  - `within_12m`
  - `current_recession`
- expose standard fit/predict_proba interface
- support configurable feature lists

---

### 2. Regularized logistic regression

New module:

```text
src/recession_risk/models/regularized_logit.py
```

Requirements:

- support lasso and elastic-net variants
- select regularization via config
- output coefficients and selected features where applicable

---

### 3. Optional tree-based models

New module:

```text
src/recession_risk/models/tree_models.py
```

Requirements:

- support gradient boosting classifier
- keep dependency footprint reasonable
- output feature importance summary

---

### 4. Ensemble model

New module:

```text
src/recession_risk/models/ensemble.py
```

Requirements:

- combine selected benchmark and expanded models
- begin with simple average of calibrated probabilities
- optionally support stacked meta-model later

---

## Suggested initial feature set

Use a compact and interpretable first-pass set:

- term spread
- policy rate / short rate
- high-yield spread
- unemployment gap
- payroll growth
- ISM new orders
- LEI growth
- equity drawdown
- financial conditions index if available

Do not over-expand the feature count in the first implementation.

---

## Model design requirements

- Forecast and nowcast models must remain separate.
- Each horizon should have its own model specification.
- All models must conform to a common interface:

```python
fit(X, y)
predict_proba(X)
get_model_summary()
```

---

## Acceptance criteria for Phase 2

- Existing baselines still run unchanged.
- New models are selectable from config.
- Separate probabilities can be produced for different horizons.
- Reports compare benchmark vs expanded model performance.

---

# Phase 3 — Event-based evaluation

## Goal

Evaluate models based on recession-warning usefulness, not only generic binary metrics.

## Deliverables

### 1. Event metrics module

New module:

```text
src/recession_risk/backtest/event_metrics.py
```

Metrics to add:

- average warning lead time before recession start
- median lead time
- fraction of recessions flagged at least 3 months ahead
- fraction of recessions flagged at least 6 months ahead
- false positive months during expansions
- continuous false-alarm streak length
- episode recall
- per-recession scorecards

---

### 2. Threshold analysis

New module:

```text
src/recession_risk/backtest/thresholds.py
```

Responsibilities:

- compute performance across multiple probability thresholds
- produce threshold comparison tables
- allow threshold selection rules based on calibration or utility

Suggested output:

```text
outputs/backtests/threshold_analysis.csv
```

---

### 3. Episode summary outputs

New outputs:

```text
outputs/backtests/event_scorecard.csv
outputs/backtests/episode_summary.csv
```

Each recession episode should show:

- first warning date
- months of lead time
- missed or hit
- max predicted probability before onset
- false alarms prior to onset

---

## Keep existing standard metrics

Do not remove:

- AUC
- precision
- recall
- F1
- Brier score
- calibration / ECE

Instead, extend them with event-centric metrics.

---

## Acceptance criteria for Phase 3

- Reports contain both standard and event-based metrics.
- Event summaries are produced automatically.
- Threshold tables are generated for configured cutoffs.

---

# Phase 4 — Data architecture refactor

## Goal

Make data sourcing, transforms, and series metadata explicit and maintainable.

## Deliverables

### 1. Series registry

New files:

```text
config/series_registry.yaml
src/recession_risk/data/registry.py
```

Each series should define:

- source
- vintage source
- frequency
- release lag
- transformation
- aggregation method
- whether it is realtime-eligible

Example:

```yaml
UNRATE:
  source: FRED
  vintage_source: ALFRED
  frequency: monthly
  release_lag_days: 5
  transform: level
  realtime_eligible: true

DGS10:
  source: FRED
  frequency: daily
  aggregation: monthly_average
  transform: level
  realtime_eligible: true
```

---

### 2. Data dictionary

New file:

```text
docs/data_dictionary.md
```

Should document:

- all series used
- transformation logic
- frequencies
- release assumptions
- feature definitions

---

### 3. Cache/version metadata

Add support for:

- pull timestamps
- cache metadata
- source tracking
- checksum or versioning where practical

---

## Acceptance criteria for Phase 4

- Data panel construction depends on a registry rather than ad hoc series definitions.
- Data dictionary exists and matches the registry.
- Cache metadata is preserved for traceability.

---

# Phase 5 — Reporting and investor interpretation

## Goal

Make outputs easy to interpret for macro monitoring and investment workflows.

## Deliverables

### 1. Current snapshot report

Add a current snapshot with:

- `P(recession now)`
- `P(within 3m)`
- `P(within 6m)`
- `P(within 12m)`
- model comparison table
- historical percentile context

---

### 2. Signal driver summary

Add a deterministic narrative section describing:

- which indicators currently drive the reading
- whether current risk is rising, falling, or stable
- whether model disagreement is high or low

Keep this rules-based, not LLM-generated.

---

### 3. Regime classification

Add simple regime buckets such as:

- 0–15%: low risk
- 15–35%: rising risk
- 35–60%: elevated risk
- 60%+: high / imminent risk

These buckets should be configurable.

---

### 4. Historical comparison charts

Add:

- recession probability through time
- current reading vs historical range
- model comparison across past cycles
- episode-by-episode warning visualization

---

### 5. Optional portfolio interpretation

Add a template-driven section for:

- equities
- duration
- credit beta
- defensives / cash

This should be descriptive and scenario-oriented, not prescriptive trading advice.

---

## Reporting outputs

Possible output structure:

```text
outputs/reports/current_snapshot/
outputs/reports/historical_comparison/
outputs/reports/charts/
outputs/reports/tables/
```

---

## Acceptance criteria for Phase 5

- Reports include a current snapshot section.
- Current and historical probabilities are visually comparable.
- Regime classification appears in report outputs.
- Existing Markdown/HTML reporting remains functional.

---

# Suggested file structure

## Files likely to modify

```text
config/default.yaml
src/recession_risk/cli.py
src/recession_risk/data/panel.py
src/recession_risk/models/baselines.py
src/recession_risk/backtest/metrics.py
src/recession_risk/reporting/*
tests/test_pipeline.py
```

## New files to add

```text
config/series_registry.yaml
config/realtime.yaml

src/recession_risk/data/vintages.py
src/recession_risk/data/release_calendar.py
src/recession_risk/data/realtime_panel.py
src/recession_risk/data/registry.py

src/recession_risk/models/logit_multivariate.py
src/recession_risk/models/regularized_logit.py
src/recession_risk/models/tree_models.py
src/recession_risk/models/ensemble.py

src/recession_risk/backtest/realtime_runner.py
src/recession_risk/backtest/event_metrics.py
src/recession_risk/backtest/thresholds.py

docs/data_dictionary.md
docs/modeling_notes.md
docs/realtime_backtesting.md
```

---

# Config evolution

## Example config structure

```yaml
data_mode: realtime

realtime:
  use_vintages: true
  release_lags: true
  estimation_window: expanding

models:
  benchmarks:
    - yield_curve_logit
    - inversion_rule
    - hy_spread_logit
    - sahm_rule

  multivariate:
    enabled: true
    targets:
      - within_3m
      - within_6m
      - within_12m
      - current_recession
    features:
      - term_spread_10y_3m
      - hy_oas
      - unemployment_gap
      - payroll_growth_3m
      - ism_new_orders
      - equity_drawdown_6m

  regularized_logit:
    enabled: true
    penalty: elasticnet

  tree_models:
    enabled: false

  ensemble:
    enabled: true
    members:
      - yield_curve_logit
      - multivariate_logit
      - regularized_logit

evaluation:
  thresholds: [0.15, 0.25, 0.35, 0.50]
  event_windows_months: [3, 6, 12]

reporting:
  include_current_snapshot: true
  include_event_scorecards: true
  include_portfolio_interpretation: true
```

---

# Testing requirements

## 1. Pipeline integrity tests

Keep and extend current end-to-end fixture tests.

## 2. No-leakage tests

Add tests proving:

- a forecast dated `t` never uses data released after `t`
- realtime mode differs from latest-available mode when revisions exist
- vintage selection is correct for synthetic examples

## 3. Numerical behavior tests

Add tests for:

- expected sign of benchmark model coefficients where appropriate
- rising signal probabilities under synthetic pre-recession setups
- correct event metric calculations

## 4. Threshold and report tests

Add tests for:

- threshold table generation
- report output completeness
- expected columns in archived prediction files

---

# CI and engineering hardening

## Add

- GitHub Actions CI
- linting
- type checking
- reproducible random seeds
- changelog
- release tags
- example notebook(s)

## Standards

- use typed functions where practical
- avoid breaking existing CLI contracts
- keep public interfaces documented
- ensure outputs are deterministic

---

# Implementation order

## Sprint 1

1. series registry
2. release lag logic
3. realtime panel
4. realtime backtest runner

## Sprint 2

1. multivariate logistic model
2. regularized logistic model
3. horizon-specific target handling

## Sprint 3

1. event metrics
2. threshold analysis
3. episode summaries

## Sprint 4

1. ensemble model
2. optional tree-based models
3. reporting enhancements

## Sprint 5

1. CI
2. docs
3. examples
4. cleanup and packaging polish

---

# Definition of done

The upgrade is complete only when the repo can:

1. Build a pseudo-real-time monthly panel with no look-ahead leakage.
2. Produce separate nowcast and 3m/6m/12m recession odds.
3. Run expanding-window historical backtests.
4. Compare baseline, multivariate, and ensemble models.
5. Report both standard and event-based evaluation metrics.
6. Generate current-state and historical monitoring reports.
7. Pass automated tests and CI.

---

# Codex execution instructions

Implement the repo upgrade in phases without breaking the existing baseline pipeline.

Priorities:

1. Fix historical realism first using realtime data logic.
2. Add multivariate models second.
3. Improve evaluation third.
4. Improve reporting and engineering last.

Constraints:

- Preserve backward compatibility.
- Reuse the existing config-driven project structure.
- Keep baseline models as permanent benchmarks.
- Add tests for realtime no-leakage behavior.
- Keep all outputs organized under `outputs/`.
- Avoid unnecessary dependency bloat.

Deliver code incrementally with clear commits grouped by phase:

- Phase 1: realtime data layer
- Phase 2: expanded models
- Phase 3: evaluation layer
- Phase 4: reporting and docs
- Phase 5: CI and cleanup