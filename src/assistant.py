"""AI-powered supply-chain risk assistant.

Rather than dumping the whole inventory into the prompt, the assistant is given
*tools* it can call to query the current state. The model decides which tools to
call, reads the results, and writes a plain-English risk briefing for the
procurement team. This uses the SDK's beta tool runner, which drives the
call -> execute -> loop cycle automatically.
"""
from __future__ import annotations

import json
import os

import anthropic
from anthropic import beta_tool

from .inventory import SKU, reorder_list, supplier_exposure

# Model id is configurable so you can swap in a cheaper, faster one when you're
# iterating locally.
MODEL = os.getenv("AI_MODEL", "")

# The tool functions need access to the current inventory. We stash it in a
# module-level variable that generate_briefing() sets before running the model.
_INVENTORY: list[SKU] = []


def _set_inventory(inventory: list[SKU]) -> None:
    global _INVENTORY
    _INVENTORY = inventory


@beta_tool
def list_reorder_items() -> str:
    """List every SKU that is at or below its reorder point and needs a purchase order.

    Returns a JSON array, most urgent first, where each item includes the supplier,
    lead time, current inventory position, reorder point, days of stock remaining,
    and the suggested order quantity.
    """
    items = []
    for s in reorder_list(_INVENTORY):
        items.append(
            {
                "sku": s.sku,
                "name": s.name,
                "supplier": s.supplier,
                "lead_time_days": s.lead_time_days,
                "inventory_position": s.inventory_position,
                "reorder_point": round(s.reorder_point(), 1),
                "days_of_cover": round(s.days_of_cover(), 1),
                "suggested_order_qty": s.suggested_order_qty(),
                "unit_cost": s.unit_cost,
            }
        )
    return json.dumps(items)


@beta_tool
def supplier_risk_summary() -> str:
    """Summarize exposure per supplier.

    Returns a JSON object keyed by supplier name with the number of SKUs sourced,
    how many of those are currently due for reorder, the longest lead time, and the
    dollar value of stock already on open purchase orders.
    """
    return json.dumps(supplier_exposure(_INVENTORY))


@beta_tool
def get_sku(sku: str) -> str:
    """Get the full planning detail for a single SKU by its code (e.g. "PM-60KW-22")."""
    for s in _INVENTORY:
        if s.sku.lower() == sku.lower():
            return json.dumps(
                {
                    "sku": s.sku,
                    "name": s.name,
                    "category": s.category,
                    "supplier": s.supplier,
                    "unit_cost": s.unit_cost,
                    "avg_daily_demand": s.avg_daily_demand,
                    "lead_time_days": s.lead_time_days,
                    "on_hand": s.on_hand,
                    "on_order": s.on_order,
                    "safety_stock": round(s.safety_stock(), 1),
                    "reorder_point": round(s.reorder_point(), 1),
                    "eoq": round(s.eoq(), 1),
                    "needs_reorder": s.needs_reorder(),
                }
            )
    return json.dumps({"error": f"SKU {sku!r} not found"})


SYSTEM_PROMPT = """\
You are a supply-chain analyst for a mid-size distributor of EV charging \
components (connectors, cables, control boards, power modules, enclosures). \
You write concise, decision-ready risk briefings for the procurement team.

Use the available tools to inspect the current inventory before writing. \
Ground every claim in the numbers the tools return.

Write the briefing as short markdown with these sections:
- **Immediate actions** — SKUs that need a PO now, with supplier, lead time, and suggested quantity.
- **Supplier concentration risk** — where too much depends on one supplier or long lead times.
- **Watch list** — items trending toward a reorder but not there yet.
Keep it tight and specific. No preamble."""

USER_PROMPT = (
    "Review the current inventory and give me a supply-chain risk briefing "
    "for this week's procurement review."
)


def generate_briefing(inventory: list[SKU], model: str = MODEL) -> str:
    """Run the model over the inventory with tool access and return its briefing."""
    if not model:
        raise RuntimeError(
            "No model configured. Set the AI_MODEL environment variable to the "
            "model id you want the briefing to run on."
        )
    _set_inventory(inventory)
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment

    runner = client.beta.messages.tool_runner(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=[list_reorder_items, supplier_risk_summary, get_sku],
        messages=[{"role": "user", "content": USER_PROMPT}],
    )

    final_message = None
    for message in runner:
        final_message = message

    if final_message is None:
        return "_No response from the model._"
    return "".join(b.text for b in final_message.content if b.type == "text")
