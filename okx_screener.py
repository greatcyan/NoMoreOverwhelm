"""
OKX MA100 Demarcation Line Screener - Multi-Timeframe (MTF) variant
=====================================================================

Companion to okx_swap_screener.py, originally built to mirror the "MA100
Demarcation Line [MTF]" Pine Script indicator's multi-timeframe check.

*** This is the MTF variant of okx_demarcation_screener.py. ***
NOTE: H4 and H1 MA100 demarcation checks have been added back on top of
D1, purely for PROBABILITY STACKING - i.e. extra confluence context (how
many timeframes a token is trending above its own MA100 on at once), NOT
as additional hard filter requirements. The required filter set below is
UNCHANGED from the D1-only script: Above_All_TF still means "above the D1
MA100 demarcation line" and alone decides who makes the
okx_demarcation_above_all_latest.csv list. Above_H4/Above_H1 (plus the
summary TF_Stack_Count/TF_Stack_All columns described under "Multi-
timeframe stacking columns" below) are additional INFORMATIONAL columns
on every CSV - use them to rank/filter candidates within the existing
D1-qualified list by how much multi-timeframe confluence they also have,
rather than to exclude anyone from it. If you want H4/H1 to become hard
requirements again (like the pre-MTF version of this screener briefly
did), that's a one-line change - see TF_STACK_HARD_GATE near the top of
the CONFIG section.

For every live USDT-margined perpetual swap on OKX, pulls D1 candles,
computes the MA100, and keeps tokens whose current price is trading
ABOVE it as the final list (Above_All_TF) - same as the D1-only script.
H4 and H1 candles are pulled alongside D1 purely to populate the stacking
columns.

Final filter set (all required, ANDed together, all ON by default)
---------------------------------------------------------------------
  1. Above_All_TF    - price above the MA100 demarcation line on D1
                        (Above_D1). This is the sole trend gate - AOTS_D1
                        is no longer part of the required filter set, see
                        "AOTS info columns" below. (H4/H1 are informational
                        only here - see the MTF note above.)
  2. RSI_D1 > 50      - daily RSI14 strictly above --min-rsi (default 50)
  3. RSI touch (N-day) - RSI_Highest_<N>D > --min-swing-high-rsi (default
                        70): the highest daily RSI14 touched anywhere in
                        the trailing N days (N = --swing-high-lookback-
                        days, default 22, today included) - see "RSI
                        touch filter (N-day)" below
  4. Near_Any_High     - close is within --near-high-pct (default 25%) of
                        the 3M/6M/52W/ATH level, or already broke one
                        (--no-require-near-high to disable) - see
                        "Near-high filter" below
Liquidity (--min-liquidity-usd, default $500,000, checked against a
trailing 14-day AVERAGE daily USDT volume - see "Liquidity filter + sort"
below) is an additional floor/sort key on top of these, not part of the
"final" list above.

Multi-timeframe stacking columns (informational only - not a filter)
---------------------------------------------------------------------
Added back for probability stacking: alongside Above_D1, every row now
also gets Above_H4 and Above_H1 (same "close above its own MA100
demarcation line" check, computed independently on the 4-hour and
1-hour timeframes), plus their own Close_H4/MA100_H4/MA_Alignment_H4/
AOTS_H4 and Close_H1/MA100_H1/MA_Alignment_H1/AOTS_H1 columns (mirrors
of the D1 ones, see "AOTS info columns" below).

Two summary columns roll these up:
  TF_Stack_Count - how many of {D1, H4, H1} the token is currently above
                   its own MA100 on (0-3). Use this to rank/sort the
                   Above_All_TF list by confluence strength - a 3/3 stack
                   is a stronger, higher-probability signal than a 1/3.
  TF_Stack_All   - True only when Above_D1 AND Above_H4 AND Above_H1 are
                   all True (the full 3-timeframe stack) - a quick
                   boolean filter for "show me only the fully-stacked
                   ones" in Power BI, without changing what makes the
                   required Above_All_TF list in the first place.
Set TF_STACK_HARD_GATE = True (near the top of CONFIG) to fold
TF_Stack_All into Above_All_TF itself, turning this back into a hard
D1+H4+H1 requirement like the screener's pre-MTF behaviour - off by
default so the MTF columns stay purely additive/informational, per the
"add it for probability stacking" request this variant was built for.

Why "current price" instead of only fully-closed candles
----------------------------------------------------------
The Pine indicator compares the chart's live, real-time close (which
updates intrabar) against a live MA100 that also includes that still-
forming bar - that's what barstate.islast does. To match that behaviour
(rather than lag behind it), this screener does the same: it does NOT drop
the still-forming current candle on any timeframe. The MA100 and the
"above/below" check both use the most recent `MA_LEN` candles exactly as
OKX returns them, forming bar included. If you'd rather only ever act on
fully-closed candles, pass --closed-only (filters out confirm == "0" on
every timeframe before computing).

MA type
-------
Matches the indicator's default MA Type = SMA. Pass --ma-type EMA to switch
(uses a plain pandas EMA over the fetched window - not TradingView's
SMA-seeded EMA - so treat EMA mode as a close approximation, not an exact
match, especially in the first ~100 bars of history for a given run).

AOTS info columns (informational only - not a filter)
---------------------------------------------------------------------
Alongside the above/below-MA100 check, the daily timeframe also gets an
MA_Alignment_D1 + AOTS_D1 column - fast/mid/slow (MA20/MA50/MA100)
AOTS/iAOTS/ZS/iZS/Sideways classification (AOTS = MA20 > MA50 > MA100),
same as okx_swap_screener.py's classify_ma_alignment(). AOTS_All_TF is
kept as a column (for CSV-schema consistency with earlier versions of
this screener, which had multiple timeframes) and is just AOTS_D1.

AOTS_D1 is NOT part of the final filter set anymore - the "above MA100"
check (Above_D1/Above_All_TF, filter #1 above) is now the sole trend
gate, so a token sitting above a flattening/sideways daily MA100 (without
a genuine bullish MA20/MA50/MA100 stack) still passes. AOTS_D1/
MA_Alignment_D1/AOTS_All_TF are still computed and written to every CSV,
for context or for building your own AOTS filter on the Power BI side.

Output
------
Writes three CSVs per run into --output-dir:
  okx_demarcation_scan_<UTC date>.csv   - every live instrument, with an
                                           Above_<TF> column per timeframe
                                           (D1, H4, H1) plus Above_All_TF
                                           and the TF_Stack_Count/
                                           TF_Stack_All confluence columns
  okx_demarcation_latest.csv            - same, overwritten every run
  okx_demarcation_above_all_latest.csv  - ONLY the Above_All_TF == True rows
                                           (the actual screener output -
                                           still gated on D1 alone unless
                                           TF_STACK_HARD_GATE is turned on)

Requirements
------------
    pip install requests pandas --break-system-packages

Liquidity filter + sort
---------------------------------------------------------------------
Every row gets TWO liquidity figures:
  Vol24h_USDT       - today's live 24h traded volume in USDT notional
                       (OKX's `volCcy24h` ticker field - one single extra
                       API call covers every instrument at once, no
                       per-instrument cost). Shown for context/display
                       (e.g. the Discord digest's "Vol:" figure) only -
                       NOT used for filtering.
  AvgVol_<N>D_USDT   - a trailing N-day AVERAGE of daily USDT notional
                       volume (N = --avg-vol-lookback-days, default 14),
                       computed off the deep D1 history already fetched
                       for the high-break flags - no extra API cost. This
                       is the actual liquidity filter/sort key: steadier
                       than a single day's snapshot, so one noisy day (a
                       spike or a quiet weekend) can't let a thin token
                       through or wrongly exclude a solid one. A token
                       with less than N days of history gets its average
                       over whatever's available, flagged via
                       Partial_AvgVol_<N>D rather than being dropped.
--min-liquidity-usd drops anything below that AvgVol_<N>D_USDT figure
(default $500,000 - tokens averaging less than that are treated as
illiquid and excluded; 0 = no filtering), and the final Above_All_TF list
is always sorted DESCENDING by it - most liquid first.

RSI filter (1D)
---------------------------------------------------------------------
Every row also gets RSI_D1 - Wilder's RSI14 computed on the 1D timeframe
(reuses the D1 candles already fetched for the MA100 check, so no extra
API cost). The final output additionally requires RSI_D1 > --min-rsi
(default 50 - strictly greater than, not above-or-equal). A token with
insufficient 1D history (RSI_D1 is blank) is excluded, same as the
MA checks. Change the timeframe this filters on via RSI_FILTER_TF.

3-month / 6-month / 52-week / all-time high breaks (BOS)
---------------------------------------------------------------------
Every row also gets Is_3M_High_Break / Is_6M_High_Break / Is_52W_High_Break
/ Is_ATH_Break - True when the latest daily candle's High broke above the
highest High of the 90/182/364/all-available days strictly BEFORE it (a
genuine breakout above the prior range, not just "today happens to be
included in its own max"). Prior_High_3M / Prior_High_6M / Prior_High_52W /
Prior_High_ATH give the level that was broken, for context or charting in
Power BI.

These four flags are also rolled up into a single categorical BOS column
(used in the Discord watchlist line), picked by priority - the widest
genuine break wins:
    52WH   - broke the 52-week high (takes priority over 6M/3M)
    6MH    - broke the 6-month high but not the 52-week high
    3MH    - broke the 3-month high but not the 6-month/52-week high
    NONE   - none of the above
(Is_ATH_Break is tracked separately and is not folded into BOS.)
BOS and the four Is_*_Break flags themselves are informational only - like
AOTS, they do NOT change which rows pass Above_All_TF/the liquidity/RSI
filters. The related Near_Any_High flag (below) DOES filter.

A token with less history than a window needs gets Partial_3M_History /
Partial_6M_History / Partial_52W_History = True instead of being dropped
(the break is still computed against whatever history is available, per
the project's newly-listed-pairs rule). All of these flags share the SAME
deep D1 fetch used for the D1 MA100/AOTS/RSI checks
(get_deep_daily_candles()), so they add no extra per-timeframe request -
but that deep fetch itself walks further back than the other timeframes'
CANDLE_FETCH_LIMIT: it starts with one /market/candles call (300 recent
daily bars) then pages further back through /market/history-candles (100
bars/page) until either the instrument's listing date is reached or
--ath-max-history-pages extra pages have been used (default 15 -> ~1,800
daily bars / ~5 years), so this run takes noticeably longer than before -
most tokens stop early once their listing date is hit, but very old ones
will use the full budget. When the page budget runs out before reaching
the listing date, ATH_History_Complete is False for that row (and the
Discord watchlist line shows "52WH*" for that token) - the ATH/52WH check
is then only against the highest high within that capped lookback, not a
literal all-time/52-week high. Raise --ath-max-history-pages for a more
literal result at the cost of a slower run.

Last-touch RSI (overbought check)
---------------------------------------------------------------------
Every row also gets RSI_Highest_21D / RSI_Touch_70_21D, computed from the
same Wilder RSI14 series used for RSI_D1 (no extra API cost): RSI_Highest_
21D is the highest daily RSI14 value over the trailing 21 daily bars, and
RSI_Touch_70_21D is True when that 21-day high exceeded 70 at any point -
i.e. the token touched overbought recently even if RSI has since cooled
off. This is also what the Discord WATCHLISTS line shows, and tokens
within each BOS group there are sorted by RSI_Highest_21D DESCENDING
(strongest recent momentum first). Change the threshold/lookback via
RSI_TOUCH_THRESHOLD / RSI_TOUCH_LOOKBACK_DAYS.

RSI touch filter (N-day)
---------------------------------------------------------------------
Same concept as the 21-day RSI touch feature above, computed via the same
compute_rsi_touch() with a different window: every row also gets
RSI_Highest_<N>D / RSI_Touch_70_<N>D (N = --swing-high-lookback-days,
default 22, today included) - the highest daily RSI14 touched anywhere in
the trailing N days. This one IS part of the final filter set: the output
requires RSI_Highest_<N>D > --min-swing-high-rsi (default 70). A token
that hasn't touched RSI>70 at any point in the last N days is excluded
even if it's above its MA100 demarcation line and its current RSI_D1 is
fine.

Near-high filter
---------------------------------------------------------------------
Every row also gets Near_3M_High / Near_6M_High / Near_52W_High / Near_ATH
and a matching Pct_From_3M_High / Pct_From_6M_High / Pct_From_52W_High /
Pct_From_ATH - each Near_* is True when the latest CLOSE is within
--near-high-pct percent of that window's prior-high level (default 25%),
OR has already broken it (a break always counts as "near"); Pct_From_*
gives the signed distance (negative = still below the level, 0+ = at or
above it) for sorting/charting in Power BI. Near_Any_High is True if ANY
of the four is near/broken, and - unlike BOS/the break flags, which are
informational only - Near_Any_High DOES filter the final output: a token
also needs Near_Any_High == True to make it into the Above_All_TF list and
the Discord digest. This surfaces tokens setting up for a breakout (close
to a resistance level) in addition to ones that already broke one. Pass
--no-require-near-high to disable this filter (the Near_*/Pct_From_*
columns are still computed and written to the CSVs either way), or
--near-high-pct to change the 25% threshold.

Discord delivery (optional)
---------------------------------------------------------------------
Pass --discord-webhook (or set the DISCORD_WEBHOOK_URL env var) and every
run posts the same digest to one or more Discord channels via incoming
webhooks. Pass a single URL, or several separated by commas (and/or
whitespace/newlines) to post to multiple channels at once - e.g.
--discord-webhook "https://discord.com/api/webhooks/AAA,https://discord.com/api/webhooks/BBB".
Each webhook is posted to independently and a failure on one (bad URL,
channel deleted, rate limit) is logged but does NOT stop the others from
getting the digest. The WATCHLISTS list is grouped into 6 fields, widest
break first - the 3 actual-break tiers, icons on the field headers - "🚀
Near 52WH BOS (N)", "🔥 Near 6MH BOS (N)", "⚡ Near 3MH BOS (N)" - followed
by 3 "approaching but not broken yet" tiers that replace the old single,
confusing "No BOS Break" catch-all, split by which window a token is
closest to breaking next - "🟣 Approaching 52W High (N)", "🟡 Approaching
6M High (N)", "🟠 Approaching 3M High (N)". Within EACH of the 6 groups,
rows are further sub-grouped by network into 5 buckets - Solana,
Ethereum (its base chain plus L2s/appchains, so Arbitrum/Optimism/zkSync
etc. don't get their own tiny groups), Bitcoin (BTC plus its L2s),
Tokenized Equities/ETFs (OKX's stock perpetuals like NVDA/META/MSTR -
not a blockchain network, kept separate rather than mixed in with
crypto), and Other Networks for the genuine long tail (smaller L1s like
Avalanche/Sui/Aptos/Celestia/etc., and anything unclassified) - see
simplify_network()/get_network()/NETWORK_MAP (OKX's API has no chain
metadata, so this is a hand-maintained, non-authoritative table). Rows
within a network bucket are sorted by % to that group's high level
descending, then by the swing-high RSI value descending. A group too big
for one Discord field (~1000 chars) spans multiple fields ("...
(cont'd 2/3)") rather than silently dropping tokens. Simple, plain line
per token - no YES/NO, no checkmarks, no color dots:
    **{Network Bucket}**
    {BASE} | {+/-X.X}% BOS | RSI Swing High Value: {X.X} | Vol: {$X.XM}
The percent is the signed distance to that group's own high level
(Pct_From_52W_High / Pct_From_6M_High / Pct_From_3M_High, matching
whichever window the group is about); Vol is the 24h USDT volume,
compact-formatted. A group with zero tokens still shows as its own field
with "(none)". A final "📝 Notes" field spells out what BOS, the
"Approaching" tiers, RSI Swing High Value, and the network buckets mean,
for anyone in the channel unfamiliar with the screener. The footer always
ends with a "⚠️ Trade at Your Own Risk" disclaimer. No CSV attached. Pass
--discord-mention (or set DISCORD_MENTION, e.g. "@here"/"@everyone"/a role
mention) to make every post actually ping instead of posting silently.

Usage
-----
    python okx_demarcation_screener.py --output-dir ./screener_output

    # Only use fully-closed candles (no live/forming bar) on every timeframe:
    python okx_demarcation_screener.py --output-dir ./screener_output --closed-only

    # Re-run every N minutes instead of exiting after one pass:
    python okx_demarcation_screener.py --output-dir ./screener_output --interval-minutes 15

    # Only keep results with at least $5M in 24h USDT volume:
    python okx_demarcation_screener.py --output-dir ./screener_output --min-liquidity-usd 5000000

    # Use a different 1D RSI floor than the default 50:
    python okx_demarcation_screener.py --output-dir ./screener_output --min-rsi 60

    # Widen the near-high band to 40% instead of the default 25%:
    python okx_demarcation_screener.py --output-dir ./screener_output --near-high-pct 40

    # Turn off the near-high requirement entirely (keep the columns, drop the filter):
    python okx_demarcation_screener.py --output-dir ./screener_output --no-require-near-high

    # Use a 20-day swing-high lookback instead of the default 50, with a 65 RSI floor:
    python okx_demarcation_screener.py --output-dir ./screener_output --swing-high-lookback-days 20 --min-swing-high-rsi 65

    # Push the all-time-high lookback deeper (slower, more literal ATH):
    python okx_demarcation_screener.py --output-dir ./screener_output --ath-max-history-pages 30

    # Also post a digest to Discord every run:
    python okx_demarcation_screener.py --output-dir ./screener_output --discord-webhook "https://discord.com/api/webhooks/..." --discord-mention "@here"

    # Post to two Discord channels (e.g. main + community) in the same run:
    python okx_demarcation_screener.py --output-dir ./screener_output --discord-webhook "https://discord.com/api/webhooks/AAA,https://discord.com/api/webhooks/BBB"
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import time
from pathlib import Path

import pandas as pd
import requests

# ============================================================================
# CONFIG
# ============================================================================

OKX_BASE_URL = "https://www.okx.com"
INSTRUMENTS_ENDPOINT = "/api/v5/public/instruments"
CANDLES_ENDPOINT = "/api/v5/market/candles"
TICKERS_ENDPOINT = "/api/v5/market/tickers"
HISTORY_CANDLES_ENDPOINT = "/api/v5/market/history-candles"

# Timeframe label -> OKX `bar` param. Order here is display/column order.
# D1 remains the sole REQUIRED trend gate (Above_All_TF = Above_D1, same
# as the single-timeframe script) - H4 and H1 are back for probability
# stacking: extra confluence columns (Above_H4/Above_H1 +
# TF_Stack_Count/TF_Stack_All, see the module docstring) computed and
# written to every CSV, but not ANDed into Above_All_TF unless
# TF_STACK_HARD_GATE below is turned on.
TIMEFRAMES: dict[str, str] = {
    "D1": "1D",
    "H4": "4H",
    "H1": "1H",
}

# Set True to fold the full D1+H4+H1 stack (TF_Stack_All) into
# Above_All_TF itself, making H4/H1 hard requirements again instead of
# informational stacking columns. Off by default - see the module
# docstring's "Multi-timeframe stacking columns" section.
TF_STACK_HARD_GATE = False

MA_LEN = 100                 # matches the indicator's "MA Length" input
MA_TYPE_DEFAULT = "SMA"      # matches the indicator's default "MA Type" input
CANDLE_FETCH_LIMIT = 110     # MA_LEN + a small buffer; one call covers it (cap is 300)

# AOTS (fast > mid > slow MA stack) info columns. AOTS = MA20 > MA50 >
# MA100 (and, via the Above_<TF> check already in the pipeline, Close >
# MA100 too) on the given timeframe.
MA_FAST_LEN = 20
MA_MID_LEN = 50
SIDEWAYS_THRESHOLD_PCT = 1.5   # MAs within this % of each other = "Sideways", not a stack

RSI_PERIOD = 14
RSI_FILTER_TF = "D1"          # which TIMEFRAMES key the RSI filter is computed/applied on
RSI_FILTER_MIN_DEFAULT = 50.0  # RSI_<RSI_FILTER_TF> must be strictly greater than this to pass

# High-break flags (3-month / 6-month / 52-week / all-time) - all computed
# off the same deep daily history pulled for the D1 timeframe (see
# get_deep_daily_candles()), so these add no extra API cost on their own.
THREE_MONTH_LOOKBACK_DAYS = 90
SIX_MONTH_LOOKBACK_DAYS = 182         # ~ 364 / 2, half the 52-week window
FIFTY_TWO_WEEK_LOOKBACK_DAYS = 364    # 52 x 7, matches the project's 52WH/52WL convention
ATH_MAX_HISTORY_PAGES = 15            # extra /market/history-candles pages (100 bars each) beyond the
                                       # initial 300 - 15 covers ~1800 daily bars (~5 years) per instrument

# "Last touch RSI > X within the last N days" (D1) - did RSI get
# overbought recently even if it's since cooled off, rather than only the
# current bar. Shown in the Discord WATCHLISTS line; tokens within each
# BOS group are sorted by this value, highest first.
RSI_TOUCH_THRESHOLD = 70.0
RSI_TOUCH_LOOKBACK_DAYS = 21

# "Highest RSI touch value in the last N days" (D1) - same concept/
# function as the 21-day RSI_Touch feature above (compute_rsi_touch()),
# just a different window - this is the one that's part of the required
# filter set. --min-swing-high-rsi (default 70) filters on it.
SWING_HIGH_LOOKBACK_DAYS = 22
SWING_HIGH_RSI_MIN_DEFAULT = 70.0

# "Near a high level" - current close is within this % of a 3M/6M/52W/ATH
# prior-high level (either still below it by less than this margin, or has
# already broken it). Flags setups approaching a breakout, not just ones
# that already happened.
NEAR_HIGH_THRESHOLD_PCT = 25.0

MIN_LIQUIDITY_USD_DEFAULT = 500_000.0   # 14-day average-daily-volume USDT notional floor - tokens
                                         # below this are excluded as illiquid; 0 = no filtering

# The liquidity filter uses a trailing N-day AVERAGE of daily USDT notional
# volume (volCcyQuote from the deep D1 history already being fetched - no
# extra API cost) rather than a single day's 24h snapshot, so one noisy day
# (a spike or a quiet weekend) doesn't let a thin token through or wrongly
# exclude a solid one. 14 days = two trading weeks, a reasonable balance
# between smoothing out noise and staying responsive to a real liquidity
# shift. Vol24h_USDT (today's live snapshot) is still computed and shown
# separately in the CSV/Discord digest for context.
AVG_VOL_LOOKBACK_DAYS_DEFAULT = 14

REQUESTS_PER_WINDOW = 18     # stay under OKX's ~20 req / 2s public limit
WINDOW_SECONDS = 2.1
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0

DISCORD_EMBED_COLOR = 0x2F81F7
DISCORD_FIELD_VALUE_MAX = 1000     # stay under Discord's 1024-char field-value cap
DISCORD_MAX_FIELDS = 25            # Discord's hard cap on fields per embed
DISCORD_EMBED_TOTAL_MAX = 5500     # safety margin under Discord's hard 6000-char
                                    # total-embed-size cap (title + footer + ALL
                                    # field names + ALL field values combined) -
                                    # a per-field cap alone isn't enough: enough
                                    # small fields can still add up past 6000 and
                                    # get the WHOLE post rejected with a 400

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("okx_demarcation_screener")


# ============================================================================
# THROTTLED HTTP SESSION
# ============================================================================


class ThrottledSession:
    """Thin wrapper over requests.Session that paces calls to stay within
    OKX's public rate limit and retries transient failures with backoff."""

    def __init__(self, requests_per_window: int = REQUESTS_PER_WINDOW, window_seconds: float = WINDOW_SECONDS):
        self._session = requests.Session()
        self._requests_per_window = requests_per_window
        self._window_seconds = window_seconds
        self._call_count = 0
        self._window_start = time.monotonic()

    def _throttle(self) -> None:
        self._call_count += 1
        if self._call_count >= self._requests_per_window:
            elapsed = time.monotonic() - self._window_start
            remaining = self._window_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
            self._call_count = 0
            self._window_start = time.monotonic()

    def get_json(self, path: str, params: dict) -> dict:
        self._throttle()
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._session.get(f"{OKX_BASE_URL}{path}", params=params, timeout=15)
                if resp.status_code == 429:
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
                resp.raise_for_status()
                payload = resp.json()
                if payload.get("code") not in ("0", 0):
                    raise RuntimeError(f"OKX API error {payload.get('code')}: {payload.get('msg')}")
                return payload
            except (requests.RequestException, RuntimeError) as exc:
                last_exc = exc
                log.warning("Request to %s failed (attempt %d/%d): %s", path, attempt, MAX_RETRIES, exc)
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
        raise RuntimeError(f"Giving up on {path} after {MAX_RETRIES} attempts") from last_exc


# ============================================================================
# OKX DATA ACCESS
# ============================================================================


def get_live_usdt_swap_instruments(session: ThrottledSession) -> list[str]:
    """Universe definition: SWAP instruments, USDT-settled, currently live.
    Re-pulled on every run since OKX lists/delists contracts regularly."""
    payload = session.get_json(INSTRUMENTS_ENDPOINT, {"instType": "SWAP"})
    rows = payload.get("data", [])
    inst_ids = [
        row["instId"]
        for row in rows
        if row.get("settleCcy") == "USDT" and row.get("state") == "live"
    ]
    log.info("Found %d live USDT-margined SWAP instruments", len(inst_ids))
    return sorted(inst_ids)


def get_24h_usdt_volume(session: ThrottledSession) -> dict[str, float]:
    """Single call covering every SWAP instrument's 24h traded volume in
    USDT notional (`volCcy24h`), used as the liquidity filter/sort key.
    Cheap on purpose - no need to hit this once per instrument."""
    payload = session.get_json(TICKERS_ENDPOINT, {"instType": "SWAP"})
    rows = payload.get("data", [])
    volumes: dict[str, float] = {}
    for row in rows:
        inst_id = row.get("instId")
        if not inst_id:
            continue
        try:
            volumes[inst_id] = float(row.get("volCcy24h") or 0.0)
        except (TypeError, ValueError):
            volumes[inst_id] = 0.0
    return volumes


def _rows_to_df(rows: list, closed_only: bool = False) -> pd.DataFrame:
    """Shared parser for both /market/candles and /market/history-candles
    row shapes: [ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm]."""
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(
        rows,
        columns=["ts", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"],
    )
    if closed_only:
        df = df[df["confirm"] == "1"]
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
    for col in ("open", "high", "low", "close", "vol", "volCcyQuote"):
        df[col] = df[col].astype(float)
    df = df.sort_values("ts").reset_index(drop=True)
    return df


def get_candles(
    session: ThrottledSession,
    inst_id: str,
    bar: str,
    limit: int = CANDLE_FETCH_LIMIT,
    closed_only: bool = False,
) -> pd.DataFrame:
    """Fetch the last `limit` candles for one instrument/timeframe.

    `confirm` is "1" for a fully closed candle and "0" for the bar still in
    progress. By default the still-forming candle is KEPT (not filtered) so
    the latest close/MA match what the live chart shows - pass
    closed_only=True to drop it instead.
    A single call covers up to 300 bars, so no pagination is needed here.
    """
    payload = session.get_json(CANDLES_ENDPOINT, {"instId": inst_id, "bar": bar, "limit": str(limit)})
    return _rows_to_df(payload.get("data", []), closed_only=closed_only)


def get_deep_daily_candles(
    session: ThrottledSession,
    inst_id: str,
    max_history_pages: int = ATH_MAX_HISTORY_PAGES,
    closed_only: bool = False,
) -> tuple[pd.DataFrame, bool]:
    """Fetch as much 1D history as available for one instrument, used for
    the 3-month/52-week/all-time-high break flags (and, reused, for the
    D1 MA100/AOTS/RSI checks too - no separate D1 fetch needed).

    Starts with one /market/candles call (up to 300 recent daily bars),
    then walks further back with /market/history-candles (`after` = the
    oldest timestamp seen so far, 100 bars per page - OKX's page cap on
    that endpoint) until either the instrument's listing date is reached
    (a page comes back shorter than 100 rows) or `max_history_pages` extra
    pages have been fetched, whichever comes first.

    Returns (df, history_is_complete). history_is_complete is False when
    the page cap was hit before reaching the listing date - i.e. the
    "all-time" high for that token is actually just the highest high
    within the capped lookback, not truly since listing. See
    ATH_MAX_HISTORY_PAGES in the module docstring for how to extend it."""
    first = get_candles(session, inst_id, "1D", limit=300, closed_only=closed_only)
    if first.empty:
        return first, True

    frames = [first]
    history_is_complete = True
    oldest_ts_ms = int(first["ts"].iloc[0].timestamp() * 1000)

    for _ in range(max_history_pages):
        payload = session.get_json(
            HISTORY_CANDLES_ENDPOINT,
            {"instId": inst_id, "bar": "1D", "after": str(oldest_ts_ms), "limit": "100"},
        )
        rows = payload.get("data", [])
        if not rows:
            break
        page_df = _rows_to_df(rows, closed_only=False)  # history pages are always fully-closed already
        if page_df.empty:
            break
        frames.append(page_df)
        oldest_ts_ms = int(page_df["ts"].iloc[0].timestamp() * 1000)
        if len(rows) < 100:
            break  # shorter than a full page -> reached the instrument's listing date
    else:
        history_is_complete = False  # loop exhausted max_history_pages without hitting the listing date

    combined = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset="ts")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    return combined, history_is_complete


# ============================================================================
# INDICATOR LOGIC
# ============================================================================


def wilder_rsi_series(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Standard Wilder's RSI (same definition as okx_swap_screener.py's
    wilder_rsi) computed for every bar, not just the last one - needed for
    the "did RSI touch > X within the last N days" check. Values before
    there's enough history are NaN."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.where(avg_loss != 0.0, 100.0)  # no losses in the window -> RSI 100
    return rsi.astype(float)


def wilder_rsi(close: pd.Series, period: int = RSI_PERIOD) -> float | None:
    """Current (last-bar) Wilder's RSI value, or None if there isn't enough
    history yet."""
    if len(close) < period + 1:
        return None
    last = wilder_rsi_series(close, period=period).iloc[-1]
    return None if pd.isna(last) else float(last)


def compute_ma100(close: pd.Series, length: int = MA_LEN, ma_type: str = MA_TYPE_DEFAULT) -> float | None:
    """Current MA100 value (last close included), or None if there isn't
    enough history yet on this timeframe."""
    if len(close) < length:
        return None
    window = close.iloc[-length:]
    if ma_type.upper() == "EMA":
        return float(window.ewm(span=length, adjust=False).mean().iloc[-1])
    return float(window.mean())  # SMA


def classify_ma_alignment(
    ma_fast: float | None,
    ma_mid: float | None,
    ma_slow: float | None,
    sideways_threshold_pct: float = SIDEWAYS_THRESHOLD_PCT,
) -> str:
    """AOTS / iAOTS / ZS / iZS / Sideways - identical rule to
    okx_swap_screener.py's classify_ma_alignment():
      AOTS      - full bullish stack:  fast > mid > slow
      iAOTS     - full bearish stack:  fast < mid < slow
      Sideways  - the three MAs are bunched within sideways_threshold_pct
                  of each other (checked first)
      ZS/iZS    - partial/mixed stack, bullish/bearish-leaning
    """
    if ma_fast is None or ma_mid is None or ma_slow is None or pd.isna(ma_fast) or pd.isna(ma_mid) or pd.isna(ma_slow):
        return "Insufficient Data"

    avg = (ma_fast + ma_mid + ma_slow) / 3.0
    spread_pct = (max(ma_fast, ma_mid, ma_slow) - min(ma_fast, ma_mid, ma_slow)) / avg * 100.0
    if spread_pct <= sideways_threshold_pct:
        return "Sideways"

    bullish_fast_mid = ma_fast > ma_mid
    bullish_mid_slow = ma_mid > ma_slow
    bullish_fast_slow = ma_fast > ma_slow
    bullish_votes = sum([bullish_fast_mid, bullish_mid_slow, bullish_fast_slow])

    if bullish_fast_mid and bullish_mid_slow:
        return "AOTS"
    if not bullish_fast_mid and not bullish_mid_slow:
        return "iAOTS"
    return "ZS" if bullish_votes >= 2 else "iZS"


def compute_tf_status(df: pd.DataFrame, length: int = MA_LEN, ma_type: str = MA_TYPE_DEFAULT) -> dict:
    """Returns last_close, MA100 + above/below, and the fast/mid/slow MA
    stack's AOTS classification for one timeframe's candle frame. Values
    are None when there isn't enough history to judge."""
    if df.empty:
        return {"close": None, "ma100": None, "is_above": None, "ma_alignment": "Insufficient Data", "is_aots": None}

    last_close = float(df["close"].iloc[-1])
    ma_fast = compute_ma100(df["close"], length=MA_FAST_LEN, ma_type=ma_type)
    ma_mid = compute_ma100(df["close"], length=MA_MID_LEN, ma_type=ma_type)
    ma_slow = compute_ma100(df["close"], length=length, ma_type=ma_type)

    is_above = (last_close > ma_slow) if ma_slow is not None else None
    ma_alignment = classify_ma_alignment(ma_fast, ma_mid, ma_slow)
    is_aots = (ma_alignment == "AOTS") if ma_alignment != "Insufficient Data" else None

    return {
        "close": last_close,
        "ma100": ma_slow,
        "is_above": is_above,
        "ma_alignment": ma_alignment,
        "is_aots": is_aots,
    }


def compute_high_breaks(
    df_d1: pd.DataFrame,
    history_is_complete: bool,
    three_month_days: int = THREE_MONTH_LOOKBACK_DAYS,
    six_month_days: int = SIX_MONTH_LOOKBACK_DAYS,
    fifty_two_week_days: int = FIFTY_TWO_WEEK_LOOKBACK_DAYS,
    near_threshold_pct: float = NEAR_HIGH_THRESHOLD_PCT,
) -> dict:
    """3-month / 6-month / 52-week / all-time high BREAK flags from the
    deep D1 history: True when the latest daily candle's High is a new
    high above the highest High of the N days strictly BEFORE it (a
    genuine breakout above the prior range, not just "today happens to
    equal the max of a window that includes today"). Each window's own
    prior-high value is included too, for context / use in Power BI.

    BOS ("break of structure") is a single categorical summary of the
    three windows below ATH - "52WH" if the 52-week high broke, else
    "6MH" if the 6-month high broke, else "3MH" if the 3-month high broke,
    else "NONE". A 52-week break implies the 6M/3M ones also broke (it's
    the widest window), so only the strongest tier is shown.

    Near_<window>_High is True when the latest CLOSE is within
    `near_threshold_pct` of that window's prior-high level - i.e. either
    already at/above the level (a break) or trading no more than
    `near_threshold_pct`% below it, flagging a token setting up for a
    breakout even before it happens. Pct_From_<window>_High gives the
    signed distance (negative = below the level, 0 or positive = at/above
    it) for context/sorting in Power BI. Near_Any_High is True if any of
    the four windows is near/broken - this is what --require-near-high
    filters on.

    A token with less than the full lookback of history gets a
    Partial_<window> flag instead of being silently dropped (per the
    project's "newly-listed pairs should show partial-period high with a
    flag, not be dropped" rule) - the break flag is still computed against
    whatever history is available.

    ATH_History_Complete is False when the all-time high is only the
    highest high within the ATH_MAX_HISTORY_PAGES-capped lookback, not
    truly since listing (see get_deep_daily_candles())."""
    empty_result = {
        "Prior_High_3M": None, "Is_3M_High_Break": None, "Partial_3M_History": None,
        "Pct_From_3M_High": None, "Near_3M_High": None,
        "Prior_High_6M": None, "Is_6M_High_Break": None, "Partial_6M_History": None,
        "Pct_From_6M_High": None, "Near_6M_High": None,
        "Prior_High_52W": None, "Is_52W_High_Break": None, "Partial_52W_History": None,
        "Pct_From_52W_High": None, "Near_52W_High": None,
        "Prior_High_ATH": None, "Is_ATH_Break": None, "ATH_History_Complete": history_is_complete,
        "Pct_From_ATH": None, "Near_ATH": None,
        "Near_Any_High": None,
        "BOS": "NONE",
        "Days_History_D1": len(df_d1),
    }
    if df_d1.empty or len(df_d1) < 2:
        return empty_result

    current_high = float(df_d1["high"].iloc[-1])
    current_close = float(df_d1["close"].iloc[-1])
    prior = df_d1["high"].iloc[:-1]  # everything strictly before the latest candle

    def pct_and_near(level: float | None) -> tuple[float | None, bool | None]:
        if level is None or level == 0:
            return None, None
        pct_from = round((current_close - level) / level * 100.0, 4)
        near = pct_from >= -near_threshold_pct
        return pct_from, near

    def window_result(n_days: int) -> tuple[float | None, bool | None, bool, float | None, bool | None]:
        window = prior.tail(n_days)
        if window.empty:
            return None, None, True, None, None
        prior_high = float(window.max())
        pct_from, near = pct_and_near(prior_high)
        return round(prior_high, 8), current_high > prior_high, len(window) < n_days, pct_from, near

    high_3m, break_3m, partial_3m, pct_3m, near_3m = window_result(three_month_days)
    high_6m, break_6m, partial_6m, pct_6m, near_6m = window_result(six_month_days)
    high_52w, break_52w, partial_52w, pct_52w, near_52w = window_result(fifty_two_week_days)

    prior_high_ath = float(prior.max()) if not prior.empty else None
    break_ath = (current_high > prior_high_ath) if prior_high_ath is not None else None
    pct_ath, near_ath = pct_and_near(prior_high_ath)

    if break_52w:
        bos = "52WH"
    elif break_6m:
        bos = "6MH"
    elif break_3m:
        bos = "3MH"
    else:
        bos = "NONE"

    near_flags = [f for f in (near_3m, near_6m, near_52w, near_ath) if f is not None]
    near_any = any(near_flags) if near_flags else None

    return {
        "Prior_High_3M": high_3m,
        "Is_3M_High_Break": break_3m,
        "Partial_3M_History": partial_3m,
        "Pct_From_3M_High": pct_3m,
        "Near_3M_High": near_3m,
        "Prior_High_6M": high_6m,
        "Is_6M_High_Break": break_6m,
        "Partial_6M_History": partial_6m,
        "Pct_From_6M_High": pct_6m,
        "Near_6M_High": near_6m,
        "Prior_High_52W": high_52w,
        "Is_52W_High_Break": break_52w,
        "Partial_52W_History": partial_52w,
        "Pct_From_52W_High": pct_52w,
        "Near_52W_High": near_52w,
        "Prior_High_ATH": round(prior_high_ath, 8) if prior_high_ath is not None else None,
        "Is_ATH_Break": break_ath,
        "ATH_History_Complete": history_is_complete,
        "Pct_From_ATH": pct_ath,
        "Near_ATH": near_ath,
        "Near_Any_High": near_any,
        "BOS": bos,
        "Days_History_D1": len(df_d1),
    }


def compute_rsi_touch(df_d1: pd.DataFrame, threshold: float = RSI_TOUCH_THRESHOLD, lookback_days: int = RSI_TOUCH_LOOKBACK_DAYS) -> dict:
    """"Last touch RSI > threshold within the last N days" (D1): did RSI14
    get above `threshold` at ANY point in the last `lookback_days` daily
    bars, even if it's since cooled back down - not just the current bar.
    RSI_Highest_<lookback_days>D is the actual peak value, for context."""
    col_suffix = f"{lookback_days}D"
    if df_d1.empty:
        return {f"RSI_Highest_{col_suffix}": None, f"RSI_Touch_{threshold:g}_{col_suffix}": None}

    rsi_series = wilder_rsi_series(df_d1["close"])
    window = rsi_series.tail(lookback_days).dropna()
    if window.empty:
        return {f"RSI_Highest_{col_suffix}": None, f"RSI_Touch_{threshold:g}_{col_suffix}": None}

    highest = float(window.max())
    return {
        f"RSI_Highest_{col_suffix}": round(highest, 2),
        f"RSI_Touch_{threshold:g}_{col_suffix}": highest > threshold,
    }


def compute_avg_volume(df_d1: pd.DataFrame, lookback_days: int = AVG_VOL_LOOKBACK_DAYS_DEFAULT) -> dict:
    """Trailing N-day AVERAGE daily USDT notional volume (mean of
    volCcyQuote over the last `lookback_days` daily bars), computed off the
    same deep D1 history already fetched for the high-break flags - no
    extra API cost. This is the steadier liquidity measure used for
    --min-liquidity-usd filtering (see AVG_VOL_LOOKBACK_DAYS_DEFAULT),
    separate from Vol24h_USDT (today's live snapshot, kept for display).
    A token with less than `lookback_days` of history gets its average
    over whatever is available, flagged via Partial_AvgVol - per the
    project's "newly-listed pairs get a partial-period value with a flag,
    not a drop" rule - rather than being silently excluded."""
    col_suffix = f"{lookback_days}D"
    avg_col = f"AvgVol_{col_suffix}_USDT"
    partial_col = f"Partial_AvgVol_{col_suffix}"
    if df_d1.empty or "volCcyQuote" not in df_d1.columns:
        return {avg_col: None, partial_col: None}

    window = df_d1["volCcyQuote"].tail(lookback_days)
    if window.empty:
        return {avg_col: None, partial_col: None}

    return {
        avg_col: round(float(window.mean()), 2),
        partial_col: len(window) < lookback_days,
    }


def compute_row(
    session: ThrottledSession,
    inst_id: str,
    ma_type: str = MA_TYPE_DEFAULT,
    closed_only: bool = False,
    ath_max_history_pages: int = ATH_MAX_HISTORY_PAGES,
    near_high_threshold_pct: float = NEAR_HIGH_THRESHOLD_PCT,
    swing_high_lookback_days: int = SWING_HIGH_LOOKBACK_DAYS,
    avg_vol_lookback_days: int = AVG_VOL_LOOKBACK_DAYS_DEFAULT,
    tf_stack_hard_gate: bool = TF_STACK_HARD_GATE,
) -> dict:
    """One deep D1 fetch per instrument feeds everything - Close_D1/
    MA100_D1/Above_D1 (the "above MA100" trend gate), MA_Alignment_D1/
    AOTS_D1 (informational only - see "AOTS info columns" in the module
    docstring), RSI_D1, the 3M/6M/52W/ATH high-break + near-high flags,
    the two RSI-touch windows (21D display + the swing-high-lookback-days
    filter window), and the N-day average USDT volume (the liquidity
    filter - see compute_avg_volume()).

    Two lighter extra fetches (just CANDLE_FETCH_LIMIT recent bars each,
    not deep history) get the same MA100 status on H4 and H1, added back
    for probability stacking (see "Multi-timeframe stacking columns" in
    the module docstring) - these feed Above_H4/Above_H1 + the
    TF_Stack_Count/TF_Stack_All confluence columns.

    tf_stack_hard_gate: when True, folds TF_Stack_All (the full D1+H4+H1
    stack) into Above_All_TF itself instead of leaving H4/H1 purely
    informational - set via --tf-stack-hard-gate on the CLI, or change the
    TF_STACK_HARD_GATE default near the top of CONFIG. Off by default."""
    row: dict = {
        "InstId": inst_id,
        "BaseCcy": inst_id.split("-")[0],
    }

    df, history_is_complete = get_deep_daily_candles(
        session, inst_id, max_history_pages=ath_max_history_pages, closed_only=closed_only
    )
    status = compute_tf_status(df, ma_type=ma_type)
    row["Close_D1"] = status["close"]
    row["MA100_D1"] = round(status["ma100"], 8) if status["ma100"] is not None else None
    row["Above_D1"] = status["is_above"]
    row["MA_Alignment_D1"] = status["ma_alignment"]
    row["AOTS_D1"] = status["is_aots"]

    # H4 / H1 - probability-stacking columns only (see module docstring).
    # Reuses TIMEFRAMES' bar strings so this stays in sync with the config
    # block if someone retunes which bars "H4"/"H1" map to.
    df_h4 = get_candles(session, inst_id, TIMEFRAMES["H4"], closed_only=closed_only)
    status_h4 = compute_tf_status(df_h4, ma_type=ma_type)
    row["Close_H4"] = status_h4["close"]
    row["MA100_H4"] = round(status_h4["ma100"], 8) if status_h4["ma100"] is not None else None
    row["Above_H4"] = status_h4["is_above"]
    row["MA_Alignment_H4"] = status_h4["ma_alignment"]
    row["AOTS_H4"] = status_h4["is_aots"]

    df_h1 = get_candles(session, inst_id, TIMEFRAMES["H1"], closed_only=closed_only)
    status_h1 = compute_tf_status(df_h1, ma_type=ma_type)
    row["Close_H1"] = status_h1["close"]
    row["MA100_H1"] = round(status_h1["ma100"], 8) if status_h1["ma100"] is not None else None
    row["Above_H1"] = status_h1["is_above"]
    row["MA_Alignment_H1"] = status_h1["ma_alignment"]
    row["AOTS_H1"] = status_h1["is_aots"]

    # insufficient data can't be confirmed True, so it counts as False for
    # the stack tally - a token with no H4/H1 history yet just scores lower
    # on TF_Stack_Count rather than breaking the count.
    above_d1_bool = bool(status["is_above"])
    above_h4_bool = bool(status_h4["is_above"])
    above_h1_bool = bool(status_h1["is_above"])
    row["TF_Stack_Count"] = int(above_d1_bool) + int(above_h4_bool) + int(above_h1_bool)
    row["TF_Stack_All"] = above_d1_bool and above_h4_bool and above_h1_bool

    row.update(compute_high_breaks(df, history_is_complete, near_threshold_pct=near_high_threshold_pct))
    row.update(compute_rsi_touch(df))  # 21D touch (Discord WATCHLISTS line + sort key)
    row.update(compute_rsi_touch(df, threshold=SWING_HIGH_RSI_MIN_DEFAULT, lookback_days=swing_high_lookback_days))  # filter-relevant Nd touch
    row.update(compute_avg_volume(df, lookback_days=avg_vol_lookback_days))  # liquidity filter (replaces single-day 24h snapshot)

    rsi = wilder_rsi(df["close"]) if not df.empty else None
    row["RSI_D1"] = round(rsi, 2) if rsi is not None else None

    # Above_All_TF stays D1-only (same trend gate as the single-timeframe
    # script) unless tf_stack_hard_gate is turned on, in which case the
    # full D1+H4+H1 stack becomes the hard requirement again.
    row["Above_All_TF"] = (row["TF_Stack_All"] if tf_stack_hard_gate else above_d1_bool)
    row["AOTS_All_TF"] = bool(status["is_aots"])  # informational only
    row["LastRefreshed"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return row


# ============================================================================
# NETWORK LOOKUP (best-effort, manually maintained - see note below)
# ============================================================================

# OKX's public API (instruments/candles/tickers) does NOT return any
# blockchain/chain metadata for these perpetual swap contracts - there is
# no live source this script can pull "network" from. This is a hand-
# maintained BaseCcy -> network mapping, built from general knowledge, not
# verified against an authoritative source (e.g. CoinGecko's asset-platform
# data) - treat it as a best-effort starting point, NOT a source of truth,
# and edit/extend it directly as you spot wrong or missing entries. Several
# BaseCcy values scanned by this screener are actually tokenized US
# equities/ETFs (OKX offers these alongside crypto perpetuals, e.g. NVDA,
# META, MSTR) - those have no blockchain "network" in the usual sense, so
# they're bucketed separately into STOCK_TICKERS rather than guessed at.
# Anything not found in either table falls into "Other/Unclassified".
NETWORK_MAP: dict[str, str] = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "AVAX": "Avalanche",
    "NEAR": "NEAR", "SUI": "Sui", "WAL": "Sui", "APT": "Aptos", "TIA": "Celestia",
    "SEI": "Sei", "INJ": "Injective", "KSM": "Kusama", "ALGO": "Algorand",
    "ZIL": "Zilliqa", "QTUM": "Qtum", "NEO": "Neo", "GAS": "Neo",
    "ARB": "Arbitrum", "OP": "Optimism", "STX": "Stacks (Bitcoin L2)",
    "ZK": "zkSync (Ethereum L2)", "ZRO": "Ethereum (LayerZero)",
    "BERA": "Berachain", "TAO": "Bittensor", "OKB": "X Layer (OKX, Ethereum L2)",
    "RENDER": "Solana", "PYTH": "Solana", "JUP": "Solana", "RAY": "Solana",
    "W": "Solana", "MEW": "Solana", "PUMP": "Solana", "GRASS": "Solana",
    "MUBARAK": "Solana", "HUMA": "Solana",
    "WLD": "Optimism", "MAGIC": "Arbitrum", "BIGTIME": "Ethereum (appchain)",
    "PLUME": "Ethereum (Plume L2)", "MERL": "Bitcoin (Merlin L2)",
    "AR": "Arweave", "AAVE": "Ethereum", "COMP": "Ethereum", "SNX": "Ethereum",
    "AXS": "Ethereum/Ronin", "MANA": "Ethereum", "ENJ": "Ethereum",
    "BAT": "Ethereum", "ZRX": "Ethereum", "ARKM": "Ethereum", "API3": "Ethereum",
    "IMX": "Ethereum (Immutable X)", "GALA": "Ethereum/GalaChain",
    "ONDO": "Ethereum", "AGLD": "Ethereum", "YGG": "Ethereum/Polygon",
    "NMR": "Ethereum", "BAND": "Ethereum", "INIT": "Initia (Cosmos)",
}
# Confidently-identified tokenized US equities/ETFs scanned by the screener
# (OKX trades these as perpetuals alongside crypto). Not exhaustive.
STOCK_TICKERS: set[str] = {
    "NVDA", "META", "MSTR", "AMD", "CRWD", "HPE", "CSCO", "MRVL", "ISRG",
    "A", "SMH", "QQQ", "ASML", "TQQQ", "AMAT", "TWLO", "PROS", "CIEN",
    "EWZ", "GME", "OPENAI", "ALAB", "GEV", "SPCX",
}


def get_network(base_ccy: str) -> str:
    """Best-effort network/category lookup - see NETWORK_MAP's note above.
    Returns a blockchain name, "Tokenized Equities/ETFs" for known stock
    tickers, or "Other/Unclassified" for anything not in either table."""
    if base_ccy in STOCK_TICKERS:
        return "Tokenized Equities/ETFs"
    return NETWORK_MAP.get(base_ccy, "Other/Unclassified")


# Ethereum L2s/appchains whose NETWORK_MAP label doesn't literally contain
# the word "Ethereum" (e.g. "Arbitrum", "Optimism", "zkSync", "X Layer") but
# which still settle back to Ethereum - folded into the Ethereum bucket by
# simplify_network() below rather than each getting its own group.
ETH_L2_TOKENS: set[str] = {"ARB", "OP", "WLD", "MAGIC", "ZK", "OKB"}

# "Other Networks" used to be a single catch-all covering everything that
# wasn't Solana or Ethereum - that meant Bitcoin itself, half a dozen other
# L1s (Avalanche, Sui, Aptos, ...), AND tokenized stocks like NVDA/MSTR were
# all mixed into one vague bucket with no way to tell which was which
# without opening the CSV. Bitcoin and Tokenized Equities/ETFs are now
# their own buckets (both are large, recognizable, and NOT the same kind
# of thing as a random smaller L1), so "Other Networks" is left genuinely
# small - the long tail of less-common L1s only.
NETWORK_GROUP_ORDER = ["Solana", "Ethereum", "Bitcoin", "Tokenized Equities/ETFs", "Other Networks"]


def simplify_network(base_ccy: str) -> str:
    """Collapses get_network()'s ~15 detailed chain/category labels down to
    the 5 buckets used for Discord digest sub-grouping:
      Solana                     - the base chain plus Solana-ecosystem
                                    tokens (RENDER, PYTH, JUP, etc.)
      Ethereum                   - the base chain plus its L2s/appchains/
                                    LayerZero-bridged tokens (Arbitrum,
                                    Optimism, zkSync, X Layer, Immutable X,
                                    etc. all land here, not split out)
      Bitcoin                    - BTC itself plus Bitcoin L2s (Stacks,
                                    Merlin)
      Tokenized Equities/ETFs    - OKX's tokenized stock perpetuals
                                    (NVDA, META, MSTR, ...) - not a
                                    blockchain network at all, so these no
                                    longer get mixed in with crypto L1s
      Other Networks             - the genuine long tail: other L1s not
                                    common/large enough for their own
                                    bucket (Avalanche, Sui, Aptos,
                                    Celestia, Sei, Injective, Kusama,
                                    Algorand, Zilliqa, Qtum, Neo,
                                    Berachain, Bittensor, Arweave, Initia,
                                    and anything unclassified)
    This is the grouping actually used in the digest - the full per-chain
    NETWORK_MAP/get_network() detail isn't used directly because it
    produces too many tiny groups and blows Discord's embed-size budget."""
    network = get_network(base_ccy)
    if "Solana" in network:
        return "Solana"
    if "Ethereum" in network or base_ccy in ETH_L2_TOKENS:
        return "Ethereum"
    if "Bitcoin" in network:
        return "Bitcoin"
    if network == "Tokenized Equities/ETFs":
        return "Tokenized Equities/ETFs"
    return "Other Networks"


# ============================================================================
# DISCORD DELIVERY (optional)
# ============================================================================


# Display order for the Discord digest's 6 groups. The first 3 are actual
# breaks (BOS != "NONE", widest window first). The user found one single
# "No BOS Break" pile confusing, so that pile is now split into 3 clearer
# "Approaching <window> High" groups by which window a token is closest to
# breaking next (see _approach_tier()) - same widest-first ordering.
# Each tuple is (group_key, header_label, emoji, pct_col).
DIGEST_GROUPS: list[tuple[str, str, str, str]] = [
    ("52WH", "Near 52WH BOS", "\U0001F680", "Pct_From_52W_High"),   # 🚀 widest break
    ("6MH", "Near 6MH BOS", "\U0001F525", "Pct_From_6M_High"),      # 🔥
    ("3MH", "Near 3MH BOS", "⚡", "Pct_From_3M_High"),               # ⚡
    ("APPROACH_52W", "Approaching 52W High", "\U0001F7E3", "Pct_From_52W_High"),  # 🟣
    ("APPROACH_6M", "Approaching 6M High", "\U0001F7E1", "Pct_From_6M_High"),     # 🟡
    ("APPROACH_3M", "Approaching 3M High", "\U0001F7E0", "Pct_From_3M_High"),     # 🟠
]


def _approach_tier(row: pd.Series) -> str:
    """For a row that hasn't broken any high yet (BOS == 'NONE'), which
    window it's closing in on next - widest first, mirroring BOS's own
    break-tier priority (52W > 6M > 3M). Falls back to '3M' if somehow
    none of the Near_*_High flags are set (shouldn't happen given the
    Near_Any_High filter, but keeps every row bucketed somewhere)."""
    if row.get("Near_52W_High"):
        return "APPROACH_52W"
    if row.get("Near_6M_High"):
        return "APPROACH_6M"
    return "APPROACH_3M"


def _pct_str(pct: float | None) -> str:
    """Plain signed percent, no color/dot - e.g. '+2.3%' or '-20.2%'."""
    if pd.isna(pct):
        return "N/A"
    return f"{pct:+.1f}%"


def _fmt_vol(vol: float | None) -> str:
    """24h USDT volume, compact: $1.2B / $57.7M / $950.0K / $12."""
    if pd.isna(vol):
        return "N/A"
    vol = float(vol)
    if vol >= 1_000_000_000:
        return f"${vol / 1_000_000_000:.1f}B"
    if vol >= 1_000_000:
        return f"${vol / 1_000_000:.1f}M"
    if vol >= 1_000:
        return f"${vol / 1_000:.1f}K"
    return f"${vol:.0f}"


def _watchlist_line(row: pd.Series, swing_high_rsi_col: str, pct_col: str) -> str:
    """One WATCHLISTS row, simple/plain - no color dots, no YES/NO, no
    checkmark/cross: "TOKEN | {pct}% BOS | RSI Swing High Value: {value}
    | Vol: {vol}". `pct_col` is passed in by the caller (it depends on
    which digest group - actual BOS tier or "approaching" tier - the row
    is being rendered under, not just the row's own BOS value)."""
    pct_str = _pct_str(row.get(pct_col))
    rsi_val = row.get(swing_high_rsi_col)
    rsi_str = f"{rsi_val:.1f}" if pd.notna(rsi_val) else "N/A"
    vol_str = _fmt_vol(row.get("Vol24h_USDT"))
    return f"{row['BaseCcy']} | {pct_str} BOS | RSI Swing High Value: {rsi_str} | Vol: {vol_str}"


def _group_lines(group_rows: pd.DataFrame, swing_high_rsi_col: str, pct_col: str) -> list[str]:
    """Builds one digest group's WATCHLISTS lines, sub-grouped by network
    bucket (Solana / Ethereum / Bitcoin / Tokenized Equities-ETFs / Other
    Networks - see simplify_network(), NETWORK_GROUP_ORDER for the order),
    each as its own bold header line, in that order - only non-empty
    buckets get a header. Within each network bucket, rows are sorted by
    `pct_col` descending, then by the swing-high RSI value descending
    (highest/closest-to-breaking, strongest momentum first). Returns []
    for an empty group (caller handles the "(none)" case)."""
    if group_rows.empty:
        return []
    rows = group_rows.copy()
    rows["_network_bucket"] = rows["BaseCcy"].map(simplify_network)
    lines: list[str] = []
    for bucket in NETWORK_GROUP_ORDER:
        bucket_rows = rows[rows["_network_bucket"] == bucket]
        if bucket_rows.empty:
            continue
        sorted_rows = bucket_rows.sort_values([pct_col, swing_high_rsi_col], ascending=[False, False])
        lines.append(f"**{bucket}**")
        lines.extend(_watchlist_line(row, swing_high_rsi_col, pct_col) for _, row in sorted_rows.iterrows())
    return lines


def _chunk_group_lines(lines: list[str], max_chars: int = DISCORD_FIELD_VALUE_MAX) -> list[str]:
    """Splits a BOS group's WATCHLISTS lines into as many field-sized
    chunks as needed, WITHOUT dropping any token - a large group (e.g.
    "No BOS Break" with 90+ tokens) used to be silently truncated
    (pop-from-end) past Discord's ~1000-char field-value cap, which meant
    real, passing tokens near the bottom of the sort order (lower
    swing-high RSI) just disappeared from the digest with no indication.
    Now every line gets its own field if needed - see build_discord_digest()
    for how these chunks turn into "(cont'd N/M)" fields. Returns ["(none)"]
    for an empty group so the field still renders as its own section."""
    if not lines:
        return ["(none)"]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        added_len = len(line) + (1 if current else 0)  # +1 for the joining "\n"
        if current and current_len + added_len > max_chars:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += added_len
    if current:
        chunks.append("\n".join(current))
    return chunks


MAX_DIGEST_PAGES = 5   # safety cap on how many separate Discord messages one
                        # run will send - if even this many pages can't fit
                        # everything (extreme edge case), the remainder is
                        # disclosed via the omission line on the last page
                        # rather than sending an unbounded number of messages


def build_discord_digest(
    above_all: pd.DataFrame,
    run_date: str,
    total_scanned: int,
    min_rsi: float,
    swing_high_lookback_days: int = SWING_HIGH_LOOKBACK_DAYS,
    tf_stack_hard_gate: bool = TF_STACK_HARD_GATE,
) -> list[dict]:
    """Builds the Discord digest as a LIST of one or more embeds (one per
    Discord message) in the WATCHLISTS layout, grouped into up to 6
    sections (see DIGEST_GROUPS): the 3 actual-break tiers (52WH/6MH/3MH,
    widest first) plus - replacing the old single, confusing "No BOS
    Break" catch-all - 3 clearer "Approaching 52W/6M/3M High" tiers for
    tokens that haven't broken a high yet, split by which window they're
    closest to breaking next (see _approach_tier()). Within each section,
    rows are further sub-grouped by network bucket - Solana / Ethereum /
    Other Networks, see simplify_network() - each with its own bold
    header, sorted within that bucket by % to the group's high level
    descending, then by the swing-high RSI value descending (see
    _group_lines()). One plain line per token, no color dots, no
    YES/NO/checkmarks: "TOKEN | {pct}% BOS | RSI Swing High Value:
    {value} | Vol: {vol}".

    Previously everything was squeezed into ONE embed, and tokens that
    didn't fit Discord's 25-field/6000-char-per-message caps were just
    counted in a "N more token(s) couldn't fit" warning instead of
    actually being shown - not lost, but not visible in the channel
    either. Now, when one message isn't enough, the digest SPANS MULTIPLE
    Discord messages instead ("... (Part 2/3)" in the title) so every
    passing token actually shows up in the channel. Each message repeats
    the header/footer/Notes field so it reads standalone. Capped at
    MAX_DIGEST_PAGES messages per run as a last-resort safety net (an
    extreme edge case only) - if even that isn't enough, the remainder is
    disclosed via an omission line in the final message's Notes field
    rather than sending unlimited messages. The footer always ends with a
    "Trade at Your Own Risk" disclaimer. No CSV attached."""
    # The required gate stays D1-only (or the full stack if
    # tf_stack_hard_gate is on - see --tf-stack-hard-gate / TF_STACK_HARD_GATE)
    # - TIMEFRAMES also contains H4/H1 now (added for probability stacking,
    # see module docstring), so build this label from the actual gate
    # rather than every fetched timeframe.
    gate_tf_list = "D1+H4+H1 (TF_Stack_All)" if tf_stack_hard_gate else "D1"
    swing_high_rsi_col = f"RSI_Highest_{swing_high_lookback_days}D"

    base_title = f"OKX MA100 Demarcation Screener - {run_date} UTC"
    footer_text = (
        f"{total_scanned} instruments scanned - Above MA100 on {gate_tf_list}, "
        f"RSI {RSI_FILTER_TF} > {min_rsi:g} | ⚠️ Trade at Your Own Risk"
    )
    notes_name = "\U0001F4DD Notes"
    notes_base_value = (
        "BOS = Break of Structure (52WH/6MH/3MH = the 52-week/6-month/3-month high was broken)\n"
        "Approaching 52W/6M/3M High = hasn't broken a high yet, but is closing in on that window's level next\n"
        f"RSI Swing High Value = highest daily RSI14 touched in the last {swing_high_lookback_days} days\n"
        "Each section is sub-grouped by network (Solana / Ethereum / Bitcoin / Tokenized Equities-ETFs / "
        "Other Networks - the smaller/less common chains only), sorted by % then RSI within it - network is "
        "a best-effort lookup, not authoritative (see NETWORK_MAP in the script)"
    )
    header_name = f"\U0001F4CB WATCHLISTS ({len(above_all)})"
    header_value = "​"
    # worst-case title suffix reserved on every page so the real "(Part N/M)"
    # text (always shorter than this) never pushes a page over budget
    title_suffix_reserve = " (Part 99/99)"
    # extra room reserved for the "N more token(s) omitted" line that might
    # get appended to the last page's Notes, so adding it never breaks the budget
    omission_line_budget = 160

    fixed_chars = (
        len(base_title) + len(title_suffix_reserve) + len(footer_text)
        + len(notes_name) + len(notes_base_value) + omission_line_budget
        + len(header_name) + len(header_value)
    )
    max_body_fields = DISCORD_MAX_FIELDS - 1  # reserve one field slot per page for "Notes"
    char_budget_per_page = DISCORD_EMBED_TOTAL_MAX - fixed_chars

    # tag every "no break yet" row with which window it's approaching next,
    # so the group filter below can split them into the 3 APPROACH_* tiers
    none_mask = above_all["BOS"] == "NONE"
    approach_tier_col = pd.Series(index=above_all.index, dtype=object)
    if none_mask.any():
        approach_tier_col.loc[none_mask] = above_all.loc[none_mask].apply(_approach_tier, axis=1)

    # Pass 1: build every (name, chunk) field across all 6 groups, fully
    # chunked (_chunk_group_lines already guarantees no token is dropped
    # within a single group) - pagination below just decides which page
    # each of these fields lands on, nothing here can lose a token.
    all_fields: list[dict] = []
    for group_key, header_label, emoji, pct_col in DIGEST_GROUPS:
        if group_key.startswith("APPROACH_"):
            group_rows = above_all[none_mask & (approach_tier_col == group_key)]
        else:
            group_rows = above_all[above_all["BOS"] == group_key]
        token_count = len(group_rows)

        lines = _group_lines(group_rows, swing_high_rsi_col, pct_col)
        chunks = _chunk_group_lines(lines)
        for chunk_idx, chunk in enumerate(chunks):
            name = f"{emoji} {header_label} ({token_count})"
            if len(chunks) > 1:
                name += f" - cont'd {chunk_idx + 1}/{len(chunks)}"
            all_fields.append({"name": name, "value": chunk})

    # Pass 2: paginate those fields across messages, each page staying
    # under Discord's per-message field/char caps.
    pages: list[list[dict]] = [[]]
    page_chars = [0]
    omitted_tokens = 0
    for field in all_fields:
        field_chars = len(field["name"]) + len(field["value"])
        current = pages[-1]
        fits_current_page = len(current) < max_body_fields and page_chars[-1] + field_chars <= char_budget_per_page
        if not fits_current_page:
            if len(pages) >= MAX_DIGEST_PAGES:
                # safety net exhausted - disclose rather than keep paginating forever
                omitted_tokens += sum(1 for ln in field["value"].split("\n") if ln and not ln.startswith("**"))
                continue
            pages.append([])
            page_chars.append(0)
            current = pages[-1]
        current.append(field)
        page_chars[-1] += field_chars

    total_pages = len(pages)
    embeds: list[dict] = []
    for i, page_fields in enumerate(pages, start=1):
        title = base_title + (f" (Part {i}/{total_pages})" if total_pages > 1 else "")
        notes_value = notes_base_value
        if i == total_pages and omitted_tokens:
            notes_value += (
                f"\n⚠️ {omitted_tokens} more token(s) passed the screen but couldn't fit even across "
                f"{MAX_DIGEST_PAGES} Discord messages - see the CSV for the full list."
            )
        fields = (
            [{"name": header_name, "value": header_value, "inline": False}]
            + [{"name": f["name"], "value": f["value"], "inline": False} for f in page_fields]
            + [{"name": notes_name, "value": notes_value, "inline": False}]
        )
        embeds.append({
            "title": title,
            "color": DISCORD_EMBED_COLOR,
            "fields": fields,
            "footer": {"text": footer_text},
        })
    return embeds


def parse_webhook_urls(raw: str) -> list[str]:
    """Splits --discord-webhook / DISCORD_WEBHOOK_URL on commas, whitespace,
    and newlines so one or more webhook URLs can be supplied - e.g. your
    main channel's webhook AND a community channel's webhook at the same
    time. Blank entries (trailing commas, extra spaces) are dropped."""
    if not raw:
        return []
    parts = raw.replace("\n", ",").replace(" ", ",").split(",")
    return [p.strip() for p in parts if p.strip()]


def post_to_discord(webhook_url: str, embed: dict, mention: str | None = None) -> None:
    """Posts the digest embed to a Discord incoming webhook as plain text -
    no file attached. `mention`, if given, is sent as the message's plain
    "content" (e.g. "@here", "@everyone", or a role mention like
    "<@&123456789012345678>") so the message actually pings/notifies instead
    of posting silently - an embed's own fields never trigger a
    notification on their own."""
    payload: dict = {"embeds": [embed]}
    if mention:
        payload["content"] = mention
        payload["allowed_mentions"] = {"parse": ["everyone", "roles", "users"]}
    resp = requests.post(webhook_url, json=payload, timeout=30)
    resp.raise_for_status()


# ============================================================================
# PIPELINE
# ============================================================================


def run_screener(
    output_dir: Path,
    ma_type: str = MA_TYPE_DEFAULT,
    closed_only: bool = False,
    min_liquidity_usd: float = MIN_LIQUIDITY_USD_DEFAULT,
    min_rsi: float = RSI_FILTER_MIN_DEFAULT,
    ath_max_history_pages: int = ATH_MAX_HISTORY_PAGES,
    near_high_threshold_pct: float = NEAR_HIGH_THRESHOLD_PCT,
    require_near_high: bool = True,
    swing_high_lookback_days: int = SWING_HIGH_LOOKBACK_DAYS,
    min_swing_high_rsi: float = SWING_HIGH_RSI_MIN_DEFAULT,
    avg_vol_lookback_days: int = AVG_VOL_LOOKBACK_DAYS_DEFAULT,
    discord_webhook: str | None = None,
    discord_mention: str | None = None,
    tf_stack_hard_gate: bool = TF_STACK_HARD_GATE,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)
    session = ThrottledSession()

    inst_ids = get_live_usdt_swap_instruments(session)
    tf_count = len(TIMEFRAMES)  # D1 + H4 + H1 fetched per instrument (probability-stacking columns)
    gate_tf_count = 3 if tf_stack_hard_gate else 1  # what actually gates Above_All_TF - see --tf-stack-hard-gate
    log.info(
        "Scanning %d instruments x %d timeframes (D1/H4/H1, H4+H1 for probability stacking only),"
        " plus deep D1 history (up to %d extra pages/instrument for the 3M/52W/ATH break flags)"
        " - this takes a few minutes under OKX's rate limit",
        len(inst_ids), tf_count, ath_max_history_pages,
    )

    rows = []
    for i, inst_id in enumerate(inst_ids, start=1):
        try:
            rows.append(compute_row(
                session, inst_id, ma_type=ma_type, closed_only=closed_only,
                ath_max_history_pages=ath_max_history_pages,
                near_high_threshold_pct=near_high_threshold_pct,
                tf_stack_hard_gate=tf_stack_hard_gate,
                swing_high_lookback_days=swing_high_lookback_days,
                avg_vol_lookback_days=avg_vol_lookback_days,
            ))
        except Exception as exc:
            log.error("Failed on %s: %s", inst_id, exc)
        if i % 25 == 0 or i == len(inst_ids):
            log.info("Progress: %d/%d instruments scanned", i, len(inst_ids))

    result = pd.DataFrame(rows)

    # Vol24h_USDT: today's live 24h snapshot, one single call covers every
    # instrument so it adds no per-instrument request cost - kept as a
    # display/context column (shown in the CSV and the Discord digest's
    # "Vol:" figure) but NOT used for the liquidity filter anymore (see
    # AvgVol_<N>D_USDT below, added in compute_row()/compute_avg_volume()).
    volumes = get_24h_usdt_volume(session)
    result["Vol24h_USDT"] = result["InstId"].map(volumes).fillna(0.0)

    run_date = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    dated_path = output_dir / f"okx_demarcation_scan_{run_date}.csv"
    latest_path = output_dir / "okx_demarcation_latest.csv"
    result.to_csv(dated_path, index=False)
    result.to_csv(latest_path, index=False)

    rsi_col = f"RSI_{RSI_FILTER_TF}"
    swing_high_col = f"RSI_Highest_{swing_high_lookback_days}D"
    avg_vol_col = f"AvgVol_{avg_vol_lookback_days}D_USDT"
    mask = (
        (result["Above_All_TF"] == True)  # noqa: E712
        & (result[avg_vol_col].fillna(0.0) >= min_liquidity_usd)
        & (result[rsi_col] > min_rsi)
        & (result[swing_high_col] > min_swing_high_rsi)
    )
    if require_near_high:
        mask &= (result["Near_Any_High"] == True)  # noqa: E712
    above_all = result[mask].sort_values(avg_vol_col, ascending=False).reset_index(drop=True)
    above_all_path = output_dir / "okx_demarcation_above_all_latest.csv"
    above_all.to_csv(above_all_path, index=False)

    log.info(
        "%d / %d instruments are above the MA100 demarcation line on ALL %d required timeframe(s)"
        " (min %d-day avg liquidity: $%s USDT, RSI %s > %s, swing-high (%dD) RSI > %s,"
        " near-high filter: %s within %s%%) - sorted by %d-day avg volume, highest first"
        " [H4/H1 fetched for probability stacking (TF_Stack_Count/TF_Stack_All columns), %s]",
        len(above_all), len(result), gate_tf_count, avg_vol_lookback_days, f"{min_liquidity_usd:,.0f}",
        RSI_FILTER_TF, f"{min_rsi:g}",
        swing_high_lookback_days, f"{min_swing_high_rsi:g}",
        "on" if require_near_high else "off", f"{near_high_threshold_pct:g}", avg_vol_lookback_days,
        "required via --tf-stack-hard-gate" if tf_stack_hard_gate else "not required (informational only)",
    )
    if not above_all.empty:
        log.info("Above all TFs: %s", ", ".join(above_all["BaseCcy"].tolist()))

    log.info("Wrote %s, %s, %s", dated_path, latest_path, above_all_path)

    if discord_webhook:
        webhook_urls = parse_webhook_urls(discord_webhook)
        if webhook_urls:
            embeds = build_discord_digest(
                above_all, run_date, total_scanned=len(result), min_rsi=min_rsi,
                swing_high_lookback_days=swing_high_lookback_days,
                tf_stack_hard_gate=tf_stack_hard_gate,
            )
            for url in webhook_urls:
                try:
                    # multi-page digests send one message per embed, in
                    # order ("Part 1/3", "Part 2/3", ...) - the ping (if
                    # any) only goes on the first message, not repeated on
                    # every page. A short pause between pages keeps this
                    # well under Discord's per-webhook rate limit.
                    for i, embed in enumerate(embeds):
                        post_to_discord(url, embed, mention=discord_mention if i == 0 else None)
                        if i < len(embeds) - 1:
                            time.sleep(1.0)
                    page_note = f" ({len(embeds)} messages)" if len(embeds) > 1 else ""
                    log.info("Posted digest to Discord%s (%s)", page_note, url.rsplit("/", 1)[-1][:8] + "...")
                except Exception as exc:
                    # one bad/rate-limited/deleted webhook shouldn't stop the others
                    log.error("Discord post failed for %s...: %s", url[:50], exc)

    return above_all


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="OKX USDT swap MA100 demarcation-line screener")
    parser.add_argument("--output-dir", type=Path, default=Path("./screener_output"))
    parser.add_argument("--ma-type", choices=["SMA", "EMA"], default=MA_TYPE_DEFAULT)
    parser.add_argument(
        "--closed-only",
        action="store_true",
        help="Only use fully-closed candles on every timeframe (drops the still-forming bar instead of matching the live chart).",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=None,
        help="If set, keep running and re-scan every N minutes instead of exiting after one pass.",
    )
    parser.add_argument(
        "--min-liquidity-usd",
        type=float,
        default=MIN_LIQUIDITY_USD_DEFAULT,
        help=(
            f"Drop results below this trailing N-day AVERAGE daily USDT notional volume "
            f"(AvgVol_<N>D_USDT, N = --avg-vol-lookback-days; default ${MIN_LIQUIDITY_USD_DEFAULT:,.0f}, "
            f"0 = no filtering). Steadier than a single day's 24h snapshot. The output is always sorted "
            f"descending by this value. Today's live 24h volume is still shown separately as Vol24h_USDT."
        ),
    )
    parser.add_argument(
        "--avg-vol-lookback-days",
        type=int,
        default=AVG_VOL_LOOKBACK_DAYS_DEFAULT,
        help=f"Trailing daily-bar window used for the average-volume liquidity filter (default {AVG_VOL_LOOKBACK_DAYS_DEFAULT}).",
    )
    parser.add_argument(
        "--min-rsi",
        type=float,
        default=RSI_FILTER_MIN_DEFAULT,
        help=f"Drop results where the {RSI_FILTER_TF} RSI14 is not strictly greater than this (default {RSI_FILTER_MIN_DEFAULT:g}).",
    )
    parser.add_argument(
        "--ath-max-history-pages",
        type=int,
        default=ATH_MAX_HISTORY_PAGES,
        help=(
            f"Extra /market/history-candles pages (100 daily bars each) fetched per instrument beyond the "
            f"initial 300, for the 3M/52W/ATH break flags (default {ATH_MAX_HISTORY_PAGES} -> up to "
            f"~{300 + ATH_MAX_HISTORY_PAGES * 100} daily bars). Higher = a more literal all-time-high, slower run."
        ),
    )
    parser.add_argument(
        "--near-high-pct",
        type=float,
        default=NEAR_HIGH_THRESHOLD_PCT,
        help=(
            f"A token is 'near' a 3M/6M/52W/ATH high level when its close is within this percent of "
            f"that level, or already above it (default {NEAR_HIGH_THRESHOLD_PCT:g})."
        ),
    )
    parser.add_argument(
        "--require-near-high",
        dest="require_near_high",
        action="store_true",
        default=True,
        help="Require Near_Any_High (within --near-high-pct of, or already broke, at least one of the "
             "3M/6M/52W/ATH levels) to pass the screen. On by default.",
    )
    parser.add_argument(
        "--no-require-near-high",
        dest="require_near_high",
        action="store_false",
        help="Disable the near-high requirement (the Near_* columns are still computed and written to the CSVs).",
    )
    parser.add_argument(
        "--swing-high-lookback-days",
        type=int,
        default=SWING_HIGH_LOOKBACK_DAYS,
        help=(
            f"Trailing daily-bar window (today included) used to find the highest RSI14 touched recently "
            f"(default {SWING_HIGH_LOOKBACK_DAYS})."
        ),
    )
    parser.add_argument(
        "--min-swing-high-rsi",
        type=float,
        default=SWING_HIGH_RSI_MIN_DEFAULT,
        help=(
            f"Require the highest RSI14 touched in that lookback window (RSI_Highest_<lookback>D) to be "
            f"strictly greater than this (default {SWING_HIGH_RSI_MIN_DEFAULT:g})."
        ),
    )
    parser.add_argument(
        "--tf-stack-hard-gate",
        dest="tf_stack_hard_gate",
        action="store_true",
        default=TF_STACK_HARD_GATE,
        help=(
            "MTF variant only. H4 and H1 MA100 demarcation checks are added back alongside D1 for "
            "probability stacking (TF_Stack_Count 0-3, TF_Stack_All) - informational columns on every "
            "CSV, NOT required by default. Pass this flag to fold TF_Stack_All into Above_All_TF itself, "
            "making 'above its own MA100 on D1 AND H4 AND H1' a hard requirement again, same as this "
            "screener's pre-MTF behaviour. Off by default."
        ),
    )
    parser.add_argument(
        "--discord-webhook",
        default=os.environ.get("DISCORD_WEBHOOK_URL"),
        help=(
            "Discord incoming-webhook URL to post a digest to every run (or set DISCORD_WEBHOOK_URL). "
            "Pass multiple URLs separated by commas to post to several channels at once, e.g. "
            '"https://discord.com/api/webhooks/AAA,https://discord.com/api/webhooks/BBB".'
        ),
    )
    parser.add_argument(
        "--discord-mention",
        default=os.environ.get("DISCORD_MENTION"),
        help='Optional mention to prepend so the message pings, e.g. "@here", "@everyone", or a role mention (or set DISCORD_MENTION).',
    )
    args = parser.parse_args()

    kwargs = dict(
        ma_type=args.ma_type,
        closed_only=args.closed_only,
        min_liquidity_usd=args.min_liquidity_usd,
        avg_vol_lookback_days=args.avg_vol_lookback_days,
        min_rsi=args.min_rsi,
        ath_max_history_pages=args.ath_max_history_pages,
        near_high_threshold_pct=args.near_high_pct,
        require_near_high=args.require_near_high,
        swing_high_lookback_days=args.swing_high_lookback_days,
        min_swing_high_rsi=args.min_swing_high_rsi,
        discord_webhook=args.discord_webhook,
        discord_mention=args.discord_mention,
        tf_stack_hard_gate=args.tf_stack_hard_gate,
    )

    if args.interval_minutes:
        while True:
            run_screener(args.output_dir, **kwargs)
            log.info("Sleeping %d minutes until next scan...", args.interval_minutes)
            time.sleep(args.interval_minutes * 60)
    else:
        run_screener(args.output_dir, **kwargs)


if __name__ == "__main__":
    main()
