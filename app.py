import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import os
from datetime import datetime, timedelta
import hashlib

st.set_page_config(page_title="TPI Dashboard", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# ---------- Branding (footer) ----------
st.markdown("""
<style>
.block-container { padding-top: 1rem; }
.main-card { background: #0f172a; border: 1px solid #1e293b; border-radius: 16px; padding: 1.2rem; margin-bottom: 1rem; }
.title { font-size: 1.6rem; font-weight: 700; color: #e2e8f0; }
.subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 0.8rem; }
.verdict { color: #22c55e; font-weight: 650; }
.gauge-label { text-align: center; font-size: 0.78rem; color: #94a3b8; margin-top: -8px; margin-bottom: 8px; }
.stat-pill { background: #1e293b; border-radius: 12px; padding: 0.6rem; text-align: center; }
.stat-label { font-size: 0.65rem; color: #94a3b8; text-transform: uppercase; }
.stat-value { font-size: 1.15rem; font-weight: 700; color: #e2e8f0; }
.banner { background: #1e3a5f; border-left: 4px solid #60a5fa; padding: 0.6rem 1rem; border-radius: 8px; margin-bottom: 1rem; color: #e2e8f0; }
.footer { text-align: center; color: #475569; font-size: 0.75rem; margin-top: 2rem; padding: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# ---------- File paths (Streamlit Cloud safe) ----------
PAPER_BOOK_FILE = "tpi_paper_book.json"
HISTORY_FILE = "tpi_history.json"
STATE_FILE = "tpi_last_state.json"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

# ---------- Live data loader ----------
def get_live_data():
    book = load_json(PAPER_BOOK_FILE, {})
    history = load_json(HISTORY_FILE, [])

    # Fallback sample if no real book yet
    if not book or not book.get("equity_curve"):
        return {
            "balance": 9817.44, "start_balance": 10000,
            "regime": "Bullish", "verdict": "LEAN BUY", "rotation": "Risk-Off",
            "macro": 0.20, "ltpi": 0.47, "mtpi": -0.06, "fng": 69, "fng_norm": 0.38,
            "btc_dom_trend": 1.0, "btc_dom": 59.5, "altseason_30": 54, "eth_btc": 0.0306,
            "btc": 50, "eth": 15, "gold": 13, "cash": 16, "alts": 6,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "open_positions": [
                {"Asset": "BTC", "Side": "Long", "Size": "0.058 BTC", "Entry": "$81,200", "Current": "$83,300", "P&L": "+$122", "Why": "Core sleeve", "EntryDate": "2026-09-18", "R": "+0.8", "Note": "Still in uptrend"},
                {"Asset": "ETH", "Side": "Long", "Size": "0.59 ETH", "Entry": "$2,480", "Current": "$2,552", "P&L": "+$42", "Why": "Core sleeve", "EntryDate": "2026-09-18", "R": "+0.6", "Note": "Holding relative strength"},
                {"Asset": "Gold", "Side": "Long", "Size": "0.31 oz", "Entry": "$4,050", "Current": "$4,198", "P&L": "+$46", "Why": "Ballast", "EntryDate": "2026-09-01", "R": "+0.4", "Note": "Macro hedge"},
                {"Asset": "SOL", "Side": "Long", "Size": "1.06 SOL", "Entry": "$108", "Current": "$111", "P&L": "+$3", "Why": "Alt sleeve", "EntryDate": "2026-10-02", "R": "+0.2", "Note": "Small selective"},
                {"Asset": "LINK", "Side": "Long", "Size": "0.91 LINK", "Entry": "$14.20", "Current": "$13.32", "P&L": "-$1", "Why": "Alt sleeve", "EntryDate": "2026-10-02", "R": "-0.1", "Note": "Watching"},
            ],
            "closed_trades": [
                {"Date": "2026-10-08", "Asset": "ZEC", "Side": "Long", "P&L": "+$18", "R": "+0.6"},
                {"Date": "2026-10-05", "Asset": "ADA", "Side": "Long", "P&L": "-$4", "R": "-0.2"},
                {"Date": "2026-10-02", "Asset": "HYPE", "Side": "Long", "P&L": "+$31", "R": "+1.1"},
                {"Date": "2026-09-28", "Asset": "BTC", "Side": "Long", "P&L": "+$94", "R": "+0.8"},
                {"Date": "2026-09-22", "Asset": "ETH", "Side": "Long", "P&L": "+$27", "R": "+0.7"},
            ],
            "equity_curve": [
                {"date": "2026-09-01", "equity": 10000, "btc_hodl": 10000, "dd_pct": 0},
                {"date": "2026-09-18", "equity": 9920, "btc_hodl": 9780, "dd_pct": -0.8},
                {"date": "2026-10-12", "equity": 9817, "btc_hodl": 9687, "dd_pct": -1.8},
            ],
            "regime_history": [
                {"date": "2026-09-01", "regime": "Neutral", "btc": 45, "eth": 10, "gold": 15, "cash": 25, "alts": 5},
                {"date": "2026-09-18", "regime": "Bullish", "btc": 50, "eth": 15, "gold": 13, "cash": 16, "alts": 6},
                {"date": "2026-10-12", "regime": "Bullish", "btc": 50, "eth": 15, "gold": 13, "cash": 16, "alts": 6},
            ],
            "alt_breakdown": [
                {"coin": "SOL", "pct": 1.2, "note": "High-throughput L1"},
                {"coin": "ZEC", "pct": 1.2, "note": "Privacy coin"},
                {"coin": "HYPE", "pct": 1.2, "note": "Perp DEX"},
                {"coin": "LINK", "pct": 1.2, "note": "Oracle"},
                {"coin": "ADA", "pct": 1.2, "note": "Research L1"},
            ],
            "perf_7d": -0.8, "perf_30d": -1.8, "perf_90d": 2.4, "max_dd": -1.8, "sharpe": 0.65,
            "last_update": datetime.now().isoformat(),
        }

    # Real book path (simplified mapping)
    equity = book.get("equity_curve", [])
    last = equity[-1] if equity else {}
    balance = last.get("equity", 9817)
    return {
        "balance": balance, "start_balance": book.get("start_equity", 10000),
        "regime": book.get("last_regime", "Bullish"),
        "verdict": "LEAN BUY", "rotation": "Risk-Off",
        "macro": 0.20, "ltpi": 0.47, "mtpi": -0.06, "fng": 69, "fng_norm": 0.38,
        "btc_dom_trend": 1.0, "btc_dom": 59.5, "altseason_30": 54, "eth_btc": 0.0306,
        "btc": 50, "eth": 15, "gold": 13, "cash": 16, "alts": 6,
        "timestamp": last.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M")),
        "open_positions": [],  # fill from book positions if present
        "closed_trades": book.get("trades", [])[-10:],
        "equity_curve": equity[-90:],
        "regime_history": [],
        "alt_breakdown": [],
        "perf_7d": 0, "perf_30d": 0, "perf_90d": 0, "max_dd": last.get("dd_pct", 0), "sharpe": 0.5,
        "last_update": datetime.now().isoformat(),
    }

data = get_live_data()

# ---------- What changed banner ----------
last_state = load_json(STATE_FILE, {})
current_sig = f"{data['regime']}|{data['alts']}|{data['btc']}"
if last_state.get("sig") and last_state["sig"] != current_sig:
    st.markdown(f'<div class="banner">What changed: regime or allocation shifted since your last visit.</div>', unsafe_allow_html=True)
save_json(STATE_FILE, {"sig": current_sig, "ts": datetime.now().isoformat()})

# ---------- Gauges ----------
def make_gauge(value, title, kind):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"size": 12, "color": "#94a3b8"}},
        number={"font": {"size": 22, "color": "#e2e8f0"}},
        gauge={
            "axis": {"range": [-1, 1], "tickcolor": "#475569"},
            "bar": {"color": "#FFD700", "thickness": 0.15},
            "steps": [
                {"range": [-1, -0.3], "color": "#ef4444"},
                {"range": [-0.3, 0.3], "color": "#64748b"},
                {"range": [0.3, 1], "color": "#22c55e"},
            ],
            "threshold": {"line": {"color": "#FFD700", "width": 3}, "thickness": 0.8, "value": value},
        }
    ))
    fig.update_layout(height=180, margin=dict(l=20, r=20, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", font={"color": "#e2e8f0"})
    return fig

def gauge_label(val, kind):
    labels = {
        "macro": "Risk-On" if val > 0.2 else "Risk-Off" if val < -0.2 else "Neutral",
        "ltpi": "Bullish" if val > 0.3 else "Bearish" if val < -0.3 else "Neutral",
        "mtpi": "Strong" if val > 0.2 else "Weak" if val < -0.2 else "Neutral",
        "fng": "Greed" if val > 0.3 else "Fear" if val < -0.3 else "Neutral",
        "dom": "BTC Strength" if val > 0 else "Alt Strength",
    }
    return labels.get(kind, "")

# ---------- UI ----------
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown('<div class="title">TPI Allocation · This Week</div>', unsafe_allow_html=True)
st.markdown(f'<div class="subtitle">LEAN BUY · <span class="verdict">{data["regime"]}</span> · {data["rotation"]}</div>', unsafe_allow_html=True)
st.caption(f"Logged in as {st.session_state.get('discord_user', {}).get('username', 'VIP')}")

gcols = st.columns(5)
for col, (val, title, kind) in zip(gcols, [
    (data["macro"], "Macro", "macro"), (data["ltpi"], "LTPI Long-Term", "ltpi"),
    (data["mtpi"], "MTPI Medium-Term", "mtpi"), (data["fng_norm"], f"Fear & Greed {data['fng']}", "fng"),
    (data["btc_dom_trend"], "BTC Dom Trend", "dom"),
]):
    with col:
        st.plotly_chart(make_gauge(val, title, kind), use_container_width=True, config={"displayModeBar": False})
        st.markdown(f'<div class="gauge-label">{gauge_label(val, kind)}</div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Rolling performance
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Rolling Performance")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("7-Day", f"{data['perf_7d']:+.1f}%")
c2.metric("30-Day", f"{data['perf_30d']:+.1f}%")
c3.metric("90-Day", f"{data['perf_90d']:+.1f}%")
c4.metric("Max DD", f"{data['max_dd']:.1f}%")
c5.metric("Sharpe", f"{data['sharpe']:.2f}")
st.markdown("</div>", unsafe_allow_html=True)

# Equity curve
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Equity Curve & Drawdown")
eq_df = pd.DataFrame(data["equity_curve"])
if not eq_df.empty:
    if "date" not in eq_df.columns and "timestamp" in eq_df.columns:
        eq_df["date"] = eq_df["timestamp"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["equity"], name="TPI Account", line=dict(color="#4ade80", width=2.5)))
    if "btc_hodl" in eq_df.columns:
        fig.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["btc_hodl"], name="BTC HODL", line=dict(color="#f7931a", width=2, dash="dot")))
    if "dd_pct" in eq_df.columns:
        fig.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["dd_pct"], name="Drawdown %", yaxis="y2",
                                 line=dict(color="#f87171", width=1.5), fill="tozeroy", fillcolor="rgba(248,113,113,0.15)"))
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"),
                      height=290, margin=dict(l=40, r=40, t=8, b=25),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                      yaxis=dict(title="Equity"), yaxis2=dict(title="DD %", overlaying="y", side="right", showgrid=False))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.info("No equity data yet.")
st.markdown("</div>", unsafe_allow_html=True)

# Regime history
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Regime History & Allocation Snapshots")
st.dataframe(pd.DataFrame(data["regime_history"]), hide_index=True, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# Account
pnl = data["balance"] - data["start_balance"]
pnl_pct = (pnl / data["start_balance"]) * 100 if data["start_balance"] else 0
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Account")
a1, a2, a3, a4 = st.columns(4)
a1.metric("Balance", f"${data['balance']:,.2f}")
a2.metric("Starting", f"${data['start_balance']:,.0f}")
a3.metric("Total P&L", f"${pnl:,.2f}", f"{pnl_pct:+.2f}%")
a4.metric("Open Positions", str(len(data["open_positions"])))
st.markdown("</div>", unsafe_allow_html=True)

# Target mix
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Target Mix")
assets = ["₿ BTC", "Ξ ETH", "🪙 Gold", "💵 Cash", "✦ Alts"]
values = [data["btc"], data["eth"], data["gold"], data["cash"], data["alts"]]
colors = ["#f7931a", "#627eea", "#eab308", "#64748b", "#8b5cf6"]
fig = go.Figure()
for asset, val, color in zip(assets, values, colors):
    fig.add_trace(go.Bar(y=[asset], x=[val], orientation="h", marker_color=color,
                         text=f"{val}%", textposition="outside", textfont=dict(color="white", size=11), showlegend=False))
fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"),
                  xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False),
                  yaxis=dict(categoryorder="array", categoryarray=["✦ Alts", "💵 Cash", "🪙 Gold", "Ξ ETH", "₿ BTC"]),
                  height=240, margin=dict(l=90, r=30, t=5, b=5), bargap=0.3)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
st.markdown("</div>", unsafe_allow_html=True)

# Open positions + detail expander
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Open Positions")
open_df = pd.DataFrame(data["open_positions"])
if not open_df.empty and "P&L" in open_df.columns:
    def color_pnl(val):
        s = str(val)
        if s.startswith("+"): return "color: #22c55e"
        if s.startswith("-"): return "color: #ef4444"
        return ""
    styled = open_df.style.map(color_pnl, subset=["P&L"])
    st.dataframe(styled, hide_index=True, use_container_width=True)
else:
    st.dataframe(open_df, hide_index=True, use_container_width=True)

with st.expander("Position details"):
    if not open_df.empty:
        for _, row in open_df.iterrows():
            st.markdown(f"**{row.get('Asset', '')}** · {row.get('Side', '')} · Entry {row.get('EntryDate', 'n/a')} · R {row.get('R', 'n/a')}")
            st.caption(row.get("Note", "No additional note"))
    else:
        st.write("No open positions.")
st.markdown("</div>", unsafe_allow_html=True)

# Closed trades
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Closed Trades")
closed_df = pd.DataFrame(data["closed_trades"])
if not closed_df.empty and "P&L" in closed_df.columns:
    def color_pnl(val):
        s = str(val)
        if s.startswith("+"): return "color: #22c55e"
        if s.startswith("-"): return "color: #ef4444"
        return ""
    styled_preview = closed_df.head(4).style.map(color_pnl, subset=["P&L"])
    st.dataframe(styled_preview, hide_index=True, use_container_width=True)
    with st.expander("View full closed trade history"):
        st.dataframe(closed_df.style.map(color_pnl, subset=["P&L"]), hide_index=True, use_container_width=True)
else:
    st.dataframe(closed_df.head(4), hide_index=True, use_container_width=True)
    with st.expander("View full closed trade history"):
        st.dataframe(closed_df, hide_index=True, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# Alt sleeve
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Alt Sleeve")
cols = st.columns(5)
for i, a in enumerate(data.get("alt_breakdown", [])):
    with cols[i]:
        st.markdown(f'<div style="background:#0f172a; border-radius:12px; padding:0.55rem; text-align:center; border:1px solid #334155;">'
                    f'<div style="font-weight:700;">{a["coin"]}</div><div style="color:#8b5cf6; font-weight:650;">{a["pct"]}%</div>'
                    f'<div style="font-size:0.65rem; color:#94a3b8;">{a["note"]}</div></div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Key stats
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Key Market Stats")
c1, c2, c3, c4, c5 = st.columns(5)
for col, (lab, val) in zip([c1,c2,c3,c4,c5], [
    ("Altseason 30d", f"{data['altseason_30']}"), ("BTC Dominance", f"{data['btc_dom']}%"),
    ("Fear & Greed", f"{data['fng']}"), ("ETH / BTC", f"{data['eth_btc']:.4f}"), ("LTPI", f"{data['ltpi']:.2f}"),
]):
    with col:
        st.markdown(f'<div class="stat-pill"><div class="stat-label">{lab}</div><div class="stat-value">{val}</div></div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Freshness
try:
    last = datetime.fromisoformat(data.get("last_update", datetime.now().isoformat()))
    mins = int((datetime.now() - last).total_seconds() / 60)
    freshness = f"Updated {mins} minutes ago" if mins < 120 else "Data from daily run"
except Exception:
    freshness = "Data from daily run"
st.caption(f"{freshness} · {data['timestamp']} · Traders Edge VIP")

# Footer branding
st.markdown('<div class="footer">TPI DASHBOARD · Traders Edge VIP</div>', unsafe_allow_html=True)

if st.button("Refresh data", type="primary"):
    st.rerun()
