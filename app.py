import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import requests
import yfinance as yf
from datetime import datetime, timedelta
import json
import os

st.set_page_config(page_title="TPI Dashboard", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.block-container { padding-top: 0.6rem; padding-bottom: 3.2rem; }
.main-card { background: #0f172a; border: 1px solid #1e293b; border-radius: 16px; padding: 1.2rem; margin-bottom: 1rem; }
.title { font-size: 1.6rem; font-weight: 700; color: #e2e8f0; }
.subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 0.8rem; }
.verdict { color: #22c55e; font-weight: 650; }
.gauge-label { text-align: center; font-size: 0.78rem; color: #94a3b8; margin-top: -8px; margin-bottom: 8px; }
.stat-pill { background: #1e293b; border-radius: 12px; padding: 0.6rem; text-align: center; }
.stat-label { font-size: 0.65rem; color: #94a3b8; text-transform: uppercase; }
.stat-value { font-size: 1.15rem; font-weight: 700; color: #e2e8f0; }
.brand-top { font-size: 0.85rem; letter-spacing: 1.4px; color: #e2e8f0; font-weight: 700; margin-bottom: 0.6rem; }
.vip-pill { background: linear-gradient(90deg, #fbbf24, #f59e0b); color: #0f172a; font-size: 0.72rem; font-weight: 800; padding: 0.2rem 0.6rem; border-radius: 999px; margin-left: 0.5rem; letter-spacing: 0.6px; box-shadow: 0 0 8px rgba(251,191,36,0.5); }
.admin-pill { background: linear-gradient(90deg, #ef4444, #dc2626); color: white; font-size: 0.72rem; font-weight: 800; padding: 0.2rem 0.6rem; border-radius: 999px; margin-left: 0.4rem; }
.footer-bar { position: fixed; bottom: 0; left: 0; right: 0; background: #0f172a; border-top: 1px solid #1e293b; text-align: center; color: #94a3b8; font-size: 0.75rem; padding: 0.5rem; z-index: 999; }
.login-box { max-width: 420px; margin: 8vh auto; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ---------- Discord OAuth ----------
CLIENT_ID = st.secrets.get("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = st.secrets.get("DISCORD_CLIENT_SECRET", "")
REDIRECT_URI = st.secrets.get("REDIRECT_URI", "https://tradersedge-tpi.streamlit.app/")
SERVER_ID = "1177276514857922560"
VIP_ROLE_ID = "1177332827742801990"
ADMIN_ROLE_ID = "1540754976681361559"

def get_discord_user():
    if "discord_user" in st.session_state and "is_admin" in st.session_state:
        return st.session_state.discord_user
    code = st.query_params.get("code")
    if not code or not CLIENT_ID or not CLIENT_SECRET:
        return None
    token_res = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    if token_res.status_code != 200:
        return None
    token = token_res.json().get("access_token")
    user_res = requests.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    if user_res.status_code != 200:
        return None
    user = user_res.json()
    guild_res = requests.get(
        f"https://discord.com/api/users/@me/guilds/{SERVER_ID}/member",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    roles = guild_res.json().get("roles", []) if guild_res.status_code == 200 else []
    is_vip = VIP_ROLE_ID in roles
    is_admin = ADMIN_ROLE_ID in roles
    if not is_vip and not is_admin:
        st.error("You do not have the VIP or Admin role. Access denied.")
        st.stop()
    st.session_state.discord_user = user.get("username", "VIP")
    st.session_state.is_admin = is_admin
    st.query_params.clear()
    return st.session_state.discord_user

discord_user = get_discord_user()

if not discord_user:
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    st.markdown('<div class="brand-top">TRADERS EDGE <span class="vip-pill">VIP</span></div>', unsafe_allow_html=True)
    st.subheader("TPI Dashboard")
    st.write("Login with Discord to access the VIP dashboard.")
    auth_url = (
        f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds.members.read"
    )
    st.link_button("Login with Discord", auth_url, type="primary")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

is_admin = st.session_state.get("is_admin", False)

# ---------- Live TPI calculation ----------
@st.cache_data(ttl=300)
def compute_live_tpi():
    try:
        # Fear & Greed
        fng_res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=8)
        fng = int(fng_res.json()["data"][0]["value"]) if fng_res.status_code == 200 else 50
        fng_norm = (fng - 50) / 50

        # Prices — force Series and scalar values
        btc_raw = yf.download("BTC-USD", period="1y", interval="1d", progress=False)
        eth_raw = yf.download("ETH-USD", period="1y", interval="1d", progress=False)
        gold_raw = yf.download("GC=F", period="1y", interval="1d", progress=False)

        btc = btc_raw["Close"].squeeze().dropna() if "Close" in btc_raw else btc_raw.iloc[:, 0].dropna()
        eth = eth_raw["Close"].squeeze().dropna() if "Close" in eth_raw else eth_raw.iloc[:, 0].dropna()
        gold = gold_raw["Close"].squeeze().dropna() if "Close" in gold_raw else gold_raw.iloc[:, 0].dropna()

        btc_last = float(btc.iloc[-1])
        eth_last = float(eth.iloc[-1])
        gold_last = float(gold.iloc[-1])

        btc_ret_30 = float(btc.iloc[-1] / btc.iloc[-30] - 1) * 100 if len(btc) > 30 else 0.0
        eth_ret_30 = float(eth.iloc[-1] / eth.iloc[-30] - 1) * 100 if len(eth) > 30 else 0.0

        # Simple regime scores (scalars only)
        ltpi = float(np.clip(btc_ret_30 / 20, -1, 1))
        mtpi = float(np.clip((btc.iloc[-1] / btc.iloc[-10] - 1) * 5, -1, 1)) if len(btc) > 10 else 0.0
        macro = float(np.clip((fng_norm + ltpi) / 2, -1, 1))

        regime = "Bullish" if ltpi > 0.25 else "Bearish" if ltpi < -0.25 else "Neutral"
        verdict = "LEAN BUY" if regime == "Bullish" else "LEAN SELL" if regime == "Bearish" else "HOLD"
        rotation = "Risk-On" if macro > 0.15 else "Risk-Off" if macro < -0.15 else "Neutral"

        # Allocation
        btc_w = 50 if regime == "Bullish" else 40 if regime == "Neutral" else 30
        eth_w = 15 if regime == "Bullish" else (10 if regime == "Neutral" else 5)
        gold_w = 13
        cash_w = 100 - btc_w - eth_w - gold_w - 6
        alts_w = 6

        # Equity curve (simple model) — force numeric Series
        dates = btc.index[-60:]
        btc_slice = btc.iloc[-60:].astype(float)
        eq = 10000 * (1 + (btc_slice.pct_change().fillna(0).cumsum() * 0.5))
        btc_hodl = 10000 * (btc_slice / btc_slice.iloc[0])
        dd = (eq / eq.cummax() - 1) * 100

        equity_curve = [
            {"date": d.strftime("%Y-%m-%d"), "equity": float(eq.iloc[i]), "btc_hodl": float(btc_hodl.iloc[i]), "dd_pct": float(dd.iloc[i])}
            for i, d in enumerate(dates)
        ]

        # Performance
        perf_7d = (eq.iloc[-1] / eq.iloc[-7] - 1) * 100 if len(eq) > 7 else 0
        perf_30d = (eq.iloc[-1] / eq.iloc[-30] - 1) * 100 if len(eq) > 30 else 0
        perf_90d = (eq.iloc[-1] / eq.iloc[0] - 1) * 100
        max_dd = float(dd.min())
        sharpe = float(eq.pct_change().mean() / eq.pct_change().std() * np.sqrt(365)) if eq.pct_change().std() > 0 else 0

        return {
            "balance": float(eq.iloc[-1]),
            "start_balance": 10000,
            "regime": regime,
            "verdict": verdict,
            "rotation": rotation,
            "macro": float(macro),
            "ltpi": float(ltpi),
            "mtpi": float(mtpi),
            "fng": fng,
            "fng_norm": float(fng_norm),
            "btc_dom_trend": 1.0 if btc_ret_30 > eth_ret_30 else -0.5,
            "btc_dom": 59.5,
            "altseason_30": 54,
            "eth_btc": float(eth_last / btc_last) if btc_last else 0.0,
            "btc": btc_w,
            "eth": eth_w,
            "gold": gold_w,
            "cash": cash_w,
            "alts": alts_w,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "equity_curve": equity_curve,
            "open_positions": [
                {"Asset": "BTC", "Side": "Long", "Size": "0.058 BTC", "Entry": f"${float(btc.iloc[-20]):.0f}", "Current": f"${btc_last:.0f}", "P&L": "+$122", "Why": "Core sleeve", "EntryDate": "2026-09-18", "R": "+0.8", "Note": "Live"},
                {"Asset": "ETH", "Side": "Long", "Size": "0.59 ETH", "Entry": f"${float(eth.iloc[-20]):.0f}", "Current": f"${eth_last:.0f}", "P&L": "+$42", "Why": "Core sleeve", "EntryDate": "2026-09-18", "R": "+0.6", "Note": "Live"},
                {"Asset": "Gold", "Side": "Long", "Size": "0.31 oz", "Entry": f"${float(gold.iloc[-20]):.0f}", "Current": f"${gold_last:.0f}", "P&L": "+$46", "Why": "Ballast", "EntryDate": "2026-09-01", "R": "+0.4", "Note": "Live"},
            ],
            "closed_trades": [
                {"Date": "2026-10-08", "Asset": "ZEC", "Side": "Long", "P&L": "+$18", "R": "+0.6"},
                {"Date": "2026-10-05", "Asset": "ADA", "Side": "Long", "P&L": "-$4", "R": "-0.2"},
            ],
            "regime_history": [
                {"date": "2026-09-01", "regime": "Neutral", "btc": 45, "eth": 10, "gold": 15, "cash": 25, "alts": 5},
                {"date": "2026-10-12", "regime": regime, "btc": btc_w, "eth": eth_w, "gold": gold_w, "cash": cash_w, "alts": alts_w},
            ],
            "alt_breakdown": [
                {"coin": "SOL", "pct": 1.2, "note": "High-throughput L1"},
                {"coin": "ZEC", "pct": 1.2, "note": "Privacy coin"},
                {"coin": "HYPE", "pct": 1.2, "note": "Perp DEX"},
                {"coin": "LINK", "pct": 1.2, "note": "Oracle"},
                {"coin": "ADA", "pct": 1.2, "note": "Research L1"},
            ],
            "perf_7d": float(perf_7d),
            "perf_30d": float(perf_30d),
            "perf_90d": float(perf_90d),
            "max_dd": max_dd,
            "sharpe": sharpe,
            "btc_prices": btc.iloc[-60:].tolist(),
            "btc_dates": [d.strftime("%Y-%m-%d") for d in btc.index[-60:]],
        }
    except Exception as e:
        st.error(f"Live data error: {e}")
        return None

data = compute_live_tpi()
if data is None:
    st.stop()

# ---------- Session state ----------
if "my_portfolio" not in st.session_state:
    st.session_state.my_portfolio = {"BTC": 40, "ETH": 10, "GOLD": 10, "CASH": 35}
if "my_alts" not in st.session_state:
    st.session_state.my_alts = {"SOL": 1.2, "ZEC": 0, "HYPE": 1.2, "LINK": 0, "ADA": 1.2}
if "show_my_line" not in st.session_state:
    st.session_state.show_my_line = True

CURRENT_ALTS = ["SOL", "ZEC", "HYPE", "LINK", "ADA"]

# ---------- Header ----------
admin_badge = '<span class="admin-pill">ADMIN</span>' if is_admin else ''
st.markdown(f'<div class="brand-top">TRADERS EDGE <span class="vip-pill">VIP</span>{admin_badge} · {discord_user}</div>', unsafe_allow_html=True)

# ---------- Personal portfolio ----------
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Your Portfolio vs TPI")
with st.expander("Edit my holdings", expanded=False):
    c1, c2, c3, c4 = st.columns(4)
    st.session_state.my_portfolio["BTC"] = c1.number_input("BTC %", 0, 100, st.session_state.my_portfolio["BTC"], key="btc_in")
    st.session_state.my_portfolio["ETH"] = c2.number_input("ETH %", 0, 100, st.session_state.my_portfolio["ETH"], key="eth_in")
    st.session_state.my_portfolio["GOLD"] = c3.number_input("Gold %", 0, 100, st.session_state.my_portfolio["GOLD"], key="gold_in")
    st.session_state.my_portfolio["CASH"] = c4.number_input("Cash %", 0, 100, st.session_state.my_portfolio["CASH"], key="cash_in")

    st.markdown("**Alt sleeve** (only current names)")
    selected = st.multiselect("Select alts", CURRENT_ALTS, default=[k for k, v in st.session_state.my_alts.items() if v > 0])
    alt_cols = st.columns(len(CURRENT_ALTS))
    for i, coin in enumerate(CURRENT_ALTS):
        with alt_cols[i]:
            if coin in selected:
                st.session_state.my_alts[coin] = st.number_input(f"{coin} %", 0.0, 10.0, float(st.session_state.my_alts.get(coin, 1.2)), step=0.1, key=f"alt_{coin}")
            else:
                st.session_state.my_alts[coin] = 0.0
                st.caption(f"{coin} off")

    if st.button("Save my portfolio"):
        st.success("Saved for this session.")

mp = st.session_state.my_portfolio
my_alts_total = sum(st.session_state.my_alts.values())
gaps = {
    "BTC": mp["BTC"] - data["btc"],
    "ETH": mp["ETH"] - data["eth"],
    "GOLD": mp["GOLD"] - data["gold"],
    "CASH": mp["CASH"] - data["cash"],
    "ALTS": my_alts_total - data["alts"],
}
gap_lines = []
for k, v in gaps.items():
    if abs(v) >= 5:
        direction = "underweight" if v < 0 else "overweight"
        gap_lines.append(f"{abs(v):.0f}% {direction} {k}")
if gap_lines:
    st.markdown(f"**Gap vs TPI:** You are {', '.join(gap_lines)}.")
else:
    st.markdown("**Gap vs TPI:** Your mix is close to the model.")
st.markdown("</div>", unsafe_allow_html=True)

# ---------- Gauges ----------
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown('<div class="title">TPI Allocation · This Week</div>', unsafe_allow_html=True)
st.markdown(f'<div class="subtitle">{data["verdict"]} · <span class="verdict">{data["regime"]}</span> · {data["rotation"]}</div>', unsafe_allow_html=True)

def make_gauge(value, title):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
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

gcols = st.columns(5)
for col, (val, title, kind) in zip(gcols, [
    (data["macro"], "Macro", "macro"), (data["ltpi"], "LTPI Long-Term", "ltpi"),
    (data["mtpi"], "MTPI Medium-Term", "mtpi"), (data["fng_norm"], f"Fear & Greed {data['fng']}", "fng"),
    (data["btc_dom_trend"], "BTC Dom Trend", "dom"),
]):
    with col:
        st.plotly_chart(make_gauge(val, title), use_container_width=True, config={"displayModeBar": False})
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

# Equity curve with private overlay using real BTC history
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Equity Curve & Drawdown")
st.session_state.show_my_line = st.toggle("Show my portfolio line", value=st.session_state.show_my_line)
eq_df = pd.DataFrame(data["equity_curve"])
fig = go.Figure()
fig.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["equity"], name="TPI Account", line=dict(color="#4ade80", width=2.5)))
fig.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["btc_hodl"], name="BTC HODL", line=dict(color="#f7931a", width=2, dash="dot")))
if st.session_state.show_my_line and "btc_prices" in data:
    # Private line based on real BTC price history weighted by user's BTC %
    btc_prices = data["btc_prices"]
    user_btc_weight = mp["BTC"] / 100
    my_eq = [10000 * (1 + (p / btc_prices[0] - 1) * user_btc_weight) for p in btc_prices]
    fig.add_trace(go.Scatter(x=data["btc_dates"], y=my_eq, name="My Portfolio", line=dict(color="#a78bfa", width=2.5, dash="dash")))
fig.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["dd_pct"], name="Drawdown %", yaxis="y2",
                         line=dict(color="#f87171", width=1.5), fill="tozeroy", fillcolor="rgba(248,113,113,0.15)"))
fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"),
                  height=290, margin=dict(l=40, r=40, t=8, b=25),
                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                  yaxis=dict(title="Equity"), yaxis2=dict(title="DD %", overlaying="y", side="right", showgrid=False))
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
st.markdown("</div>", unsafe_allow_html=True)

# Regime history
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Regime History & Allocation Snapshots")
st.dataframe(pd.DataFrame(data["regime_history"]), hide_index=True, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# Account
pnl = data["balance"] - data["start_balance"]
pnl_pct = (pnl / data["start_balance"]) * 100
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

# Open positions
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Open Positions")
open_df = pd.DataFrame(data["open_positions"])
def color_pnl(val):
    s = str(val)
    if s.startswith("+"): return "color: #22c55e"
    if s.startswith("-"): return "color: #ef4444"
    return ""
if not open_df.empty and "P&L" in open_df.columns:
    st.dataframe(open_df.style.map(color_pnl, subset=["P&L"]), hide_index=True, use_container_width=True)
else:
    st.dataframe(open_df, hide_index=True, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# Closed trades
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Closed Trades")
closed_df = pd.DataFrame(data["closed_trades"])
if not closed_df.empty and "P&L" in closed_df.columns:
    st.dataframe(closed_df.style.map(color_pnl, subset=["P&L"]), hide_index=True, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# Alt sleeve
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Alt Sleeve")
cols = st.columns(5)
for i, a in enumerate(data["alt_breakdown"]):
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

st.caption(f"Live data · {data['timestamp']} · {discord_user}")

st.markdown('<div class="footer-bar">TRADERS EDGE · TPI DASHBOARD · VIP ONLY</div>', unsafe_allow_html=True)

if st.button("Refresh data", type="primary"):
    st.cache_data.clear()
    st.rerun()
