# E-Commerce Sales & Customer Behavior Analytics

A college DWDM mini-project using a Flask dashboard, a SQLite star schema, monthly sales analysis, customer value segments, and an explainable demand forecast.

## Requirements

- Python 3.10 or later
- VS Code with the Microsoft Python extension
- Internet access when loading Bootstrap, Chart.js, and the optional web fonts from their CDNs
- WEKA is optional; it is only needed to explore the downloaded mining datasets

## Run on Windows

Open this folder in VS Code, choose **Terminal → New Terminal**, then run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe generate_dataset.py
.\.venv\Scripts\python.exe etl.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe app.py
```

Open <http://127.0.0.1:5000>. Stop the development server with **Ctrl+C**. The SQLite warehouse is created at `data/warehouse.db`; it can be rebuilt by running `etl.py` again. The generated source data is deterministic, so running its generator again recreates the same 24-month sample.

In VS Code, use **Ctrl+Shift+P → Python: Select Interpreter** and select `.venv\Scripts\python.exe` so the editor uses the project's dependencies.

## Sample dataset

`generate_dataset.py` creates 24 months of synthetic order-line records for 120 customers and 15 products across Electronics, Fashion, Home Appliances, Beauty, and Sports. The CSV includes order ID, date, customer ID and name, product, category, price, quantity, discount, sales amount, and rating. The fixed random seed makes the sample repeatable; it is demonstration data, not real customer information.

## Warehouse and ETL

The fact-table grain is one product line on an order. `etl.py` trims text, parses dates and numeric values, removes incomplete or invalid rows and duplicate order/product lines, and recalculates net sales as `price × quantity × (1 − discount)`.

| Table | Role |
| --- | --- |
| `Fact_Sales` | Order ID, customer/product/date keys, price, quantity, discount, net sales, and rating |
| `Dim_Customer` | Customer identifier and name |
| `Dim_Product` | Product, category, and unit price |
| `Dim_Date` | Calendar date, year, month, month name, and quarter |

## Analytics and prediction

- Total orders count distinct order IDs. Average order value is total net revenue divided by distinct orders.
- Customer purchase frequency is order count divided by the number of observed months. Spending segments use the customer-spend 25th and 75th percentiles.
- The forecast aggregates units by calendar month, fills missing product months with zero, fits a scikit-learn linear regression on time, and clips negative predictions to zero. The estimate is useful for demonstrating trend-based demand prediction, not a production inventory decision.
- Estimated forecast revenue uses product list price and does not project future discounts. The model does not account for seasonality, promotions, or uncertainty.

## WEKA datasets

Use **WEKA CSV** in the customer section to download numeric customer features for SimpleKMeans. The ARFF download includes the same numeric fields and a quartile-derived `segment` class; in WEKA Explorer, set `segment` as the class for a J48 demonstration. The class is derived from spending rules in this sample, so it illustrates the workflow rather than providing independent ground-truth labels.

## Project layout

```text
app.py                  Flask routes and WEKA exports
analytics.py            Dashboard queries, customer analysis, regression
etl.py                  Data cleaning and SQLite star-schema loading
generate_dataset.py     Reproducible synthetic source-data generator
data/raw_sales.csv      Generated source dataset
templates/index.html    Dashboard structure
static/css/styles.css   Responsive dashboard styles
static/js/dashboard.js  Charts, filters, and forecast interactions
tests/                  ETL, analytics, and Flask route tests
```