# Marketing Attribution & LTV Dashboard
*(MySQL + Python + Power BI)*

This project integrates **MySQL databases**, **Python processing**, and **Power BI visualization** to analyze marketing campaign effectiveness through different **attribution models** and business metrics such as **observed LTV**, **cost per purchasing customer**, and **ROAS**.

## Project Structure
- `powerbi/` — Power BI report and metric update instructions (`Dashboard_P1.pbix`) stored via Git LFS
- `sql/` — SQL scripts to create and populate tables
- `scripts/` — Python ETL scripts
- `data/` — (optional) sample data
- `requirements.txt` — Python dependencies
- `.env.example` — example environment variables
- `README.md` — project documentation

## How to Run the Project

### 1. Set up Python environment
- python -m venv .venv
- .\.venv\Scripts\activate   # On Windows
- pip install -r requirements.txt

### 2. Configure environment variables
- Create a **.env** file based on **.env.example**:
- MYSQL_HOST=localhost
- MYSQL_PORT=3306
- MYSQL_USER=demo_user
- MYSQL_PASSWORD=demo_pass
- MYSQL_DB=analytics_portfolio

### 3. Load database
From the repository root, run `python -m scripts.run_pipeline` to create the database, load the bundled CSVs and build attribution/LTV tables.

### 4. Connect Power BI
- Open **powerbi/Dashboard_P1.pbix**
- Update connection credentials to your **MySQL** instance
- Apply `powerbi/metric_fixes.dax`, refresh data and complete `powerbi/VALIDATION.md` before treating the report as updated.

## Key metrics
- **Attributed Revenue (Selected)** - Revenue assigned to a channel based on chosen attribution model
- **Total Revenue (Selected)** - Total revenue from orders
- **Orders (Selected)** - Unique orders
- **Customers (Selected)** – Unique customers
- **Total Spend (Selected)** – Total marketing spend
- **Cost per Purchasing Customer (Selected)** – Spend divided by period purchasing customers
- **Avg LTV (sel)** – Average lifetime value, adjusted by horizon_days
- **ROAS (Selected)** – Return on advertising spend

## Attribution Models Implemented
- **First Click** – Assigns all value to the first customer touchpoint
- **Last Click** – Assigns all value to the last touchpoint before purchase
- **Linear** – Distributes value evenly across all touchpoints
- **Time Decay** – Gives more weight to touchpoints closer to the purchase

## Filters and segmentation
- Date range
- Attribution model
- Marketing channel
- Horizon Days

## Dashboard example

Historical layout screenshots; the PBIX still requires the Desktop metric update described below.

<img width="1182" height="657" alt="image" src="https://github.com/user-attachments/assets/f407b83e-cb62-4d80-8d6f-b6ebd03a58ac" />
<img width="1178" height="661" alt="image" src="https://github.com/user-attachments/assets/bd6a593c-f134-4447-8ba1-d7fba663b881" />
<img width="1175" height="656" alt="image" src="https://github.com/user-attachments/assets/1283ac03-1fea-4140-a93a-dc9e1a557d41" />

## Actionable Insights From The Dashboard
- Compare channel-attributed revenue, spend and cost per purchasing customer
- Inspect mature customer cohort value across observation horizons
- Detect campaigns producing **ROAS below 1 (attributed revenue below advertising spend)** that should be optimized  or discontinued
- Compare how metrics change under **different attribution models**

## Notes
- The .pbix file is stored using Git LFS due to its size.
- The actual .env file is never uploaded; use .env.example as a template.
- Sample data is fictional and does not represent real customer information.

## Reproduce the data pipeline

Python 3.12 + MySQL 8. Install `requirements.txt`, configure `.env`, then run `python -m scripts.run_pipeline` from the repository root. The bundled CSVs can be used directly; `python -m scripts.generate_data` regenerates the sample. The configured user needs database/table creation permissions.

Run checks with `pip install -r requirements-dev.txt` then `python -m pytest -q`. LTV includes zero-purchase acquired customers and only fully observed horizons. `ANALYTICS_AS_OF_DATE` specifies the actual observation end; otherwise it is inferred conservatively from the latest source observation. Never set it to a future date just to make a cohort mature.

Attribution preserves unassigned orders in an explicit Unattributed channel and distributes whole cents without losing revenue.

## Power BI validation status

The original PBIX and screenshots are historical. Python corrections do not modify the binary model automatically. Apply `powerbi/metric_fixes.dax` and complete `powerbi/VALIDATION.md` in Desktop before publishing the dashboard as corrected. CAC/attribution-cohort comparisons are limited by the sample's acquisition information.

The MySQL integration check is `python -m scripts.verify_metrics`. CI rebuilds twice against MySQL 8 and verifies per-order conservation for all four attribution models, purchase/customer identity and LTV domain constraints.

## Refresh a Desktop copy without a local Python environment

The metrics workflow tests against MySQL 8.0.42 and publishes a `marketing-corrected-mysql-snapshot` artifact after the pipeline passes. Its `marketing_corregido.sql` file creates **analytics_portfolio_corrected** and imports the eight corrected tables. It does not drop or overwrite the original `analytics_portfolio` database. This is a one-time import into a fresh destination; an existing destination must be handled explicitly before a repeat import.

CI restores the SQL into a separate database, compares primary-key-ordered row hashes and row counts for every table, reruns metric invariants, and verifies the source database remains unchanged. `snapshot-validation.json` records those checks and the snapshot hash.

In Power BI, change the MySQL database and any Power Query navigation schema keys to `analytics_portfolio_corrected`. Preserve the existing Power Query query names so the DAX table references remain valid. Then refresh, complete the Desktop checklist, and save a new PBIX. Display LTV and purchasing-customer cost separately rather than a ratio of mismatched cohort/period populations.
