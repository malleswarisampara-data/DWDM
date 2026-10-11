"""Dashboard, customer behavior, and explainable sales forecasting queries."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LinearRegression


ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = ROOT / "data" / "warehouse.db"


def query_rows(query, parameters=(), database_path=DEFAULT_DATABASE):
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(query, parameters).fetchall()]


def get_dashboard_data(database_path=DEFAULT_DATABASE):
    metric = query_rows(
        "SELECT COALESCE(SUM(f.sales_amount), 0) AS revenue, "
        "COUNT(DISTINCT f.order_id) AS orders, "
        "COUNT(DISTINCT f.customer_key) AS customers "
        "FROM Fact_Sales f",
        database_path=database_path,
    )[0]
    metric["average_order_value"] = metric["revenue"] / metric["orders"] if metric["orders"] else 0

    monthly_sales = query_rows(
        "SELECT printf('%04d-%02d', d.year, d.month) AS month, "
        "ROUND(SUM(f.sales_amount), 2) AS revenue, SUM(f.quantity) AS units "
        "FROM Fact_Sales f JOIN Dim_Date d ON d.date_key = f.date_key "
        "GROUP BY d.year, d.month ORDER BY d.year, d.month",
        database_path=database_path,
    )
    category_sales = query_rows(
        "SELECT p.category AS category, ROUND(SUM(f.sales_amount), 2) AS revenue, "
        "SUM(f.quantity) AS units FROM Fact_Sales f "
        "JOIN Dim_Product p ON p.product_key = f.product_key "
        "GROUP BY p.category ORDER BY revenue DESC",
        database_path=database_path,
    )
    top_products = query_rows(
        "SELECT p.product_name AS product, p.category, SUM(f.quantity) AS units, "
        "ROUND(SUM(f.sales_amount), 2) AS revenue FROM Fact_Sales f "
        "JOIN Dim_Product p ON p.product_key = f.product_key "
        "GROUP BY p.product_key ORDER BY units DESC LIMIT 5",
        database_path=database_path,
    )

    return {
        "metrics": {
            "total_revenue": round(metric["revenue"], 2),
            "total_orders": metric["orders"],
            "total_customers": metric["customers"],
            "average_order_value": round(metric["average_order_value"], 2),
        },
        "monthly_sales": monthly_sales,
        "category_sales": category_sales,
        "top_products": top_products,
    }


def get_product_catalog(database_path=DEFAULT_DATABASE):
    return query_rows(
        "SELECT DISTINCT category FROM Dim_Product ORDER BY category",
        database_path=database_path,
    )


def get_products_for_category(category, database_path=DEFAULT_DATABASE):
    return query_rows(
        "SELECT product_name AS product FROM Dim_Product WHERE category = ? ORDER BY product_name",
        (category,),
        database_path,
    )


def get_forecast(category, product, periods=1, database_path=DEFAULT_DATABASE):
    periods = int(periods)
    if not 1 <= periods <= 12:
        raise ValueError("Choose a prediction period from 1 to 12 months.")

    product_rows = query_rows(
        "SELECT product_key, unit_price FROM Dim_Product WHERE category = ? AND product_name = ?",
        (category, product),
        database_path,
    )
    if not product_rows:
        raise ValueError("That product does not belong to the selected category.")

    monthly = query_rows(
        "SELECT d.year, d.month, SUM(f.quantity) AS units, ROUND(SUM(f.sales_amount), 2) AS revenue "
        "FROM Fact_Sales f JOIN Dim_Date d ON d.date_key = f.date_key "
        "WHERE f.product_key = ? GROUP BY d.year, d.month ORDER BY d.year, d.month",
        (product_rows[0]["product_key"],),
        database_path,
    )
    if len(monthly) < 3:
        raise ValueError("At least three months of history are needed for a forecast.")

    monthly_frame = pd.DataFrame(monthly)
    monthly_frame["period"] = pd.PeriodIndex.from_fields(
        year=monthly_frame["year"], month=monthly_frame["month"], freq="M"
    )
    complete_periods = pd.period_range(monthly_frame["period"].min(), monthly_frame["period"].max(), freq="M")
    monthly_series = monthly_frame.set_index("period")["units"].reindex(complete_periods, fill_value=0).astype(float)

    model = LinearRegression()
    time_steps = list(range(len(monthly_series)))
    model.fit([[step] for step in time_steps], monthly_series.to_numpy())

    future_steps = list(range(len(monthly_series), len(monthly_series) + periods))
    predictions = model.predict([[step] for step in future_steps])
    current = monthly_frame.iloc[-1]
    future = []
    for step, prediction in zip(future_steps, predictions):
        future_period = complete_periods[-1] + (step - len(monthly_series) + 1)
        forecast_units = max(0, int(round(prediction)))
        future.append(
            {
                "month": str(future_period),
                "label": future_period.strftime("%b %Y"),
                "units": forecast_units,
                "revenue": round(forecast_units * product_rows[0]["unit_price"], 2),
            }
        )

    slope = float(model.coef_[0])
    trend = "Increasing" if slope > 0.5 else "Decreasing" if slope < -0.5 else "Stable"
    history = [
        {
            "month": str(period),
            "label": period.strftime("%b %Y"),
            "units": int(monthly_series.loc[period]),
            "revenue": round(float(monthly_frame.loc[monthly_frame["period"] == period, "revenue"].iloc[0]), 2)
            if period in monthly_frame["period"].values
            else 0,
        }
        for period in complete_periods
    ]

    return {
        "category": category,
        "product": product,
        "method": "Linear regression on monthly units sold",
        "trend": trend,
        "monthly_slope": round(slope, 2),
        "current_period": current["period"].strftime("%B %Y"),
        "current_units": int(current["units"]),
        "current_revenue": round(float(current["revenue"]), 2),
        "historical": history,
        "predictions": future,
    }


def get_customer_analytics(database_path=DEFAULT_DATABASE):
    customers = query_rows(
        "SELECT c.customer_id, c.customer_name, COUNT(DISTINCT f.order_id) AS order_count, "
        "ROUND(SUM(f.sales_amount), 2) AS total_spent, "
        "GROUP_CONCAT(DISTINCT p.category) AS categories, "
        "GROUP_CONCAT(DISTINCT p.product_name) AS products, "
        "(SELECT COUNT(DISTINCT year * 100 + month) FROM Dim_Date) AS observed_months "
        "FROM Fact_Sales f JOIN Dim_Customer c ON c.customer_key = f.customer_key "
        "JOIN Dim_Product p ON p.product_key = f.product_key "
        "GROUP BY c.customer_key ORDER BY total_spent DESC",
        database_path=database_path,
    )
    spends = pd.Series([customer["total_spent"] for customer in customers], dtype=float)
    low_boundary = float(spends.quantile(0.25)) if not spends.empty else 0
    high_boundary = float(spends.quantile(0.75)) if not spends.empty else 0

    segments = {"High Value": 0, "Regular": 0, "Low Value": 0}
    for customer in customers:
        spend = customer["total_spent"]
        segment = "High Value" if spend >= high_boundary else "Low Value" if spend <= low_boundary else "Regular"
        segments[segment] += 1
        customer["segment"] = segment
        customer["average_order_value"] = round(spend / customer["order_count"], 2)
        customer["purchase_frequency"] = round(customer["order_count"] / customer["observed_months"], 2)
        customer["categories"] = customer["categories"].split(",") if customer["categories"] else []
        customer["products"] = customer["products"].split(",") if customer["products"] else []
        del customer["observed_months"]

    return {
        "customers": customers,
        "segments": [{"segment": name, "customers": count} for name, count in segments.items()],
        "thresholds": {"low_value_max": round(low_boundary, 2), "high_value_min": round(high_boundary, 2)},
    }