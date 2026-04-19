import pandas as pd
import pytest
from unittest.mock import patch, AsyncMock
from app.services.data_fetcher import parse_massive_response, get_cache_path, is_cache_fresh


def test_parse_massive_response_returns_dataframe():
    raw = {
        "results": [
            {"t": 1609459200000, "o": 130.0, "h": 133.0, "l": 129.0, "c": 132.0, "v": 1000000},
            {"t": 1609545600000, "o": 132.0, "h": 135.0, "l": 131.0, "c": 134.0, "v": 1100000},
        ]
    }
    df = parse_massive_response(raw)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 2
    assert df.index.name == "date"


def test_parse_empty_response_returns_empty_df():
    raw = {"results": []}
    df = parse_massive_response(raw)
    assert len(df) == 0


def test_get_cache_path_contains_ticker():
    path = get_cache_path("AAPL")
    assert "AAPL" in str(path)
    assert str(path).endswith(".parquet")


def test_is_cache_fresh_returns_false_for_nonexistent(tmp_path):
    from pathlib import Path
    result = is_cache_fresh(tmp_path / "nonexistent.parquet")
    assert result is False
