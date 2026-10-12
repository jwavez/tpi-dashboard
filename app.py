import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import requests
from datetime import datetime
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

DISCORD_CLIENT_ID = st.secrets.get("DISCORD_CLIENT_ID", "1559177904636825690")
DISCORD_CLIENT_SECRET = st.secrets.get("DISCORD_CLIENT_SECRET", "I0waUTNBVXSEBEmsdorwBavrUD57OmUI")
DISCORD_SERVER_ID = "1177276514857922560"
VIP_ROLE_ID = "1177332827742801990"
REDIRECT_URI = st.secrets.get("REDIRECT_URI", "http://localhost:8501/")
DISCORD_WEBHOOK = str(st.secrets.get("DISCORD_WEBHOOK", "")).strip()

if "discord_user" not in st.session_state:
    st.session_state.discord_user = None
if "has_vip" not in st.session_state:
    st.session_state.has_vip = False

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

def log_usage(username):
    log_file = "usage_log.json"
    entry = {"user": username, "time": datetime.now().strftime("%Y-%m-%d %H:%M")}
    try:
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                logs = json.load(f)
        else:
            logs = []
        logs.append(entry)
        logs = logs[-200:]
        with open(log_file, "w") as f:
            json.dump(logs, f)
    except Exception:
        pass

user = st.session_state.discord_user
if user:
    log_usage(user.get("username", "unknown"))

@st.cache_data(ttl=180)
def get_live_data():
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
        "balance": 9817.44, "start_balance": 10000,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "equity_curve": [
            {"date": "2026-09-01", "equity": 10000, "btc_hodl": 10000},
            {"date": "2026-09-15", "equity": 10240, "btc_hodl": 10180},
            {"date": "2026-10-01", "equity": 9980, "btc_hodl": 10350},
            {"date": "2026-10-12", "equity": 9817, "btc_hodl": 10420},
        ],
        "regime_history": [
            {"date": "2026-09-01", "regime": "Neutral"},
            {"date": "2026-09-18", "regime": "Bullish"},
            {"date": "2026-10-05", "regime": "Bullish"},
            {"date": "2026-10-12", "regime": "Bullish"},
        ],
        "alert": None,
        "perf_30d": -1.8,
        "btc_30d": 4.2,
    }

data = get_live_data()

if len(data["regime_history"]) >= 2:
    last = data["regime_history"][-1]["regime"]
    prev = data["regime_history"][-2]["regime"]
    if last != prev:
        data["alert"] = f"Regime changed from {prev} to {last}"

def gauge_label(value, kind):
    if kind == "macro":
        return "Risk-On" if value > 0.2 else "Neutral" if value > -0.2 else "Risk-Off"
    if kind == "ltpi":
        return "Strong" if value > 0.3 else "Bullish" if value > 0 else "Weak" if value > -0.3 else "Bearish"
    if kind == "mtpi":
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

if data.get("alert"):
    st.markdown(f'<div class="alert">⚠️ {data["alert"]}</div>', unsafe_allow_html=True)

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown('<div class="title">TPI Allocation · This Week</div>', unsafe_allow_html=True)
st.markdown(f'<div class="subtitle">LEAN BUY · <span class="verdict">{data["regime"]}</span> · {data["rotation"]}</div>', unsafe_allow_html=True)
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

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("30-Day Performance")
p1, p2 = st.columns(2)
with p1:
    st.markdown(f'<div class="perf-card"><div class="stat-label">TPI Model</div><div class="stat-value">{data["perf_30d"]:+.1f}%</div></div>', unsafe_allow_html=True)
with p2:
    st.markdown(f'<div class="perf-card"><div class="stat-label">BTC HODL</div><div class="stat-value">{data["btc_30d"]:+.1f}%</div></div>', unsafe_allow_html=True)
st.caption("Model vs Bitcoin over the last 30 days")
st.markdown("</div>", unsafe_allow_html=True)

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

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Equity Curve vs BTC HODL")
eq_df = pd.DataFrame(data["equity_curve"])
fig_eq = go.Figure()
fig_eq.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["equity"], name="TPI Account", line=dict(color="#4ade80", width=2.5)))
fig_eq.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["btc_hodl"], name="BTC HODL", line=dict(color="#f7931a", width=2, dash="dot")))
fig_eq.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"),
                     height=250, margin=dict(l=35, r=15, t=5, b=30),
                     legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig_eq, use_container_width=True, config={"displayModeBar": False})
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Regime History")
reg_df = pd.DataFrame(data["regime_history"])
fig_reg = go.Figure(go.Scatter(x=reg_df["date"], y=[1]*len(reg_df), mode="markers+text",
                               marker=dict(size=12, color="#4ade80"),
                               text=reg_df["regime"], textposition="top center"))
fig_reg.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#e2e8f0"), height=160, margin=dict(l=15, r=15, t=15, b=25),
                      yaxis=dict(visible=False), showlegend=False)
st.plotly_chart(fig_reg, use_container_width=True, config={"displayModeBar": False})
st.markdown("</div>", unsafe_allow_html=True)

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

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Open Positions")
open_pos = pd.DataFrame({
    "Asset": ["BTC", "ETH", "Gold", "SOL", "LINK"],
    "Side": ["Long"]*5,
    "Size": ["0.058 BTC", "0.59 ETH", "0.31 oz", "1.06 SOL", "0.91 LINK"],
    "Entry": ["$81,200", "$2,480", "$4,050", "$108", "$14.20"],
    "Current": ["$83,300", "$2,552", "$4,198", "$111", "$13.32"],
    "P&L": ["+$122", "+$42", "+$46", "+$3", "-$1"],
    "Why open": ["Core sleeve", "Core sleeve", "Ballast", "Alt sleeve", "Alt sleeve"],
})
st.dataframe(open_pos[["Asset", "Side", "Size", "Entry", "Current", "P&L"]], hide_index=True, use_container_width=True)
with st.expander("Position details"):
    st.dataframe(open_pos, hide_index=True, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Closed Trades")
closed_full = pd.DataFrame({
    "Date": ["2026-10-08", "2026-10-05", "2026-10-02", "2026-09-28", "2026-09-22", "2026-09-18", "2026-09-12"],
    "Asset": ["ZEC", "ADA", "HYPE", "BTC", "ETH", "SOL", "GOLD"],
    "Side": ["Long"]*7,
    "P&L": ["+$18", "-$4", "+$31", "+$94", "+$27", "+$12", "+$41"],
    "R": ["+0.6", "-0.2", "+1.1", "+0.8", "+0.7", "+0.4", "+0.9"],
})
st.dataframe(closed_full.head(4), hide_index=True, use_container_width=True)
with st.expander("View full closed trade history"):
    st.dataframe(closed_full, hide_index=True, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Alt Sleeve")
cols = st.columns(5)
for i, a in enumerate(data["alt_breakdown"]):
    with cols[i]:
        st.markdown(f'<div style="background:#0f172a; border-radius:12px; padding:0.6rem; text-align:center; border:1px solid #334155;">'
                    f'<div style="font-weight:700;">{a["coin"]}</div>'
                    f'<div style="color:#8b5cf6; font-weight:650;">{a["pct"]}%</div>'
                    f'<div style="font-size:0.68rem; color:#94a3b8;">{a["note"]}</div></div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Key Market Stats")
c1, c2, c3, c4, c5 = st.columns(5)
for col, (lab, val) in zip([c1, c2, c3, c4, c5], [
    ("Altseason 30d", f"{data['altseason_30']}"),
    ("BTC Dominance", f"{data['btc_dom']}%"),
    ("Fear & Greed", f"{data['fng']}"),
    ("ETH / BTC", f"{data['eth_btc']:.4f}"),
    ("LTPI", f"{data['ltpi']:.2f}"),
]):
    with col:
        st.markdown(f'<div class="stat-pill"><div class="stat-label">{lab}</div><div class="stat-value">{val}</div></div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

st.caption(f"Last updated {data['timestamp']}  ·  Traders Edge VIP")

if st.button("Refresh data", type="primary"):
    st.rerun()

# Always show the Discord button
if st.button("Send daily summary to Discord"):
    if not DISCORD_WEBHOOK or not DISCORD_WEBHOOK.startswith("https://discord.com/api/webhooks/"):
        st.error("Webhook is missing or invalid. Check the DISCORD_WEBHOOK secret (must be one single line).")
    else:
        msg = (
            f"**TPI Daily** · {data['verdict']} · {data['regime']}\n"
            f"{data['btc']}% BTC · {data['eth']}% ETH · {data['gold']}% Gold · "
            f"{data['cash']}% Cash · {data['alts']}% Alts"
        )
        try:
            r = requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=10)
            if r.status_code in (200, 204):
                st.success("Summary sent to Discord")
            else:
                st.error(f"Discord returned {r.status_code}")
        except Exception as e:
            st.error(f"Failed to send: {e}")
