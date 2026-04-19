import pytest
from app.services.sp500_universe import get_top5, ALL_TICKERS

def test_get_top5_2000():
    result = get_top5(2000)
    assert len(result) == 5
    assert "GE" in result
    assert "MSFT" in result

def test_get_top5_2024():
    result = get_top5(2024)
    assert "NVDA" in result
    assert "AAPL" in result
    assert len(result) == 5

def test_get_top5_unknown_year_raises():
    with pytest.raises(ValueError):
        get_top5(1999)

def test_all_tickers_contains_expected():
    assert "BRK-B" in ALL_TICKERS
    assert "GOOGL" in ALL_TICKERS
    assert "MSFT" in ALL_TICKERS
    assert len(ALL_TICKERS) >= 15  # at least 15 unique tickers
