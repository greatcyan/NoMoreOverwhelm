"""Thin, throttled client for the OKX v5 public REST API (no API key required)."""
from __future__ import annotations

import logging
import time
from collections import deque

import pandas as pd
import requests

log = logging.getLogger(__name__)

CANDLE_COLUMNS = ["ts", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"]
OKX_RATE_LIMIT_CODES = {"50011", "50061"}  # "too many requests" variants


class OkxApiError(RuntimeError):
    pass


class RateLimiter:
    """Sliding-window limiter: at most `max_calls` per `period` seconds."""

    def __init__(self, max_calls: int, period: float) -> None:
        self.max_calls = max_calls
        self.period = period
        self._calls: deque[float] = deque()

    def wait(self) -> None:
        now = time.monotonic()
        while self._calls and now - self._calls[0] >= self.period:
            self._calls.popleft()
        if len(self._calls) >= self.max_calls:
            time.sleep(max(self.period - (now - self._calls[0]), 0) + 0.01)
        self._calls.append(time.monotonic())


class OkxClient:
    # Kept below OKX's published limits (candles 40/2s, others 20/2s) to leave headroom.
    _LIMITS = {
        "/api/v5/market/candles": (30, 2.0),
        "/api/v5/market/history-candles": (15, 2.0),
        "/api/v5/public/instruments": (15, 2.0),
        "/api/v5/market/tickers": (15, 2.0),
    }

    def __init__(self, base_url: str = "https://www.okx.com", timeout: float = 15.0, max_retries: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": "okx-screener/1.0"})
        self._limiters = {path: RateLimiter(*lim) for path, lim in self._LIMITS.items()}

    # ---- core request -------------------------------------------------------
    def _get(self, path: str, params: dict | None = None) -> list[dict]:
        limiter = self._limiters.get(path)
        for attempt in range(1, self.max_retries + 1):
            if limiter:
                limiter.wait()
            try:
                resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                self._backoff(attempt, f"network error: {exc}")
                continue

            if resp.status_code in (403, 451):
                raise OkxApiError(
                    f"HTTP {resp.status_code} from {self.base_url}{path}. OKX is blocking this runner's IP/region. "
                    "Try another OKX_BASE_URL, or run on a self-hosted runner (see README)."
                )
            if resp.status_code == 429 or resp.status_code >= 500:
                self._backoff(attempt, f"HTTP {resp.status_code}")
                continue
            resp.raise_for_status()

            payload = resp.json()
            code = str(payload.get("code"))
            if code == "0":
                return payload.get("data", [])
            if code in OKX_RATE_LIMIT_CODES:
                self._backoff(attempt, f"OKX rate limit code {code}")
                continue
            raise OkxApiError(f"OKX error {code} on {path} {params}: {payload.get('msg')}")

        raise OkxApiError(f"Gave up on {path} {params} after {self.max_retries} attempts")

    @staticmethod
    def _backoff(attempt: int, reason: str) -> None:
        delay = min(2 ** attempt * 0.5, 15)
        log.warning("Retry %s in %.1fs (%s)", attempt, delay, reason)
        time.sleep(delay)

    # ---- endpoints ----------------------------------------------------------
    def get_usdt_swaps(self, settle_ccy: str = "USDT") -> pd.DataFrame:
        data = self._get("/api/v5/public/instruments", {"instType": "SWAP"})
        df = pd.DataFrame(data)
        df = df[(df["settleCcy"] == settle_ccy) & (df["state"] == "live")].copy()
        df["BaseCcy"] = df["instId"].str.split("-").str[0]
        cols = ["instId", "BaseCcy", "ctVal", "ctValCcy", "listTime"]
        return df[[c for c in cols if c in df.columns]].reset_index(drop=True)

    def get_tickers(self) -> pd.DataFrame:
        return pd.DataFrame(self._get("/api/v5/market/tickers", {"instType": "SWAP"}))

    def get_daily_candles(self, inst_id: str, bars_needed: int = 370) -> pd.DataFrame:
        """Closed daily candles, oldest → newest. Pages into history-candles past the 300-bar cap."""
        rows: list[list[str]] = self._get(
            "/api/v5/market/candles", {"instId": inst_id, "bar": "1Dutc", "limit": 300}
        )
        while rows and len(rows) < bars_needed + 1:
            oldest_ts = rows[-1][0]  # responses are newest-first
            page = self._get(
                "/api/v5/market/history-candles",
                {"instId": inst_id, "bar": "1Dutc", "after": oldest_ts, "limit": 100},
            )
            if not page:
                break  # reached listing date
            rows.extend(page)
        return parse_candles(rows)


def parse_candles(rows: list[list[str]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume", "VolumeUSDT"])
    df = pd.DataFrame(rows, columns=CANDLE_COLUMNS[: len(rows[0])])
    df = df[df["confirm"] == "1"]  # drop the still-forming current-day bar
    df = df.drop_duplicates("ts")
    out = pd.DataFrame(
        {
            "Date": pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True).dt.date,
            "Open": df["open"].astype(float),
            "High": df["high"].astype(float),
            "Low": df["low"].astype(float),
            "Close": df["close"].astype(float),
            "Volume": df["volCcy"].astype(float),          # base currency (e.g. BTC), not contracts
            "VolumeUSDT": df["volCcyQuote"].astype(float),
        }
    )
    return out.sort_values("Date").reset_index(drop=True)
