"""CLI entry point:  python -m screener --mode auto|daily|hourly [--limit N] [--no-discord]"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback

from .config import Config
from .discord_notify import post_daily_summary, post_signals, post_status
from .pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(description="OKX USDT perpetual swap screener")
    parser.add_argument("--mode", choices=["auto", "daily", "hourly"], default="auto",
                        help="auto = full candle rebuild on the first run after the UTC daily close, live overlay otherwise")
    parser.add_argument("--limit", type=int, default=None, help="only process the first N instruments (testing)")
    parser.add_argument("--no-discord", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = Config()
    if args.no_discord:
        object.__setattr__(cfg, "discord_webhook_screener", None)
        object.__setattr__(cfg, "discord_webhook_status", None)

    run_url = None
    if os.getenv("GITHUB_RUN_ID"):
        run_url = f"{os.getenv('GITHUB_SERVER_URL')}/{os.getenv('GITHUB_REPOSITORY')}/actions/runs/{os.getenv('GITHUB_RUN_ID')}"

    try:
        result = run(cfg, args.mode, args.limit)
    except Exception as exc:
        logging.exception("Run failed")
        post_status(cfg.discord_webhook_status, False,
                    f"{type(exc).__name__}: {exc}\n{run_url or ''}\n```{traceback.format_exc()[-1500:]}```")
        return 1

    if result.mode == "daily":
        post_daily_summary(cfg.discord_webhook_screener, result.live, result.failures)
        failed = ", ".join(list(result.failures)[:15])
        post_status(cfg.discord_webhook_status, True,
                    f"Daily rebuild: {len(result.latest)} pairs, {len(result.failures)} failed"
                    + (f" ({failed})" if failed else "") + (f"\n{run_url}" if run_url else ""))
    post_signals(cfg.discord_webhook_screener, result.signals)
    return 0


if __name__ == "__main__":
    sys.exit(main())
