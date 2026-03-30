# U.S. Recession Odds Platform

This repository started as a replication of four canonical U.S. recession-risk signals and now serves as a small, reproducible recession-odds platform with:

- benchmark models
- pseudo-real-time data handling
- expanded multivariate models
- event-based evaluation
- investor-facing reporting

The benchmark layer remains permanent:

- Yield-curve logit for `P(recession within next 12 months)`
- Yield-curve inversion rule using `10Y - 3M < 0`
- High-yield credit-spread logit for `P(current recession state)`
- Sahm-style unemployment-gap detection rule

## Data sources

Primary source series are defined in `config/series_registry.yaml`.

- FRED `DGS10`: 10-Year Treasury Constant Maturity Rate
- FRED `DTB3`: 3-Month Treasury Bill Secondary Market Rate
- FRED `UNRATE`: Civilian Unemployment Rate
- FRED `BAMLH0A0HYM2`: ICE BofA US High Yield Index Option-Adjusted Spread
- FRED `PAYEMS`: All Employees, Total Nonfarm
- FRED `AMTMNO`: Manufacturers' New Orders
- FRED `USALOLITOAASTSAM`: OECD Composite Leading Indicator for the United States
- FRED `SPASTT01USM661N`: OECD Total Share Prices for the United States
- `data/reference/nber_chronology.csv`: checked-in NBER peak/trough chronology used to build recession labels

## Labels

- `current_recession`: monthly recession dummy, marked from the month after each NBER peak through the trough month
- `within_3m`, `within_6m`, `within_12m`: `1` if any recession month occurs in the next `H` months
- `recession_start`: first recession month of each episode

Yield-curve models are treated as forecasting models because they target forward recession occurrence. HY spread and Sahm-style rules are treated as recession-state detectors.

## Features and modes

The latest expanded feature set remains compact and interpretable:

- `term_spread`
- `DTB3`
- `BAMLH0A0HYM2`
- `sahm_gap`
- `UNRATE`
- `PAYEMS_growth_3m_ann`
- `AMTMNO_change_3m`
- `US_OECD_CLI_growth_3m`
- `equity_drawdown_6m`

Realtime mode builds an as-of monthly panel that respects configured release lags and uses cached ALFRED vintages where available.

- Default mode remains `latest_available`
- Realtime mode is enabled with `--data-mode realtime` or by setting `data_mode: realtime`
- `ingest --include-vintages` downloads ALFRED files for realtime-eligible macro series

## Commands

All commands default to `config/default.yaml`.

```bash
recession-risk ingest
recession-risk ingest --include-vintages
recession-risk build-panel
recession-risk build-panel --data-mode realtime
recession-risk run-baselines
recession-risk run-robustness
recession-risk run-realtime-backtest
recession-risk run-expanded-models
recession-risk run-expanded-models --data-mode realtime
recession-risk render-report
recession-risk render-html-summary
```

If you do not install the package, run with `PYTHONPATH=src` and `python -m recession_risk.cli ...`.
Use `config/realtime.yaml` when you want a small explicit realtime override file.

## Reporting and governance

Investor-facing outputs now separate:

- `latest_available` snapshot
- `realtime` snapshot

Expanded-model probabilities are calibrated before investor-facing selection. Snapshot auto-selection is quality-gated using:

- minimum AUC
- minimum episode recall
- maximum ECE for probability models
- maximum false-alarm streak by target

If no expanded model passes the gates for a target, reporting falls back to the best benchmark model and records the reason.

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

Optional tree models require:

```bash
python -m pip install -e ".[ml]"
```

## Outputs

- `data/raw/*.csv`: cached FRED downloads
- `data/vintages/*.csv`: cached ALFRED downloads for realtime-eligible series
- `data/processed/monthly_panel*.csv|parquet`: processed latest-available and realtime panels
- `reports/tables/baseline_*.csv`: benchmark outputs
- `outputs/backtests/*.csv`: realtime, expanded, event, threshold, and summary outputs
- `outputs/reports/tables/*.csv`: current snapshot, mode comparison, and governance tables
- `outputs/reports/charts/*.png`: investor-facing charts
- `reports/recession_risk_report.md`
- `reports/recession_risk_summary.html`

The source registry is documented in `config/series_registry.yaml`, and the human-readable field descriptions live in `docs/data_dictionary.md`.

## Current known limitations

- The expanded feature set is still intentionally compact rather than a full macro panel.
- Some expanded models remain weakly calibrated even after deterministic Platt scaling and will be excluded by the snapshot gates.
- The investor snapshot now shows both latest-available and realtime views, but the monthly memo workflow still assumes a single primary view unless explicitly updated.
- Tree models remain optional and experimental rather than a core production path.

## Additional docs

- `docs/data_dictionary.md`
- `docs/modeling_notes.md`
- `docs/realtime_backtesting.md`
- `docs/release_checklist.md`
- `docs/open_source_backlog.md`
- `CHANGELOG.md`
- `examples/recession_monitoring_walkthrough.ipynb`
