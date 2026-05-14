"""
Historical Nasdaq-100 constituency data.

No equivalent of fja05680/sp500 exists for NAS100 with full coverage back to 2000.
Investigated sources:
  - yfiua/index-constituents: only from 2023/07
  - jmccarrell/n100tickers (nasdaq-100-ticker-history): YAML-based, only from 2015
  - Gary-Strauss/NASDAQ100_Constituents: current snapshot only

Result: load_constituents() returns None → candidate-only mode (no constituency filter).
        compute_top5_history will use NAS100_CANDIDATES directly without index membership
        validation. This is acceptable because NAS100_CANDIDATES is curated to only include
        historical Nasdaq-100 top-weight stocks.
"""

import pandas as pd


def load_constituents() -> pd.DataFrame | None:
    """
    Returns None — no reliable historical NAS100 constituency dataset
    covering 2000–2025 is publicly available in a parseable format.
    Falls back to candidate-only mode in compute_top5_history.
    """
    return None


def get_members_on_date(df: pd.DataFrame, dt) -> set[str]:
    """Unused — only present for interface symmetry with sp500_constituents."""
    return set()
