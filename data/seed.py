"""
Seeds a SQLite 'gold-layer' star-schema warehouse for the GenBI-Lab demo.

Schema (procurement / supply-chain domain):
    fact_purchase_orders  -- grain: one row per purchase-order line
    dim_supplier, dim_product, dim_warehouse, dim_date

Data is generated with a fixed RNG seed so benchmark gold answers stay stable.
"""
import os
import sqlite3
import random
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "warehouse.db")
RNG = random.Random(42)

SUPPLIERS = [
    # name, country, tier, risk_rating
    ("Acme Components", "USA", "Tier 1", "Low"),
    ("Nordic Steelworks", "Sweden", "Tier 1", "Low"),
    ("Shenzhen Precision", "China", "Tier 2", "Medium"),
    ("Bavaria Castings", "Germany", "Tier 1", "Low"),
    ("Gujarat Polymers", "India", "Tier 2", "Medium"),
    ("Pacific Fasteners", "USA", "Tier 3", "High"),
    ("Andes Mining Co", "Chile", "Tier 2", "High"),
    ("Kyoto Electronics", "Japan", "Tier 1", "Low"),
]

PRODUCTS = [
    # name, category, subcategory
    ("Brass Valve 1in", "Plumbing", "Valves"),
    ("Ceramic Cartridge", "Plumbing", "Cartridges"),
    ("Stainless Bolt M8", "Hardware", "Fasteners"),
    ("Copper Tubing 10ft", "Plumbing", "Tubing"),
    ("Control PCB v3", "Electronics", "Boards"),
    ("Rubber Gasket Set", "Hardware", "Seals"),
    ("Cast Iron Sink Base", "Fixtures", "Castings"),
    ("LED Sensor Module", "Electronics", "Sensors"),
    ("Powder-Coat Pigment", "Materials", "Coatings"),
    ("Aluminium Trim 4ft", "Fixtures", "Trim"),
]

WAREHOUSES = [
    ("Kohler WI Hub", "Midwest"),
    ("Dallas DC", "South"),
    ("Reno DC", "West"),
    ("Atlanta DC", "South"),
]


def build_schema(cur):
    cur.executescript(
        """
        DROP TABLE IF EXISTS fact_purchase_orders;
        DROP TABLE IF EXISTS dim_supplier;
        DROP TABLE IF EXISTS dim_product;
        DROP TABLE IF EXISTS dim_warehouse;
        DROP TABLE IF EXISTS dim_date;

        CREATE TABLE dim_supplier (
            supplier_key INTEGER PRIMARY KEY,
            supplier_name TEXT NOT NULL,
            country TEXT,
            tier TEXT,
            risk_rating TEXT
        );
        CREATE TABLE dim_product (
            product_key INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT,
            subcategory TEXT
        );
        CREATE TABLE dim_warehouse (
            warehouse_key INTEGER PRIMARY KEY,
            warehouse_name TEXT NOT NULL,
            region TEXT
        );
        CREATE TABLE dim_date (
            date_key INTEGER PRIMARY KEY,
            full_date TEXT,
            month INTEGER,
            quarter INTEGER,
            year INTEGER
        );
        CREATE TABLE fact_purchase_orders (
            po_id INTEGER PRIMARY KEY,
            date_key INTEGER REFERENCES dim_date(date_key),
            supplier_key INTEGER REFERENCES dim_supplier(supplier_key),
            product_key INTEGER REFERENCES dim_product(product_key),
            warehouse_key INTEGER REFERENCES dim_warehouse(warehouse_key),
            order_qty INTEGER,
            unit_cost REAL,
            total_cost REAL,
            lead_time_days INTEGER,
            on_time_flag INTEGER,   -- 1 = delivered on time, 0 = late
            defect_qty INTEGER
        );
        """
    )


def seed_dimensions(cur):
    for i, (name, country, tier, risk) in enumerate(SUPPLIERS, start=1):
        cur.execute(
            "INSERT INTO dim_supplier VALUES (?,?,?,?,?)",
            (i, name, country, tier, risk),
        )
    for i, (name, cat, sub) in enumerate(PRODUCTS, start=1):
        cur.execute("INSERT INTO dim_product VALUES (?,?,?,?)", (i, name, cat, sub))
    for i, (name, region) in enumerate(WAREHOUSES, start=1):
        cur.execute("INSERT INTO dim_warehouse VALUES (?,?,?)", (i, name, region))

    # two years of dates: 2024-2025
    start = date(2024, 1, 1)
    for n in range((date(2026, 1, 1) - start).days):
        d = start + timedelta(days=n)
        dk = int(d.strftime("%Y%m%d"))
        quarter = (d.month - 1) // 3 + 1
        cur.execute(
            "INSERT INTO dim_date VALUES (?,?,?,?,?)",
            (dk, d.isoformat(), d.month, quarter, d.year),
        )


def seed_facts(cur):
    cur.execute("SELECT date_key FROM dim_date")
    date_keys = [r[0] for r in cur.fetchall()]
    base_cost = {i: round(RNG.uniform(4, 220), 2) for i in range(1, len(PRODUCTS) + 1)}

    for po_id in range(1, 4001):
        dk = RNG.choice(date_keys)
        sup = RNG.randint(1, len(SUPPLIERS))
        prod = RNG.randint(1, len(PRODUCTS))
        wh = RNG.randint(1, len(WAREHOUSES))
        qty = RNG.randint(10, 600)
        unit = round(base_cost[prod] * RNG.uniform(0.9, 1.15), 2)
        total = round(qty * unit, 2)
        # higher-risk suppliers run later and more defective
        risk = SUPPLIERS[sup - 1][3]
        late_bias = {"Low": 0.10, "Medium": 0.22, "High": 0.38}[risk]
        lead = RNG.randint(3, 14) + (8 if risk == "High" else 0)
        on_time = 0 if RNG.random() < late_bias else 1
        defect_rate = {"Low": 0.004, "Medium": 0.012, "High": 0.03}[risk]
        defects = int(qty * defect_rate * RNG.uniform(0, 2))
        cur.execute(
            "INSERT INTO fact_purchase_orders VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (po_id, dk, sup, prod, wh, qty, unit, total, lead, on_time, defects),
        )


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    build_schema(cur)
    seed_dimensions(cur)
    seed_facts(cur)
    conn.commit()
    cur.execute("SELECT COUNT(*), ROUND(SUM(total_cost),2) FROM fact_purchase_orders")
    n, spend = cur.fetchone()
    conn.close()
    print(f"Seeded {DB_PATH}: {n} purchase orders, total spend ${spend:,.2f}")


if __name__ == "__main__":
    main()
