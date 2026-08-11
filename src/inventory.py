"""Core supply-chain inventory math.

Everything a procurement analyst actually uses to decide *when* to reorder and
*how much* to order:

- Safety stock   — buffer against demand/lead-time variability, sized to a service level
- Reorder point  — the inventory position that should trigger a purchase order
- EOQ            — the order quantity that minimizes combined ordering + holding cost

These are textbook operations-management formulas; the point of the module is to
apply them to a real (mock) EV-charging-parts catalog so the numbers mean something.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# z-score for a target cycle service level (probability of not stocking out while
# waiting for a replenishment order to arrive). A few common levels, looked up by
# nearest match so the CSV can use friendly values like 0.95.
SERVICE_LEVEL_Z = {
    0.80: 0.8416,
    0.85: 1.0364,
    0.90: 1.2816,
    0.95: 1.6449,
    0.98: 2.0537,
    0.99: 2.3263,
}

DAYS_PER_YEAR = 365


def z_for_service_level(service_level: float) -> float:
    """Return the z-score for the closest supported service level."""
    nearest = min(SERVICE_LEVEL_Z, key=lambda level: abs(level - service_level))
    return SERVICE_LEVEL_Z[nearest]


@dataclass
class SKU:
    """A single stock-keeping unit and everything needed to plan its replenishment."""

    sku: str
    name: str
    category: str
    supplier: str
    unit_cost: float          # $ per unit
    avg_daily_demand: float   # units/day
    demand_std: float         # std dev of daily demand (units)
    lead_time_days: float     # supplier lead time
    on_hand: int              # units physically in stock
    on_order: int             # units already on a placed PO
    order_cost: float         # fixed $ cost to place one purchase order
    holding_cost_rate: float  # annual holding cost as a fraction of unit cost
    service_level: float = 0.95

    # --- planning calculations ---------------------------------------------

    @property
    def annual_demand(self) -> float:
        return self.avg_daily_demand * DAYS_PER_YEAR

    @property
    def inventory_position(self) -> int:
        """On-hand plus already on order — what you compare against the reorder point."""
        return self.on_hand + self.on_order

    def safety_stock(self) -> float:
        """Buffer stock = z * demand_std * sqrt(lead_time).

        Scales with demand variability and the square root of lead time, and with
        how confident (service level) we want to be about not stocking out.
        """
        z = z_for_service_level(self.service_level)
        return z * self.demand_std * math.sqrt(self.lead_time_days)

    def reorder_point(self) -> float:
        """Expected demand over the lead time, plus safety stock."""
        return self.avg_daily_demand * self.lead_time_days + self.safety_stock()

    def eoq(self) -> float:
        """Economic Order Quantity = sqrt(2 * D * S / H).

        D = annual demand, S = per-order cost, H = annual holding cost per unit.
        The order size that balances ordering frequency against holding cost.
        """
        holding_per_unit = self.holding_cost_rate * self.unit_cost
        if holding_per_unit <= 0:
            return 0.0
        return math.sqrt(2 * self.annual_demand * self.order_cost / holding_per_unit)

    def needs_reorder(self) -> bool:
        return self.inventory_position <= self.reorder_point()

    def days_of_cover(self) -> float:
        """How many days of demand the current on-hand stock covers."""
        if self.avg_daily_demand <= 0:
            return float("inf")
        return self.on_hand / self.avg_daily_demand

    def suggested_order_qty(self) -> int:
        """If a reorder is due, order enough to reach reorder point + EOQ; else 0."""
        if not self.needs_reorder():
            return 0
        target = self.reorder_point() + self.eoq()
        return max(0, math.ceil(target - self.inventory_position))

    def annual_holding_cost(self) -> float:
        """Rough annual holding cost of carrying half an EOQ plus safety stock."""
        holding_per_unit = self.holding_cost_rate * self.unit_cost
        return holding_per_unit * (self.eoq() / 2 + self.safety_stock())


def reorder_list(inventory: list[SKU]) -> list[SKU]:
    """SKUs that are at or below their reorder point, most urgent first."""
    due = [s for s in inventory if s.needs_reorder()]
    # Most urgent = fewest days of cover.
    return sorted(due, key=lambda s: s.days_of_cover())


def supplier_exposure(inventory: list[SKU]) -> dict[str, dict]:
    """Aggregate risk per supplier: SKU count, how many are due, max lead time, PO value."""
    summary: dict[str, dict] = {}
    for s in inventory:
        entry = summary.setdefault(
            s.supplier,
            {"skus": 0, "reorder_due": 0, "max_lead_time_days": 0.0, "open_po_value": 0.0},
        )
        entry["skus"] += 1
        entry["max_lead_time_days"] = max(entry["max_lead_time_days"], s.lead_time_days)
        entry["open_po_value"] += s.on_order * s.unit_cost
        if s.needs_reorder():
            entry["reorder_due"] += 1
    return summary
