"""Policy-based business-cost calculations kept as separate, non-additive cost lines."""

from __future__ import annotations

import pandas as pd

from .config import (
    BREACH_CREDIT_INR,
    CONTACT_COST_INR,
    REPLACEMENT_LOGISTICS_INR,
    TRANSFER_COST_INR,
)


def calculate_business_impact(tickets: pd.DataFrame, products: pd.DataFrame) -> dict[str, object]:
    """Calculate independently defensible policy cost lines; do not total them together."""
    replacement_rows = tickets.loc[tickets["replacement_issued"].eq("Y")].merge(
        products[["sku", "unit_cost_inr"]], left_on="product_sku", right_on="sku", how="left", validate="many_to_one"
    )
    replacement_rows["replacement_planning_cost_inr"] = replacement_rows["unit_cost_inr"] + REPLACEMENT_LOGISTICS_INR
    contact_cost = tickets["channel"].map(CONTACT_COST_INR)
    breach_count = int(tickets["is_breached"].sum())
    transfer_count = int(tickets["transfers"].sum())
    return {
        "replacement_count": int(len(replacement_rows)),
        "replacement_planning_cost_inr": float(replacement_rows["replacement_planning_cost_inr"].sum(skipna=True)),
        "replacement_missing_product_cost": int(replacement_rows["unit_cost_inr"].isna().sum()),
        "breach_count": breach_count,
        "breach_credit_cost_inr": breach_count * BREACH_CREDIT_INR,
        "contact_operating_cost_inr": float(contact_cost.sum(skipna=True)),
        "unmapped_contact_channels": int(contact_cost.isna().sum()),
        "transfer_count": transfer_count,
        "transfer_rehandling_cost_inr": transfer_count * TRANSFER_COST_INR,
    }

