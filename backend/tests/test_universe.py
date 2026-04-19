from app.services.universe import get_tickers


def test_top5_returns_5_tickers():
    tickers = get_tickers(5)
    assert len(tickers) == 5
    assert "AAPL" in tickers
    assert "NVDA" in tickers


def test_top10_returns_10_tickers():
    tickers = get_tickers(10)
    assert len(tickers) == 10


def test_top20_returns_20_tickers():
    tickers = get_tickers(20)
    assert len(tickers) == 20


def test_top10_includes_top5():
    top5 = set(get_tickers(5))
    top10 = set(get_tickers(10))
    assert top5.issubset(top10)


def test_invalid_size_raises():
    import pytest
    with pytest.raises(ValueError):
        get_tickers(99)
