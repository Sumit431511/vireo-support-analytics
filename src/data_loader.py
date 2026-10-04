"""Data access functions. Customer data is intentionally not loaded by the app."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import DATA_DIR


@dataclass(frozen=True)
class DataBundle:
    tickets: pd.DataFrame
    agents: pd.DataFrame
    products: pd.DataFrame
    orders: pd.DataFrame


def load_data(data_dir: Path = DATA_DIR) -> DataBundle:
    """Load only the source tables required for the MVP's stated calculations."""
    return DataBundle(
        tickets=pd.read_csv(data_dir / "tickets.csv"),
        agents=pd.read_csv(data_dir / "agents.csv"),
        products=pd.read_csv(data_dir / "products.csv"),
        orders=pd.read_csv(data_dir / "orders.csv"),
    )

