# Realtime Backtesting

Phase 1 adds a pseudo-real-time path alongside the existing latest-available pipeline.

## What changes

- `data_mode: latest_available` keeps the original behavior.
- `data_mode: realtime` builds a monthly panel using only observations available as of each forecast month.
- Realtime-eligible macro series can use cached ALFRED vintages.
- Release lags are controlled by `config/series_registry.yaml`.

## Commands

```bash
python -m recession_risk.cli ingest --include-vintages
python -m recession_risk.cli build-panel --data-mode realtime
python -m recession_risk.cli run-realtime-backtest
```

## Key outputs

- `data/processed/monthly_panel_realtime.csv`
- `outputs/backtests/realtime_predictions.csv`
- `outputs/backtests/realtime_metrics.csv`

## Current scope

This phase keeps the baseline benchmark models and adds realtime-aware feature construction and expanding-window backtesting. It does not yet add multivariate or ensemble models.
