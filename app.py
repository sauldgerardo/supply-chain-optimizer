"""Streamlit dashboard for the EV-charging-parts reorder optimizer.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from src.data import load_inventory
from src.inventory import reorder_list, supplier_exposure

st.set_page_config(page_title="EV Parts Supply Chain", page_icon="⚡", layout="wide")


@st.cache_data
def _load() -> list:
    return load_inventory()


def inventory_frame(inventory) -> pd.DataFrame:
    """Build the display table with all planning columns computed."""
    records = []
    for s in inventory:
        records.append(
            {
                "SKU": s.sku,
                "Name": s.name,
                "Category": s.category,
                "Supplier": s.supplier,
                "On hand": s.on_hand,
                "On order": s.on_order,
                "Lead time (d)": s.lead_time_days,
                "Safety stock": round(s.safety_stock(), 1),
                "Reorder point": round(s.reorder_point(), 1),
                "EOQ": round(s.eoq(), 1),
                "Days cover": round(s.days_of_cover(), 1),
                "Reorder?": "🔴 YES" if s.needs_reorder() else "🟢 ok",
                "Suggested qty": s.suggested_order_qty(),
            }
        )
    return pd.DataFrame(records)


inventory = _load()

st.title("⚡ EV Charging Parts — Supply Chain Optimizer")
st.caption(
    "Mock inventory for a mid-size EV-charging-components distributor. "
    "Reorder points, safety stock, and EOQ are computed from demand and lead-time data."
)

# --- KPI row ---------------------------------------------------------------
due = reorder_list(inventory)
open_po_value = sum(s.on_order * s.unit_cost for s in inventory)
inventory_value = sum(s.on_hand * s.unit_cost for s in inventory)

c1, c2, c3, c4 = st.columns(4)
c1.metric("SKUs tracked", len(inventory))
c2.metric("Need reorder", len(due))
c3.metric("On-hand value", f"${inventory_value:,.0f}")
c4.metric("Open PO value", f"${open_po_value:,.0f}")

# --- Inventory table -------------------------------------------------------
st.subheader("Inventory & replenishment plan")
df = inventory_frame(inventory)
only_due = st.checkbox("Show only SKUs that need reordering")
if only_due:
    df = df[df["Reorder?"].str.contains("YES")]
st.dataframe(df, use_container_width=True, hide_index=True)

# --- Purchase order suggestions -------------------------------------------
if due:
    st.subheader("Suggested purchase orders")
    po_rows = [
        {
            "SKU": s.sku,
            "Name": s.name,
            "Supplier": s.supplier,
            "Order qty": s.suggested_order_qty(),
            "Est. cost": f"${s.suggested_order_qty() * s.unit_cost:,.0f}",
            "Lead time (d)": s.lead_time_days,
        }
        for s in due
    ]
    st.table(pd.DataFrame(po_rows))

# --- Supplier exposure -----------------------------------------------------
st.subheader("Supplier exposure")
exposure = supplier_exposure(inventory)
exp_df = pd.DataFrame(
    [
        {
            "Supplier": name,
            "SKUs": e["skus"],
            "Reorder due": e["reorder_due"],
            "Max lead time (d)": e["max_lead_time_days"],
            "Open PO value": f"${e['open_po_value']:,.0f}",
        }
        for name, e in exposure.items()
    ]
)
st.dataframe(exp_df, use_container_width=True, hide_index=True)

# --- AI risk briefing ------------------------------------------------------
st.subheader("AI risk briefing")
st.caption("The assistant inspects the live inventory via tool calls and writes a briefing.")

if not (os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("AI_MODEL")):
    st.info("Set the `ANTHROPIC_API_KEY` and `AI_MODEL` environment variables to enable the AI briefing.")
else:
    if st.button("Generate risk briefing"):
        with st.spinner("Analyzing the inventory…"):
            from src.assistant import generate_briefing

            try:
                briefing = generate_briefing(inventory)
                st.markdown(briefing)
            except Exception as exc:  # surface API/config errors in the UI
                st.error(f"Could not generate briefing: {exc}")
