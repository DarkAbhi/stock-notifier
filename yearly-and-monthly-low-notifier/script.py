import yfinance as yf
import requests
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import os

# List of BSE stock symbols to track (Yahoo Finance format, e.g., 'RELIANCE.BO')
TRACKED_STOCKS = [
    'RELIANCE.BO',
    'BIOCON.BO',
    'ATGL.BO',
    'INOXWIND.BO',
    'SWIGGY.BO',
    'ICICIBANK.BO',
    'AXISBANK.BO',
    'JINDALSTEL.BO',
    'JKTYRE.BO',
    'TCS.BO'
]

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


# Set up logging
LOG_FILE = 'stock_notifier.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=2)
    ]
)
logger = logging.getLogger(__name__)


def send_telegram_message(message):
    """Send a message to the configured Telegram chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error(
            "Telegram credentials are not set in environment variables.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        logger.info("Sent Telegram message: %s", message[:100])
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")


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
                pct_from_52w = ((current_price - fifty_two_week_low) /
                                fifty_two_week_low) * 100 if fifty_two_week_low else None
                pct_from_month = ((current_price - monthly_low) /
                                  monthly_low) * 100 if monthly_low else None
                summary = (
                    f"\nSummary:\n"
                    f"- {pct_from_month:.2f}% from Monthly Low (₹{monthly_low:.2f})\n"
                    f"- {pct_from_52w:.2f}% from 52-Week Low (₹{fifty_two_week_low:.2f})"
                )
                analysis_summaries.append(
                    f"- {name} ({symbol}) has a current price of ₹{current_price:.2f}, its 52-week low price is ₹{fifty_two_week_low:.2f}, and its monthly low price is ₹{monthly_low:.2f}"
                )
                # 52-week low notification
                if abs(current_price - fifty_two_week_low) < 1e-2:
                    message = (
                        f"\U0001F4C8 <b>{name} ({symbol})</b> has reached its <b>52-week low</b>!\n"
                        f"Current Price: ₹{current_price}\n"
                        f"52-Week Low: ₹{fifty_two_week_low}"
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
        logger.info("No stocks have reached their 52-week or monthly lows today.")
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
