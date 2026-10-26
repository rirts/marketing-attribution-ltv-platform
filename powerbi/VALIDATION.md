# Power BI correction checklist

The original PBIX is preserved; these changes require Power BI Desktop and have not been applied to its binary model here. Do not present the old file as corrected.

1. Run `python -m scripts.run_pipeline` and refresh data in Desktop.
2. Replace the measures in `metric_fixes.dax`. Rename CAC and LTV/CAC as indicated; the source data does not establish acquisition-channel CAC.
3. Keep the horizon slicers bound to `fact_ltv_cohort[horizon_days]`; select a single horizon. Test 30/60/90/180 and multiselect (the card should be blank).
4. LTV uses all mature cohort customers, including zero-purchase customers, independently of marketing channel. Disable the channel/date interaction for the LTV card/chart, label them “Mature cohort revenue per acquired customer — all channels”, and add a cohort signup filter if needed. The buyer-cost card is a separate period metric; do not imply a validated acquisition LTV/CAC comparison.
5. Check attribution revenue sums to order revenue per model, including Unattributed.
6. Save the corrected PBIX and fresh screenshots. Remove the obsolete disconnected Horizon table after updating all dependencies.

The Python tests validate monetary reconciliation, zero-purchase customers and cohort maturity. They do not execute DAX or verify report interactions.
