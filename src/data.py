"""Load the SKU catalog from CSV into `SKU` objects."""
from __future__ import annotations

import csv
from pathlib import Path

from .inventory import SKU

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "inventory.csv"


def load_inventory(path: Path | str = DATA_FILE) -> list[SKU]:
    """Read the inventory CSV and return a list of SKU objects."""
    rows: list[SKU] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(
                SKU(
                    sku=row["sku"],
                    name=row["name"],
                    category=row["category"],
                    supplier=row["supplier"],
                    unit_cost=float(row["unit_cost"]),
                    avg_daily_demand=float(row["avg_daily_demand"]),
                    demand_std=float(row["demand_std"]),
                    lead_time_days=float(row["lead_time_days"]),
                    on_hand=int(row["on_hand"]),
                    on_order=int(row["on_order"]),
                    order_cost=float(row["order_cost"]),
                    holding_cost_rate=float(row["holding_cost_rate"]),
                    service_level=float(row["service_level"]),
                )
            )
    return rows
