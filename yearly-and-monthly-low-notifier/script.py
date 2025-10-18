import yfinance as yf
import requests
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import os
import time
from pathlib import Path

TRACKED_STOCKS = [
    'BEL.BO',
    'BHEL.BO',
    'CANBK.BO',
    'CDSL.NS',
    'ETERNAL.BO',
    'GOLDBEES.BO',
    'HDFCBANK.BO',
    'IDFCFIRSTB.BO',
    'INFY.BO',
    'IOC.BO',
    'IRCTC.BO',
    'IRFC.BO',
    'ITBEES.NS',
    'ITC.BO',
    'JSL.BO',
    'KTKBANK.NS',
    'NHPC.BO',
    'NTPC.BO',
    'ONGC.BO',
    'PNB.BO',
    'RVNL.BO',
    'SBIN.BO',
    'SUZLON.BO',
    'SWIGGY.BO',
    'TATACONSUM.BO',
    'TATAMOTORS.BO',
    'TATAPOWER.BO',
    'VEDL.BO',
    'YESBANK.BO',

    'ATHERENERG.BO',
    'LGEINDIA.BO',
    'RELIANCE.BO',
    'BIOCON.BO',
    'ATGL.BO',
    'INOXWIND.BO',
    'ICICIBANK.BO',
    'AXISBANK.BO',
    'JINDALSTEL.BO',
    'JKTYRE.BO',
    'TCS.BO'
]

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=SCRIPT_DIR / ".env")

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TELEGRAM_MESSAGE_MAX = 4000


# Set up logging
LOG_DIR = SCRIPT_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'stock_notifier.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(str(LOG_FILE), maxBytes=5*1024*1024, backupCount=2)
    ]
)
logger = logging.getLogger(__name__)
logger.info("Logging to %s", LOG_FILE)


def send_telegram_message(message):
    """Send a message to the configured Telegram chat, splitting into multiple messages if needed."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error(
            "Telegram credentials are not set in environment variables.")
        return

    def split_message_into_chunks(text, limit):
        lines = text.splitlines(keepends=True)
        chunks = []
        current = ""
        for line in lines:
            if len(current) + len(line) <= limit:
                current += line
            else:
                if current:
                    chunks.append(current)
                    current = ""
                if len(line) > limit:
                    start = 0
                    while start < len(line):
                        chunks.append(line[start:start+limit])
                        start += limit
                else:
                    current = line
        if current:
            chunks.append(current)
        return chunks

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = split_message_into_chunks(message, TELEGRAM_MESSAGE_MAX)
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': chunk + (f"\n\n(Part {idx}/{total})" if total > 1 else ""),
            'parse_mode': 'HTML'
        }
        try:
            response = requests.post(url, data=payload, timeout=10)
            response.raise_for_status()
            if total > 1:
                logger.info("Sent Telegram message (part %d/%d)", idx, total)
            else:
                logger.info("Sent Telegram message")
                logger.info("Telegram message content: %s", chunk)
        except Exception as e:
            logger.error(
                f"Failed to send Telegram message (part {idx}/{total}): {e}")
        if idx < total:
            time.sleep(0.5)


def check_stocks():
    """Check each tracked stock for 52-week and monthly lows, notify if condition is met."""
    any_alert = False
    analysis_summaries = []
    try:
        for symbol in TRACKED_STOCKS:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                current_price = info.get('regularMarketPrice')
                fifty_two_week_low = info.get('fiftyTwoWeekLow')
                name = info.get('shortName', symbol)
                if current_price is None or fifty_two_week_low is None:
                    logger.warning(f"Missing data for {symbol}, skipping.")
                    continue
                hist = ticker.history(period='1mo', interval='1d')
                if hist.empty or 'Low' not in hist:
                    logger.warning(
                        f"No historical data for {symbol}, skipping.")
                    continue
                monthly_low = hist['Low'].min()

                fifty_two_week_low_date_text = "N/A"
                try:
                    hist_1y = ticker.history(period='1y', interval='1d')
                    if (not hist_1y.empty) and ('Low' in hist_1y):
                        tol = 1e-6
                        mask = (hist_1y['Low'] -
                                fifty_two_week_low).abs() <= tol
                        if not mask.any():
                            mask = (hist_1y['Low'] <=
                                    fifty_two_week_low * (1 + 1e-6))
                        if mask.any():
                            matching_dates = hist_1y.index[mask]
                            if len(matching_dates) > 0:
                                date_obj = matching_dates[-1]
                                try:
                                    fifty_two_week_low_date_text = date_obj.date().isoformat()
                                except Exception:
                                    fifty_two_week_low_date_text = str(
                                        date_obj)
                except Exception:
                    fifty_two_week_low_date_text = "N/A"

                pct_from_52w = ((current_price - fifty_two_week_low) /
                                fifty_two_week_low) * 100 if fifty_two_week_low else None
                pct_from_month = ((current_price - monthly_low) /
                                  monthly_low) * 100 if monthly_low else None
                summary = (
                    f"\nSummary:\n"
                    f"- {pct_from_month:.2f}% from Monthly Low (₹{monthly_low:.2f})\n"
                    f"- {pct_from_52w:.2f}% from 52-Week Low (₹{fifty_two_week_low:.2f})\n"
                    f"- Reached 52-Week Low on: {fifty_two_week_low_date_text}"
                )
                analysis_summaries.append(
                    f"- {name} ({symbol}) has a current price of ₹{current_price:.2f}, its 52-week low price is ₹{fifty_two_week_low:.2f} (reached on {fifty_two_week_low_date_text}), and its monthly low price is ₹{monthly_low:.2f}"
                )

                # 52-week low notification
                if abs(current_price - fifty_two_week_low) < 1e-2:
                    message = (
                        f"\U0001F4C8 <b>{name} ({symbol})</b> has reached its <b>52-week low</b>!\n"
                        f"Current Price: ₹{current_price}\n"
                        f"52-Week Low: ₹{fifty_two_week_low}\n"
                        f"Reached 52-Week Low on: {fifty_two_week_low_date_text}"
                        f"{summary}"
                    )
                    send_telegram_message(message)
                    logger.info(f"{symbol} reached 52-week low.")
                    any_alert = True
                # Monthly low notification
                elif abs(current_price - monthly_low) < 1e-2:
                    message = (
                        f"\U0001F4C9 <b>{name} ({symbol})</b> has reached its <b>monthly low</b>!\n"
                        f"Current Price: ₹{current_price}\n"
                        f"Monthly Low: ₹{monthly_low}"
                        f"{summary}"
                    )
                    send_telegram_message(message)
                    logger.info(f"{symbol} reached monthly low.")
                    any_alert = True
            except Exception as stock_error:
                error_msg = f"Error fetching data for {symbol}: {stock_error}"
                logger.error(error_msg)
                send_telegram_message(f"\u26A0\ufe0f {error_msg}")
    except Exception as e:
        error_msg = f"\u26A0\ufe0f Error in stock check: {e}"
        logger.error(error_msg)
        send_telegram_message(error_msg)
    if not any_alert:
        logger.info(
            "No stocks have reached their 52-week or monthly lows today.")
        if analysis_summaries:
            message = (
                "No stocks have reached their 52-week or monthly lows today.\n\n"
                "Summary:\n" + "\n".join(analysis_summaries)
            )
        else:
            message = (
                "No stocks have reached their 52-week or monthly lows today. "
                "(No symbols had sufficient data to analyze.)"
            )
        send_telegram_message(message)


def main():
    send_telegram_message("Stock monitoring script has started running.")
    logger.info("Stock monitoring script has started running.")
    check_stocks()
    send_telegram_message("Stock monitoring script has finished running.")
    logger.info("Stock monitoring script has finished running.")


if __name__ == "__main__":
    main()
