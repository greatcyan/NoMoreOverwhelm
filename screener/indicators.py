"""Indicator maths. Pure functions on pandas objects — easy to unit test."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period, min_periods=period).mean()


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.DataFrame:
    """Wilder's RSI (RMA smoothing, SMA seed) — same method TradingView uses.

    Returns RSI plus the running average gain/loss, so a provisional live RSI
    can be computed later from the last closed bar without re-pulling history.
    """
    values = close.to_numpy(dtype=float)
    n = len(values)
    avg_gain = np.full(n, np.nan)
    avg_loss = np.full(n, np.nan)
    if n > period:
        delta = np.diff(values)
        gains = np.clip(delta, 0, None)
        losses = np.clip(-delta, 0, None)
        avg_gain[period] = gains[:period].mean()
        avg_loss[period] = losses[:period].mean()
        for i in range(period + 1, n):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period

    rsi = np.array([_rsi_from_avgs(g, l) for g, l in zip(avg_gain, avg_loss)])
    return pd.DataFrame({"RSI": rsi, "AvgGain": avg_gain, "AvgLoss": avg_loss}, index=close.index)


def next_rsi(avg_gain: float, avg_loss: float, last_close: float, new_price: float, period: int = 14) -> float:
    """One Wilder step forward: RSI if the current bar closed at `new_price`."""
    if any(map(_isnan, (avg_gain, avg_loss, last_close, new_price))):
        return math.nan
    change = new_price - last_close
    g = (avg_gain * (period - 1) + max(change, 0)) / period
    l = (avg_loss * (period - 1) + max(-change, 0)) / period
    return _rsi_from_avgs(g, l)


def _rsi_from_avgs(avg_gain: float, avg_loss: float) -> float:
    if _isnan(avg_gain) or _isnan(avg_loss):
        return math.nan
    if avg_loss == 0:
        return 50.0 if avg_gain == 0 else 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def _isnan(x: float) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def compute_daily_metrics(
    candles: pd.DataFrame,
    ma_periods: tuple[int, ...] = (20, 50, 100),
    rsi_period: int = 14,
    window_52w: int = 364,
) -> dict | None:
    """One screener row from an instrument's closed daily candles (oldest → newest)."""
    if candles.empty:
        return None
    close = candles["Close"]
    last = candles.iloc[-1]
    rsi = wilder_rsi(close, rsi_period).iloc[-1]
    window = candles.tail(window_52w)
    high_52w, low_52w = window["High"].max(), window["Low"].min()

    row = {
        "Date": last["Date"],
        "Open": last["Open"],
        "High": last["High"],
        "Low": last["Low"],
        "Close": last["Close"],
        "Volume": last["Volume"],
        "VolumeUSDT": last["VolumeUSDT"],
        **{f"MA{p}": sma(close, p).iloc[-1] for p in ma_periods},
        f"RSI{rsi_period}": rsi["RSI"],
        "High_52W": high_52w,
        "Low_52W": low_52w,
        "Pct_From_52WH": last["Close"] / high_52w - 1,  # fractions: format as % in Power BI
        "Pct_From_52WL": last["Close"] / low_52w - 1,
        "Bars_Available": len(candles),
        "Is_Partial_52W": len(window) < window_52w,
        # Wilder state — lets hourly runs compute a live RSI without history
        "RSI_AvgGain": rsi["AvgGain"],
        "RSI_AvgLoss": rsi["AvgLoss"],
    }
    return row
