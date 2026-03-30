# Historical Comparison

| Target                        | Model                                | As of      |   Probability |   Raw score |   Historical percentile |    AUC |   Episode recall | Regime               |
|:------------------------------|:-------------------------------------|:-----------|--------------:|------------:|------------------------:|-------:|-----------------:|:---------------------|
| P(recession now)              | HY Credit Logit                      | 2026-03-01 |        0.0026 |      0.0026 |                  0.1082 | 0.9743 |             0.5  | low risk             |
| P(recession now)              | Regularized Logit Current Recession  | 2026-02-01 |        0.0446 |      0.0446 |                  0.1498 | 0.9469 |             0.5  | low risk             |
| P(recession now)              | Sahm Rule                            | 2026-02-01 |        0.4667 |      0.2333 |                  0.7216 | 0.9102 |             1    | elevated risk        |
| P(recession now)              | Ensemble Current Recession           | 2026-02-01 |        0.0239 |      0.0239 |                  0.1101 | 0.6539 |             1    | low risk             |
| P(recession now)              | Multivariate Logit Current Recession | 2026-02-01 |        0.0033 |      0.0033 |                  0.4978 | 0.4459 |             1    | low risk             |
| P(recession within 3 months)  | Multivariate Logit Within 3M         | 2026-02-01 |        0.0743 |      0.0743 |                  0.1042 | 0.7168 |             1    | low risk             |
| P(recession within 3 months)  | Ensemble Within 3M                   | 2026-02-01 |        0.0521 |      0.0521 |                  0.1042 | 0.7168 |             0    | low risk             |
| P(recession within 3 months)  | Regularized Logit Within 3M          | 2026-02-01 |        0.0299 |      0.0299 |                  1      | 0.5    |             0    | low risk             |
| P(recession within 6 months)  | Multivariate Logit Within 6M         | 2026-02-01 |        0.131  |      0.131  |                  0.25   | 0.6259 |             1    | low risk             |
| P(recession within 6 months)  | Ensemble Within 6M                   | 2026-02-01 |        0.0999 |      0.0999 |                  0.25   | 0.613  |             1    | low risk             |
| P(recession within 6 months)  | Regularized Logit Within 6M          | 2026-02-01 |        0.0688 |      0.0688 |                  0.4792 | 0.5426 |             0    | low risk             |
| P(recession within 12 months) | Yield Curve Logit                    | 2026-03-01 |        0.156  |      0.156  |                  0.7268 | 0.8561 |             0.75 | rising risk          |
| P(recession within 12 months) | Yield Curve Inversion                | 2026-03-01 |        0      |     -0.6153 |                  0.8897 | 0.8561 |             0.75 | low risk             |
| P(recession within 12 months) | Ensemble Within 12M                  | 2026-02-01 |        0.5156 |      0.5156 |                  0.2917 | 0.5893 |             1    | elevated risk        |
| P(recession within 12 months) | Multivariate Logit Within 12M        | 2026-02-01 |        0.8543 |      0.8543 |                  0.2708 | 0.5813 |             1    | high / imminent risk |
| P(recession within 12 months) | Regularized Logit Within 12M         | 2026-02-01 |        0.1768 |      0.1768 |                  0.5729 | 0.5367 |             0    | rising risk          |

![Selected Probabilities](../charts/selected_probabilities.png)

![Current Model Comparison](../charts/current_model_comparison.png)

![Episode Warning Timing](../charts/episode_warning_timing.png)