# NIFTY One-Percent Drop Notifier

Small Python script that monitors NIFTY 50 (via Yahoo Finance) and sends Telegram alerts when the index drops by whole percent steps (‑1%, ‑2%, …) from the all‑time high (ATH). It also notifies on new ATHs.

## Features

- Computes ATH from Yahoo Finance daily history.
- Periodically polls live price and alerts on each whole percent drop from ATH.
- Sends alerts to Telegram (bot + chat). If Telegram is not configured the script logs the messages it would send.
- Persists state (ATH, prev_k, last price, last ATH date) to a JSON file and performs a simple migration from the older `next_k` schema.
- Rotating logs for diagnostics.

## Requirements

- Python 3.8+
- pip packages:
  - yfinance
  - python-dotenv
  - requests

Install dependencies:

```bash
python -m pip install yfinance python-dotenv requests
```

## Files

- script.py — main monitoring script.
- nifty_yahoo_state.json — state file (created automatically).
- logs/nifty.log — rotating log file (created automatically).
- .env — environment variables (not tracked).

## Configuration (.env)

Create a `.env` file in the same directory as `script.py` with these variables:

```
# filepath: /Users/abhishek/Documents/stock-notifier/nifty-one-percent-drop-notifier/.env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF  # your Telegram bot token
TELEGRAM_CHAT_ID=987654321         # chat id to send alerts to
POLL_SECS=900                       # optional: polling interval in seconds (default 900)
LOG_LEVEL=INFO                      # optional: DEBUG, INFO, WARNING, ERROR
LOG_DIR=/path/to/log/dir            # optional: custom log directory
```

## Usage

Run the script from the project directory:

```bash
python script.py
```

Run in background via systemd / supervisor / screen / tmux as you prefer.

## Behavior / Notes

- On first run the script computes ATH from Yahoo daily history and stores it in the state file.
- The script now stores `prev_k` (the last observed integer percent drop bucket). If an older state file uses `next_k`, the script will migrate it automatically on load.
- Every POLL_SECS seconds it fetches the latest price:
  - If price > ATH → new ATH alert is sent and `prev_k` is reset to 0.
  - If price falls into deeper integer percent buckets, the script sends alerts for each newly crossed whole-percent bucket (e.g., -1%, -2%, -3%).
  - If price recovers (moves to a smaller-drop bucket), the script logs a recovery and updates `prev_k` in state (no Telegram alert for recovery).
- ATH is refreshed once per day (or on first run) and `prev_k` is reset when ATH is refreshed.

## Logs & State

- Logs: default `logs/nifty.log` (rotating).
- State: `nifty_yahoo_state.json` (in script directory).
- To reset ATH or alert buckets, stop the script and remove or edit the state file.

## Troubleshooting

- If no price data: ensure network access and that yfinance is working.
- If Telegram errors: verify bot token and chat id; inspect logs for HTTP responses.
- Yahoo data is delayed — alerts note that source is delayed.

## License

This project is for personal and educational use.
