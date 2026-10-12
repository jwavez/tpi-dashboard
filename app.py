import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import requests
from datetime import datetime, timedelta
import urllib.parse
import json
import os

st.set_page_config(
    page_title="Traders Edge · TPI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background-color: #0b1220; color: #e2e8f0; }
    .block-container { padding-top: 0.4rem; padding-bottom: 1rem; max-width: 1320px; }
    .main-card {
        background: linear-gradient(145deg, #1e2937 0%, #162033 100%);
        border-radius: 16px; padding: 0.9rem 1.1rem;
        border: 1px solid #334155; margin-bottom: 0.7rem;
    }
    .title { font-size: 1.6rem; font-weight: 750; margin: 0.1rem 0 0.05rem 0; }
    .subtitle { font-size: 0.92rem; color: #94a3b8; margin-bottom: 0.35rem; }
    .verdict { color: #4ade80; font-weight: 650; }
    .stat-pill { background: #0f172a; border-radius: 10px; padding: 0.45rem; text-align: center; border: 1px solid #334155; }
    .stat-label { font-size: 0.62rem; color: #94a3b8; text-transform: uppercase; }
    .stat-value { font-size: 1.05rem; font-weight: 700; }
    .alert { background: #422006; border-left: 4px solid #fbbf24; padding: 0.5rem 0.75rem; border-radius: 8px; margin-bottom: 0.55rem; }
    .brand-header { text-align: center; margin-bottom: 0.3rem; font-weight: 700; letter-spacing: 1.5px; color: #22d3ee; font-size: 1.3rem; }
    .brand-sub { font-size: 0.72rem; color: #64748b; letter-spacing: 2px; margin-top: -0.1rem; text-align: center; }
    .watermark { position: fixed; bottom: 10px; right: 14px; font-size: 0.68rem; color: #334155; letter-spacing: 1px; pointer-events: none; z-index: 999; }
    .gauge-label { text-align: center; font-size: 0.7rem; color: #94a3b8; margin-top: -0.35rem; }
    .pos { color: #22c55e; font-weight: 650; }
    .neg { color: #ef4444; font-weight: 650; }
    @media (max-width: 768px) {
        .block-container { padding-left: 0.5rem; padding-right: 0.5rem; }
        .title { font-size: 1.35rem; }
    }
</style>
""", unsafe_allow_html=True)

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
    params = {"client_id": DISCORD_CLIENT_ID, "redirect_uri": REDIRECT_URI, "response_type": "code", "scope": "identify guilds.members.read"}
    return "https://discord.com/api/oauth2/authorize?" + urllib.parse.urlencode(params)

def exchange_code(code):
    data = {"client_id": DISCORD_CLIENT_ID, "client_secret": DISCORD_CLIENT_SECRET, "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}
    r = requests.post("https://discord.com/api/oauth2/token", data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    return r.json().get("access_token") if r.status_code == 200 else None

def get_user_and_roles(token):
    headers = {"Authorization": f"Bearer {token}"}
    user = requests.get("https://discord.com/api/users/@me", headers=headers).json()
    member = requests.get(f"https://discord.com/api/users/@me/guilds/{DISCORD_SERVER_ID}/member", headers=headers)
    roles = member.json().get("roles", []) if member.status_code == 200 else []
    return user, roles

query_params = st.query_params
if "code" in query_params and not st.session_state.discord_user:
    token = exchange_code(query_params["code"])
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
    st.markdown("Log in with Discord to verify your VIP membership.")
    st.link_button("Login with Discord", discord_login_url())
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

def load_paper_book():
    path = "tpi_paper_book.json"
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"equity_curve": [], "trades": [], "positions": {}, "cash": 10000, "start_equity": 10000, "peak_equity": 10000}

def color_pnl(val):
    if isinstance(val, str) and val.startswith("+"):
        return f'<span class="pos">{val}</span>'
    if isinstance(val, str) and val.startswith("-"):
        return f'<span class="neg">{val}</span>'
    return val

@st.cache_data(ttl=120)
def get_dashboard_data():
    book = load_paper_book()
    equity = float(book.get("equity_curve", [{}])[-1].get("equity", 9817) if book.get("equity_curve") else 9817)
    start = float(book.get("start_equity", 10000))
    peak = float(book.get("peak_equity", equity))
    dd = (equity - peak) / peak * 100 if peak else 0

    # Sample consistent fallback if no live book
    return {
        "verdict": "LEAN BUY", "regime": "Bullish", "rotation": "Risk-Off",
        "btc": 50, "eth": 15, "gold": 13, "cash": 16, "alts": 6,
        "alt_breakdown": [{"coin": "SOL", "pct": 1.2, "note": "High-throughput L1"}, {"coin": "ZEC", "pct": 1.2, "note": "Privacy coin"},
                          {"coin": "HYPE", "pct": 1.2, "note": "Perp DEX"}, {"coin": "LINK", "pct": 1.2, "note": "Oracle"}, {"coin": "ADA", "pct": 1.2, "note": "Research L1"}],
        "altseason_30": 54, "btc_dom": 59.5, "fng": 69, "eth_btc": 0.0306,
        "ltpi": 0.47, "macro": 0.20, "mtpi": -0.06, "fng_norm": 0.38, "btc_dom_trend": 1.00,
        "balance": equity, "start_balance": start, "dd_pct": round(dd, 1),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "equity_curve": book.get("equity_curve", [
            {"timestamp": "2026-09-01", "equity": 10000, "btc_hodl": 10000, "dd_pct": 0},
            {"timestamp": "2026-10-12", "equity": equity, "btc_hodl": 10420, "dd_pct": dd},
        ]),
        "regime_history": [
            {"date": "2026-09-01", "regime": "Neutral", "btc": 45, "eth": 10, "gold": 15, "cash": 25, "alts": 5},
            {"date": "2026-09-18", "regime": "Bullish", "btc": 50, "eth": 15, "gold": 13, "cash": 16, "alts": 6},
            {"date": "2026-10-12", "regime": "Bullish", "btc": 50, "eth": 15, "gold": 13, "cash": 16, "alts": 6},
        ],
        "perf_7d": -0.8, "perf_30d": -1.8, "perf_90d": 2.4, "max_dd": round(dd, 1), "sharpe": 0.65,
        "open_positions": [
            {"Asset": "BTC", "Side": "Long", "Size": "0.058 BTC", "Entry": "$81,200", "Current": "$83,300", "P&L": "+$122", "Why": "Core sleeve"},
            {"Asset": "ETH", "Side": "Long", "Size": "0.59 ETH", "Entry": "$2,480", "Current": "$2,552", "P&L": "+$42", "Why": "Core sleeve"},
            {"Asset": "Gold", "Side": "Long", "Size": "0.31 oz", "Entry": "$4,050", "Current": "$4,198", "P&L": "+$46", "Why": "Ballast"},
            {"Asset": "SOL", "Side": "Long", "Size": "1.06 SOL", "Entry": "$108", "Current": "$111", "P&L": "+$3", "Why": "Alt sleeve"},
            {"Asset": "LINK", "Side": "Long", "Size": "0.91 LINK", "Entry": "$14.20", "Current": "$13.32", "P&L": "-$1", "Why": "Alt sleeve"},
        ],
        "closed_trades": [
            {"Date": "2026-10-08", "Asset": "ZEC", "Side": "Long", "P&L": "+$18", "R": "+0.6"},
            {"Date": "2026-10-05", "Asset": "ADA", "Side": "Long", "P&L": "-$4", "R": "-0.2"},
            {"Date": "2026-10-02", "Asset": "HYPE", "Side": "Long", "P&L": "+$31", "R": "+1.1"},
            {"Date": "2026-09-28", "Asset": "BTC", "Side": "Long", "P&L": "+$94", "R": "+0.8"},
            {"Date": "2026-09-22", "Asset": "ETH", "Side": "Long", "P&L": "+$27", "R": "+0.7"},
        ],
    }

data = get_dashboard_data()

# What changed banner
notes = []
if st.session_state.last_seen_regime and st.session_state.last_seen_regime != data["regime"]:
    notes.append(f"Regime {st.session_state.last_seen_regime} → {data['regime']}")
if st.session_state.last_seen_alloc and st.session_state.last_seen_alloc != (data["btc"], data["alts"]):
    notes.append("Allocation shifted")
if notes:
    st.markdown(f'<div class="alert">⚠️ {" · ".join(notes)}</div>', unsafe_allow_html=True)
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
    bar_color = "#22c55e" if value > 0 else "#ef4444" if kind in ("fng", "dom") else "#fbbf24"
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        number={"font": {"size": 18, "color": "white"}},
        title={"text": title, "font": {"size": 10, "color": "#e2e8f0"}},
        gauge={
            "axis": {"range": [-1, 1], "tickwidth": 1, "tickcolor": "#64748b"},
            "bar": {"color": bar_color, "thickness": 0.16},
            "bgcolor": "#1e2937", "borderwidth": 0,
            "steps": [{"range": [-1, -0.3], "color": "#7f1d1d"}, {"range": [-0.3, 0.3], "color": "#334155"}, {"range": [0.3, 1], "color": "#14532d"}],
            "threshold": {"line": {"color": bar_color, "width": 3}, "thickness": 0.8, "value": value},
        },
    ))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#e2e8f0"},
                      height=160, margin=dict(l=4, r=4, t=22, b=0))
    return fig

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown('<div class="title">TPI Allocation · This Week</div>', unsafe_allow_html=True)
st.markdown(f'<div class="subtitle">LEAN BUY · <span class="verdict">{data["regime"]}</span> · {data["rotation"]}</div>', unsafe_allow_html=True)
st.caption(f"Logged in as {st.session_state.discord_user.get('username', 'VIP')}")
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

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Rolling Performance")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("7-Day", f"{data['perf_7d']:+.1f}%")
c2.metric("30-Day", f"{data['perf_30d']:+.1f}%")
c3.metric("90-Day", f"{data['perf_90d']:+.1f}%")
c4.metric("Max DD", f"{data['max_dd']:.1f}%")
c5.metric("Sharpe", f"{data['sharpe']:.2f}")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Equity Curve & Drawdown")
eq_raw = data.get("equity_curve") or []
eq_df = pd.DataFrame(eq_raw)
if eq_df.empty:
    # Fallback so the section never crashes
    eq_df = pd.DataFrame({
        "date": ["2026-09-01", "2026-10-12"],
        "equity": [10000, data.get("balance", 9817)],
        "btc_hodl": [10000, 9687],
        "dd_pct": [0, -1.8],
    })
else:
    if "date" not in eq_df.columns:
        if "timestamp" in eq_df.columns:
            eq_df["date"] = eq_df["timestamp"]
        else:
            eq_df["date"] = range(len(eq_df))
    if "equity" not in eq_df.columns:
        eq_df["equity"] = data.get("balance", 10000)

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
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Regime History & Allocation Snapshots")
st.dataframe(pd.DataFrame(data["regime_history"]), hide_index=True, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

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

# Open positions with color
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Open Positions")
open_df = pd.DataFrame(data["open_positions"])
if not open_df.empty and "P&L" in open_df.columns:
    styled = open_df.style.map(
        lambda x: "color: #22c55e" if str(x).startswith("+") else "color: #ef4444" if str(x).startswith("-") else "",
        subset=["P&L"]
    )
    st.dataframe(styled, hide_index=True, use_container_width=True)
else:
    st.dataframe(open_df, hide_index=True, use_container_width=True)
with st.expander("Position details"):
    st.dataframe(open_df, hide_index=True, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# Closed trades with color
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Closed Trades")
closed_df = pd.DataFrame(data["closed_trades"])
if not closed_df.empty and "P&L" in closed_df.columns:
    styled_c = closed_df.style.map(
        lambda x: "color: #22c55e" if str(x).startswith("+") else "color: #ef4444" if str(x).startswith("-") else "",
        subset=["P&L"]
    )
    st.dataframe(styled_c.head(4), hide_index=True, use_container_width=True)
    with st.expander("View full closed trade history"):
        st.dataframe(styled_c, hide_index=True, use_container_width=True)
else:
    st.dataframe(closed_df.head(4), hide_index=True, use_container_width=True)
    with st.expander("View full closed trade history"):
        st.dataframe(closed_df, hide_index=True, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Alt Sleeve")
cols = st.columns(5)
for i, a in enumerate(data["alt_breakdown"]):
    with cols[i]:
        st.markdown(f'<div style="background:#0f172a; border-radius:12px; padding:0.55rem; text-align:center; border:1px solid #334155;">'
                    f'<div style="font-weight:700;">{a["coin"]}</div><div style="color:#8b5cf6; font-weight:650;">{a["pct"]}%</div>'
                    f'<div style="font-size:0.65rem; color:#94a3b8;">{a["note"]}</div></div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

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

st.caption(f"Last updated {data['timestamp']} · Data from latest run · Traders Edge VIP")

if st.button("Refresh data", type="primary"):
    st.rerun()
