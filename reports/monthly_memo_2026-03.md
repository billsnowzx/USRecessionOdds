# U.S. Recession Odds Memo: March 2026

Prepared on March 30, 2026 from the repository's current HTML monitoring outputs. The latest saved model dates in the snapshot are March 1, 2026 for `P(recession now)` and `P(recession within 12 months)`, and February 1, 2026 for the 3-month and 6-month forward models.

## Bottom Line

The current signal set still points to low near-term recession risk, but the 12-month outlook remains somewhat less comfortable than the very short horizons. The repo's selected snapshot shows:

| Horizon | Selected Model | As Of | Probability | Regime |
|:--|:--|:--|--:|:--|
| `P(recession now)` | HY Credit Logit | 2026-03-01 | 0.26% | low risk |
| `P(recession within 3 months)` | Multivariate Logit Within 3M | 2026-02-01 | 7.43% | low risk |
| `P(recession within 6 months)` | Multivariate Logit Within 6M | 2026-02-01 | 13.10% | low risk |
| `P(recession within 12 months)` | Yield Curve Logit | 2026-03-01 | 15.60% | rising risk |

The practical reading is that the system does not currently indicate an active recession or an imminent downturn over the next quarter, but it does continue to assign a somewhat higher probability to recession over the next year than over the next few months.

## Key Signals

- Credit remains calm. The HY credit model is the strongest nowcast in the stack and currently reports only `0.26%` recession probability.
- Labor-market deterioration is not confirmed by the selected snapshot, although the Sahm rule remains materially more cautious than the credit-based nowcast.
- The term spread is positive and steepening, which is better than an inversion regime, but the 12-month yield-curve probability still sits at a relatively elevated historical percentile for its own series.
- Model disagreement is high, especially for the 12-month horizon. The selected model is moderate, but some expanded models remain much more aggressive.

## Interpretation

For March 2026, the most defensible summary is: no clear recession signal now, low odds over the next 3 to 6 months, and a still-watchful 12-month outlook. That is not a recession call, but it is also not a fully benign all-clear.

From an allocation and monitoring perspective, the message is more about discipline than urgency:

- Equities: the backdrop is not hostile enough to argue for a full defensive posture, but quality and earnings resilience still make sense.
- Duration: some duration ballast remains useful if the medium-horizon growth outlook softens.
- Credit: current spread behavior does not suggest acute stress, but lower-quality credit risk should still be sized carefully.
- Cash and defensives: optionality is still worth carrying, though the short-horizon models do not justify a maximal risk-off stance.

## What Would Change This View

The memo would turn more negative if one or more of the following occurred in coming months:

- the Sahm gap moved decisively through recession-trigger territory,
- HY spreads widened sharply and stayed wide,
- the 3-month and 6-month multivariate models moved out of low-risk territory,
- the yield curve re-flattened or re-inverted in a sustained way.

Conversely, the medium-horizon concern would fade if the 12-month probability dropped back into the low-risk bucket and the model disagreement narrowed.

## Charts

![Selected probabilities](../outputs/reports/charts/selected_probabilities.png)

![Historical percentiles](../outputs/reports/charts/historical_percentiles.png)

![Current model comparison](../outputs/reports/charts/current_model_comparison.png)

![Episode warning timing](../outputs/reports/charts/episode_warning_timing.png)

## Source Files

- [Summary HTML](D:/AI/Recession_Odds/reports/recession_risk_summary.html)
- [Snapshot table](D:/AI/Recession_Odds/outputs/reports/tables/current_snapshot.csv)
- [Model comparison table](D:/AI/Recession_Odds/outputs/reports/tables/model_comparison.csv)
