"""
Schwab ETF Automated Trader
Supports: DCA scheduling, portfolio rebalancing, and price-trigger alerts
Requires: schwab-py library (pip install schwab-py)
"""

import os
import json
import time
import logging
import schedule
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# --- pip install schwab-py python-dotenv schedule ---
import schwab

# ─────────────────────────────────────────────
#  LOGGING SETUP
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("trader.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  LOAD CREDENTIALS FROM .env  (never hardcode)
# ─────────────────────────────────────────────
load_dotenv()

APP_KEY      = os.getenv("SCHWAB_APP_KEY")
APP_SECRET   = os.getenv("SCHWAB_APP_SECRET")
ACCOUNT_HASH = os.getenv("SCHWAB_ACCOUNT_HASH")   # encrypted account ID from Schwab API
TOKEN_PATH   = os.getenv("SCHWAB_TOKEN_PATH", "schwab_token.json")

_MISSING = [name for name, val in [
    ("SCHWAB_APP_KEY", APP_KEY),
    ("SCHWAB_APP_SECRET", APP_SECRET),
    ("SCHWAB_ACCOUNT_HASH", ACCOUNT_HASH),
] if not val]
if _MISSING:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(_MISSING)}\n"
        "Check your .env file."
    )

# ─────────────────────────────────────────────
#  YOUR ETF UNIVERSE
# ─────────────────────────────────────────────
ETFS = ["DIV", "XLRE", "SCHH", "VNQ", "VOO", "SRET", "JEPQ", "QQQ", "SDIV", "SPHD"]

# ─────────────────────────────────────────────
#  STRATEGY CONFIGURATION
# ─────────────────────────────────────────────

# 1) DCA: Amount in USD to buy per ETF per scheduled run
DCA_AMOUNT_PER_ETF = 50.00   # e.g. $50 per ETF per week

# 2) Target allocations for rebalancing (must sum to 1.0)
TARGET_ALLOCATIONS = {
    "VOO":  0.25,
    "JEPQ": 0.15,
    "QQQ":  0.15,
    "VNQ":  0.10,
    "XLRE": 0.08,
    "SCHH": 0.08,
    "DIV":  0.07,
    "SPHD": 0.05,
    "SDIV": 0.04,
    "SRET": 0.03,
}

# 3) Price triggers — buy if price drops to or below trigger price
PRICE_TRIGGERS = {
    "VOO":  450.00,
    "JEPQ": 48.00,
    "QQQ":  430.00,
    # Add more as needed
}

# Rebalance drift threshold (rebalance if any ETF drifts > X% from target)
REBALANCE_THRESHOLD = 0.05   # 5%

_alloc_total = sum(TARGET_ALLOCATIONS.values())
if abs(_alloc_total - 1.0) > 0.001:
    raise ValueError(
        f"TARGET_ALLOCATIONS must sum to 1.0, but sums to {_alloc_total:.4f}. "
        "Fix the allocations before running."
    )

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def is_market_open() -> bool:
    """Returns True if US equity markets are currently open (Mon–Fri, 9:30–16:00 ET)."""
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return market_open <= now <= market_close


# ─────────────────────────────────────────────
#  CLIENT INITIALIZATION
# ─────────────────────────────────────────────
def get_client():
    """Initialize and return authenticated Schwab client."""
    try:
        client = schwab.auth.client_from_token_file(TOKEN_PATH, APP_KEY, APP_SECRET)
        log.info("Authenticated using saved token.")
        return client
    except FileNotFoundError:
        log.info("No token found — launching OAuth flow...")
        client = schwab.auth.client_from_login_flow(
            APP_KEY, APP_SECRET,
            callback_url="https://127.0.0.1:8182",
            callback_timeout=300,
            token_path=TOKEN_PATH
        )
        return client

def get_quote(client, symbol: str) -> float:
    """Fetch last price for a symbol."""
    resp = client.get_quote(symbol)
    resp.raise_for_status()
    data = resp.json()
    return float(data[symbol]["quote"]["lastPrice"])

def get_portfolio(client) -> dict:
    """Return {symbol: {'shares': x, 'value': y}} for all ETF positions."""
    resp = client.get_account(ACCOUNT_HASH, fields=[client.Account.Fields.POSITIONS])
    resp.raise_for_status()
    positions = resp.json().get("securitiesAccount", {}).get("positions", [])
    portfolio = {}
    for pos in positions:
        sym = pos["instrument"]["symbol"]
        if sym in ETFS:
            portfolio[sym] = {
                "shares": float(pos["longQuantity"]),
                "value":  float(pos["marketValue"])
            }
    return portfolio

def place_market_buy(client, symbol: str, shares: float, dry_run: bool = True):
    """Place a market buy order. Set dry_run=False to execute real trades."""
    shares = round(shares, 6)   # fractional shares supported by Schwab
    log.info(f"{'[DRY RUN] ' if dry_run else ''}BUY {shares} shares of {symbol}")
    if dry_run:
        return {"status": "dry_run", "symbol": symbol, "shares": shares}

    order = schwab.orders.equities.equity_buy_market(symbol, shares)
    resp = client.place_order(ACCOUNT_HASH, order)
    resp.raise_for_status()
    log.info(f"Order placed: {symbol} x {shares} — Status: {resp.status_code}")
    return resp.json()

# ─────────────────────────────────────────────
#  STRATEGY 1: Dollar-Cost Averaging (DCA)
# ─────────────────────────────────────────────
def run_dca(client, dry_run: bool = True):
    """Buy $DCA_AMOUNT_PER_ETF of each ETF in the universe."""
    log.info("=== Running DCA Strategy ===")
    for symbol in ETFS:
        try:
            price = get_quote(client, symbol)
            shares = DCA_AMOUNT_PER_ETF / price
            place_market_buy(client, symbol, shares, dry_run=dry_run)
            time.sleep(0.5)   # avoid rate limits
        except Exception as e:
            log.error(f"DCA failed for {symbol}: {e}")

# ─────────────────────────────────────────────
#  STRATEGY 2: Portfolio Rebalancing
# ─────────────────────────────────────────────
def run_rebalance(client, dry_run: bool = True):
    """Buy underweight ETFs to bring portfolio back to target allocations."""
    log.info("=== Running Rebalance Strategy ===")
    try:
        portfolio = get_portfolio(client)
    except Exception as e:
        log.error(f"Rebalance aborted — could not fetch portfolio: {e}")
        return

    total_value = sum(pos["value"] for pos in portfolio.values())

    if total_value == 0:
        log.warning("Portfolio is empty — skipping rebalance.")
        return

    for symbol, target_pct in TARGET_ALLOCATIONS.items():
        try:
            current_value = portfolio.get(symbol, {}).get("value", 0.0)
            current_pct   = current_value / total_value
            drift         = target_pct - current_pct

            log.info(f"{symbol}: target={target_pct:.1%}, current={current_pct:.1%}, drift={drift:+.1%}")

            if drift > REBALANCE_THRESHOLD:
                buy_value = drift * total_value
                price     = get_quote(client, symbol)
                shares    = buy_value / price
                place_market_buy(client, symbol, shares, dry_run=dry_run)
                time.sleep(0.5)
        except Exception as e:
            log.error(f"Rebalance failed for {symbol}: {e}")

# ─────────────────────────────────────────────
#  STRATEGY 3: Price-Trigger Buys
# ─────────────────────────────────────────────
def run_price_triggers(client, dry_run: bool = True):
    """Buy fixed $DCA_AMOUNT when price drops to or below trigger."""
    if not is_market_open():
        log.info("Price trigger check skipped — market is closed.")
        return
    log.info("=== Checking Price Triggers ===")
    for symbol, trigger_price in PRICE_TRIGGERS.items():
        try:
            current_price = get_quote(client, symbol)
            log.info(f"{symbol}: current=${current_price:.2f}, trigger=${trigger_price:.2f}")
            if current_price <= trigger_price:
                shares = DCA_AMOUNT_PER_ETF / current_price
                log.info(f"TRIGGER HIT: {symbol} at ${current_price:.2f}")
                place_market_buy(client, symbol, shares, dry_run=dry_run)
        except Exception as e:
            log.error(f"Price trigger check failed for {symbol}: {e}")

# ─────────────────────────────────────────────
#  SCHEDULER
# ─────────────────────────────────────────────
def start_scheduler(dry_run: bool = True):
    """
    Schedule all three strategies.
    Adjust times to match market hours (9:30 AM–4:00 PM ET).
    """
    client = get_client()

    # DCA: every Monday at 10:00 AM
    schedule.every().monday.at("10:00").do(run_dca, client=client, dry_run=dry_run)

    # Rebalance: first trading day of each month (approximated as every 4 weeks)
    schedule.every(2).weeks.do(run_rebalance, client=client, dry_run=dry_run)

    # Price triggers: every 30 minutes during market hours
    schedule.every(30).minutes.do(run_price_triggers, client=client, dry_run=dry_run)

    log.info(f"Scheduler started. dry_run={'ON' if dry_run else 'OFF — LIVE TRADING'}")
    while True:
        schedule.run_pending()
        time.sleep(60)

# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Change dry_run=False only when you are ready for live trading
    start_scheduler(dry_run=True)
