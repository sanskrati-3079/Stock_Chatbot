"""Shared styling, navigation state and render helpers."""

import html
from uuid import uuid4

import plotly.graph_objects as go
import streamlit as st

# ----------------------------- Constants -----------------------------
ACCENT = "#6d4aff"
UP, DOWN, NEUTRAL = "#16a34a", "#dc2626", "#64748b"
SMA20_C, SMA50_C, BB_C = "#d97706", "#0891b2", "#94a3b8"
GRID = "rgba(15,23,42,0.07)"
SIGNAL_COLORS = {"BUY": UP, "SELL": DOWN, "HOLD": "#d97706"}
SIGNAL_EMOJI = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}
CURRENCY_SYMBOLS = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥", "HKD": "HK$"}

POPULAR = ["AAPL", "TSLA", "NVDA", "MSFT", "TCS.NS", "RELIANCE.NS", "INFY.NS", "BTC-USD"]
PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"]

HOME, ANALYZE, COMPARE, WATCHLIST, CHAT, LEARN = (
    "🏠 Home", "📈 Analyze", "⚖️ Compare", "⭐ Watchlist", "💬 AI Chat", "📚 Learn",
)
NAV_ITEMS = [HOME, ANALYZE, COMPARE, WATCHLIST, CHAT, LEARN]


# ----------------------------- State & navigation -----------------------------
def init_state():
    ss = st.session_state
    ss.setdefault("nav", HOME)
    ss.setdefault("ticker", "AAPL")
    ss.setdefault("recent", [])
    ss.setdefault("watchlist", ["AAPL", "TSLA", "NVDA", "TCS.NS", "RELIANCE.NS"])
    ss.setdefault("period", "6mo")


def goto(page: str, ticker: str | None = None):
    """Use as a button on_click callback so the navbar widget can be updated safely."""
    st.session_state.nav = page
    if ticker:
        st.session_state.ticker = ticker


def toggle_watch(ticker: str):
    wl = st.session_state.watchlist
    if ticker in wl:
        wl.remove(ticker)
    else:
        wl.append(ticker)


def remember(ticker: str):
    recent = [t for t in st.session_state.recent if t != ticker]
    st.session_state.recent = [ticker] + recent[:5]


# ----------------------------- Formatting -----------------------------
def esc(s) -> str:
    return html.escape(str(s))


def fmt_money(value: float, currency: str | None = None) -> str:
    sym = CURRENCY_SYMBOLS.get((currency or "").upper(), "")
    return f"{sym}{value:,.2f}"


def fmt_big(n: float) -> str:
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(n) >= div:
            return f"{n / div:.2f}{unit}"
    return f"{n:,.0f}"


def cls(v: float) -> str:
    return "up" if v > 0 else "down" if v < 0 else "flat"


def arrow(v: float) -> str:
    return "▲" if v > 0 else "▼" if v < 0 else "■"


def color_for(v: float) -> str:
    return UP if v > 0 else DOWN if v < 0 else NEUTRAL


# ----------------------------- HTML snippets -----------------------------
def html_block(s: str):
    st.markdown(s, unsafe_allow_html=True)


def section(title: str, subtitle: str = "", eyebrow: str = ""):
    eb = f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""
    sub = f'<div class="sec-sub">{subtitle}</div>' if subtitle else ""
    html_block(f'<div class="sec">{eb}<div class="sec-title">{title}</div>{sub}</div>')


def sparkline_svg(values: list[float], color: str, width: int = 160, height: int = 44) -> str:
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    step = width / (len(vals) - 1)
    pts = [(i * step, height - 3 - (v - lo) / rng * (height - 6)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"M0,{height} L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" L{width},{height} Z"
    gid = f"g{uuid4().hex[:8]}"
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none" height="{height}">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0.35"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
        f'<path d="{area}" fill="url(#{gid})"/>'
        f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="1.8" '
        f'vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>'
    )


def signal_badge(signal: str, confidence: float | None = None) -> str:
    c = SIGNAL_COLORS.get(signal, NEUTRAL)
    conf = f" · {confidence:.0f}%" if confidence is not None else ""
    return f'<span class="badge" style="color:{c};background:{c}1f;border-color:{c}66">{esc(signal)}{conf}</span>'


def card(label: str, value: str, sub: str = "", extra: str = "", style: str = "", value_cls: str = "") -> str:
    return (
        f'<div class="card" style="{style}"><div class="k">{label}</div>'
        f'<div class="v {value_cls}">{value}</div><div class="s">{sub}</div>{extra}</div>'
    )


def cards_grid(items: list[str], min_width: int = 190):
    html_block(f'<div class="cards" style="grid-template-columns:repeat(auto-fit,minmax({min_width}px,1fr))">{"".join(items)}</div>')


def signal_card(data: dict) -> str:
    color = SIGNAL_COLORS.get(data["signal"], NEUTRAL)
    conf = max(0.0, min(100.0, float(data["confidence"])))
    return card(
        "Signal",
        f'<span style="color:{color}">{esc(data["signal"])}</span>',
        f"Confidence {conf:.1f}%",
        extra=f'<div class="bar"><span style="width:{conf}%;background:{color}"></span></div>',
        style=f"border-color:{color}55;background:linear-gradient(135deg,{color}22,#ffffff 70%)",
    )


def rsi_card(rsi: float) -> str:
    label = "Oversold" if rsi < 30 else "Overbought" if rsi > 70 else "Neutral zone"
    return card(
        "RSI (14)", f"{rsi:.2f}", label,
        extra=f'<div class="rsi-track"><div class="m" style="left:{max(0, min(100, rsi))}%"></div></div>',
    )


# ----------------------------- Plotly -----------------------------
PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}


def style_fig(fig: go.Figure, height: int = 420, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=36 if legend else 12, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#475569", size=12),
        showlegend=legend,
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#ffffff", bordercolor="#e2e8f0", font=dict(color="#0f172a")),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, side="right")
    return fig


def show_fig(fig: go.Figure, key: str):
    st.plotly_chart(fig, use_container_width=True, key=key, config=PLOTLY_CONFIG)


# ----------------------------- CSS -----------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"], .stMarkdown, .stButton button, input, textarea, [data-baseweb="tab"] {
  font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
}
.stApp {
  background:
    radial-gradient(1100px 560px at 8% -12%, rgba(109,74,255,0.10), transparent 60%),
    radial-gradient(900px 500px at 100% 0%, rgba(8,145,178,0.07), transparent 60%),
    #f6f7fb;
  color: #0f172a;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"], #MainMenu, footer { display: none !important; }
.block-container { padding-top: 1.2rem; padding-bottom: 6rem; max-width: 1280px; }

/* ---------- Navbar ---------- */
.nav-brand { display:flex; align-items:center; gap:10px; padding-top:2px; }
.brand-logo {
  width:38px; height:38px; border-radius:11px; display:grid; place-items:center; font-size:19px;
  background: linear-gradient(135deg, #7c5cff, #22d3ee); box-shadow: 0 6px 18px rgba(109,74,255,.25);
}
.brand-name { font-weight:900; font-size:1.2rem; letter-spacing:-0.03em; color:#0f172a; line-height:1.1; }
.brand-sub { font-size:.68rem; color:#64748b; }
div[data-testid="stRadio"] div[role="radiogroup"] {
  gap: 4px; flex-wrap: wrap; justify-content: flex-end;
  background: #ffffff; border:1px solid #e6e8f0; box-shadow: 0 1px 2px rgba(16,24,40,.04);
  padding: 5px; border-radius: 14px; width: fit-content; margin-left: auto;
}
div[data-testid="stRadio"] label[data-baseweb="radio"] {
  margin: 0; padding: 7px 14px; border-radius: 10px; cursor: pointer; transition: all .15s ease;
}
div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child { display: none; }
div[data-testid="stRadio"] label[data-baseweb="radio"] p { font-weight:600; font-size:.88rem; color:#64748b; }
div[data-testid="stRadio"] label[data-baseweb="radio"]:hover { background: #f1f0ff; }
div[data-testid="stRadio"] label[data-baseweb="radio"]:hover p { color:#0f172a; }
div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
  background: linear-gradient(135deg, #6d4aff, #4f7bff); box-shadow: 0 4px 12px rgba(109,74,255,.28);
}
div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p { color:#fff; }
.nav-sep { height:1px; background: linear-gradient(90deg, transparent, #e2e8f0, transparent); margin: .6rem 0 1.4rem; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e6e8f0; }
.side-label {
  font-size:.68rem; font-weight:700; letter-spacing:.09em; text-transform:uppercase;
  color:#64748b; margin: 1.1rem 0 .45rem 0;
}
.status { display:flex; align-items:center; gap:8px; font-size:.8rem; color:#475569; }
.status .dot { width:8px; height:8px; border-radius:50%; }

/* ---------- Buttons & inputs ---------- */
.stButton > button, .stFormSubmitButton > button {
  border-radius: 10px; border: 1px solid #e2e8f0; background: #ffffff; color: #1e293b;
  font-weight: 600; transition: all .15s ease; box-shadow: 0 1px 2px rgba(16,24,40,.04);
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: #6d4aff; color: #6d4aff; background: #f5f3ff; transform: translateY(-1px);
}
.stButton > button:focus:not(:active) { border-color:#6d4aff; color:#6d4aff; box-shadow:none; }
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"] {
  background: linear-gradient(135deg, #6d4aff, #4f7bff); border: none; color: #fff;
  box-shadow: 0 6px 16px rgba(109,74,255,.28);
}
.stButton > button[kind="primary"]:hover { filter: brightness(1.07); color:#fff; }
.stButton > button[kind="primary"]:focus:not(:active) { color:#fff; }
[data-testid="stTextInput"] input { border-radius: 10px; }
[data-testid="stTextInput"] > div > div, [data-baseweb="select"] > div {
  background:#ffffff !important; border-color:#e2e8f0 !important;
}

/* ---------- Hero ---------- */
.hero {
  position:relative; overflow:hidden; padding: 44px 44px 36px; border-radius: 24px; margin-bottom: 1rem;
  background: linear-gradient(135deg, #efeaff 0%, #eef6ff 55%, #e8fbff 100%);
  border: 1px solid #e3defc; box-shadow: 0 10px 30px rgba(109,74,255,0.08);
}
.hero::after {
  content:""; position:absolute; right:-80px; top:-80px; width:320px; height:320px; border-radius:50%;
  background: radial-gradient(circle, rgba(109,74,255,.18), transparent 70%); filter: blur(10px);
}
.hero h1 {
  font-size: 2.9rem; font-weight: 900; letter-spacing: -0.04em; line-height:1.05; margin: 0 0 14px; padding: 0;
  background: linear-gradient(90deg, #0f172a 25%, #6d28d9 62%, #0891b2);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; max-width: 820px;
}
.hero p { color:#475569; margin:0; font-size:1.08rem; max-width: 680px; line-height:1.6; }
.pills { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; }
.pill {
  display:inline-flex; align-items:center; gap:6px; font-size:.74rem; font-weight:600;
  padding:4px 11px; border-radius:999px; border:1px solid #e2e8f0; background:#ffffff; color:#334155;
}
.pill .dot { width:7px; height:7px; border-radius:50%; }
.stats-strip { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr)); gap: 12px; margin: 26px 0 0; }
.stat .n { font-size:1.6rem; font-weight:800; color:#0f172a; letter-spacing:-0.02em; }
.stat .l { font-size:.8rem; color:#64748b; }

/* ---------- Sections ---------- */
.sec { margin: 2.2rem 0 1rem; }
.eyebrow { font-size:.72rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; color:#6d4aff; margin-bottom:4px; }
.sec-title { font-size:1.45rem; font-weight:800; color:#0f172a; letter-spacing:-0.02em; }
.sec-sub { color:#64748b; font-size:.92rem; margin-top:4px; }

/* ---------- Cards ---------- */
.cards { display:grid; gap:14px; margin-bottom: 1rem; }
.card {
  background: #ffffff; border:1px solid #e6e8f0; border-radius:16px; padding:16px 18px;
  box-shadow: 0 1px 2px rgba(16,24,40,.04), 0 4px 14px rgba(16,24,40,.04);
  transition: border-color .15s, box-shadow .15s;
}
.card:hover { border-color: #c9bfff; box-shadow: 0 6px 20px rgba(109,74,255,.10); }
.card .k { font-size:.7rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:#64748b; }
.card .v { font-size:1.5rem; font-weight:800; color:#0f172a; margin-top:6px; letter-spacing:-0.02em; }
.card .s { font-size:.8rem; color:#64748b; margin-top:4px; }
.card .spark { width:100%; display:block; margin-top:10px; }
.up { color:#16a34a !important; } .down { color:#dc2626 !important; } .flat { color:#64748b !important; }
.bar { height:6px; border-radius:999px; background: #eef0f5; margin-top:10px; overflow:hidden; }
.bar > span { display:block; height:100%; border-radius:999px; }
.rsi-track {
  position:relative; height:6px; border-radius:999px; margin-top:12px;
  background: linear-gradient(90deg, #16a34a 0%, #16a34a 30%, #cbd5e1 30%, #cbd5e1 70%, #dc2626 70%);
}
.rsi-track .m {
  position:absolute; top:-4px; width:4px; height:14px; border-radius:2px; background:#0f172a;
  box-shadow: 0 0 0 2px #fff; transform: translateX(-50%);
}
.badge {
  display:inline-block; padding:4px 12px; border-radius:999px; border:1px solid; font-weight:800; font-size:.82rem;
  letter-spacing:.02em;
}

.feature { padding: 22px; }
.feature .ic {
  width:42px; height:42px; border-radius:12px; display:grid; place-items:center; font-size:20px; margin-bottom:12px;
  background: #f1edff; border:1px solid #e0d8ff;
}
.feature .t { font-weight:700; color:#0f172a; font-size:1.02rem; }
.feature .d { color:#64748b; font-size:.88rem; margin-top:6px; line-height:1.55; }
.step .num {
  font-size:.8rem; font-weight:800; color:#fff; width:30px; height:30px; border-radius:50%;
  display:grid; place-items:center; background: linear-gradient(135deg,#6d4aff,#0891b2); margin-bottom:12px;
}

/* ---------- Analysis header ---------- */
.an-head { display:flex; justify-content:space-between; align-items:flex-end; flex-wrap:wrap; gap:12px; margin: .3rem 0 1rem; }
.an-ticker { font-size:2.2rem; font-weight:900; letter-spacing:-0.03em; color:#0f172a; line-height:1.05; display:flex; align-items:center; gap:12px; }
.an-meta { color:#64748b; font-size:.85rem; margin-top:6px; }
.an-price { text-align:right; }
.an-price .v { font-size:2.2rem; font-weight:900; color:#0f172a; line-height:1.05; letter-spacing:-0.02em; }
.chg { font-weight:700; font-size:.95rem; }

/* ---------- Reasons ---------- */
.reasons { display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap:10px; }
.reason {
  display:flex; gap:10px; align-items:flex-start; font-size:.9rem; color:#334155; line-height:1.5;
  background: #ffffff; border:1px solid #e6e8f0; border-radius:12px; padding:12px 14px;
}
.reason .i { flex:none; width:22px; height:22px; border-radius:7px; display:grid; place-items:center; font-size:.75rem; font-weight:800; }

/* ---------- Streamlit widgets ---------- */
[data-testid="stPlotlyChart"] {
  background: #ffffff; border:1px solid #e6e8f0; border-radius:16px; padding: 8px 8px 0 8px;
  box-shadow: 0 1px 2px rgba(16,24,40,.04), 0 4px 14px rgba(16,24,40,.04);
}
[data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid #e2e8f0; }
button[data-baseweb="tab"] { border-radius: 10px 10px 0 0; padding: 8px 14px; }
button[data-baseweb="tab"] p { font-weight:600; }
[data-baseweb="tab-highlight"] { background: #6d4aff; }
[data-testid="stChatMessage"] {
  background: #ffffff; border:1px solid #e6e8f0; border-radius:16px; padding: 14px 16px;
  box-shadow: 0 1px 2px rgba(16,24,40,.04);
}
[data-testid="stChatInput"] {
  border-radius:14px !important; border:1px solid #c9bfff !important; box-shadow: 0 0 0 4px rgba(109,74,255,0.06);
}
[data-testid="stBottom"] > div { background: transparent; }
[data-testid="stExpander"] details { border-radius:14px; border:1px solid #e6e8f0; background: #ffffff; }
[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; border:1px solid #e6e8f0; background:#fff; }

.footer { margin-top: 3rem; padding-top: 1.4rem; border-top:1px solid #e2e8f0; color:#64748b; font-size:.8rem; line-height:1.6; }
.callout {
  border-radius:14px; padding:14px 16px; font-size:.88rem; color:#78350f; line-height:1.55;
  background: #fffbeb; border:1px solid #fde68a;
}

@media (max-width: 768px) {
  .hero { padding: 28px 22px; }
  .hero h1 { font-size: 2rem; }
  div[data-testid="stRadio"] div[role="radiogroup"] { justify-content: flex-start; margin-left: 0; }
}
</style>
"""


def inject_css():
    html_block(CSS)
