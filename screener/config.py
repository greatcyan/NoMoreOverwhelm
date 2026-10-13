"""Runtime configuration, read from environment variables so secrets never live in code."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    okx_base_url: str = field(default_factory=lambda: os.getenv("OKX_BASE_URL", "https://www.okx.com"))
    settle_ccy: str = field(default_factory=lambda: os.getenv("SETTLE_CCY", "USDT"))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "data")))

    # Indicator settings
    bars_needed: int = 370            # 364 for 52W + buffer; also covers MA100
    window_52w: int = 364             # 52 x 7 daily candles
    ma_periods: tuple[int, ...] = (20, 50, 100)
    rsi_period: int = 14

    # Discord (optional — pipeline still runs and writes files without them)
    discord_webhook_screener: str | None = field(default_factory=lambda: os.getenv("DISCORD_WEBHOOK_SCREENER") or None)
    discord_webhook_status: str | None = field(default_factory=lambda: os.getenv("DISCORD_WEBHOOK_STATUS") or None)

    @property
    def latest_path(self) -> Path:
        return self.data_dir / "screener_latest.csv"

    @property
    def history_path(self) -> Path:
        return self.data_dir / "screener_history.csv"

    @property
    def live_path(self) -> Path:
        return self.data_dir / "screener_live.csv"

    @property
    def signal_state_path(self) -> Path:
        return self.data_dir / "state" / "signals_sent.json"
