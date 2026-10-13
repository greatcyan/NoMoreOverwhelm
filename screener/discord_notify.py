"""Discord webhook posts: daily summary, hourly signals, and pipeline status."""
from __future__ import annotations

import logging

import pandas as pd
import requests

log = logging.getLogger(__name__)

FIELD_LIMIT = 1024  # Discord embed field value cap


def _post(webhook_url: str | None, payload: dict) -> None:
    if not webhook_url:
        return
    resp = requests.post(webhook_url, json=payload, timeout=10)
    if resp.status_code >= 400:
        log.error("Discord webhook failed: HTTP %s %s", resp.status_code, resp.text[:200])


def _block(df: pd.DataFrame) -> str:
    """Render a small table inside a code block, trimmed to Discord's field limit."""
    if df.empty:
        return "_none_"
    lines = df.to_string(index=False).splitlines()
    out = []
    for line in lines:
        if len("\n".join(out + [line])) + 8 > FIELD_LIMIT:
            break
        out.append(line)
    return "```\n" + "\n".join(out) + "\n```"


def _fmt(df: pd.DataFrame, pct_cols: tuple[str, ...] = (), num_cols: tuple[str, ...] = ()) -> pd.DataFrame:
    df = df.copy()
    df["InstId"] = df["InstId"].str.replace("-USDT-SWAP", "", regex=False)
    if "LastPrice" in df:
        df["LastPrice"] = df["LastPrice"].map("{:.6g}".format)  # works for BTC and sub-cent coins
    for c in pct_cols:
        df[c] = (df[c] * 100).map("{:+.1f}%".format)
    for c in num_cols:
        df[c] = df[c].map("{:.1f}".format)
    return df


def post_daily_summary(webhook_url: str | None, live: pd.DataFrame, failures: dict[str, str], top_n: int = 8) -> None:
    rsi = "RSI14"
    oversold = _fmt(live.nsmallest(top_n, rsi)[["InstId", rsi, "Pct_From_52WH_Live"]],
                    ("Pct_From_52WH_Live",), (rsi,)).rename(columns={"Pct_From_52WH_Live": "vs52WH"})
    overbought = _fmt(live.nlargest(top_n, rsi)[["InstId", rsi, "Pct_From_52WH_Live"]],
                      ("Pct_From_52WH_Live",), (rsi,)).rename(columns={"Pct_From_52WH_Live": "vs52WH"})
    near_high = live[~live["Is_Partial_52W"]].nlargest(top_n, "Pct_From_52WH_Live")
    near_high = _fmt(near_high[["InstId", "Pct_From_52WH_Live", rsi]], ("Pct_From_52WH_Live",), (rsi,)) \
        .rename(columns={"Pct_From_52WH_Live": "vs52WH"})
    above_all = int((live[["Pct_From_MA20_Live", "Pct_From_MA50_Live", "Pct_From_MA100_Live"]] > 0).all(axis=1).sum())

    embed = {
        "title": f"📊 OKX USDT Swap Screener — daily close {live['Date'].max()}",
        "description": f"{len(live)} pairs · {above_all} above MA20/50/100 · {len(failures)} failed",
        "color": 0x2ECC71,
        "fields": [
            {"name": "🔻 Most oversold (RSI14)", "value": _block(oversold), "inline": False},
            {"name": "🔺 Most overbought (RSI14)", "value": _block(overbought), "inline": False},
            {"name": "🎯 Closest to 52W high", "value": _block(near_high), "inline": False},
        ],
    }
    _post(webhook_url, {"embeds": [embed]})


def post_signals(webhook_url: str | None, signals: pd.DataFrame) -> None:
    if signals.empty:
        return
    fields = []
    for name, grp in signals.groupby("Signal", sort=True):
        table = _fmt(grp[["InstId", "LastPrice", "Chg_Today", "RSI14_Live"]], ("Chg_Today",), ("RSI14_Live",)) \
            .rename(columns={"Chg_Today": "Today", "RSI14_Live": "RSI"})
        fields.append({"name": f"{name} ({len(grp)})", "value": _block(table), "inline": False})
    _post(webhook_url, {"embeds": [{"title": "⚡ New intraday signals", "color": 0xF1C40F, "fields": fields[:25]}]})


def post_status(webhook_url: str | None, ok: bool, message: str) -> None:
    _post(webhook_url, {"embeds": [{
        "title": "✅ Screener run OK" if ok else "❌ Screener run FAILED",
        "description": message[:4000],
        "color": 0x2ECC71 if ok else 0xE74C3C,
    }]})
