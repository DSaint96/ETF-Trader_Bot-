# ETF Trading Bot — Schwab API

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Status](https://img.shields.io/badge/Status-Active%20%7C%20Dry%20Run-green?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)

An automated ETF price-monitoring and trading bot built in Python, integrated with the **Charles Schwab brokerage REST API**. The bot authenticates via OAuth 2.0, checks live prices on a configurable schedule, and fires buy orders when ETF prices drop below defined trigger thresholds — all with a safe **dry-run mode** for testing without real capital.

---

## Features

- **OAuth 2.0 authentication** — handles token refresh automatically and persists tokens to a local JSON file
- **Scheduled price monitoring** — checks prices every 30 minutes using APScheduler
- **Configurable trigger prices** — set custom buy-in targets per ETF (VOO, JEPQ, QQQ)
- **Dry-run mode** — simulates all actions with full logging and zero real trades
- **Structured logging** — every check, error, and trade is logged with timestamps to `trader.log`
- **Error handling** — graceful recovery from network failures and API timeouts

---

## Tech Stack

| Tool | Purpose |
|---|---|
| Python 3.10+ | Core language |
| `schwab-py` | Schwab API client library |
| `APScheduler` | Job scheduling |
| `requests` | HTTP client for API calls |
| `logging` | Structured event logging |
| `json` | Token persistence |

---

## How It Works

```
Startup
  └── Load OAuth token from schwab_token.json
  └── Authenticate with Schwab API

Every 30 minutes
  └── Refresh token if expired
  └── Fetch live quote for VOO, JEPQ, QQQ
  └── Compare current price vs. trigger price
      ├── Price ABOVE trigger → log "watching", do nothing
      └── Price AT or BELOW trigger → log "trigger fired"
          └── [Dry run] → log simulated buy
          └── [Live mode] → execute market buy order
```

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/DSaint96/etf-trading-bot.git
cd etf-trading-bot
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure your credentials
Create a `.env` file in the root directory:
```
SCHWAB_CLIENT_ID=your_client_id
SCHWAB_CLIENT_SECRET=your_client_secret
```

### 4. Set your trigger prices
Edit the `config` section in `schwab_trader.py`:
```python
TRIGGERS = {
    "VOO":  450.00,
    "JEPQ": 48.00,
    "QQQ":  430.00,
}
DRY_RUN = True  # Set to False for live trading
```

### 5. Run the bot
```bash
python schwab_trader.py
```

---

## Sample Log Output

```
2026-03-13 09:36:02 [INFO] Scheduler started. dry_run=ON
2026-03-13 09:36:04 [INFO] VOO: current=$615.49, trigger=$450.00
2026-03-13 09:36:04 [INFO] JEPQ: current=$57.05, trigger=$48.00
2026-03-13 09:36:05 [INFO] QQQ: current=$599.29, trigger=$430.00
```

---

## Project Status

| Phase | Status |
|---|---|
| OAuth 2.0 authentication | ✅ Complete |
| Scheduled price monitoring | ✅ Complete |
| Dry-run mode | ✅ Complete |
| Live trade execution | 🔄 In progress |
| Dashboard visualization | ✅ Complete (Chart.js) |
| Email/SMS alert on trigger | 🔜 Planned |

---

## Skills Demonstrated

`Python` `REST APIs` `OAuth 2.0` `API Authentication` `Task Scheduling` `Error Handling` `Logging` `Financial Automation` `JSON` `Environment Variables`

---

## Disclaimer

This project is for educational and portfolio purposes. This is not financial advice. Always use dry-run mode before committing real capital.

---

*Built by [Dennis Saint](https://github.com/DSaint96) — part of an IT/cybersecurity portfolio demonstrating real-world Python automation and API integration.*
