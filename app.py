import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import requests
from datetime import datetime, timedelta
import urllib.parse
import json
import os
import numpy as np

st.set_page_config(
    page_title="Traders Edge · TPI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background-color: #0b1220; color: #e2e8f0; }
    .block-container { padding-top: 0.5rem; padding-bottom: 1.2rem; max-width: 1320px; }
    .main-card {
        background: linear-gradient(145deg, #1e2937 0%, #162033 100%);
        border-radius: 16px;
        padding: 1rem 1.2rem;
        border: 1px solid #334155;
        margin-bottom: 0.75rem;
    }
    .title { font-size: 1.65rem; font-weight: 750; margin: 0.15rem 0 0.05rem 0; }
    .subtitle { font-size: 0.95rem; color: #94a3b8; margin-bottom: 0.4rem; }
    .verdict { color: #4ade80; font-weight: 650; }
    .stat-pill {
        background: #0f172a; border-radius: 10px; padding: 0.5rem;
        text-align: center; border: 1px solid #334155;
    }
    .stat-label { font-size: 0.64rem; color: #94a3b8; text-transform: uppercase; }
    .stat-value { font-size: 1.1rem; font-weight: 700; }
    .alert { background: #422006; border-left: 4px solid #fbbf24; padding: 0.55rem 0.8rem; border-radius: 8px; margin-bottom: 0.6rem; }
    .brand-header { text-align: center; margin-bottom: 0.4rem; font-weight: 700; letter-spacing: 1.5px; color: #22d3ee; font-size: 1.35rem; }
    .brand-sub { font-size: 0.75rem; color: #64748b; letter-spacing: 2px; margin-top: -0.15rem; text-align: center; }
    .watermark { position: fixed; bottom: 12px; right: 16px; font-size: 0.7rem; color: #334155; letter-spacing: 1px; pointer-events: none; z-index: 999; }
    .perf-card { background: #0f172a; border-radius: 12px; padding: 0.8rem; border: 1px solid #334155; text-align: center; }
    .gauge-label { text-align: center; font-size: 0.72rem; color: #94a3b8; margin-top: -0.4rem; }
</style>
""", unsafe_allow_html=True)

# Discord OAuth
DISCORD_CLIENT_ID = st.secrets.get("DISCORD_CLIENT_ID", "1559177904636825690")
DISCORD_CLIENT_SECRET = st.secrets.get("DISCORD_CLIENT_SECRET", "I0waUTNBVXSEBEmsdorwBavrUD57OmUI")
DISCORD_SERVER_ID = "1177276514857922560"
VIP_ROLE_ID = "1177332827742801990"
REDIRECT_URI = st.secrets.get("REDIRECT_URI", "http://localhost:8501/")

if "discord_user" not in st.session_state:
    st.session_state.discord_user = None
if "has_vip" not in st.session_state:
    st.session_state.has_vip = False
if "last_seen_regime" not in st.session_state:
    st.session_state.last_seen_regime = None
if "last_seen_alloc" not in st.session_state:
    st.session_state.last_seen_alloc = None

def discord_login_url():
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds.members.read",
    }
    return "https://discord.com/api/oauth2/authorize?" + urllib.parse.urlencode(params)

def exchange_code(code):
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    if r.status_code != 200:
        return None
    return r.json().get("access_token")

def get_user_and_roles(token):
    headers = {"Authorization": f"Bearer {token}"}
    user = requests.get("https://discord.com/api/users/@me", headers=headers).json()
    member = requests.get(
        f"https://discord.com/api/users/@me/guilds/{DISCORD_SERVER_ID}/member",
        headers=headers,
    )
    roles = []
    if member.status_code == 200:
        roles = member.json().get("roles", [])
    return user, roles

query_params = st.query_params
if "code" in query_params and not st.session_state.discord_user:
    code = query_params["code"]
    token = exchange_code(code)
    if token:
        user, roles = get_user_and_roles(token)
        st.session_state.discord_user = user
        st.session_state.has_vip = VIP_ROLE_ID in roles
        st.query_params.clear()
        st.rerun()

st.markdown('<div class="brand-header">TRADERS EDGE</div>', unsafe_allow_html=True)
st.markdown('<div class="brand-sub">TPI DASHBOARD</div>', unsafe_allow_html=True)
st.markdown('<div class="watermark">TRADERS EDGE</div>', unsafe_allow_html=True)

if not st.session_state.discord_user or not st.session_state.has_vip:
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    st.subheader("VIP Access")
    if st.session_state.discord_user and not st.session_state.has_vip:
        st.error("You are logged in with Discord but do not have the VIP role.")
    else:
        st.markdown("Log in with Discord to verify your VIP membership and open the live TPI dashboard.")
    st.link_button("Login with Discord", discord_login_url())
    st.caption("Access is granted only if you hold the VIP role in the Traders Edge server.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# Live data function — replace the body with your real compute_tpi() + paper book
@st.cache_data(ttl=180)
def get_live_data():
    # TODO: replace this with a real call to compute_tpi() and update_paper_book()
    dates = pd.date_range(end=datetime.now(), periods=90, freq="D")
    equity = 10000 * np.cumprod(1 + np.random.normal(0.0004, 0.012, 90))
    btc = 10000 * np.cumprod(1 + np.random.normal(0.0006, 0.018, 90))
    eq_df = pd.DataFrame({"date": dates, "equity": equity, "btc_hodl": btc})
    peak = eq_df["equity"].cummax()
    eq_df["drawdown"] = (eq_df["equity"] - peak) / peak * 100

    return {
        "verdict": "LEAN BUY",
        "regime": "Bullish",
        "rotation": "Risk-Off",
        "btc": 50, "eth": 15, "gold": 13, "cash": 16, "alts": 6,
        "alt_breakdown": [
            {"coin": "SOL", "pct": 1.2, "note": "High-throughput L1"},
            {"coin": "ZEC", "pct": 1.2, "note": "Privacy coin"},
            {"coin": "HYPE", "pct": 1.2, "note": "Perp DEX"},
            {"coin": "LINK", "pct": 1.2, "note": "Oracle"},
            {"coin": "ADA", "pct": 1.2, "note": "Research L1"},
        ],
        "altseason_30": 54, "btc_dom": 59.5, "fng": 69, "eth_btc": 0.0306,
        "ltpi": 0.47, "macro": 0.20, "mtpi": -0.06, "fng_norm": 0.38, "btc_dom_trend": 1.00,
        "balance": float(equity[-1]), "start_balance": 10000,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "equity_df": eq_df,
        "regime_history": [
            {"date": "2026-09-01", "regime": "Neutral", "btc": 45, "eth": 10, "gold": 15, "cash": 25, "alts": 5},
            {"date": "2026-09-18", "regime": "Bullish", "btc": 50, "eth": 15, "gold": 13, "cash": 16, "alts": 6},
            {"date": "2026-10-05", "regime": "Bullish", "btc": 50, "eth": 15, "gold": 13, "cash": 16, "alts": 6},
            {"date": "2026-10-12", "regime": "Bullish", "btc": 50, "eth": 15, "gold": 13, "cash": 16, "alts": 6},
        ],
        "perf_7d": -0.8, "perf_30d": -1.8, "perf_90d": 2.4,
        "max_dd": -4.2, "sharpe": 0.65,
    }

data = get_live_data()

# What changed banner
change_notes = []
if st.session_state.last_seen_regime and st.session_state.last_seen_regime != data["regime"]:
    change_notes.append(f"Regime moved from {st.session_state.last_seen_regime} to {data['regime']}")
if st.session_state.last_seen_alloc and st.session_state.last_seen_alloc != (data["btc"], data["alts"]):
    change_notes.append("Allocation weights shifted")
if change_notes:
    st.markdown(f'<div class="alert">⚠️ {" · ".join(change_notes)}</div>', unsafe_allow_html=True)
st.session_state.last_seen_regime = data["regime"]
st.session_state.last_seen_alloc = (data["btc"], data["alts"])

def gauge_label(value, kind):
    if kind == "macro":
        return "Risk-On" if value > 0.2 else "Neutral" if value > -0.2 else "Risk-Off"
    if kind in ("ltpi", "mtpi"):
        return "Strong" if value > 0.3 else "Bullish" if value > 0 else "Weak" if value > -0.3 else "Bearish"
    if kind == "fng":
        return "Extreme Greed" if value > 0.6 else "Greed" if value > 0.2 else "Neutral" if value > -0.2 else "Fear" if value > -0.6 else "Extreme Fear"
    if kind == "dom":
        return "BTC Strength" if value > 0 else "Alt Strength"
    return ""

def make_gauge(value, title, kind="neutral"):
    if kind in ("fng", "dom"):
        bar_color = "#22c55e" if value > 0 else "#ef4444"
    else:
        bar_color = "#fbbf24"
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        number={"font": {"size": 20, "color": "white"}},
        title={"text": title, "font": {"size": 11, "color": "#e2e8f0"}},
        gauge={
            "axis": {"range": [-1, 1], "tickwidth": 1, "tickcolor": "#64748b"},
            "bar": {"color": bar_color, "thickness": 0.18},
            "bgcolor": "#1e2937", "borderwidth": 0,
            "steps": [
                {"range": [-1, -0.3], "color": "#7f1d1d"},
                {"range": [-0.3, 0.3], "color": "#334155"},
                {"range": [0.3, 1], "color": "#14532d"},
            ],
            "threshold": {"line": {"color": bar_color, "width": 4}, "thickness": 0.85, "value": value},
        },
    ))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font={"color": "#e2e8f0"}, height=175,
                      margin=dict(l=6, r=6, t=26, b=0))
    return fig

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown('<div class="title">TPI Allocation · This Week</div>', unsafe_allow_html=True)
st.markdown(f'<div class="subtitle">LEAN BUY · <span class="verdict">{data["regime"]}</span> · {data["rotation"]}</div>', unsafe_allow_html=True)
user = st.session_state.discord_user
if user:
    st.caption(f"Logged in as {user.get('username', 'VIP Member')}")
g1, g2, g3, g4, g5 = st.columns(5)
with g1:
    st.plotly_chart(make_gauge(data["macro"], "Macro", "macro"), use_container_width=True, config={"displayModeBar": False})
    st.markdown(f'<div class="gauge-label">{gauge_label(data["macro"], "macro")}</div>', unsafe_allow_html=True)
with g2:
    st.plotly_chart(make_gauge(data["ltpi"], "LTPI Long-Term", "ltpi"), use_container_width=True, config={"displayModeBar": False})
    st.markdown(f'<div class="gauge-label">{gauge_label(data["ltpi"], "ltpi")}</div>', unsafe_allow_html=True)
with g3:
    st.plotly_chart(make_gauge(data["mtpi"], "MTPI Medium-Term", "mtpi"), use_container_width=True, config={"displayModeBar": False})
    st.markdown(f'<div class="gauge-label">{gauge_label(data["mtpi"], "mtpi")}</div>', unsafe_allow_html=True)
with g4:
    st.plotly_chart(make_gauge(data["fng_norm"], f"Fear & Greed {data['fng']}", "fng"), use_container_width=True, config={"displayModeBar": False})
    st.markdown(f'<div class="gauge-label">{gauge_label(data["fng_norm"], "fng")}</div>', unsafe_allow_html=True)
with g5:
    st.plotly_chart(make_gauge(data["btc_dom_trend"], "BTC Dom Trend", "dom"), use_container_width=True, config={"displayModeBar": False})
    st.markdown(f'<div class="gauge-label">{gauge_label(data["btc_dom_trend"], "dom")}</div>', unsafe_allow_html=True)
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

# Equity + drawdown
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Equity Curve & Drawdown")
eq_df = data["equity_df"]
fig = go.Figure()
fig.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["equity"], name="TPI Account", line=dict(color="#4ade80", width=2.5)))
fig.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["btc_hodl"], name="BTC HODL", line=dict(color="#f7931a", width=2, dash="dot")))
fig.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["drawdown"], name="Drawdown %", yaxis="y2",
                         line=dict(color="#f87171", width=1.5), fill="tozeroy", fillcolor="rgba(248,113,113,0.15)"))
fig.update_layout(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"),
    height=320, margin=dict(l=40, r=40, t=10, b=30),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    yaxis=dict(title="Equity"),
    yaxis2=dict(title="Drawdown %", overlaying="y", side="right", showgrid=False)
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
st.markdown("</div>", unsafe_allow_html=True)

# Regime history with allocation
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Regime History & Allocation Snapshots")
reg_df = pd.DataFrame(data["regime_history"])
st.dataframe(reg_df, hide_index=True, use_container_width=True)
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
a4.metric("Open Positions", "5")
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
                         text=f"{val}%", textposition="outside", textfont=dict(color="white", size=12),
                         hovertemplate=f"<b>{asset}</b><br>{val}%<extra></extra>", showlegend=False))
fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0", size=12),
                  xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False, zeroline=False),
                  yaxis=dict(showgrid=False, tickfont=dict(size=13),
                             categoryorder="array", categoryarray=["✦ Alts", "💵 Cash", "🪙 Gold", "Ξ ETH", "₿ BTC"]),
                  height=260, margin=dict(l=95, r=40, t=5, b=5), bargap=0.32)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
st.markdown("</div>", unsafe_allow_html=True)

st.caption(f"Last updated {data['timestamp']}  ·  Traders Edge VIP")

if st.button("Refresh data", type="primary"):
    st.rerun()
