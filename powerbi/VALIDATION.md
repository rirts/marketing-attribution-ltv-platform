# Power BI validation

## Committed report

The corrected Desktop file is committed as `powerbi/Dashboard_P1.pbix`.

- SHA-256: `0a043d6f21598d6d1a936d8b4db345b424a636f36b54f2ed3165f216b679d8e4`.
- Received and reviewed: 2026-10-27.
- The eight imported source tables match the verified MySQL snapshot, including individual source values and primary keys. Date readback allows 2 ms of VertiPaq decoding tolerance.
- All eight M queries use `analytics_portfolio_corrected` for the connection and schema, preserve their existing table names, and set `CreateNavigationProperties=false`.
- A full Desktop refresh succeeded after this connector option was applied. The original cyclic-refresh failure is no longer reproduced in that refresh; its internal root cause has not been independently established.
- The revenue card aliases allocated attributed revenue. It no longer sums whole shared orders for a selected channel under linear/time-decay attribution.
- The selected-horizon LTV measure, default of 180 and separate horizon-line measure are applied. The LTV/CAC ratio measure is removed.
- The cost card displays **Cost per Buyer**; Page 3 uses **Cost per Buyer by Channel**.
- Page 3 uses `Calendar[YearMonth]` sorted ascending. The displayed period has 13 separate months, including both Novembers.
- Pages 2 and 3 have no horizon slicer. The Horizon table remains because it owns Selected Horizon.

## Evidence and limits

The owner completed the ten model-count/total checks in Desktop and reported that Page 1 interactions behaved as expected. Screenshots verify 108 orders, revenue of approximately 7.95K, 180-day LTV of 96.13 and the chronological 13-month series. The current monthly screenshot follows the successful full refresh.

Static readback verifies the corrected formula and stored source rows. It does not run the Power BI DAX engine or render the report. The split-model results below are derived from the stored allocation rows and are available as explicit Desktop queries in `regression_checks.dax`; they are not presented as automated DAX-engine execution.

| Selection | Expected allocated revenue |
|---|---:|
| All channels, each individual model | 7,951.11 |
| Google Ads, first click | 1,172.43 |
| Google Ads, last click | 1,892.48 |
| Google Ads, linear | 1,171.85 |
| Google Ads, time decay | 1,137.10 |

All reported monetary values share one synthetic demo unit. The CSVs do not supply an ISO currency; the dollar sign is a display convention without currency conversion.

## Repeat after changing the report or data

1. Rebuild the MySQL tables and refresh the Desktop report. Preserve query names.
2. Run `python -m scripts.verify_powerbi` against that database. CI checks all source values, query settings, the revenue alias and key visual definitions.
3. Run `powerbi/regression_checks.dax` in Desktop's DAX query view. Check full-model totals, channel-specific allocated revenue and LTV horizon cases.
4. Check Page 1 interactions:

   | Source | LTV card | LTV line |
   |---|---|---|
   | Channel | No change | No change |
   | Order-date range | No change | No change |
   | Attribution model | No change | No change |
   | Horizon | Selected horizon | All four horizons remain |
   | Channel revenue-chart selection | No change | No change |

   The disconnected Calendar and single-direction channel relationships do not restrict LTV. Existing explicit interaction settings also isolate the LTV visuals. A future relationship change requires retesting these interactions.

5. Check labels, title visibility, the monthly axis and a full refresh. Save the PBIX and update screenshots from Desktop when the layout changes.

The MySQL pipeline check is `python -m scripts.verify_metrics`. CI also restores the exported snapshot, compares source/restored table hashes and verifies preservation of the original database.

