# EV Charging Parts — Supply Chain Optimizer

An inventory reorder-point optimizer for a **mock mid-size distributor of EV
charging components** (connectors, cables, control boards, power modules,
enclosures). It computes the replenishment math procurement teams actually use,
and uses an **AI model** to turn the raw numbers into a plain-English risk briefing.

Built with **Python**, **Streamlit**, and an **LLM API** (tool use).

---

## What it does

- Tracks SKUs across suppliers with demand, lead time, and stock levels.
- Computes, per SKU:
  - **Safety stock** — `z × demand_std × √lead_time`, sized to a service level
  - **Reorder point** — `avg_daily_demand × lead_time + safety_stock`
  - **Economic Order Quantity (EOQ)** — `√(2 × annual_demand × order_cost / holding_cost)`
- Flags which SKUs need a purchase order and suggests order quantities.
- Aggregates **supplier concentration risk** (SKUs per supplier, lead times, open PO value).
- **AI risk briefing:** the model inspects the live inventory through tool calls and
  writes a decision-ready briefing for the procurement review.

## How it's laid out

```
supply-chain-optimizer/
├── app.py                 # Streamlit dashboard
├── data/
│   └── inventory.csv      # Mock EV-parts catalog (12 SKUs)
├── src/
│   ├── inventory.py       # Core planning math (reorder point, safety stock, EOQ)
│   ├── data.py            # CSV -> SKU objects
│   └── assistant.py       # AI risk assistant (tool use)
└── tests/
    └── test_inventory.py  # Unit tests for the math
```

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your API key (only needed for the AI briefing)
setx ANTHROPIC_API_KEY "..."          # Windows (new terminal after)
# export ANTHROPIC_API_KEY="..."       # macOS/Linux

# 4. Pick the model id to use for the briefing
setx AI_MODEL "..."
```

Get a key at <https://console.anthropic.com/>.

## Run

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints. The dashboard works without an API key;
the **AI risk briefing** button is enabled once `ANTHROPIC_API_KEY` and
`AI_MODEL` are set.

## Test

```bash
pytest
```

## The math, briefly

| Concept | Formula | Why it matters |
|---|---|---|
| Safety stock | `z × σ_demand × √lead_time` | Buffer against demand & lead-time variability |
| Reorder point | `demand × lead_time + safety_stock` | The trigger level for a new order |
| EOQ | `√(2 D S / H)` | Order size that minimizes ordering + holding cost |

`z` comes from the target service level (e.g. 95% → 1.645).

## How the AI layer works

The assistant (`src/assistant.py`) doesn't get the whole catalog pasted into the
prompt. Instead it's given **tools** — `list_reorder_items`, `supplier_risk_summary`,
`get_sku` — and the SDK's tool runner lets the model call them, read the
results, and write the briefing. The model id comes from the `AI_MODEL`
environment variable; point it at a smaller model for cheaper, faster runs.

---

*This is a portfolio / learning project. The business and data are fictional.*
