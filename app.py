"""Flask application for the e-commerce analytics project."""

import csv
import io
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from analytics import (
    DEFAULT_DATABASE,
    get_customer_analytics,
    get_dashboard_data,
    get_forecast,
    get_product_catalog,
    get_products_for_category,
)
from etl import DEFAULT_SOURCE, run_etl
from generate_dataset import main as generate_sample_dataset


def ensure_warehouse(database_path=DEFAULT_DATABASE):
    database_path = Path(database_path)
    if database_path.exists():
        return
    if database_path == DEFAULT_DATABASE and not DEFAULT_SOURCE.exists():
        generate_sample_dataset()
    if not DEFAULT_SOURCE.exists():
        raise FileNotFoundError(f"Raw dataset not found: {DEFAULT_SOURCE}")
    run_etl(DEFAULT_SOURCE, database_path)


def create_app(database_path=DEFAULT_DATABASE):
    ensure_warehouse(database_path)
    app = Flask(__name__)
    app.config["DATABASE_PATH"] = Path(database_path)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/dashboard")
    def dashboard():
        return jsonify(get_dashboard_data(app.config["DATABASE_PATH"]))

    @app.get("/api/customers")
    def customers():
        return jsonify(get_customer_analytics(app.config["DATABASE_PATH"]))

    @app.get("/api/catalog")
    def catalog():
        return jsonify({"categories": get_product_catalog(app.config["DATABASE_PATH"])})

    @app.get("/api/products")
    def products():
        category = request.args.get("category", "")
        return jsonify({"products": get_products_for_category(category, app.config["DATABASE_PATH"])})

    @app.get("/api/forecast")
    def forecast():
        try:
            result = get_forecast(
                request.args.get("category", ""),
                request.args.get("product", ""),
                request.args.get("periods", "1"),
                app.config["DATABASE_PATH"],
            )
        except (TypeError, ValueError) as error:
            return jsonify({"error": str(error)}), 400
        return jsonify(result)

    @app.get("/api/exports/customers.csv")
    def export_customer_csv():
        customers_data = get_customer_analytics(app.config["DATABASE_PATH"])["customers"]
        output = io.StringIO()
        fields = [
            "order_count",
            "total_spent",
            "average_order_value",
            "purchase_frequency",
            "distinct_categories",
        ]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for customer in customers_data:
            writer.writerow(
                {
                    "order_count": customer["order_count"],
                    "total_spent": customer["total_spent"],
                    "average_order_value": customer["average_order_value"],
                    "purchase_frequency": customer["purchase_frequency"],
                    "distinct_categories": len(customer["categories"]),
                }
            )
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name="customer_behavior_weka.csv",
        )

    @app.get("/api/exports/customers.arff")
    def export_customer_arff():
        customers_data = get_customer_analytics(app.config["DATABASE_PATH"])["customers"]
        lines = [
            "@RELATION customer_behavior",
            "",
            "@ATTRIBUTE order_count NUMERIC",
            "@ATTRIBUTE total_spent NUMERIC",
            "@ATTRIBUTE average_order_value NUMERIC",
            "@ATTRIBUTE purchase_frequency NUMERIC",
            "@ATTRIBUTE distinct_categories NUMERIC",
            "@ATTRIBUTE segment {High_Value,Regular,Low_Value}",
            "",
            "@DATA",
        ]
        for customer in customers_data:
            segment = customer["segment"].replace(" ", "_")
            lines.append(
                f"{customer['order_count']},{customer['total_spent']},"
                f"{customer['average_order_value']},{customer['purchase_frequency']},"
                f"{len(customer['categories'])},{segment}"
            )
        return send_file(
            io.BytesIO("\n".join(lines).encode("utf-8")),
            mimetype="text/plain",
            as_attachment=True,
            download_name="customer_behavior_weka.arff",
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)