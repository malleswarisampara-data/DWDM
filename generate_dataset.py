"""Generate a repeatable synthetic e-commerce order-line dataset."""

import csv
import random
from calendar import monthrange
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT_FILE = ROOT / "data" / "raw_sales.csv"

PRODUCTS = [
    ("Electronics", "Laptop", 850.00, 18),
    ("Electronics", "Smartphone", 620.00, 30),
    ("Electronics", "Wireless Headphones", 95.00, 44),
    ("Fashion", "Denim Jacket", 72.00, 36),
    ("Fashion", "Running Sneakers", 88.00, 40),
    ("Fashion", "Everyday Backpack", 48.00, 31),
    ("Home Appliances", "Air Fryer", 115.00, 24),
    ("Home Appliances", "Coffee Maker", 79.00, 29),
    ("Home Appliances", "Robot Vacuum", 280.00, 13),
    ("Beauty", "Skincare Set", 54.00, 42),
    ("Beauty", "Hair Dryer", 68.00, 26),
    ("Beauty", "Vitamin C Serum", 32.00, 48),
    ("Sports", "Yoga Mat", 35.00, 38),
    ("Sports", "Adjustable Dumbbells", 190.00, 16),
    ("Sports", "Fitness Tracker", 125.00, 22),
]

FIRST_NAMES = [
    "Aarav", "Aisha", "Amara", "Arjun", "Avery", "Chen", "Dara", "Elena",
    "Fatima", "Gabriel", "Hana", "Ibrahim", "Isla", "Jai", "Kai", "Layla",
    "Leo", "Maya", "Mei", "Noah", "Olivia", "Priya", "Ravi", "Sara", "Zara",
]
LAST_NAMES = [
    "Adams", "Bennett", "Carter", "Das", "Evans", "Fernandez", "Gupta",
    "Hughes", "Iyer", "Johnson", "Khan", "Lee", "Miller", "Patel", "Wong",
]
FIELDNAMES = [
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


def generate_rows():
    randomizer = random.Random(42)
    customers = [
        (f"CUST-{number:04d}", f"{randomizer.choice(FIRST_NAMES)} {randomizer.choice(LAST_NAMES)}")
        for number in range(1, 121)
    ]
    rows = []
    order_number = 0

    for month_index in range(24):
        year = 2024 + month_index // 12
        month = month_index % 12 + 1
        for _ in range(55):
            order_number += 1
            customer_id, customer_name = randomizer.choice(customers)
            day = randomizer.randint(1, monthrange(year, month)[1])
            order_id = f"ORD-{order_number:05d}"
            product_count = randomizer.choices([1, 2, 3], weights=[68, 27, 5])[0]
            selected_products = randomizer.sample(PRODUCTS, product_count)

            for category, product, price, baseline in selected_products:
                category_multiplier = {
                    "Electronics": 1.025,
                    "Fashion": 1.012,
                    "Home Appliances": 1.018,
                    "Beauty": 1.03,
                    "Sports": 1.02,
                }[category]
                trend_multiplier = category_multiplier ** month_index
                seasonal_multiplier = 1.24 if month in (11, 12) else 1.08 if month in (5, 6) else 1
                mean_quantity = baseline * trend_multiplier * seasonal_multiplier / 24
                quantity = max(1, round(randomizer.gauss(mean_quantity, max(1, mean_quantity * 0.24))))
                discount = randomizer.choice([0, 0, 0.05, 0.10, 0.15, 0.20])
                rows.append(
                    {
                        "Order ID": order_id,
                        "Date": f"{year}-{month:02d}-{day:02d}",
                        "Customer ID": customer_id,
                        "Customer Name": customer_name,
                        "Product": product,
                        "Category": category,
                        "Price": f"{price:.2f}",
                        "Quantity": quantity,
                        "Discount": f"{discount:.2f}",
                        "Sales Amount": f"{price * quantity * (1 - discount):.2f}",
                        "Rating": f"{randomizer.uniform(3.2, 5.0):.1f}",
                    }
                )

    return rows


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    rows = generate_rows()
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows):,} order lines at {OUTPUT_FILE}")


if __name__ == "__main__":
    main()