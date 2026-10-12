import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="TPI Professional Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background-color: #0b1220; color: #e2e8f0; }
    .block-container { padding-top: 0.7rem; padding-bottom: 1.4rem; max-width: 1320px; }
    .main-card {
        background: linear-gradient(145deg, #1e2937 0%, #162033 100%);
        border-radius: 16px;
        padding: 1.15rem 1.35rem;
        border: 1px solid #334155;
        margin-bottom: 0.85rem;
    }
    .title { font-size: 1.75rem; font-weight: 750; margin: 0 0 0.05rem 0; }
    .subtitle { font-size: 0.98rem; color: #94a3b8; margin-bottom: 0.45rem; }
    .verdict { color: #4ade80; font-weight: 650; }
    .stat-pill {
        background: #0f172a; border-radius: 10px; padding: 0.55rem;
        text-align: center; border: 1px solid #334155;
    }
    .stat-label { font-size: 0.66rem; color: #94a3b8; text-transform: uppercase; }
    .stat-value { font-size: 1.15rem; font-weight: 700; }
    .alert { background: #422006; border-left: 4px solid #fbbf24; padding: 0.6rem 0.9rem; border-radius: 8px; margin-bottom: 0.7rem; }
</style>
""", unsafe_allow_html=True)

# Multi-key VIP gate (add/remove keys here)
VALID_KEYS = {
    "TE-VIP-001": "Member A",
    "TE-VIP-002": "Member B",
    "TE-VIP-003": "Member C",
    # Add more keys as needed. Remove a key to revoke access.
}

if "vip_ok" not in st.session_state:
    st.session_state.vip_ok = False
    st.session_state.member_name = ""

if not st.session_state.vip_ok:
    st.markdown('<div class="main-card">', unsafe_allow_html=True)
    st.subheader("VIP Access")
    key = st.text_input("Enter your personal VIP key", type="password")
    if st.button("Unlock Dashboard"):
        if key in VALID_KEYS:
            st.session_state.vip_ok = True
            st.session_state.member_name = VALID_KEYS[key]
            st.rerun()
        else:
            st.error("Invalid or expired key")
    st.caption("Each member receives a unique key. Keys can be revoked at any time.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

@st.cache_data(ttl=180)
def get_live_data():
    # Replace this return with a call to your compute_tpi() + update_paper_book()
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
        "alert": "Alt sleeve active (6%) — selective alts only",
    }

data = get_live_data()

def make_gauge(value, title, color_mode="neutral"):
    if color_mode in ("fng", "dom"):
        bar_color = "#22c55e" if value > 0 else "#ef4444"
    else:
        bar_color = "#fbbf24"
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        number={"font": {"size": 22, "color": "white"}},
        title={"text": title, "font": {"size": 11, "color": "#e2e8f0"}},
        gauge={
            "axis": {"range": [-1, 1], "tickwidth": 1, "tickcolor": "#64748b"},
            "bar": {"color": bar_color, "thickness": 0.2},
            "bgcolor": "#1e2937", "borderwidth": 0,
            "steps": [
                {"range": [-1, -0.3], "color": "#7f1d1d"},
                {"range": [-0.3, 0.3], "color": "#334155"},
                {"range": [0.3, 1], "color": "#14532d"},
            ],
            "threshold": {"line": {"color": bar_color, "width": 5}, "thickness": 0.9, "value": value},
        },
    ))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font={"color": "#e2e8f0"}, height=190,
                      margin=dict(l=8, r=8, t=28, b=0))
    return fig

# Alert
if data.get("alert"):
    st.markdown(f'<div class="alert">⚠️ {data["alert"]}</div>', unsafe_allow_html=True)

# Header
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.markdown('<div class="title">TPI Allocation · This Week</div>', unsafe_allow_html=True)
st.markdown(f'<div class="subtitle">LEAN BUY · <span class="verdict">{data["regime"]}</span> · {data["rotation"]}</div>', unsafe_allow_html=True)
if st.session_state.member_name:
    st.caption(f"Logged in as {st.session_state.member_name}")
g1, g2, g3, g4, g5 = st.columns(5)
with g1: st.plotly_chart(make_gauge(data["macro"], "Macro"), use_container_width=True, config={"displayModeBar": False})
with g2: st.plotly_chart(make_gauge(data["ltpi"], "LTPI Long-Term"), use_container_width=True, config={"displayModeBar": False})
with g3: st.plotly_chart(make_gauge(data["mtpi"], "MTPI Medium-Term"), use_container_width=True, config={"displayModeBar": False})
with g4: st.plotly_chart(make_gauge(data["fng_norm"], f"Fear & Greed {data['fng']}", "fng"), use_container_width=True, config={"displayModeBar": False})
with g5: st.plotly_chart(make_gauge(data["btc_dom_trend"], "BTC Dom Trend", "dom"), use_container_width=True, config={"displayModeBar": False})
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

# Equity curve
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Equity Curve vs BTC HODL")
eq_df = pd.DataFrame(data["equity_curve"])
fig_eq = go.Figure()
fig_eq.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["equity"], name="TPI Account", line=dict(color="#4ade80", width=2.5)))
fig_eq.add_trace(go.Scatter(x=eq_df["date"], y=eq_df["btc_hodl"], name="BTC HODL", line=dict(color="#f7931a", width=2, dash="dot")))
fig_eq.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0"),
                     height=260, margin=dict(l=40, r=20, t=5, b=35),
                     legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
st.plotly_chart(fig_eq, use_container_width=True, config={"displayModeBar": False})
st.markdown("</div>", unsafe_allow_html=True)

# Regime history
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Regime History")
reg_df = pd.DataFrame(data["regime_history"])
fig_reg = go.Figure(go.Scatter(x=reg_df["date"], y=[1]*len(reg_df), mode="markers+text",
                               marker=dict(size=14, color="#4ade80"),
                               text=reg_df["regime"], textposition="top center"))
fig_reg.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#e2e8f0"), height=180, margin=dict(l=20, r=20, t=20, b=30),
                      yaxis=dict(visible=False), showlegend=False)
st.plotly_chart(fig_reg, use_container_width=True, config={"displayModeBar": False})
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
                         text=f"{val}%", textposition="outside", textfont=dict(color="white", size=13),
                         hovertemplate=f"<b>{asset}</b><br>{val}%<extra></extra>", showlegend=False))
fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#e2e8f0", size=12),
                  xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False, zeroline=False),
                  yaxis=dict(showgrid=False, tickfont=dict(size=14),
                             categoryorder="array", categoryarray=["✦ Alts", "💵 Cash", "🪙 Gold", "Ξ ETH", "₿ BTC"]),
                  height=280, margin=dict(l=100, r=45, t=5, b=5), bargap=0.34)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
st.markdown("</div>", unsafe_allow_html=True)

# Open positions
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

# Closed trades
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

# Alt sleeve + stats
st.markdown('<div class="main-card">', unsafe_allow_html=True)
st.subheader("Alt Sleeve")
cols = st.columns(5)
for i, a in enumerate(data["alt_breakdown"]):
    with cols[i]:
        st.markdown(f'<div style="background:#0f172a; border-radius:12px; padding:0.65rem; text-align:center; border:1px solid #334155;">'
                    f'<div style="font-weight:700;">{a["coin"]}</div>'
                    f'<div style="color:#8b5cf6; font-weight:650;">{a["pct"]}%</div>'
                    f'<div style="font-size:0.7rem; color:#94a3b8;">{a["note"]}</div></div>', unsafe_allow_html=True)
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

st.caption(f"Last updated {data['timestamp']}  ·  Unique key access")

if st.button("Refresh data", type="primary"):
    st.rerun()
