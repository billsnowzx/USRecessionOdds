# Current Snapshot

## Latest Available

| Mode             | Target                        | Selected model                      | As of      |   Probability |   Historical percentile | Regime      | Quality gates   | Selection note                                                     |
|:-----------------|:------------------------------|:------------------------------------|:-----------|--------------:|------------------------:|:------------|:----------------|:-------------------------------------------------------------------|
| Latest available | P(recession now)              | Regularized Logit Current Recession | 2026-01-01 |        0.0525 |                  0.4292 | low risk    | pass            | Selected from eligible candidates                                  |
| Latest available | P(recession within 3 months)  | Multivariate Logit Within 3M        | 2026-01-01 |        0      |                  0.4854 | low risk    | fail            | No benchmark candidate available; using best available model.      |
| Latest available | P(recession within 6 months)  | Multivariate Logit Within 6M        | 2026-01-01 |        0      |                  0.5194 | low risk    | fail            | No benchmark candidate available; using best available model.      |
| Latest available | P(recession within 12 months) | Yield Curve Logit                   | 2026-03-01 |        0.156  |                  0.7268 | rising risk | pass            | No expanded model passed quality gates; falling back to benchmark. |

## Realtime

| Mode     | Target                        | Selected model               | As of      |   Probability |   Historical percentile | Regime      | Quality gates   | Selection note                                                     |
|:---------|:------------------------------|:-----------------------------|:-----------|--------------:|------------------------:|:------------|:----------------|:-------------------------------------------------------------------|
| Realtime | P(recession now)              | Ensemble Current Recession   | 2026-03-01 |        0.0255 |                  0.3463 | low risk    | pass            | Selected from eligible candidates                                  |
| Realtime | P(recession within 3 months)  | Multivariate Logit Within 3M | 2026-03-01 |        0      |                  0.3981 | low risk    | fail            | No benchmark candidate available; using best available model.      |
| Realtime | P(recession within 6 months)  | Multivariate Logit Within 6M | 2026-03-01 |        0      |                  0.6303 | low risk    | fail            | No benchmark candidate available; using best available model.      |
| Realtime | P(recession within 12 months) | Yield Curve Logit (Realtime) | 2026-03-01 |        0.1977 |                  0.7168 | rising risk | pass            | No expanded model passed quality gates; falling back to benchmark. |

## Mode Comparison

| Target                        | Latest available model              | Latest available as of   |   Latest available probability | Latest available regime   | Latest available note                                              | Realtime model               | Realtime as of   |   Realtime probability | Realtime regime   | Realtime note                                                      |   Probability delta | Material gap   |
|:------------------------------|:------------------------------------|:-------------------------|-------------------------------:|:--------------------------|:-------------------------------------------------------------------|:-----------------------------|:-----------------|-----------------------:|:------------------|:-------------------------------------------------------------------|--------------------:|:---------------|
| P(recession now)              | Regularized Logit Current Recession | 2026-01-01               |                         0.0525 | low risk                  | Selected from eligible candidates                                  | Ensemble Current Recession   | 2026-03-01       |                 0.0255 | low risk          | Selected from eligible candidates                                  |              0.027  | False          |
| P(recession within 3 months)  | Multivariate Logit Within 3M        | 2026-01-01               |                         0      | low risk                  | No benchmark candidate available; using best available model.      | Multivariate Logit Within 3M | 2026-03-01       |                 0      | low risk          | No benchmark candidate available; using best available model.      |              0      | False          |
| P(recession within 6 months)  | Multivariate Logit Within 6M        | 2026-01-01               |                         0      | low risk                  | No benchmark candidate available; using best available model.      | Multivariate Logit Within 6M | 2026-03-01       |                 0      | low risk          | No benchmark candidate available; using best available model.      |             -0      | False          |
| P(recession within 12 months) | Yield Curve Logit                   | 2026-03-01               |                         0.156  | rising risk               | No expanded model passed quality gates; falling back to benchmark. | Yield Curve Logit (Realtime) | 2026-03-01       |                 0.1977 | rising risk       | No expanded model passed quality gates; falling back to benchmark. |             -0.0417 | False          |

![Latest available selected history](../charts/selected_probabilities_latest_available.png)

![Realtime selected history](../charts/selected_probabilities_realtime.png)