# Release Checklist

Use this checklist before publishing a monthly monitoring update or a tagged repo release.

## Data and backtests

- Run `recession-risk ingest --include-vintages` if the raw cache should be refreshed
- Run `recession-risk build-panel`
- Run `recession-risk build-panel --data-mode realtime`
- Run `recession-risk run-baselines`
- Run `recession-risk run-realtime-backtest`
- Run `recession-risk run-expanded-models`
- Run `recession-risk run-expanded-models --data-mode realtime`

## Reports

- Run `recession-risk render-report`
- Run `recession-risk render-html-summary`
- Review `outputs/reports/tables/current_snapshot_latest_available.csv`
- Review `outputs/reports/tables/current_snapshot_realtime.csv`
- Review `outputs/reports/tables/snapshot_mode_comparison.csv`
- Update the monthly memo if a dated memo is being published

## Validation

- Run `python -m ruff check .`
- Run `python -m mypy src`
- Run `python -m pytest -q`
- Confirm the selected models and fallback notes in `outputs/reports/tables/model_selection_quality.csv`

## Publish

- Update `CHANGELOG.md`
- Create a git tag
- Draft release notes summarizing methodology, current snapshot changes, and any material latest-vs-realtime gap
- Push commit and tag to GitHub
