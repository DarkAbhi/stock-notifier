#!/usr/bin/env python3
import os
import json
import math
import time
import logging
from logging.handlers import RotatingFileHandler
import datetime as dt
from pathlib import Path

import requests
import yfinance as yf
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=SCRIPT_DIR / ".env")

TICKER = "^NSEI"
SYMBOL = "NIFTY 50"
STATE_FILE = SCRIPT_DIR / "nifty_yahoo_state.json"

POLL_SECS = int(os.getenv("POLL_SECS", "900"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = Path(os.getenv("LOG_DIR", SCRIPT_DIR / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "nifty.log"

logger = logging.getLogger("nifty_ath")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

fmt = logging.Formatter(
    fmt="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S%z",
)

ch = logging.StreamHandler()
ch.setFormatter(fmt)
logger.addHandler(ch)

fh = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=5)
fh.setFormatter(fmt)
logger.addHandler(fh)


def now_ist():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))


def load_state():
    """
    Loads state and migrates from old schema (with next_k) to new (with prev_k).
    - prev_k = last observed integer % drop bucket.
    """
    if STATE_FILE.exists():
        try:
            s = json.loads(STATE_FILE.read_text())
            if "prev_k" not in s:
                nk = s.get("next_k")
                s["prev_k"] = max(0, (nk - 1)) if isinstance(nk, int) else 0
                s.pop("next_k", None)
                logger.info(
                    "Migrated state: set prev_k=%s from next_k=%s", s["prev_k"], nk)
            s.setdefault("ath", None)
            s.setdefault("last_price", None)
            s.setdefault("last_ath_date", None)
            return s
        except Exception as e:
            logger.warning("Could not read state file, starting fresh: %s", e)
    return {"ath": None, "prev_k": 0, "last_price": None, "last_ath_date": None}


def save_state(state):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)


def tg_send(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("[TG] Not configured. Would send: %s", text)
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID,
                  "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if r.status_code != 200:
            logger.error("[TG] HTTP %s: %s", r.status_code, r.text[:200])
        else:
            logger.info("[TG] Sent alert successfully")
    except Exception as e:
        logger.error("[TG] send error: %s", e)


def format_drop_alert(current, ath, k):
    drop_pct = 100 * (1 - (current / ath))
    return (
        f"📉 <b>{SYMBOL}</b> crossed <b>-{k}%</b> from ATH\n"
        f"• Price: <b>{current:.2f}</b>\n"
        f"• ATH: <b>{ath:.2f}</b>\n"
        f"• Total drop: <b>{drop_pct:.2f}%</b>\n"
        f"• Time: {now_ist().strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        f"• Source: Yahoo Finance (delayed)"
    )


def format_new_ath(new_ath):
    return (
        f"🚀 <b>New ATH detected</b> for <b>{SYMBOL}</b>\n"
        f"• New ATH: <b>{new_ath:.2f}</b>\n"
        f"• Time: {now_ist().strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        f"• Source: Yahoo Finance (delayed)"
    )


def compute_ath_yahoo():
    logger.info("Fetching daily history to compute ATH …")
    t = yf.Ticker(TICKER)
    hist = t.history(period="max", interval="1d", auto_adjust=False)
    if hist.empty or "High" not in hist:
        raise RuntimeError("No daily history from Yahoo.")
    ath = float(hist["High"].max())
    logger.info("Computed ATH = %.2f", ath)
    return ath


def fetch_current_price():
    t = yf.Ticker(TICKER)
    try:
        lp = t.fast_info.get("last_price")
        if lp:
            return float(lp)
    except Exception as e:
        logger.debug("fast_info failed: %s", e)
    try:
        intr = t.history(period="1d", interval="1m")
        if not intr.empty:
            return float(intr["Close"].iloc[-1])
    except Exception as e:
        logger.debug("1m history failed: %s", e)
    return None


def ensure_ath(state):
    """
    Refresh ATH once a day (or on first run). Resets prev_k because buckets are relative to ATH.
    """
    needs = (state["ath"] is None) or (
        state["last_ath_date"] != dt.date.today().isoformat())
    if needs:
        ath = compute_ath_yahoo()
        state["ath"] = float(ath)
        state["prev_k"] = 0
        state["last_ath_date"] = dt.date.today().isoformat()
        save_state(state)
        logger.info("[INIT] ATH set to %.2f; prev_k reset to 0", ath)


def loop():
    state = load_state()
    ensure_ath(state)

    logger.info("[RUN] Monitoring %s every %ss", SYMBOL, POLL_SECS)
    cycle = 0

    while True:
        cycle += 1
        logger.info("POLL #%d — Checking current price...", cycle)

        try:
            price = fetch_current_price()
            if price is None:
                logger.warning("Could not fetch price this cycle.")
            else:
                if state["ath"] is not None and price > state["ath"]:
                    state["ath"] = price
                    state["prev_k"] = 0
                    state["last_ath_date"] = dt.date.today().isoformat()
                    save_state(state)
                    tg_send(format_new_ath(state["ath"]))
                    logger.info("[ATH] New ATH %.2f", price)
                elif state["ath"]:
                    k_current = math.floor(
                        (state["ath"] - price) / (0.01 * state["ath"]))
                    logger.debug(
                        "price=%.2f, ath=%.2f, k_current=%s, prev_k=%s",
                        price, state["ath"], k_current, state["prev_k"]
                    )

                    if k_current > state["prev_k"]:
                        for k in range(state["prev_k"] + 1, k_current + 1):
                            tg_send(format_drop_alert(price, state["ath"], k))
                            logger.info(
                                "[ALERT] downward cross -%d%% at %.2f", k, price)
                            time.sleep(0.2)
                        state["prev_k"] = k_current
                        save_state(state)
                    elif k_current < state["prev_k"]:
                        logger.info(
                            "RECOVERED — price %.2f moved up to -%d%% zone (from -%d%%)",
                            price, k_current, state["prev_k"]
                        )
                        state["prev_k"] = k_current
                        save_state(state)
                    else:
                        logger.info(
                            "No change — price %.2f, ATH %.2f, drop %.2f%% → no alert triggered.",
                            price, state["ath"], 100 *
                            (1 - price / state["ath"])
                        )

                state["last_price"] = price
        except Exception as e:
            logger.exception("Unhandled error in loop: %s", e)

        if state["last_ath_date"] != dt.date.today().isoformat():
            ensure_ath(state)

        logger.debug("Sleeping for %d seconds before next poll", POLL_SECS)
        time.sleep(POLL_SECS)


if __name__ == "__main__":
    loop()
