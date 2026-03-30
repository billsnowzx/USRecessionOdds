# Recession Risk Replication

This repository replicates four baseline U.S. recession-risk measurements from the research note in this workspace:

- Yield-curve logit for `P(recession within next 12 months)`
- Yield-curve inversion rule using `10Y - 3M < 0`
- High-yield credit-spread logit for `P(current recession state)`
- Sahm-style unemployment-gap detection rule

## Data sources

- FRED `DGS10`: 10-Year Treasury Constant Maturity Rate
- FRED `DTB3`: 3-Month Treasury Bill Secondary Market Rate
- FRED `UNRATE`: Civilian Unemployment Rate
- FRED `BAMLH0A0HYM2`: ICE BofA US High Yield Index Option-Adjusted Spread
- `data/reference/nber_chronology.csv`: checked-in NBER peak/trough chronology used to build recession labels

## Label definitions

- `current_recession`: monthly recession dummy, marked from the month after each NBER peak through the trough month
- `within_3m`, `within_6m`, `within_12m`: `1` if any recession month occurs in the next `H` months
- `recession_start`: first recession month of each episode

The yield-curve models are treated as forecasting models because their target is recession occurrence over a forward horizon. The HY spread and Sahm rule are treated as detection models because they map more naturally to current recession state.

## Why results may differ from the research note

- This implementation uses latest-available FRED data, not ALFRED vintages.
- Daily financial series are aggregated to monthly means by default; robustness runs compare this with end-of-month values.
- Logistic regression is implemented directly with SciPy rather than scikit-learn to keep the environment self-contained.
- Small differences in missing-data handling or revised source histories can change coefficients and downstream metrics.

## Commands

All commands default to `config/default.yaml`.

```bash
recession-risk ingest
recession-risk build-panel
recession-risk run-baselines
recession-risk run-robustness
recession-risk render-report
recession-risk ingest --include-vintages
recession-risk build-panel --data-mode realtime
recession-risk run-realtime-backtest
recession-risk run-expanded-models
recession-risk run-expanded-models --data-mode realtime
```

If you do not install the package, run with `PYTHONPATH=src` and `python -m recession_risk.cli ...`.
Use `config/realtime.yaml` when you want a small explicit realtime override file.

## Development

Install dev tooling with:

```bash
python -m pip install -e ".[dev]"
```

Common checks:

```bash
python -m ruff check .
python -m mypy src
python -m pytest -q
```

## Output artifacts

- `data/raw/*.csv`: cached FRED downloads
- `data/raw/*.metadata.json`: raw-cache metadata sidecars with source and checksum information
- `data/processed/monthly_panel.csv` and `.parquet`
- `data/processed/monthly_panel*.metadata.json`: processed panel metadata sidecars
- `reports/tables/baseline_predictions.csv`
- `reports/tables/baseline_metrics.csv`
- `reports/tables/robustness_metrics.csv`
- `reports/figures/*.png`
- `reports/recession_risk_report.md`
- `outputs/reports/current_snapshot/*`
- `outputs/reports/historical_comparison/*`
- `outputs/reports/charts/*`
- `outputs/reports/tables/*`
- `data/vintages/*.csv`: cached ALFRED vintage downloads for realtime-eligible series
- `data/processed/monthly_panel_realtime.csv` and `.parquet`
- `outputs/backtests/realtime_predictions.csv`
- `outputs/backtests/realtime_metrics.csv`
- `outputs/backtests/expanded_predictions*.csv`
- `outputs/backtests/expanded_metrics*.csv`
- `outputs/backtests/expanded_model_summary*.csv`
- `outputs/backtests/*_event_scorecard.csv`
- `outputs/backtests/*_episode_summary.csv`
- `outputs/backtests/*_threshold_analysis.csv`

The source registry is documented in `config/series_registry.yaml`, and the human-readable field descriptions live in `docs/data_dictionary.md`.

## Realtime mode

Realtime mode builds an as-of monthly panel that respects configured release lags and uses vintage data when a cached ALFRED history is available.

- Default mode remains `latest_available`.
- Realtime mode is enabled with `--data-mode realtime` or by setting `data_mode: realtime` in config.
- `ingest --include-vintages` downloads the ALFRED files needed by realtime-eligible macro series.

## Expanded models

Phase 2 adds config-driven benchmark-adjacent models:

- multivariate logistic regression
- regularized logistic regression
- simple-average ensemble across configured model members
- optional tree-model scaffolding via `scikit-learn` when enabled

They are run through `run-expanded-models` and produce separate archived outputs for latest-available and realtime panel modes.

## Event evaluation

Phase 3 adds automatic event-oriented evaluation outputs whenever baseline, realtime, or expanded backtests are saved:

- per-episode scorecards with first warning date and lead/lag timing
- per-model episode summaries
- threshold sweeps for probability-scored models

## Reporting

Phase 5 adds investor-facing outputs while preserving the original report entrypoints:

- current snapshot table for `now`, `3m`, `6m`, and `12m` recession odds
- regime classification using configurable probability buckets
- deterministic signal-driver and model-disagreement summaries
- historical percentile and episode-warning comparison charts
- scenario-oriented portfolio interpretation text

Additional project docs:

- `docs/data_dictionary.md`
- `docs/modeling_notes.md`
- `CHANGELOG.md`
- `examples/recession_monitoring_walkthrough.ipynb`
