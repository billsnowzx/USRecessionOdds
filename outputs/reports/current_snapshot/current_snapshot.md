# Current Snapshot

| Target                        | Selected model               | As of      |   Probability |   Historical percentile | Regime      |
|:------------------------------|:-----------------------------|:-----------|--------------:|------------------------:|:------------|
| P(recession now)              | HY Credit Logit              | 2026-03-01 |        0.0026 |                  0.1082 | low risk    |
| P(recession within 3 months)  | Multivariate Logit Within 3M | 2026-02-01 |        0.0743 |                  0.1042 | low risk    |
| P(recession within 6 months)  | Multivariate Logit Within 6M | 2026-02-01 |        0.131  |                  0.25   | low risk    |
| P(recession within 12 months) | Yield Curve Logit            | 2026-03-01 |        0.156  |                  0.7268 | rising risk |

Overall regime: rising risk (driven by P(recession within 12 months))

![Historical Percentiles](../charts/historical_percentiles.png)