NAS100_TOP5 = ["AAPL", "MSFT", "NVDA", "AMZN", "META"]

NAS100_TOP10 = NAS100_TOP5 + ["GOOGL", "AVGO", "TSLA", "COST", "NFLX"]

NAS100_TOP20 = NAS100_TOP10 + [
    "AMD", "ADBE", "PEP", "CSCO", "INTC",
    "CMCSA", "TMUS", "QCOM", "TXN", "GOOG"
]

VALID_SIZES = {5: NAS100_TOP5, 10: NAS100_TOP10, 20: NAS100_TOP20}


def get_tickers(size: int) -> list[str]:
    if size not in VALID_SIZES:
        raise ValueError(f"size must be one of {list(VALID_SIZES.keys())}, got {size}")
    return VALID_SIZES[size]
