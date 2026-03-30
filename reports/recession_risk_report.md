# Recession Risk Replication Report

## Summary

This report reproduces the four baseline measurements defined in the repository configuration.

## Metrics

| model_name            | target_name       |   horizon | split_name           | test_start   |    auc |   precision |   recall |     f1 |   false_positive_months |   brier_score |      ece |   event_hit_rate |   median_timing_months |   event_hits |   n_events |
|:----------------------|:------------------|----------:|:---------------------|:-------------|-------:|------------:|---------:|-------:|------------------------:|--------------:|---------:|-----------------:|-----------------------:|-------------:|-----------:|
| yield_curve_logit     | within_12m        |        12 | fixed_1990_holdout   | 1990-01-01   | 0.8561 |      0.3023 |   0.3023 | 0.3023 |                      30 |        0.1128 |   0.0696 |             0.75 |                    9   |            3 |          4 |
| yield_curve_inversion | within_12m        |        12 | fixed_1990_holdout   | 1990-01-01   | 0.8561 |      0.3182 |   0.3256 | 0.3218 |                      30 |      nan      | nan      |             0.75 |                    9   |            3 |          4 |
| hy_credit_logit       | current_recession |         0 | fixed_2007_holdout   | 2007-01-01   | 0.9743 |      0.9    |   0.45   | 0.6    |                       1 |        0.0396 |   0.0324 |             0.5  |                    9   |            1 |          2 |
| sahm_rule             | current_recession |         0 | post_1990_monitoring | 1990-01-01   | 0.9102 |      0.3614 |   0.8333 | 0.5042 |                      53 |      nan      | nan      |             1    |                    1.5 |            4 |          4 |

## Figures

![Term spread](figures/term_spread.png)

![Yield curve probability](figures/yield_curve_probability.png)

![ROC curves](figures/baseline_roc.png)

![Yield curve calibration](figures/yield_curve_calibration.png)

## Notes

- Daily financial series are aggregated to monthly frequency before modeling.
- Yield-curve models are evaluated on expansion months for forward recession labels.
- HY credit and Sahm rule are evaluated as recession-state detectors.