# Data Dictionary

## Source registry

The canonical series definitions live in `config/series_registry.yaml`. The registry drives ingest, release lags, realtime eligibility, transforms, and deterministic feature naming.

## Core source series

| Series ID | Name | Source | Vintage Source | Frequency | Aggregation | Transform | Feature Name | Release Lag | Realtime Eligible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `DGS10` | 10-Year Treasury Constant Maturity Rate | FRED | None | Daily | Monthly mean | Level | `DGS10` | Month-end close | Yes |
| `DTB3` | 3-Month Treasury Bill Secondary Market Rate | FRED | None | Daily | Monthly mean | Level | `DTB3` | Month-end close | Yes |
| `UNRATE` | Civilian Unemployment Rate | FRED | ALFRED | Monthly | Month-end last | Level | `UNRATE` | 1 month + 5 days | Yes |
| `BAMLH0A0HYM2` | ICE BofA US High Yield Index OAS | FRED | None | Daily | Monthly mean | Level | `BAMLH0A0HYM2` | Month-end close | Yes |
| `PAYEMS` | All Employees, Total Nonfarm | FRED | ALFRED | Monthly | Month-end last | 3-month annualized growth | `PAYEMS_growth_3m_ann` | 1 month + 5 days | Yes |
| `AMTMNO` | Manufacturers' New Orders | FRED | None | Monthly | Month-end last | 3-month change | `AMTMNO_change_3m` | 1 month + 13 days | Yes |
| `USALOLITOAASTSAM` | OECD Composite Leading Indicator for the United States | FRED | ALFRED | Monthly | Month-end last | 3-month growth | `US_OECD_CLI_growth_3m` | 1 month + 14 days | Yes |
| `SPASTT01USM661N` | OECD Total Share Prices for the United States | FRED | None | Monthly | Month-end last | 6-month drawdown | `equity_drawdown_6m` | Month-end close | Yes |

## Derived features

| Feature | Definition |
| --- | --- |
| `term_spread` | `DGS10 - DTB3` |
| `sahm_gap` | `3m average UNRATE - 12m rolling minimum of 3m average UNRATE` |
| `PAYEMS_growth_3m_ann` | `((PAYEMS / PAYEMS.shift(3)) ** 4 - 1) * 100` |
| `AMTMNO_change_3m` | `AMTMNO - AMTMNO.shift(3)` |
| `US_OECD_CLI_growth_3m` | `((USALOLITOAASTSAM / USALOLITOAASTSAM.shift(3)) - 1) * 100` |
| `equity_drawdown_6m` | Percentage drawdown from the rolling 6-month peak |
| `current_recession` | NBER recession dummy from the month after each peak through the trough month |
| `recession_start` | First recession month of each NBER episode |
| `within_3m`, `within_6m`, `within_12m` | Indicator that a recession month occurs in the next 3, 6, or 12 months |

## Realtime assumptions

- Daily market series become available at month end and are aggregated to the configured monthly rule
- Monthly macro series respect their configured release lags even when no vintage file exists
- `UNRATE`, `PAYEMS`, and `USALOLITOAASTSAM` use ALFRED vintages when cached locally
- Realtime panels store `feature_date_used` and `series_vintage_date` columns for traceability on raw series

## Cache metadata

Raw downloads and processed panels write JSON sidecars alongside the CSV artifacts. These sidecars track:

- source metadata
- checksums
- file paths
- metadata write timestamp
- processed panel date range and column list
