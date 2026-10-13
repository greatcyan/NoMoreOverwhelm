"""Daily (full candle pull) and hourly (live ticker overlay) pipeline steps."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .config import Config
from .indicators import compute_daily_metrics, next_rsi
from .okx_client import OkxClient

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    mode: str
    latest: pd.DataFrame
    live: pd.DataFrame
    signals: pd.DataFrame
    failures: dict[str, str] = field(default_factory=dict)


def expected_daily_date(now: datetime | None = None) -> date:
    """Date of the most recent fully closed UTC daily candle."""
    now = now or datetime.now(timezone.utc)
    return (now - timedelta(days=1)).date()


def needs_daily_refresh(cfg: Config, now: datetime | None = None) -> bool:
    """Self-healing: rebuild if today's closed candle isn't in the latest table yet
    (first run of the UTC day, or a previous daily run failed)."""
    if not cfg.latest_path.exists():
        return True
    latest = pd.read_csv(cfg.latest_path, usecols=["Date"])
    return latest.empty or str(latest["Date"].max()) < str(expected_daily_date(now))


# ---- daily ------------------------------------------------------------------
def build_daily(client: OkxClient, cfg: Config, limit: int | None = None) -> tuple[pd.DataFrame, dict[str, str]]:
    instruments = client.get_usdt_swaps(cfg.settle_ccy)
    if limit:
        instruments = instruments.head(limit)
    log.info("Universe: %d live %s swaps", len(instruments), cfg.settle_ccy)

    rows, failures = [], {}
    for i, inst in enumerate(instruments.itertuples(index=False), start=1):
        try:
            candles = client.get_daily_candles(inst.instId, cfg.bars_needed)
            metrics = compute_daily_metrics(candles, cfg.ma_periods, cfg.rsi_period, cfg.window_52w)
            if metrics is None:
                failures[inst.instId] = "no closed candles yet"
                continue
            rows.append({"InstId": inst.instId, "BaseCcy": inst.BaseCcy, **metrics})
        except Exception as exc:  # one bad instrument must not sink the run
            failures[inst.instId] = str(exc)
            log.warning("%s failed: %s", inst.instId, exc)
        if i % 50 == 0:
            log.info("…%d/%d instruments", i, len(instruments))

    df = pd.DataFrame(rows)
    df["LastRefreshed"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return df, failures


def save_daily(df: pd.DataFrame, cfg: Config) -> None:
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(cfg.latest_path, index=False)

    # Append to history; re-runs on the same day replace that day's rows (idempotent).
    history_cols = [c for c in df.columns if not c.startswith("RSI_Avg")]
    snapshot = df[history_cols]
    if cfg.history_path.exists():
        history = pd.read_csv(cfg.history_path)
        history = pd.concat([history, snapshot], ignore_index=True)
        history["Date"] = history["Date"].astype(str)
        history = history.drop_duplicates(["InstId", "Date"], keep="last")
    else:
        history = snapshot
    history.sort_values(["Date", "InstId"]).to_csv(cfg.history_path, index=False)


# ---- hourly (live overlay) ---------------------------------------------------
def build_live(latest: pd.DataFrame, tickers: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    t = tickers[["instId", "last", "sodUtc0", "volCcy24h", "ts"]].rename(columns={"instId": "InstId"})
    for col in ("last", "sodUtc0", "volCcy24h"):
        t[col] = pd.to_numeric(t[col], errors="coerce")

    live = latest.merge(t, on="InstId", how="inner")
    rsi_col = f"RSI{cfg.rsi_period}"
    live["LastPrice"] = live["last"]
    live["Chg_Today"] = live["last"] / live["sodUtc0"] - 1
    live[f"{rsi_col}_Live"] = [
        next_rsi(g, l, c, p, cfg.rsi_period)
        for g, l, c, p in zip(live["RSI_AvgGain"], live["RSI_AvgLoss"], live["Close"], live["last"])
    ]
    live["Pct_From_52WH_Live"] = live["last"] / live["High_52W"] - 1
    live["Pct_From_52WL_Live"] = live["last"] / live["Low_52W"] - 1
    for p in cfg.ma_periods:
        live[f"Pct_From_MA{p}_Live"] = live["last"] / live[f"MA{p}"] - 1
    live["PriceTimeUTC"] = pd.to_datetime(pd.to_numeric(live["ts"]), unit="ms", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")
    live["LastRefreshed"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    keep = ["InstId", "BaseCcy", "Date", "Close", "LastPrice", "Chg_Today", rsi_col, f"{rsi_col}_Live",
            *[f"MA{p}" for p in cfg.ma_periods], *[f"Pct_From_MA{p}_Live" for p in cfg.ma_periods],
            "High_52W", "Low_52W", "Pct_From_52WH_Live", "Pct_From_52WL_Live", "Is_Partial_52W",
            "volCcy24h", "PriceTimeUTC", "LastRefreshed"]
    return live[keep].rename(columns={"volCcy24h": "Volume24h"})


def detect_signals(live: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Events that happened since the last daily close (stateless, from closed vs live values)."""
    rsi, rsi_live = f"RSI{cfg.rsi_period}", f"RSI{cfg.rsi_period}_Live"
    rules: list[tuple[str, pd.Series]] = [
        ("New 52W high", (live["LastPrice"] > live["High_52W"]) & ~live["Is_Partial_52W"]),
        ("New 52W low", (live["LastPrice"] < live["Low_52W"]) & ~live["Is_Partial_52W"]),
        ("RSI < 30", (live[rsi] >= 30) & (live[rsi_live] < 30)),
        ("RSI > 70", (live[rsi] <= 70) & (live[rsi_live] > 70)),
    ]
    for p in cfg.ma_periods:
        ma = live[f"MA{p}"]
        rules.append((f"Crossed above MA{p}", (live["Close"] < ma) & (live["LastPrice"] > ma)))
        rules.append((f"Crossed below MA{p}", (live["Close"] > ma) & (live["LastPrice"] < ma)))

    frames = [live.loc[mask.fillna(False), ["InstId", "LastPrice", "Chg_Today", rsi_live]].assign(Signal=name)
              for name, mask in rules]
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["InstId", "Signal"])


def filter_new_signals(signals: pd.DataFrame, cfg: Config, today: str) -> pd.DataFrame:
    """Drop signals already posted today so Discord isn't spammed every hour."""
    state: dict[str, list[str]] = {}
    if cfg.signal_state_path.exists():
        state = json.loads(cfg.signal_state_path.read_text())
    sent = set(state.get(today, []))
    keys = signals["InstId"] + "|" + signals["Signal"]
    fresh = signals[~keys.isin(sent)]

    cfg.signal_state_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.signal_state_path.write_text(json.dumps({today: sorted(sent | set(keys))}, indent=1))  # keep today only
    return fresh


# ---- orchestration -------------------------------------------------------------
def run(cfg: Config, mode: str = "auto", limit: int | None = None) -> RunResult:
    client = OkxClient(cfg.okx_base_url)
    failures: dict[str, str] = {}

    if mode == "daily" or (mode == "auto" and needs_daily_refresh(cfg)):
        mode = "daily"
        latest, failures = build_daily(client, cfg, limit)
        if latest.empty:
            raise RuntimeError(f"Daily build produced no rows ({len(failures)} failures)")
        save_daily(latest, cfg)
    else:
        mode = "hourly"
        latest = pd.read_csv(cfg.latest_path)
        latest["Is_Partial_52W"] = latest["Is_Partial_52W"].astype(bool)

    live = build_live(latest, client.get_tickers(), cfg)
    live.to_csv(cfg.live_path, index=False)

    today = datetime.now(timezone.utc).date().isoformat()
    signals = filter_new_signals(detect_signals(live, cfg), cfg, today)
    log.info("Mode=%s rows=%d new_signals=%d failures=%d", mode, len(live), len(signals), len(failures))
    return RunResult(mode, latest, live, signals, failures)
