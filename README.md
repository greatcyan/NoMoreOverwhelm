# OKX USDT Perpetual Screener

Hourly screener of every live USDT-margined perpetual swap on OKX, with MA20/50/100, Wilder RSI(14) and 52-week range. Runs on GitHub Actions, commits CSVs back to this repo for Power BI, and posts to Discord.

## How a run works

The workflow fires every hour at **:10 UTC**. In `auto` mode the script decides what to do:

| Run | When | What it does |
|---|---|---|
| **Daily rebuild** | First run after the 00:00 UTC candle close (00:10 UTC = 08:10 PHT), or any run where yesterday's candle is missing (self-heals after a failed run) | Pulls the instrument list and ~400 closed daily candles per pair, recomputes all indicators, overwrites `screener_latest.csv`, appends to `screener_history.csv`, posts the daily summary |
| **Hourly overlay** | The other 23 runs | One call to `/market/tickers`, overlays live price on the closed-candle indicators, writes `screener_live.csv`, posts *new* signals only |

Indicators are always calculated on **closed** daily candles (`bar=1Dutc`, unconfirmed bar dropped), so they match TradingView's daily chart. The hourly run adds provisional "live" fields on top rather than recomputing from a partial bar.

## Output files (`data/`)

| File | Grain | Behaviour | Use in Power BI |
|---|---|---|---|
| `screener_latest.csv` | 1 row per pair | Overwritten daily | Current screener (closed-candle values) |
| `screener_history.csv` | 1 row per pair per day | Appended daily, idempotent on `InstId + Date` | Screener history / trend fact table |
| `screener_live.csv` | 1 row per pair | Overwritten hourly | Intraday view: `LastPrice`, `Chg_Today`, `RSI14_Live`, `Pct_From_*_Live` |
| `state/signals_sent.json` | — | Today's already-posted signals | Internal (stops repeat Discord posts) |

Key columns: `Pct_*` columns are **fractions** (0.05 = 5%) — format as percentage in the model. `Volume` is base currency (e.g. BTC, not contracts); `VolumeUSDT` is quote volume. `Is_Partial_52W = TRUE` means the pair has under 364 days of history, so its 52W high/low covers only what exists. MAs are blank until enough bars exist.

## Setup (≈10 minutes)

1. **Create the repo.** On GitHub: New repository → name it e.g. `okx-screener` → **Public** (see trade-offs below) → create. Upload these files (or `git init`, commit, `git push`).
2. **Create two Discord webhooks.** In your server: `#screener-feed` → Edit Channel → Integrations → Webhooks → New Webhook → Copy URL. Repeat for `#pipeline-status`.
3. **Add them as secrets.** Repo → Settings → Secrets and variables → Actions → New repository secret:
   - `DISCORD_WEBHOOK_SCREENER` = `#screener-feed` URL
   - `DISCORD_WEBHOOK_STATUS` = `#pipeline-status` URL
4. **Allow the workflow to commit.** Settings → Actions → General → Workflow permissions → **Read and write permissions** → Save.
5. **First run.** Actions tab → *OKX Screener* → Run workflow → mode `daily`. Takes roughly 2–4 minutes. Check that `data/` now has CSVs and Discord got a summary.

The hourly schedule starts on its own after that.

## Connect Power BI

For a public repo, use the raw file URL with the Web connector (Anonymous auth). It refreshes in the Service without a gateway.

```m
let
    Source   = Csv.Document(
                   Web.Contents("https://raw.githubusercontent.com/<you>/okx-screener/main/data/screener_history.csv"),
                   [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed    = Table.TransformColumnTypes(Promoted, {
                   {"InstId", type text}, {"BaseCcy", type text}, {"Date", type date},
                   {"Open", type number}, {"High", type number}, {"Low", type number}, {"Close", type number},
                   {"Volume", type number}, {"VolumeUSDT", type number},
                   {"MA20", type number}, {"MA50", type number}, {"MA100", type number}, {"RSI14", type number},
                   {"High_52W", type number}, {"Low_52W", type number},
                   {"Pct_From_52WH", Percentage.Type}, {"Pct_From_52WL", Percentage.Type},
                   {"Bars_Available", Int64.Type}, {"Is_Partial_52W", type logical}, {"LastRefreshed", type datetime}
               }, "en-US")
in
    Typed
```

Suggested model: `screener_history` as the fact table, a `Date` dimension, and a `Coin` dimension (distinct `InstId`, `BaseCcy`). Bring in `screener_live` as a separate table related on `InstId` for the intraday page. Note that `raw.githubusercontent.com` caches for about 5 minutes, and the Service's own schedule limits (8/day on Pro) apply, so the intraday page is "near-live", not tick-live.

## Trade-offs to know

- **Public vs private repo.** Public gives unlimited Actions minutes and the simple anonymous Power BI connection above. The data is public market data and the webhooks are stored as secrets, so nothing sensitive is exposed. A private repo works too (roughly 800 of the free 2,000 minutes/month at this schedule), but Power BI then needs a token to read raw files, which is awkward to refresh in the Service.
- **GitHub cron is best-effort.** Scheduled runs can start 5–30 minutes late at busy times and are occasionally skipped. The self-heal check means a skipped 00:10 run is rebuilt by the next one.
- **60-day rule.** GitHub disables schedules in repos with no activity for 60 days. The hourly data commits count as activity, so this shouldn't trigger.
- **Commit volume.** Hourly runs commit `screener_live.csv`, so expect around 24 small commits a day. If that bothers you, remove `screener_live.csv` from the commit step and rely on Discord for intraday.
- **History size.** About 300 pairs × 365 days ≈ 110k rows/year (~20 MB CSV). Fine for years; switch to yearly files or Parquet if it grows uncomfortable.

## If OKX blocks the runner (HTTP 403)

GitHub-hosted runners use cloud IPs. OKX's public API has generally served US IPs, but some hosting providers' IPs get a Cloudflare 403. If the status channel shows *"HTTP 403 … blocking this runner's IP/region"*:

1. Try another domain: Settings → Secrets and variables → Actions → **Variables** → add `OKX_BASE_URL` (for example `https://us.okx.com`) and re-run.
2. Or run it on your own PC as a **self-hosted runner** (Settings → Actions → Runners → New self-hosted runner) and change `runs-on: ubuntu-latest` to `runs-on: self-hosted`. Your PC must be on for the schedule to run.

## Run locally

```bash
pip install -r requirements.txt
pytest -q
python -m screener --mode daily --limit 20 --no-discord   # quick test on 20 pairs
```

## Signals posted hourly

Each fires at most once per pair per UTC day: new 52W high/low (pairs with full history only), live RSI crossing below 30 or above 70, and price crossing above or below MA20/50/100 versus the last daily close.
