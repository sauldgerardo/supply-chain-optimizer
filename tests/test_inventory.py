"""Tests for the core inventory math."""
import math

from src.data import load_inventory
from src.inventory import SKU, reorder_list, supplier_exposure, z_for_service_level


def make_sku(**overrides) -> SKU:
    base = dict(
        sku="TST-01",
        name="Test Part",
        category="Test",
        supplier="Test Supplier",
        unit_cost=100.0,
        avg_daily_demand=10.0,
        demand_std=2.0,
        lead_time_days=9.0,
        on_hand=50,
        on_order=0,
        order_cost=50.0,
        holding_cost_rate=0.25,
        service_level=0.95,
    )
    base.update(overrides)
    return SKU(**base)


def test_z_lookup_snaps_to_nearest():
    assert z_for_service_level(0.95) == 1.6449
    # 0.955 is closest to 0.95, not 0.98
    assert z_for_service_level(0.955) == 1.6449


def test_safety_stock_formula():
    s = make_sku(demand_std=2.0, lead_time_days=9.0, service_level=0.95)
    # z * std * sqrt(lead_time) = 1.6449 * 2 * 3
    assert math.isclose(s.safety_stock(), 1.6449 * 2 * 3, rel_tol=1e-6)


def test_reorder_point_includes_safety_stock():
    s = make_sku(avg_daily_demand=10.0, lead_time_days=9.0)
    # demand over lead time (90) + safety stock
    assert math.isclose(s.reorder_point(), 90 + s.safety_stock(), rel_tol=1e-9)


def test_eoq_formula():
    s = make_sku(avg_daily_demand=10.0, order_cost=50.0, unit_cost=100.0, holding_cost_rate=0.25)
    annual_demand = 10.0 * 365
    holding_per_unit = 0.25 * 100.0
    expected = math.sqrt(2 * annual_demand * 50.0 / holding_per_unit)
    assert math.isclose(s.eoq(), expected, rel_tol=1e-9)


def test_needs_reorder_true_when_below_point():
    s = make_sku(on_hand=10, on_order=0)  # position 10 << reorder point ~100
    assert s.needs_reorder()
    assert s.suggested_order_qty() > 0


def test_needs_reorder_false_when_well_stocked():
    s = make_sku(on_hand=500, on_order=0)
    assert not s.needs_reorder()
    assert s.suggested_order_qty() == 0


def test_inventory_position_counts_on_order():
    s = make_sku(on_hand=40, on_order=60)
    assert s.inventory_position == 100


def test_reorder_list_sorted_by_urgency():
    urgent = make_sku(sku="URGENT", on_hand=5, avg_daily_demand=10)   # 0.5 days cover
    less = make_sku(sku="LESS", on_hand=20, avg_daily_demand=10)      # 2 days cover
    due = reorder_list([less, urgent])
    assert [s.sku for s in due] == ["URGENT", "LESS"]


def test_supplier_exposure_aggregates():
    a = make_sku(sku="A", supplier="Acme", on_hand=5, lead_time_days=30)
    b = make_sku(sku="B", supplier="Acme", on_hand=500, lead_time_days=10, on_order=2)
    exposure = supplier_exposure([a, b])
    assert exposure["Acme"]["skus"] == 2
    assert exposure["Acme"]["reorder_due"] == 1
    assert exposure["Acme"]["max_lead_time_days"] == 30


def test_sample_data_loads():
    inventory = load_inventory()
    assert len(inventory) == 12
    assert all(s.unit_cost > 0 for s in inventory)
