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
```

If you do not install the package, run with `PYTHONPATH=src` and `python -m recession_risk.cli ...`.

## Output artifacts

- `data/raw/*.csv`: cached FRED downloads
- `data/processed/monthly_panel.csv` and `.parquet`
- `reports/tables/baseline_predictions.csv`
- `reports/tables/baseline_metrics.csv`
- `reports/tables/robustness_metrics.csv`
- `reports/figures/*.png`
- `reports/recession_risk_report.md`
