import math

import numpy as np
import pandas as pd
import pytest

from screener.indicators import compute_daily_metrics, next_rsi, sma, wilder_rsi
from screener.okx_client import parse_candles


def test_sma_needs_full_window():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    out = sma(s, 3)
    assert out.isna().sum() == 2
    assert out.iloc[-1] == 4.0


def test_wilder_rsi_matches_reference():
    # Classic Wilder example closes (StockCharts RSI tutorial): 70.46, 66.25, 66.48, 69.35 …
    closes = pd.Series([44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84,
                        46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41,
                        46.22, 45.64])
    rsi = wilder_rsi(closes, 14)["RSI"]
    assert rsi.iloc[:14].isna().all()
    assert rsi.iloc[14] == pytest.approx(70.46, abs=0.01)
    assert rsi.iloc[15] == pytest.approx(66.25, abs=0.01)
    assert rsi.iloc[17] == pytest.approx(69.35, abs=0.01)


def test_rsi_edge_cases():
    assert wilder_rsi(pd.Series(np.arange(1, 30, dtype=float)))["RSI"].iloc[-1] == 100.0
    assert wilder_rsi(pd.Series([5.0] * 30))["RSI"].iloc[-1] == 50.0


def test_next_rsi_equals_full_recompute():
    rng = np.random.default_rng(7)
    closes = pd.Series(100 + rng.normal(0, 2, 200).cumsum())
    state = wilder_rsi(closes.iloc[:-1]).iloc[-1]
    live = next_rsi(state["AvgGain"], state["AvgLoss"], closes.iloc[-2], closes.iloc[-1])
    assert live == pytest.approx(wilder_rsi(closes)["RSI"].iloc[-1], rel=1e-9)
    assert math.isnan(next_rsi(float("nan"), 1.0, 1.0, 1.0))


def _candles(n: int) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    close = 100 + rng.normal(0, 1, n).cumsum()
    return pd.DataFrame({
        "Date": pd.date_range("2025-01-01", periods=n).date,
        "Open": close, "High": close + 1, "Low": close - 1, "Close": close,
        "Volume": 1.0, "VolumeUSDT": 100.0,
    })


def test_metrics_full_history():
    c = _candles(370)
    m = compute_daily_metrics(c)
    assert m["Is_Partial_52W"] is False or m["Is_Partial_52W"] == False  # noqa: E712
    assert m["High_52W"] == pytest.approx(c.tail(364)["High"].max())
    assert m["MA100"] == pytest.approx(c["Close"].tail(100).mean())


def test_metrics_new_listing_is_flagged_not_dropped():
    m = compute_daily_metrics(_candles(40))
    assert m["Is_Partial_52W"]
    assert math.isnan(m["MA50"]) and not math.isnan(m["MA20"])
    assert m["Bars_Available"] == 40


def test_parse_candles_drops_unconfirmed_bar_and_sorts():
    rows = [  # OKX returns newest first
        ["1760313600000", "3", "4", "2", "3.5", "10", "1", "3", "0"],  # forming bar
        ["1760227200000", "2", "3", "1", "3.0", "10", "1", "3", "1"],
        ["1760140800000", "1", "2", "0.5", "2.0", "10", "1", "2", "1"],
    ]
    df = parse_candles(rows)
    assert len(df) == 2
    assert df["Close"].tolist() == [2.0, 3.0]
