# Data Dictionary

## Source registry

The canonical series definitions live in `config/series_registry.yaml`. The registry drives ingest, monthly panel construction, and realtime eligibility.

## Core source series

| Series ID | Name | Source | Vintage Source | Frequency | Aggregation | Transform | Release Lag | Realtime Eligible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `DGS10` | 10-Year Treasury Constant Maturity Rate | FRED | None | Daily | Monthly mean | Level | Month-end close | Yes |
| `DTB3` | 3-Month Treasury Bill Secondary Market Rate | FRED | None | Daily | Monthly mean | Level | Month-end close | Yes |
| `UNRATE` | Civilian Unemployment Rate | FRED | ALFRED | Monthly | Month-end last | Level | 1 month + 5 days | Yes |
| `BAMLH0A0HYM2` | ICE BofA US High Yield Index OAS | FRED | None | Daily | Monthly mean | Level | Month-end close | Yes |

## Derived features

| Feature | Definition |
| --- | --- |
| `term_spread` | `DGS10 - DTB3` |
| `sahm_gap` | `3m average UNRATE - 12m rolling minimum of 3m average UNRATE` |
| `current_recession` | NBER recession dummy from the month after each peak through the trough month |
| `recession_start` | First recession month of each NBER episode |
| `within_3m`, `within_6m`, `within_12m` | Indicator that a recession month occurs in the next 3, 6, or 12 months |

## Realtime assumptions

- Daily market series become available at month end and are aggregated to the configured monthly rule.
- `UNRATE` uses ALFRED vintages when available and is subject to a one-month-plus-five-day release lag.
- Realtime panels store `feature_date_used` and `series_vintage_date` columns for traceability.

## Cache metadata

Raw downloads and processed panels write JSON sidecars alongside the CSV artifacts. These sidecars track:

- series/source metadata
- checksums
- file paths
- metadata write timestamp
- processed panel date range and column list
