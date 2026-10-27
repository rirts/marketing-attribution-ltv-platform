# Power BI correction checklist

The original PBIX is preserved; these changes require Power BI Desktop and have not yet been applied to its binary model in this branch.

1. Build the corrected tables with the Python pipeline or import the CI-verified snapshot into analytics_portfolio_corrected. For a snapshot, update both the MySQL database and any navigation schema keys in Power Query; preserve existing query names. Refresh the imported tables.
2. Replace the measures in metric_fixes.dax. Rename CAC (Selected) to Cost per Purchasing Customer (Selected). Replace the LTV/CAC card's field with Avg LTV (sel). Show LTV and buyer cost separately; the sample does not establish acquisition-channel CAC or matching populations for that ratio.
3. Keep the horizon slicer bound to fact_ltv_cohort[horizon_days]. Test 30/60/90/180, no selection (180 default) and multiselect (blank card).
4. Configure interactions on Page 1:

   | Source selector | LTV card | LTV-by-horizon chart |
   |---|---|---|
   | Channel | None | None |
   | Date | None | None |
   | Attribution model | None | None |
   | Horizon | Filter | None |

   Channel-chart selections should also have no effect on these two LTV visuals. Label them as mature-cohort revenue per acquired customer across all channels. A cohort-signup filter may be added explicitly. Remove horizon slicers from pages without LTV visuals.
5. With all dates and channels included, check order counts and attribution totals against snapshot-validation.json and verify all four models reconcile to order revenue, including Unattributed. Confirm zero-revenue eligible customers are included and immature horizons are absent.
6. Format monetary values with an explicit currency assumption and readable labels. Update the renamed cost-per-purchasing-customer chart on Page 3 and check for truncated labels.
7. Save the corrected PBIX and fresh screenshots. Keep the Horizon table while it owns the Selected Horizon measure; remove unused fields/measures only after checking their dependencies.

The Python/MySQL checks validate data and monetary reconciliation. They do not execute DAX or verify report interactions.
