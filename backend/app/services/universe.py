# S&P 500 — primary universe (hardcoded fallback)
SP500_TOP5 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"]

SP500_TOP10 = SP500_TOP5 + ["META", "TSLA", "AVGO", "BRK-B", "JPM"]

# NAS100 — add-on universe (hardcoded fallback)
NAS100_TOP5 = ["AAPL", "MSFT", "NVDA", "AMZN", "META"]

NAS100_TOP10 = NAS100_TOP5 + ["GOOGL", "AVGO", "TSLA", "COST", "NFLX"]

NAS100_TOP20 = NAS100_TOP10 + [
    "AMD", "ADBE", "PEP", "CSCO", "INTC",
    "CMCSA", "TMUS", "QCOM", "TXN", "GOOG"
]

UNIVERSES: dict[str, dict[int, list[str]]] = {
    "SP500": {
        5: SP500_TOP5,
        10: SP500_TOP10,
    },
    "NAS100": {
        5: NAS100_TOP5,
        10: NAS100_TOP10,
        20: NAS100_TOP20,
    },
}


def get_tickers(size: int, universe_type: str = "SP500") -> list[str]:
    utype = universe_type.upper()
    if utype not in UNIVERSES:
        raise ValueError(f"universe_type must be one of {list(UNIVERSES.keys())}, got {universe_type}")

    try:
        from app.services.dynamic_universe import get_dynamic_tickers
        return get_dynamic_tickers(utype, size)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Dynamic universe failed, using hardcoded: %s", e)

    valid = UNIVERSES[utype]
    if size not in valid:
        raise ValueError(f"size must be one of {list(valid.keys())} for {utype}, got {size}")
    return valid[size]
