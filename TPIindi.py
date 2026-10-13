#!/usr/bin/env python3
"""
TPI Professional Dashboard — swing-trader regime + allocation + official paper book.

Upgrades (2026-09-05):
- Official Crypto Fear & Greed (alternative.me)
- VIX, 10Y yield, ETH/BTC
- Altseason Index: % of top-50 alts beating BTC over 30d (and 7d confirmation)
- 2x2 rotation box: BTC price vs BTC dominance
- Single English verdict: Accumulate / Lean buy / Hold / Lean sell / Raise cash
- Allocation 2.0: BTC + ETH sleeves; ALT basket only when altseason >= 50
- Official $10k paper book (server model account): weekly-or-regime rebalance,
  5% drift trigger, equity vs BTC HODL, CSV + JSON ledger
- Discord still ONE image; paper details persist to files for the webpage

FIX (2026-10-10):
- UnicodeEncodeError on Windows when reason contains → (regime flip).
  All file opens now use encoding="utf-8". Reason strings use ASCII "->" only.

UPGRADES (2026-10-12):
- Material-change Discord text alerts (regime flip, alt sleeve on/off, F&G extreme, weekly summary)
- Alert state tracking so alerts only fire on real changes
"""

import requests
import yfinance as yf
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge, Arrow, FancyBboxPatch
import numpy as np
from datetime import datetime, timedelta
import json
import os
import csv
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

# ================== DISCORD WEBHOOK ==================
import os
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/1485939608616435876/m_ZG1k68_v7HBjb-WxGMQtTWSc8QffmuXIFsGZvaf79wM4P0oFVqfUTeGx1JXFohG580")
STREAMLIT_URL = os.environ.get("STREAMLIT_URL", "https://tradersedge-tpi.streamlit.app/")
if not WEBHOOK_URL or "PASTE_YOUR" in WEBHOOK_URL:
    print("❌ Set DISCORD_WEBHOOK environment variable or paste the URL")
    exit()

CORE_TICKERS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SPY": "SPY",
    "NASDAQ": "QQQ",
    "GOLD": "GC=F",
    "DXY": "DX-Y.NYB",
    "COPPER": "HG=F",
    "VIX": "^VIX",
    "TNX": "^TNX",
}

HISTORY_FILE = "tpi_history.json"
BTC_DOM_HISTORY_FILE = "btc_dominance_history.json"
PAPER_BOOK_FILE = "tpi_paper_book.json"
PAPER_TRADES_CSV = "tpi_paper_trades.csv"
PAPER_EQUITY_CSV = "tpi_paper_equity.csv"
ALERT_STATE_FILE = "tpi_alert_state.json"
PAPER_START_USD = 10000.0
REBALANCE_DRIFT_PCT = 5.0
ALT_BASKET_N = 5

EXCLUDE_SYMBOLS = {
    "BTC", "ETH", "USDT", "USDC", "BUSD", "DAI", "USDE", "USDS", "FDUSD", "TUSD", "PAXG",
    "STETH", "WETH", "WBTC", "CETH", "XIDR", "USDD", "FRAX", "LUSD", "GUSD", "HUSD",
    "WBETH", "WEETH", "WSTETH", "CBETH", "RETH", "USD1", "PYUSD", "FIGR", "HELOC",
}


# =============================================================================
# HTTP HELPERS
# =============================================================================
def _get_json(url, params=None, timeout=15):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code != 200:
            print(f"⚠️ HTTP {r.status_code} {url}")
            return None
        return r.json()
    except Exception as e:
        print(f"⚠️ Request error {url}: {e}")
        return None


# =============================================================================
# MARKET DATA
# =============================================================================
def fetch_coingecko_markets():
    data = _get_json(
        "https://api.coingecko.com/api/v3/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 80,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "7d,30d,24h",
        },
    )
    return data or []


def fetch_global():
    js = _get_json("https://api.coingecko.com/api/v3/global")
    if not js:
        return {}
    d = js.get("data") or {}
    mcp = d.get("market_cap_percentage") or {}
    tmc = d.get("total_market_cap") or {}
    return {
        "btc_dom": float(mcp.get("btc") or 0),
        "eth_dom": float(mcp.get("eth") or 0),
        "total_usd": float(tmc.get("usd") or 0),
    }


def fetch_fear_greed():
    js = _get_json("https://api.alternative.me/fng/", params={"limit": 1})
    try:
        row = (js or {}).get("data", [{}])[0]
        val = float(row.get("value", 50))
        label = str(row.get("value_classification") or "Neutral")
        print(f"😱 Fear & Greed official: {val:.0f} ({label})")
        return val, label
    except Exception as e:
        print(f"⚠️ F&G fetch failed: {e}")
        return 50.0, "Neutral"


def fetch_asset_data(ticker, min_days=20):
    try:
        df = yf.download(ticker, period="600d", interval="1d", progress=False, auto_adjust=True)["Close"]
        if df.empty or len(df) < min_days:
            return None
        df = df.ffill().bfill().dropna()
        if len(df) < min_days:
            return None

        latest = df.iloc[-1].item()
        price_20 = df.iloc[-20].item() if len(df) >= 20 else latest
        price_252 = df.iloc[-252].item() if len(df) >= 252 else df.iloc[0].item()
        dma200 = df.rolling(200).mean().iloc[-1].item() if len(df) >= 200 else latest

        roc_20 = ((latest - price_20) / price_20 * 100) if price_20 != 0 else 0.0
        roc_252 = ((latest - price_252) / price_252 * 100) if price_252 != 0 else 0.0
        dma_pos = ((latest - dma200) / dma200 * 100) if dma200 != 0 else 0.0
        rolling_max = df.rolling(252).max().iloc[-1].item() if len(df) >= 252 else latest
        drawdown = ((latest - rolling_max) / rolling_max * 100) if rolling_max != 0 else 0.0
        vol = df.pct_change().rolling(20).std().iloc[-1].item() * np.sqrt(252) * 100

        if np.isnan(latest) or latest == 0:
            return None

        goldish = ticker in ("GC=F", "HG=F")
        return {
            "price": round(latest, 1 if goldish else 2),
            "roc_20": round(roc_20, 2),
            "roc_252": round(roc_252, 2),
            "dma200_pos": round(dma_pos, 2),
            "drawdown": round(drawdown, 2),
            "vol": round(vol, 1) if not np.isnan(vol) else 0.0,
            "above_200dma": bool(latest > dma200),
            "dma200": round(dma200, 1 if goldish else 2),
        }
    except Exception as e:
        print(f"⚠️ Error fetching {ticker}: {e}")
        return None


def safe_norm_roc(roc):
    if roc is None or np.isnan(roc) or np.isinf(roc):
        return 0.0
    return max(min(roc / 20.0, 1.0), -1.0)


# =============================================================================
# BTC DOMINANCE HISTORY
# =============================================================================
def load_dominance_history():
    if not os.path.exists(BTC_DOM_HISTORY_FILE):
        return []
    try:
        with open(BTC_DOM_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and all(isinstance(e, list) and len(e) == 2 for e in data):
            return data
        os.remove(BTC_DOM_HISTORY_FILE)
        return []
    except Exception:
        return []


def save_dominance_history(history):
    try:
        with open(BTC_DOM_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f)
    except Exception as e:
        print(f"⚠️ Could not save dominance history: {e}")


def update_btc_dominance(current_dom):
    history = load_dominance_history()
    today_str = datetime.now().strftime("%Y-%m-%d")
    if current_dom is not None:
        if not history or history[-1][0] != today_str:
            history.append([today_str, float(current_dom)])
            history = history[-90:]
            save_dominance_history(history)
    elif history:
        current_dom = history[-1][1]

    change_20 = 0.0
    if history and current_dom is not None:
        target = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
        old = history[0][1]
        for date_str, dom in history:
            if date_str <= target:
                old = dom
        change_20 = float(current_dom) - float(old)
    norm = max(min(change_20 / 0.5, 1.0), -1.0) if current_dom is not None else 0.0
    return float(current_dom or 0), change_20, norm


# =============================================================================
# ALTSEASON + BASKET
# =============================================================================
def compute_altseason(markets, btc_30d, btc_7d):
    alts = []
    for coin in markets:
        sym = str(coin.get("symbol") or "").upper()
        if sym in EXCLUDE_SYMBOLS:
            continue
        ch30 = coin.get("price_change_percentage_30d_in_currency")
        ch7 = coin.get("price_change_percentage_7d_in_currency")
        ch24 = coin.get("price_change_percentage_24h")
        px = coin.get("current_price")
        if px is None:
            continue
        alts.append({
            "symbol": sym,
            "id": coin.get("id"),
            "name": coin.get("name"),
            "price": float(px),
            "chg_24h": float(ch24 or 0),
            "chg_7d": float(ch7 or 0),
            "chg_30d": float(ch30 or 0),
        })
        if len(alts) >= 50:
            break

    def _idx(key, btc_ret):
        if not alts or btc_ret is None:
            return 0.0, 0, 0
        wins = sum(1 for a in alts if a[key] > btc_ret)
        return round(100.0 * wins / len(alts), 1), wins, len(alts)

    idx30, w30, n30 = _idx("chg_30d", btc_30d)
    idx7, w7, n7 = _idx("chg_7d", btc_7d)
    print(f"🟣 Altseason 30d: {idx30:.0f} ({w30}/{n30} beat BTC {btc_30d:+.1f}%)")
    print(f"🟣 Altseason 7d:  {idx7:.0f} ({w7}/{n7} beat BTC {btc_7d:+.1f}%)")
    return {
        "altseason_30": idx30,
        "altseason_7": idx7,
        "alts_n": n30,
        "beats_30": w30,
        "btc_30d": btc_30d,
        "btc_7d": btc_7d,
        "alts": alts,
    }


def pick_alt_basket(alts, btc_30d, n=ALT_BASKET_N):
    clean = [a for a in alts if a["symbol"] not in EXCLUDE_SYMBOLS and "HELOC" not in a["symbol"]]
    beat = [a for a in clean if a["chg_30d"] > (btc_30d or -999)]
    mcap_rank = {a["symbol"]: i for i, a in enumerate(clean)}
    beat.sort(key=lambda a: (mcap_rank.get(a["symbol"], 99), -a["chg_30d"]))
    chosen = beat[:n]
    if len(chosen) < n:
        rest = [a for a in clean if a not in chosen]
        chosen += rest[: n - len(chosen)]
    return chosen[:n]


# =============================================================================
# TPI CORE
# =============================================================================
def compute_tpi():
    data = {
        name: {
            "price": 0, "roc_20": 0, "roc_252": 0, "dma200_pos": 0,
            "drawdown": 0, "vol": 0, "above_200dma": False, "dma200": 0,
        }
        for name in CORE_TICKERS
    }
    for name, ticker in CORE_TICKERS.items():
        d = fetch_asset_data(ticker)
        if d:
            data[name] = d

    markets = fetch_coingecko_markets()
    glob = fetch_global()
    fng_val, fng_label = fetch_fear_greed()

    btc_row = next((c for c in markets if str(c.get("symbol", "")).upper() == "BTC"), None)
    btc_30d = float((btc_row or {}).get("price_change_percentage_30d_in_currency") or data["BTC"]["roc_20"])
    btc_7d = float((btc_row or {}).get("price_change_percentage_7d_in_currency") or 0)

    season = compute_altseason(markets, btc_30d, btc_7d)
    basket = pick_alt_basket(season["alts"], btc_30d)

    alt_raw = {}
    for a in season["alts"][:10]:
        alt_raw[a["symbol"]] = {
            "price": a["price"],
            "roc_20": a["chg_24h"],
            "chg_7d": a["chg_7d"],
            "chg_30d": a["chg_30d"],
            "roc_252": 0.0,
            "dma200_pos": 0.0,
            "drawdown": 0.0,
            "vol": 0.0,
            "above_200dma": False,
            "dma200": a["price"],
        }

    btc = data["BTC"]
    nasdaq = data["NASDAQ"]
    gold = data["GOLD"]
    dxy = data["DXY"]
    copper = data["COPPER"]

    mtpi_btc = safe_norm_roc(btc["roc_20"])
    ltpi_btc = (
        0.35 * (btc["roc_252"] / 50)
        + 0.35 * (btc["dma200_pos"] / 30)
        + 0.20 * (1 if btc["roc_252"] > 0 else -1)
        + 0.10 * (btc["drawdown"] / -20)
    )
    ltpi_btc = max(min(ltpi_btc, 1.0), -1.0)

    votes = 0
    votes += 1 if btc["roc_20"] > 1 else -1
    votes += 1 if btc["above_200dma"] else -1
    votes += 1 if btc["dma200_pos"] > 0 else -1
    votes += 1 if btc["roc_252"] > 0 else -1
    vote_score = votes / 4.0

    macro = (
        ltpi_btc * 0.30
        + safe_norm_roc(nasdaq["roc_20"]) * 0.20
        + safe_norm_roc(gold["roc_20"]) * 0.15
        + safe_norm_roc(copper["roc_20"]) * 0.15
        - safe_norm_roc(dxy["roc_20"]) * 0.20
    )
    macro = max(min(macro, 1.0), -1.0)

    regime = "Bullish" if ltpi_btc > 0.3 else "Bearish" if ltpi_btc < -0.3 else "Neutral"

    def get_confidence(score):
        return int(min(95, max(50, abs(score) * 45 + 50)))

    copper_gold_ratio = (copper["price"] / gold["price"]) if gold["price"] > 0 else 0.0
    eth_px = data["ETH"]["price"]
    btc_px = data["BTC"]["price"]
    eth_btc = (eth_px / btc_px) if btc_px > 0 else 0.0

    current_dom = glob.get("btc_dom") or None
    dom_now, dom_chg_20, dom_norm = update_btc_dominance(current_dom)

    fng_norm = max(min((fng_val - 50.0) / 50.0, 1.0), -1.0)

    btc_up = btc["roc_20"] >= 0
    dom_up = dom_chg_20 >= 0
    if btc_up and dom_up:
        rotation = "BTC SEASON"
        rotation_note = "BTC leading — hold BTC, starve alts"
    elif btc_up and not dom_up:
        rotation = "ALT ROTATION"
        rotation_note = "BTC up + dominance down — selective alts OK"
    elif (not btc_up) and dom_up:
        rotation = "RISK-OFF"
        rotation_note = "Everything falling, alts worse — raise cash/gold"
    else:
        rotation = "FLIGHT TO CASH"
        rotation_note = "BTC down + dominance down — stables/cash, not alts"

    verdict_score = 0.45 * ltpi_btc + 0.30 * macro + 0.15 * mtpi_btc + 0.10 * fng_norm
    if verdict_score > 0.35:
        verdict = "ACCUMULATE"
    elif verdict_score > 0.12:
        verdict = "LEAN BUY"
    elif verdict_score > -0.12:
        verdict = "HOLD"
    elif verdict_score > -0.35:
        verdict = "LEAN SELL"
    else:
        verdict = "RAISE CASH"

    return {
        "LTPI_BTC": round(ltpi_btc, 2),
        "MTPI_BTC": round(mtpi_btc, 2),
        "MACRO": round(macro, 2),
        "VOTE_TPI": round(vote_score, 2),
        "REGIME": regime,
        "VERDICT": verdict,
        "VERDICT_SCORE": round(verdict_score, 2),
        "CONFIDENCE": {
            "LTPI": get_confidence(ltpi_btc),
            "MTPI": get_confidence(mtpi_btc),
            "MACRO": get_confidence(macro),
        },
        "FNG": round(fng_val, 0),
        "FNG_LABEL": fng_label,
        "FNG_NORM": round(fng_norm, 2),
        "SENTIMENT": round(fng_norm, 2),
        "BTC_DOMINANCE": round(dom_norm, 2),
        "BTC_DOM_PCT": round(dom_now, 2),
        "BTC_DOM_CHG_20": round(dom_chg_20, 3),
        "ETH_DOM_PCT": round(float(glob.get("eth_dom") or 0), 2),
        "ALTSEASON_30": season["altseason_30"],
        "ALTSEASON_7": season["altseason_7"],
        "ALTSEASON_BEATS": season["beats_30"],
        "ALTSEASON_N": season["alts_n"],
        "ROTATION": rotation,
        "ROTATION_NOTE": rotation_note,
        "ETH_BTC": round(eth_btc, 6),
        "raw": data,
        "alt_raw": alt_raw,
        "alt_basket": basket,
        "copper_gold_ratio": round(copper_gold_ratio, 4),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# =============================================================================
# ALLOCATION 2.0
# =============================================================================
def get_allocation(tpi):
    ltpi = tpi["LTPI_BTC"]
    macro = tpi["MACRO"]
    altseason = tpi.get("ALTSEASON_30", 0)

    if ltpi > 0.2:
        btc, eth, gold, cash = 50, 15, 15, 20
    elif ltpi < -0.2:
        btc, eth, gold, cash = 15, 5, 40, 40
    else:
        btc, eth, gold, cash = 35, 10, 25, 30

    if macro > 0.2:
        btc += 5
        cash -= 5
    elif macro < -0.2:
        btc -= 5
        gold += 3
        cash += 2

    if ltpi < -0.3:
        eth = min(eth, 5)

    alt = 0
    if altseason >= 75 and ltpi > -0.2 and macro >= 0:
        alt = 10
    elif altseason >= 50 and ltpi > -0.2 and macro > -0.1:
        alt = 6

    if alt > 0:
        take_cash = min(alt * 0.6, max(cash - 5, 0))
        take_gold = alt - take_cash
        take_gold = min(take_gold, max(gold - 5, 0))
        cash -= take_cash
        gold -= take_gold
        alt = take_cash + take_gold

    gold = max(gold, 5)
    cash = max(cash, 5)
    btc = max(btc, 0)
    eth = max(eth, 0)
    alt = max(alt, 0)

    total = btc + eth + gold + cash + alt
    if total <= 0:
        return {"BTC": 40, "ETH": 10, "GOLD": 25, "ALT": 0, "CASH": 25, "alt_breakdown": {}}
    btc = int(round(btc * 100 / total))
    eth = int(round(eth * 100 / total))
    gold = int(round(gold * 100 / total))
    alt = int(round(alt * 100 / total))
    cash = 100 - btc - eth - gold - alt
    if cash < 0:
        btc += cash
        cash = 0

    breakdown = {}
    basket = tpi.get("alt_basket") or []
    if alt > 0 and basket:
        n = len(basket)
        base = round(alt / n, 1)
        parts = [base] * n
        parts[-1] = round(alt - sum(parts[:-1]), 1)
        breakdown = {a["symbol"]: parts[i] for i, a in enumerate(basket)}

    return {
        "BTC": btc, "ETH": eth, "GOLD": gold, "ALT": alt, "CASH": cash,
        "alt_breakdown": breakdown,
    }


def compute_risk_level(vol, dd):
    if vol > 40 or dd < -20:
        return "High", "#ef4444"
    if vol > 25 or dd < -10:
        return "Medium", "#eab308"
    return "Low", "#22c55e"


# =============================================================================
# PAPER BOOK
# =============================================================================
def _empty_book():
    return {
        "started": datetime.now().strftime("%Y-%m-%d"),
        "start_equity": PAPER_START_USD,
        "cash": PAPER_START_USD,
        "positions": {"BTC": {"qty": 0.0}, "ETH": {"qty": 0.0}, "GOLD": {"qty": 0.0}, "ALTS": {}},
        "last_regime": None,
        "last_rebalance": None,
        "start_btc_px": None,
        "btc_hodl_qty": 0.0,
        "peak_equity": PAPER_START_USD,
        "trades": [],
        "equity_curve": [],
    }


def load_paper_book():
    if not os.path.exists(PAPER_BOOK_FILE):
        return _empty_book()
    try:
        with open(PAPER_BOOK_FILE, "r", encoding="utf-8") as f:
            book = json.load(f)
        book.setdefault("positions", _empty_book()["positions"])
        book.setdefault("trades", [])
        book.setdefault("equity_curve", [])
        return book
    except Exception:
        return _empty_book()


def save_paper_book(book):
    try:
        with open(PAPER_BOOK_FILE, "w", encoding="utf-8") as f:
            json.dump(book, f, indent=2)
    except Exception as e:
        print(f"⚠️ Could not save paper book: {e}")


def _ensure_trade_csv():
    if not os.path.exists(PAPER_TRADES_CSV):
        with open(PAPER_TRADES_CSV, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["timestamp", "side", "symbol", "qty", "price", "usd", "reason"])
    if not os.path.exists(PAPER_EQUITY_CSV):
        with open(PAPER_EQUITY_CSV, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["timestamp", "equity", "cash", "btc_hodl", "dd_pct", "regime", "verdict"])


def _log_trade(ts, side, symbol, qty, price, usd, reason):
    safe_reason = str(reason or "").replace("→", "->").replace("—", "-").encode("ascii", "ignore").decode("ascii")
    _ensure_trade_csv()
    with open(PAPER_TRADES_CSV, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([ts, side, symbol, f"{qty:.8f}", f"{price:.4f}", f"{usd:.2f}", safe_reason])


def _prices_from_tpi(tpi):
    raw = tpi["raw"]
    px = {
        "BTC": float(raw.get("BTC", {}).get("price") or 0),
        "ETH": float(raw.get("ETH", {}).get("price") or 0),
        "GOLD": float(raw.get("GOLD", {}).get("price") or 0),
    }
    for a in tpi.get("alt_basket") or []:
        px[a["symbol"]] = float(a["price"])
    for a in tpi.get("alt_raw") or {}:
        rec = (tpi.get("alt_raw") or {}).get(a) or {}
        if rec.get("price"):
            px[a] = float(rec["price"])
    return px


def mark_paper_equity(book, px):
    eq = float(book.get("cash") or 0)
    pos = book.get("positions") or {}
    for sym in ("BTC", "ETH", "GOLD"):
        qty = float((pos.get(sym) or {}).get("qty") or 0)
        eq += qty * float(px.get(sym) or 0)
    for sym, rec in (pos.get("ALTS") or {}).items():
        qty = float((rec or {}).get("qty") or 0)
        eq += qty * float(px.get(sym) or 0)
    return eq


def current_weights(book, px, equity):
    if equity <= 0:
        return {"BTC": 0, "ETH": 0, "GOLD": 0, "ALT": 0, "CASH": 100}
    pos = book.get("positions") or {}
    btc = float((pos.get("BTC") or {}).get("qty") or 0) * float(px.get("BTC") or 0)
    eth = float((pos.get("ETH") or {}).get("qty") or 0) * float(px.get("ETH") or 0)
    gold = float((pos.get("GOLD") or {}).get("qty") or 0) * float(px.get("GOLD") or 0)
    alt = 0.0
    for sym, rec in (pos.get("ALTS") or {}).items():
        alt += float((rec or {}).get("qty") or 0) * float(px.get(sym) or 0)
    cash = float(book.get("cash") or 0)
    return {
        "BTC": 100 * btc / equity,
        "ETH": 100 * eth / equity,
        "GOLD": 100 * gold / equity,
        "ALT": 100 * alt / equity,
        "CASH": 100 * cash / equity,
    }


def _set_sleeve_usd(book, px, sleeve, target_usd, ts, reason):
    pos = book["positions"]
    price = float(px.get(sleeve) or 0)
    if price <= 0:
        return
    cur_qty = float((pos.get(sleeve) or {}).get("qty") or 0)
    cur_usd = cur_qty * price
    delta = target_usd - cur_usd
    if abs(delta) < 1:
        pos[sleeve] = {"qty": cur_qty}
        return
    dqty = delta / price
    if delta > 0:
        spend = min(delta, book["cash"])
        if spend < 1:
            pos[sleeve] = {"qty": cur_qty}
            return
        dqty = spend / price
        book["cash"] -= spend
        pos[sleeve] = {"qty": cur_qty + dqty}
        _log_trade(ts, "BUY", sleeve, dqty, price, spend, reason)
        book["trades"].append({"ts": ts, "side": "BUY", "sym": sleeve, "qty": dqty, "px": price, "usd": spend, "reason": reason})
    else:
        sell_qty = min(cur_qty, abs(dqty))
        proceeds = sell_qty * price
        book["cash"] += proceeds
        pos[sleeve] = {"qty": cur_qty - sell_qty}
        _log_trade(ts, "SELL", sleeve, sell_qty, price, proceeds, reason)
        book["trades"].append({"ts": ts, "side": "SELL", "sym": sleeve, "qty": sell_qty, "px": price, "usd": proceeds, "reason": reason})


def _flatten_alts(book, px, ts, reason):
    alts = book["positions"].get("ALTS") or {}
    for sym, rec in list(alts.items()):
        qty = float((rec or {}).get("qty") or 0)
        price = float(px.get(sym) or 0)
        if qty > 0 and price > 0:
            proceeds = qty * price
            book["cash"] += proceeds
            _log_trade(ts, "SELL", sym, qty, price, proceeds, reason)
            book["trades"].append({"ts": ts, "side": "SELL", "sym": sym, "qty": qty, "px": price, "usd": proceeds, "reason": reason})
    book["positions"]["ALTS"] = {}


def _set_alt_basket(book, px, basket, target_usd, ts, reason):
    _flatten_alts(book, px, ts, reason + " flatten")
    if target_usd < 10 or not basket:
        return
    each = target_usd / len(basket)
    alts = {}
    for a in basket:
        sym = a["symbol"]
        price = float(px.get(sym) or a.get("price") or 0)
        if price <= 0 or book["cash"] < 1:
            continue
        spend = min(each, book["cash"])
        qty = spend / price
        book["cash"] -= spend
        alts[sym] = {"qty": qty}
        _log_trade(ts, "BUY", sym, qty, price, spend, reason)
        book["trades"].append({"ts": ts, "side": "BUY", "sym": sym, "qty": qty, "px": price, "usd": spend, "reason": reason})
    book["positions"]["ALTS"] = alts


def update_paper_book(tpi, alloc):
    book = load_paper_book()
    px = _prices_from_tpi(tpi)
    ts = tpi["timestamp"]
    btc_px = px.get("BTC") or 0

    if not book.get("start_btc_px") and btc_px > 0:
        book["start_btc_px"] = btc_px
        book["btc_hodl_qty"] = PAPER_START_USD / btc_px

    equity = mark_paper_equity(book, px)
    w = current_weights(book, px, equity)

    regime_flip = book.get("last_regime") not in (None, tpi["REGIME"])
    last_rb = book.get("last_rebalance")
    days_since = 999
    if last_rb:
        try:
            days_since = (datetime.now() - datetime.strptime(last_rb[:10], "%Y-%m-%d")).days
        except Exception:
            days_since = 999
    weekly = days_since >= 7
    empty = equity > 0 and (book.get("last_rebalance") is None)

    drift = 0.0
    for k in ("BTC", "ETH", "GOLD", "ALT", "CASH"):
        drift = max(drift, abs(w.get(k, 0) - alloc.get(k, 0)))

    should = empty or regime_flip or weekly or drift >= REBALANCE_DRIFT_PCT
    reason = "init" if empty else (
        f"regime {book.get('last_regime')}->{tpi['REGIME']}" if regime_flip
        else f"weekly {days_since}d" if weekly
        else f"drift {drift:.1f}%"
    )

    if should and equity > 0:
        print(f"📒 Paper rebalance ({reason}) equity=${equity:.2f} drift={drift:.1f}%")
        targets = {
            "BTC": equity * alloc["BTC"] / 100.0,
            "ETH": equity * alloc["ETH"] / 100.0,
            "GOLD": equity * alloc["GOLD"] / 100.0,
            "ALT": equity * alloc["ALT"] / 100.0,
        }
        _flatten_alts(book, px, ts, reason + " flatten")
        for sleeve in ("GOLD", "ETH", "BTC"):
            _set_sleeve_usd(book, px, sleeve, targets[sleeve], ts, reason)
        _set_alt_basket(book, px, tpi.get("alt_basket") or [], targets["ALT"], ts, reason)
        book["last_rebalance"] = ts
        book["last_regime"] = tpi["REGIME"]
        book["trades"] = book["trades"][-200:]
        equity = mark_paper_equity(book, px)
    elif book.get("last_regime") is None:
        book["last_regime"] = tpi["REGIME"]

    btc_hodl = float(book.get("btc_hodl_qty") or 0) * btc_px
    peak = max(float(book.get("peak_equity") or PAPER_START_USD), equity)
    book["peak_equity"] = peak
    dd = (equity - peak) / peak * 100 if peak else 0
    ret = (equity / PAPER_START_USD - 1) * 100
    hodl_ret = (btc_hodl / PAPER_START_USD - 1) * 100 if book.get("start_btc_px") else 0

    book["equity_curve"].append({
        "timestamp": ts, "equity": round(equity, 2), "btc_hodl": round(btc_hodl, 2),
        "dd_pct": round(dd, 2), "regime": tpi["REGIME"],
    })
    book["equity_curve"] = book["equity_curve"][-400:]

    _ensure_trade_csv()
    with open(PAPER_EQUITY_CSV, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            ts, f"{equity:.2f}", f"{book['cash']:.2f}", f"{btc_hodl:.2f}",
            f"{dd:.2f}", tpi["REGIME"], tpi["VERDICT"],
        ])

    save_paper_book(book)
    w = current_weights(book, px, equity)
    alt_holdings = []
    for sym, rec in (book.get("positions", {}).get("ALTS") or {}).items():
        qty = float((rec or {}).get("qty") or 0)
        price = float(px.get(sym) or 0)
        usd = qty * price
        if qty <= 0:
            continue
        alt_holdings.append({
            "symbol": sym,
            "qty": round(qty, 6),
            "price": price,
            "usd": round(usd, 2),
            "pct": round(100.0 * usd / equity, 2) if equity else 0.0,
            "target_pct": float((alloc.get("alt_breakdown") or {}).get(sym) or 0),
        })
    alt_holdings.sort(key=lambda r: r["usd"], reverse=True)
    return {
        "equity": round(equity, 2),
        "cash": round(float(book["cash"]), 2),
        "ret_pct": round(ret, 2),
        "hodl_ret_pct": round(hodl_ret, 2),
        "dd_pct": round(dd, 2),
        "drift": round(drift, 1),
        "rebalanced": should,
        "reason": reason if should else "no trade",
        "weights": {k: round(v, 1) for k, v in w.items()},
        "started": book.get("started"),
        "last_rebalance": book.get("last_rebalance"),
        "n_trades": len(book.get("trades") or []),
        "alt_holdings": alt_holdings,
        "alt_breakdown": alloc.get("alt_breakdown") or {},
    }


# =============================================================================
# HISTORY
# =============================================================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data[-150:]
        except Exception:
            print("⚠️ History file corrupted, starting fresh.")
    return []


def save_history(current):
    def convert(obj):
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert(i) for i in obj]
        if isinstance(obj, (np.floating, np.integer)):
            return float(obj) if isinstance(obj, np.floating) else int(obj)
        return obj

    slim = convert({
        "timestamp": current["timestamp"],
        "LTPI_BTC": current["LTPI_BTC"],
        "MTPI_BTC": current["MTPI_BTC"],
        "MACRO": current["MACRO"],
        "FNG": current["FNG"],
        "ALTSEASON_30": current["ALTSEASON_30"],
        "VERDICT": current["VERDICT"],
        "REGIME": current["REGIME"],
        "BTC_DOM_PCT": current["BTC_DOM_PCT"],
    })
    history = load_history()
    history.append(slim)
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f)
    except Exception as e:
        print(f"⚠️ Could not save history: {e}")


# =============================================================================
# ALERTS (material changes only)
# =============================================================================
def load_alert_state():
    if os.path.exists(ALERT_STATE_FILE):
        try:
            with open(ALERT_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_regime": None, "last_alt": None, "last_fng": None, "last_weekly": None}


def save_alert_state(state):
    try:
        with open(ALERT_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def send_text_alert(title, message, color=0x22c55e):
    payload = {
        "username": "TPI Alerts",
        "embeds": [{"title": title, "description": message, "color": color}]
    }
    try:
        r = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code in (200, 204):
            print(f"✅ Alert sent: {title}")
        else:
            print(f"⚠️ Alert failed: {r.status_code}")
    except Exception as e:
        print(f"⚠️ Alert error: {e}")


def check_and_send_alerts(tpi, alloc, paper):
    state = load_alert_state()
    now = datetime.now()

    regime = tpi.get("REGIME")
    if state.get("last_regime") and state["last_regime"] != regime:
        send_text_alert("Regime Flip", f"{state['last_regime']} → {regime}", 0xfbbf24)

    alt_on = alloc.get("ALT", 0) > 0
    if state.get("last_alt") is not None and state["last_alt"] != alt_on:
        status = "ON" if alt_on else "OFF"
        send_text_alert("Alt Sleeve", f"Alt sleeve turned {status} ({alloc.get('ALT', 0)}%)", 0x8b5cf6)

    fng = tpi.get("FNG", 50)
    if (fng >= 75 or fng <= 25) and state.get("last_fng") not in (None, fng):
        label = "Extreme Greed" if fng >= 75 else "Extreme Fear"
        color = 0xef4444 if fng <= 25 else 0x22c55e
        send_text_alert("Fear & Greed", f"{label}: {fng:.0f}", color)

    last_weekly = state.get("last_weekly")
    if not last_weekly or (now - datetime.fromisoformat(last_weekly)).days >= 7:
        ret = paper.get("ret_pct", 0)
        dd = paper.get("dd_pct", 0)
        beat = "beat" if ret > paper.get("hodl_ret_pct", 0) else "lagged"
        send_text_alert("Weekly Summary", f"Model {ret:+.1f}% · Max DD {dd:.1f}% · {beat} BTC", 0x60a5fa)
        state["last_weekly"] = now.isoformat()

    state["last_regime"] = regime
    state["last_alt"] = alt_on
    state["last_fng"] = fng
    save_alert_state(state)


# =============================================================================
# GAUGES / DASHBOARD (unchanged core drawing)
# =============================================================================
def draw_classic_gauge(ax, value, title, left_label, right_label, conf_pct=50):
    ax.set_title(title, fontsize=15, fontweight="bold", color="white", pad=26)
    ax.add_patch(Wedge((0, 0), 1, 180, 270, width=0.33, color="#ef4444", alpha=0.95))
    ax.add_patch(Wedge((0, 0), 1, 270, 360, width=0.33, color="#9ca3af", alpha=0.9))
    ax.add_patch(Wedge((0, 0), 1, 0, 90, width=0.33, color="#22c55e", alpha=0.95))
    angle = 180 + (value + 1) * 90
    ax.add_patch(Arrow(0, 0, np.cos(np.deg2rad(angle)) * 0.90, np.sin(np.deg2rad(angle)) * 0.90, width=0.28, color="#FFD700"))
    ax.scatter(0, 0, s=1850, color="#0f766e")
    val_color = "#22c55e" if value > 0.1 else "#ef4444" if value < -0.1 else "white"
    ax.text(0, -0.42, f"{value:.2f}", ha="center", fontsize=30, fontweight="bold", color=val_color)
    ax.text(-1.68, -0.55, left_label, fontsize=13, color="#ef4444", ha="center", fontweight="bold")
    ax.text(1.68, -0.55, right_label, fontsize=13, color="#22c55e", ha="center", fontweight="bold")
    for tick in np.linspace(-1, 1, 9):
        tick_angle = 180 + (tick + 1) * 90
        ax.plot(
            [0.87 * np.cos(np.deg2rad(tick_angle)), 1.04 * np.cos(np.deg2rad(tick_angle))],
            [0.87 * np.sin(np.deg2rad(tick_angle)), 1.04 * np.sin(np.deg2rad(tick_angle))],
            color="white", linewidth=2.2,
        )
    ax.text(-1.12, -1.02, "-1.00", ha="center", fontsize=10, color="#cbd5e1")
    ax.text(0, -1.08, "0.00", ha="center", fontsize=10, color="#cbd5e1")
    ax.text(1.12, -1.02, "1.00", ha="center", fontsize=10, color="#cbd5e1")
    ax.set_xlim(-1.95, 1.95)
    ax.set_ylim(-1.45, 1.65)
    ax.axis("off")
    badge_color = "#22c55e" if conf_pct >= 70 else "#eab308" if conf_pct >= 55 else "#ef4444"
    ax.text(-1.65, -1.18, f"Confidence: {conf_pct}%", ha="left", fontsize=10, color="white",
            fontweight="bold", bbox=dict(facecolor=badge_color, edgecolor="none", pad=3, alpha=0.85))


def _panel(ax, title=None):
    ax.set_facecolor("#1e2937")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    if title:
        ax.set_title(title, color="white", fontsize=14, fontweight="bold", pad=10)


def create_pro_dashboard(tpi, paper):
    plt.rcParams["font.family"] = "sans-serif"
    fig = plt.figure(figsize=(30, 34), facecolor="#0f172a")
    gs = fig.add_gridspec(9, 5, hspace=0.48, wspace=0.32,
                          height_ratios=[0.72, 1.12, 0.95, 0.62, 0.92, 1.05, 0.92, 1.12, 0.22])

    history = load_history()
    alloc = get_allocation(tpi)
    raw = tpi["raw"]
    pw = paper.get("weights") or {}
    vix = raw.get("VIX", {}).get("price", 0)
    tnx = raw.get("TNX", {}).get("price", 0)
    risk_text, _ = compute_risk_level(raw.get("BTC", {}).get("vol", 0), raw.get("BTC", {}).get("drawdown", 0))
    vcol = {"ACCUMULATE": "#22c55e", "LEAN BUY": "#86efac", "HOLD": "#fde047",
            "LEAN SELL": "#fb923c", "RAISE CASH": "#ef4444"}.get(tpi["VERDICT"], "#fde047")
    alt_bits = alloc.get("alt_breakdown") or {}
    if alloc["ALT"] > 0 and alt_bits:
        alt_line = "  ·  ".join(f"{k} {v:g}%" for k, v in alt_bits.items())
        action = (f"Hold {alloc['BTC']}% BTC  ·  {alloc['ETH']}% ETH  ·  "
                  f"{alloc['GOLD']}% Gold  ·  {alloc['CASH']}% Cash  ·  "
                  f"{alloc['ALT']}% Alts ({alt_line})")
    else:
        action = (f"Hold {alloc['BTC']}% BTC  ·  {alloc['ETH']}% ETH  ·  "
                  f"{alloc['GOLD']}% Gold  ·  {alloc['CASH']}% Cash  ·  no alts")

    assets = ["BTC", "ETH", "SPY", "NASDAQ", "GOLD"]
    colors = ["#f7931a", "#627eea", "#3b82f6", "#34a853", "#eab308"]
    for i, asset in enumerate(assets):
        ax = fig.add_subplot(gs[0, i])
        card = tpi["raw"].get(asset, {})
        roc = card.get("roc_20", 0)
        roc_color = "#22c55e" if roc >= 0 else "#ef4444"
        dma_color = "#22c55e" if card.get("above_200dma", False) else "#ef4444"
        price = card.get("price", 0)
        price_str = f"${price:,.2f}" if price > 0 else "N/A"
        ax.text(0.5, 0.86, asset, ha="center", fontsize=18, fontweight="bold", color=colors[i])
        ax.text(0.5, 0.62, price_str, ha="center", fontsize=22, fontweight="bold", color="white")
        ax.text(0.5, 0.46, f"{roc:+.1f}% (20d)", ha="center", fontsize=13, color=roc_color)
        ax.text(0.5, 0.32, f"Vol {card.get('vol', 0)}% | DD {card.get('drawdown', 0)}%", ha="center", fontsize=11, color="#94a3b8")
        ax.text(0.5, 0.16, "200DMA: " + ("▲ Above" if card.get("above_200dma", False) else "▼ Below"),
                ha="center", fontsize=11, color=dma_color)
        ax.set_facecolor("#1e2937")
        ax.axis("off")

    draw_classic_gauge(fig.add_subplot(gs[1, 0]), tpi["MACRO"], "Macro Environment", "Risk-Off", "Risk-On", tpi["CONFIDENCE"]["MACRO"])
    draw_classic_gauge(fig.add_subplot(gs[1, 1]), tpi["LTPI_BTC"], "LTPI — Long-Term", "Bearish", "Bullish", tpi["CONFIDENCE"]["LTPI"])
    draw_classic_gauge(fig.add_subplot(gs[1, 2]), tpi["MTPI_BTC"], "MTPI — Medium-Term", "Weak", "Strong", tpi["CONFIDENCE"]["MTPI"])
    draw_classic_gauge(fig.add_subplot(gs[1, 3]), tpi["FNG_NORM"], f"Fear & Greed  {tpi['FNG']:.0f} {tpi['FNG_LABEL']}", "Fear", "Greed", 60)
    draw_classic_gauge(fig.add_subplot(gs[1, 4]), tpi["BTC_DOMINANCE"], "BTC Dominance Trend", "Alt Strength", "BTC Strength", 55)

    ax_hist = fig.add_subplot(gs[2, :])
    if len(history) > 5:
        hist_120 = history[-120:]
        dates = [h["timestamp"][:10] for h in hist_120]
        macros = [h.get("MACRO", 0) for h in hist_120]
        ltpis = [h.get("LTPI_BTC", 0) for h in hist_120]
        step = max(1, len(dates) // 12)
        ax_hist.plot(dates, macros, label="Macro", color="#22c55e", linewidth=2.5)
        ax_hist.plot(dates, ltpis, label="LTPI", color="#60a5fa", linewidth=2.5)
        ax_hist.legend(facecolor="#1e2937", labelcolor="white", loc="upper left", fontsize=11)
        ax_hist.grid(True, alpha=0.25, linestyle="--")
        ax_hist.set_title("Trend history", color="white", fontsize=14, fontweight="bold", pad=10)
        ax_hist.tick_params(colors="white", labelsize=10)
        ax_hist.set_xticks(range(0, len(dates), step))
        ax_hist.set_xticklabels([dates[i] for i in range(0, len(dates), step)], rotation=25, ha="right")
        ax_hist.set_facecolor("#1e2937")
        ax_hist.set_ylim(-1.0, 1.0)
        for spine in ax_hist.spines.values():
            spine.set_color("#334155")
    else:
        _panel(ax_hist)
        ax_hist.text(0.5, 0.55, "Trend history starts after a few daily runs", ha="center", va="center", fontsize=14, color="#94a3b8")
        ax_hist.text(0.5, 0.32, tpi["timestamp"], ha="center", fontsize=11, color="#64748b")

    ax_edge = fig.add_subplot(gs[3, :])
    _panel(ax_edge)
    ax_edge.text(0.5, 0.66, f"{tpi['VERDICT']}   ·   {tpi['REGIME']}   ·   {tpi['ROTATION']}",
                 ha="center", va="center", fontsize=20, fontweight="bold", color=vcol)
    ax_edge.text(0.5, 0.28, action, ha="center", va="center", fontsize=14, color="#e2e8f0")

    chips = [
        ("Altseason 30d", f"{tpi['ALTSEASON_30']:.0f}", "#22c55e" if tpi["ALTSEASON_30"] >= 50 else "#fbbf24" if tpi["ALTSEASON_30"] >= 35 else "#94a3b8"),
        ("BTC dominance", f"{tpi['BTC_DOM_PCT']:.1f}%", "#f7931a"),
        ("ETH / BTC", f"{tpi['ETH_BTC']:.4f}", "#627eea"),
        ("VIX", f"{vix:.1f}", "#ef4444" if vix >= 20 else "#22c55e"),
        ("10Y", f"{tnx:.2f}%", "#94a3b8"),
    ]
    for i, (lab, val, col) in enumerate(chips):
        ax = fig.add_subplot(gs[4, i])
        _panel(ax)
        ax.text(0.5, 0.68, lab.upper(), ha="center", fontsize=11, color="#94a3b8", fontweight="bold")
        ax.text(0.5, 0.32, val, ha="center", fontsize=22, fontweight="bold", color=col)

    ax_table = fig.add_subplot(gs[5, :3])
    perf_assets = ["BTC", "ETH", "SPY", "NASDAQ", "GOLD", "DXY", "COPPER", "VIX"]
    table_data = [["Asset", "20d", "200d", "200DMA"]]
    for asset in perf_assets:
        d = raw.get(asset, {})
        table_data.append([asset, f"{d.get('roc_20', 0):+.1f}%", f"{d.get('roc_252', 0):+.1f}%",
                           "Above" if d.get("above_200dma") else "Below"])
    table = ax_table.table(cellText=table_data, loc="center", cellLoc="center", colWidths=[0.22, 0.22, 0.22, 0.22])
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 1.45)
    for (i, j), cell in table.get_celld().items():
        cell.set_facecolor("#334155" if i == 0 else "#1e2937")
        cell.set_text_props(weight="bold" if i == 0 else "normal", color="white" if i == 0 else "#cbd5e1")
        cell.set_edgecolor("#0f172a")
    ax_table.set_title("Markets", color="white", fontsize=14, fontweight="bold", pad=8)
    ax_table.axis("off")

    ax_key = fig.add_subplot(gs[5, 3:])
    _panel(ax_key, "Rotation & levels")
    btc_dma = raw.get("BTC", {}).get("dma200", 0)
    btc_price = raw.get("BTC", {}).get("price", 0)
    ax_key.text(0.06, 0.88,
                f"{tpi['ROTATION']}\n{tpi['ROTATION_NOTE']}\n\n"
                f"BTC 20d   {raw.get('BTC', {}).get('roc_20', 0):+.1f}%\n"
                f"BTC.D 20d {tpi['BTC_DOM_CHG_20']:+.2f} pp\n"
                f"Spot      ${btc_price:,.0f}\n"
                f"200DMA    ${btc_dma:,.0f}\n"
                f"Risk      {risk_text}",
                fontsize=12, color="#e2e8f0", va="top", fontfamily="monospace",
                transform=ax_key.transAxes, linespacing=1.45)

    ax_monitor = fig.add_subplot(gs[6, :])
    monitor_data = [["Coin", "Price", "Target %", "Held $", "30d", "7d"]]
    held_map = {h["symbol"]: h for h in (paper.get("alt_holdings") or [])}
    shown = []
    for a in (tpi.get("alt_basket") or []):
        shown.append(a["symbol"])
        tgt = float((alloc.get("alt_breakdown") or {}).get(a["symbol"]) or 0)
        h = held_map.get(a["symbol"])
        held = f"${h['usd']:,.0f}" if h else "—"
        tgt_s = f"{tgt:g}%" if tgt else "—"
        monitor_data.append([a["symbol"], f"${a['price']:,.2f}", tgt_s, held,
                             f"{a['chg_30d']:+.1f}%", f"{a['chg_7d']:+.1f}%"])
    for sym, d in list(tpi["alt_raw"].items()):
        if sym in shown or sym in EXCLUDE_SYMBOLS:
            continue
        monitor_data.append([sym, f"${d.get('price', 0):,.2f}", "—", "—",
                             f"{d.get('chg_30d', 0):+.1f}%", f"{d.get('chg_7d', 0):+.1f}%"])
        if len(monitor_data) >= 8:
            break
    mon_table = ax_monitor.table(cellText=monitor_data, loc="center", cellLoc="center",
                                 colWidths=[0.12, 0.16, 0.12, 0.14, 0.12, 0.12])
    mon_table.auto_set_font_size(False)
    mon_table.set_fontsize(11)
    mon_table.scale(1, 1.38)
    for (i, j), cell in mon_table.get_celld().items():
        cell.set_facecolor("#334155" if i == 0 else "#1e2937")
        cell.set_text_props(weight="bold" if i == 0 else "normal", color="white" if i == 0 else "#cbd5e1")
        cell.set_edgecolor("#0f172a")
    alt_state = "ON" if alloc["ALT"] > 0 else "OFF"
    names = ", ".join(f"{k} {v:g}%" for k, v in (alloc.get("alt_breakdown") or {}).items()) or "none"
    ax_monitor.set_title(f"Alt sleeve {alt_state}  ·  {alloc['ALT']}% total  ·  {names}  ·  "
                         f"Altseason {tpi['ALTSEASON_30']:.0f} ({tpi['ALTSEASON_BEATS']}/{tpi['ALTSEASON_N']} beat BTC)",
                         color="white", fontsize=13, fontweight="bold", pad=8)
    ax_monitor.axis("off")

    ax_alloc = fig.add_subplot(gs[7, :3])
    labels = ["BTC", "ETH", "GOLD", "ALT", "CASH"]
    values = [alloc["BTC"], alloc["ETH"], alloc["GOLD"], alloc["ALT"], alloc["CASH"]]
    colors_alloc = ["#f7931a", "#627eea", "#eab308", "#8b5cf6", "#64748b"]
    bars = ax_alloc.barh(labels, values, color=colors_alloc, height=0.55)
    ax_alloc.set_xlim(0, 100)
    ax_alloc.set_title("Target mix", fontsize=14, fontweight="bold", color="white", pad=8)
    ax_alloc.tick_params(colors="white", labelsize=11)
    ax_alloc.set_facecolor("#1e2937")
    for spine in ax_alloc.spines.values():
        spine.set_color("#334155")
    for bar, val in zip(bars, values):
        ax_alloc.text(val - 2 if val > 12 else val + 2, bar.get_y() + bar.get_height() / 2,
                      f"{val}%", va="center", ha="right" if val > 12 else "left",
                      color="white", fontsize=13, fontweight="bold")

    ax_acct = fig.add_subplot(gs[7, 3:])
    _panel(ax_acct, "Account")
    ret_c = "#22c55e" if paper.get("ret_pct", 0) >= 0 else "#ef4444"
    ax_acct.text(0.08, 0.78, "Balance", fontsize=11, color="#94a3b8", transform=ax_acct.transAxes)
    ax_acct.text(0.08, 0.58, f"${paper.get('equity', 0):,.2f}", fontsize=22, fontweight="bold",
                 color="white", transform=ax_acct.transAxes)
    ax_acct.text(0.08, 0.38, f"{paper.get('ret_pct', 0):+.2f}%", fontsize=16, fontweight="bold",
                 color=ret_c, transform=ax_acct.transAxes)
    held_txt = "Alts  none"
    holds = paper.get("alt_holdings") or []
    if holds:
        held_txt = "Alts  " + "  ·  ".join(f"{h['symbol']} {h['pct']:.1f}% (${h['usd']:,.0f})" for h in holds)
    ax_acct.text(0.08, 0.16,
                 f"vs BTC  {paper.get('hodl_ret_pct', 0):+.2f}%   ·   Max DD  {paper.get('dd_pct', 0):+.2f}%   ·   Cash  ${paper.get('cash', 0):,.0f}\n"
                 f"Live   BTC {pw.get('BTC', 0):.0f}%  ETH {pw.get('ETH', 0):.0f}%  "
                 f"Gold {pw.get('GOLD', 0):.0f}%  Alt {pw.get('ALT', 0):.0f}%  Cash {pw.get('CASH', 0):.0f}%\n"
                 f"{held_txt}",
                 fontsize=10, color="#cbd5e1", transform=ax_acct.transAxes, va="top", linespacing=1.45)

    ax_footer = fig.add_subplot(gs[8, :])
    ax_footer.axis("off")
    ax_footer.set_facecolor("#0f172a")
    ax_footer.text(0.5, 0.4, f"TPI  ·  {tpi['timestamp']}", ha="center", fontsize=11, color="#64748b")

    plt.suptitle(f"TPI  ·  {tpi['timestamp']}", fontsize=24, fontweight="bold", color="white", y=0.985)
    try:
        plt.tight_layout(rect=[0.02, 0.01, 0.98, 0.965])
    except Exception:
        pass
    out = "tpi_pro_dashboard.png"
    plt.savefig(out, dpi=220, bbox_inches="tight", facecolor="#0f172a")
    plt.close()
    return out


# =============================================================================
# DISCORD
# =============================================================================
def send_to_discord():
    current = compute_tpi()
    alloc = get_allocation(current)
    paper = update_paper_book(current, alloc)
    save_history(current)
    img_path = create_pro_dashboard(current, paper)

    # Material-change alerts (separate short messages)
    check_and_send_alerts(current, alloc, paper)

    alt_txt = "none"
    bits = alloc.get("alt_breakdown") or {}
    if bits:
        alt_txt = " + ".join(f"{k} {v:g}%" for k, v in bits.items())
    held_txt = "none"
    if paper.get("alt_holdings"):
        held_txt = ", ".join(f"{h['symbol']} ${h['usd']:,.0f} ({h['pct']:.1f}%)" for h in paper["alt_holdings"])
    short_msg = (
        f"**{current['VERDICT']}** | {current['REGIME']} | "
        f"LTPI {current['LTPI_BTC']:+.2f} | Macro {current['MACRO']:+.2f} | "
        f"F&G {current['FNG']:.0f} | Altseason {current['ALTSEASON_30']:.0f} | "
        f"Account {paper['ret_pct']:+.1f}% (DD {paper['dd_pct']:+.1f}%)\n"
        f"Alts **{alloc['ALT']}%**: {alt_txt}"
    )
    payload = {
        "content": f"📈 **Daily TPI Update — {current['timestamp']}**\n{short_msg}\n\n🔗 **[Open TPI Dashboard]({STREAMLIT_URL})** (VIP login required)",
        "username": "TPI Edge • VIP",
        "embeds": [{
            "title": f"{current['VERDICT']}  ·  {current['ROTATION']}",
            "description": (
                f"{current['ROTATION_NOTE']}\n"
                f"Target: {alloc['BTC']}% BTC / {alloc['ETH']}% ETH / "
                f"{alloc['GOLD']}% Gold / {alloc['CASH']}% Cash / {alloc['ALT']}% Alts\n"
                f"Alt names: {alt_txt}\n"
                f"Held alts: {held_txt}\n\n"
                f"🔗 [Open full dashboard]({STREAMLIT_URL})"
            ),
            "color": 0x22c55e if current["MACRO"] > 0 else 0xef4444,
            "image": {"url": "attachment://tpi_pro_dashboard.png"},
        }],
    }

    with open(img_path, "rb") as f:
        response = requests.post(
            WEBHOOK_URL,
            data={"payload_json": json.dumps(payload)},
            files={"file": ("tpi_pro_dashboard.png", f, "image/png")},
            timeout=60,
        )

    if response.status_code in (200, 204):
        print("✅ TPI dashboard sent (image embedded).")
    else:
        print(f"❌ Discord error: {response.status_code} {response.text[:200]}")

    print(
        f"Account ${paper['equity']:.2f} ({paper['ret_pct']:+.2f}%) "
        f"vs BTC {paper['hodl_ret_pct']:+.2f}% | {paper['reason']}"
    )


if __name__ == "__main__":
    send_to_discord()
