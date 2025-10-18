# Stock 52-Week & Monthly Low Notifier

This Python script monitors selected Indian stocks on the BSE (Bombay Stock Exchange) and notifies you via Telegram when any tracked stock reaches its 52-week low or monthly low. It also provides a summary of how far each stock is from these lows as a percentage.

## Features
- Monitors a customizable list of BSE stocks (Yahoo Finance format, e.g., `RELIANCE.BO`).
- Fetches real-time/daily stock data using Yahoo Finance (`yfinance`).
- Detects when a stock reaches its 52-week or monthly (last 30 days) low.
- Sends distinct Telegram notifications for 52-week and monthly lows, including a summary of percentage distance from both lows.
- Sends a Telegram message when the script starts, finishes, or if no stocks reach their lows.
- Structured logging to both console and a rotating log file.
- Robust error handling and Telegram alerts for errors.
- Loads sensitive information (Telegram bot token and chat ID) from a `.env` file using `python-dotenv`.
- Can be run in development mode to test functionality instantly.

## Requirements
- Python 3.8+
- `yfinance`, `requests`, `schedule`, `pytz`, `python-dotenv`

Install dependencies:
```bash
pip install yfinance requests schedule pytz python-dotenv
```

## Setup
1. **Clone or copy this repository.**
2. **Create a `.env` file in the project directory:**
   ```
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   TELEGRAM_CHAT_ID=your_telegram_chat_id_here
   ```
3. **Edit the `TRACKED_STOCKS` list in the script** to include the BSE stock symbols you want to monitor (Yahoo Finance format, e.g., `TCS.BO`).

## Usage
- **Production**
  ```bash
  python 52_week_and_monthly_low_stock_notifier.py
  ```

## Logging
- Logs are written to both the console and `stock_notifier.log` (rotating log file).

## Notifications
- Telegram notifications are sent for:
  - Script start and finish
  - Any stock reaching its 52-week or monthly low
  - If no stocks reach their lows
  - Any errors during execution

## License
This project is for personal and educational use.
