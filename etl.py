"""Clean raw order lines and load the SQLite sales star schema."""

import argparse
import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / "data" / "raw_sales.csv"
DEFAULT_DATABASE = ROOT / "data" / "warehouse.db"
REQUIRED_COLUMNS = [
    "Order ID",
    "Date",
    "Customer ID",
    "Customer Name",
    "Product",
    "Category",
    "Price",
    "Quantity",
    "Discount",
    "Sales Amount",
    "Rating",
]


def clean_data(raw_data):
    """Normalize columns, remove invalid rows, and recompute net sales."""
    missing_columns = set(REQUIRED_COLUMNS) - set(raw_data.columns)
    if missing_columns:
        raise ValueError(f"Dataset is missing columns: {', '.join(sorted(missing_columns))}")

    data = raw_data[REQUIRED_COLUMNS].copy()
    text_columns = ["Order ID", "Customer ID", "Customer Name", "Product", "Category"]
    for column in text_columns:
        data[column] = data[column].astype("string").str.strip()

    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    numeric_columns = ["Price", "Quantity", "Discount", "Sales Amount", "Rating"]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    valid = (
        data[REQUIRED_COLUMNS].notna().all(axis=1)
        & data[text_columns].ne("").all(axis=1)
        & data["Price"].gt(0)
        & data["Quantity"].gt(0)
        & data["Discount"].between(0, 1)
        & data["Rating"].between(1, 5)
    )
    data = data.loc[valid].drop_duplicates(subset=["Order ID", "Product"]).copy()
    data["Quantity"] = data["Quantity"].astype(int)
    data["Sales Amount"] = (data["Price"] * data["Quantity"] * (1 - data["Discount"])).round(2)
    return data.sort_values(["Date", "Order ID", "Product"]).reset_index(drop=True)


def load_warehouse(data, database_path=DEFAULT_DATABASE):
    """Create or refresh the four-table warehouse from cleaned rows."""
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    customers = data[["Customer ID", "Customer Name"]].drop_duplicates("Customer ID").sort_values("Customer ID")
    products = data[["Product", "Category", "Price"]].drop_duplicates("Product").sort_values("Product")
    dates = data[["Date"]].drop_duplicates().sort_values("Date").copy()
    dates["date_key"] = dates["Date"].dt.strftime("%Y%m%d").astype(int)
    dates["year"] = dates["Date"].dt.year
    dates["month"] = dates["Date"].dt.month
    dates["month_name"] = dates["Date"].dt.strftime("%B")
    dates["quarter"] = dates["Date"].dt.quarter

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS Dim_Customer (
                customer_key INTEGER PRIMARY KEY,
                customer_id TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS Dim_Product (
                product_key INTEGER PRIMARY KEY,
                product_name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                unit_price REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS Dim_Date (
                date_key INTEGER PRIMARY KEY,
                full_date TEXT NOT NULL UNIQUE,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                month_name TEXT NOT NULL,
                quarter INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS Fact_Sales (
                sales_key INTEGER PRIMARY KEY,
                order_id TEXT NOT NULL,
                customer_key INTEGER NOT NULL REFERENCES Dim_Customer(customer_key),
                product_key INTEGER NOT NULL REFERENCES Dim_Product(product_key),
                date_key INTEGER NOT NULL REFERENCES Dim_Date(date_key),
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                discount REAL NOT NULL,
                sales_amount REAL NOT NULL,
                rating REAL NOT NULL
            );
            """
        )
        connection.execute("DELETE FROM Fact_Sales")
        connection.execute("DELETE FROM Dim_Customer")
        connection.execute("DELETE FROM Dim_Product")
        connection.execute("DELETE FROM Dim_Date")

        customer_keys = {}
        for row in customers.itertuples(index=False, name=None):
            cursor = connection.execute(
                "INSERT INTO Dim_Customer (customer_id, customer_name) VALUES (?, ?)", row
            )
            customer_keys[row[0]] = cursor.lastrowid

        product_keys = {}
        for row in products.itertuples(index=False, name=None):
            cursor = connection.execute(
                "INSERT INTO Dim_Product (product_name, category, unit_price) VALUES (?, ?, ?)", row
            )
            product_keys[row[0]] = cursor.lastrowid

        for row in dates.itertuples(index=False, name=None):
            connection.execute(
                "INSERT INTO Dim_Date (date_key, full_date, year, month, month_name, quarter) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (row[1], row[0].strftime("%Y-%m-%d"), row[2], row[3], row[4], row[5]),
            )

        date_keys = dict(zip(dates["Date"].dt.strftime("%Y-%m-%d"), dates["date_key"]))
        fact_rows = [
            (
                row["Order ID"],
                customer_keys[row["Customer ID"]],
                product_keys[row["Product"]],
                date_keys[row["Date"].strftime("%Y-%m-%d")],
                row["Price"],
                row["Quantity"],
                row["Discount"],
                row["Sales Amount"],
                row["Rating"],
            )
            for _, row in data.iterrows()
        ]
        connection.executemany(
            "INSERT INTO Fact_Sales "
            "(order_id, customer_key, product_key, date_key, price, quantity, discount, sales_amount, rating) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            fact_rows,
        )
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("Fact_Sales", "Dim_Customer", "Dim_Product", "Dim_Date")
        }
    connection.close()
    return counts


def run_etl(source_path=DEFAULT_SOURCE, database_path=DEFAULT_DATABASE):
    raw_data = pd.read_csv(source_path)
    cleaned_data = clean_data(raw_data)
    counts = load_warehouse(cleaned_data, database_path)
    print(f"ETL complete: {len(raw_data):,} raw rows, {len(cleaned_data):,} clean rows")
    for table, count in counts.items():
        print(f"  {table}: {count:,}")
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Path to the raw CSV file")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE, help="Path for the SQLite warehouse")
    arguments = parser.parse_args()
    run_etl(arguments.source, arguments.database)