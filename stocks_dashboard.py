import streamlit as st
import requests
import pandas as pd
import yfinance as yf
import numpy as np
import time
import warnings
import logging
from datetime import datetime, timedelta
import pytz

warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="📈 Trading Picks",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────
#  STYLE
# ─────────────────────────────────────────────
st.markdown("""
<style>
body, .stApp { background:#0a0e1a; color:#e0e6f0; }
.main-title {
    text-align:center;
    font-size:2.2rem;
    font-weight:800;
    background:linear-gradient(90deg,#00d2ff,#7b2ff7);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
    margin-bottom:0;
}
.sub-title {
    text-align:center;
    color:#8899bb;
    font-size:0.9rem;
    margin-bottom:1.5rem;
}
.section-intraday {
    background:linear-gradient(135deg,#0d1f0d,#0a1a0a);
    border:1px solid #26de81;
    border-radius:12px;
    padding:16px 20px;
    margin-bottom:8px;
}
.section-swing {
    background:linear-gradient(135deg,#0d0d2a,#0a0a1f);
    border:1px solid #7b2ff7;
    border-radius:12px;
    padding:16px 20px;
    margin-bottom:8px;
}
.section-title-intraday {
    color:#26de81;
    font-size:1.2rem;
    font-weight:700;
    margin:0 0 4px 0;
}
.section-title-swing {
    color:#a78bfa;
    font-size:1.2rem;
    font-weight:700;
    margin:0 0 4px 0;
}
.score-badge {
    display:inline-block;
    padding:2px 10px;
    border-radius:20px;
    font-size:0.78rem;
    font-weight:700;
    margin-left:8px;
}
.score-high  { background:#1a3d1a; color:#26de81; }
.score-med   { background:#2a2a0a; color:#f9ca24; }
.market-open  { background:#0d2a0d; border:1px solid #26de81; border-radius:8px; padding:6px 14px; color:#26de81; font-weight:700; display:inline-block; }
.market-closed{ background:#2a0d0d; border:1px solid #ff4757; border-radius:8px; padding:6px 14px; color:#ff4757; font-weight:700; display:inline-block; }
.disclaimer { background:#0d1020; border:1px solid #2a3a5a; border-radius:8px; padding:10px 16px; color:#667; font-size:0.75rem; text-align:center; margin-top:16px; }
div[data-testid="stDataFrame"] { border-radius:8px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────
NSE_SYMBOLS = [
    "RELIANCE","TCS","HDFCBANK","BHARTIARTL","ICICIBANK","INFY",
    "HINDUNILVR","ITC","SBIN","BAJFINANCE","KOTAKBANK","LT",
    "HCLTECH","ASIANPAINT","AXISBANK","MARUTI","WIPRO","ULTRACEMCO",
    "ADANIENT","SUNPHARMA","ONGC","POWERGRID","NTPC","TATAMOTORS",
    "TITAN","BAJAJFINSV","TATASTEEL","ADANIPORTS","COALINDIA","M&M",
    "JSWSTEEL","GRASIM","DRREDDY","HINDALCO","INDUSINDBK","SBILIFE",
    "HDFCLIFE","BRITANNIA","CIPLA","TATACONSUM","APOLLOHOSP","TECHM",
    "DIVISLAB","HEROMOTOCO","BAJAJ-AUTO","EICHERMOT","SHRIRAMFIN","BEL",
    "TRENT","SIEMENS","HAVELLS","PIDILITIND","GODREJCP","TORNTPHARM",
    "MUTHOOTFIN","CHOLAFIN","DABUR","LUPIN","SRF","DMART","BANKBARODA",
    "INDHOTEL","ZOMATO","PNB","IOC","BPCL","GAIL","VEDL","NMDC",
    "ASHOKLEY","AUROPHARMA","MRF","POLYCAB","DIXON","PERSISTENT","MPHASIS",
    "COFORGE","OFSS","IRCTC","HAL","BHEL","RVNL","PFC","RECLTD","IRFC",
    "MOTHERSON","ALKEM","BOSCHLTD","VOLTAS","TATAPOWER","ADANIGREEN",
    "LTIM","NAUKRI","ZYDUSLIFE","IDFCFIRSTB","FEDERALBNK","BANDHANBNK",
    "SAIL","NATIONALUM","HINDCOPPER","DLF","GODREJPROP","JUBLFOOD",
    "TATACOMM","KPITTECH","TATAELXSI","CYIENT","LTTS","ZENSAR","CUMMINSIND",
]

IST = pytz.timezone("Asia/Kolkata")

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def market_open():
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    t = now.time()
    return time(9,15) <= t <= time(15,30)

from datetime import time as dtime

def ist_now():
    return datetime.now(IST).strftime("%d %b %Y %H:%M:%S IST")

# ─────────────────────────────────────────────
#  DATA FETCH
# ─────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def fetch_stock_data():
    """
    Fetch 1 year of daily data for all symbols.
    Computes: RSI, EMA9, EMA21, EMA200, VWAP approx, volume ratio.
    """
    rows = []
    syms_ns = [s + ".NS" for s in NSE_SYMBOLS]

    # Download in 2 batches
    mid = len(syms_ns) // 2
    for chunk in [syms_ns[:mid], syms_ns[mid:]]:
        try:
            data = yf.download(
                chunk, period="1y", interval="1d",
                group_by="ticker", auto_adjust=True,
                progress=False, threads=True, timeout=30
            )
            for sym_ns in chunk:
                sym = sym_ns.replace(".NS","")
                try:
                    df = data[sym_ns] if len(chunk) > 1 else data
                    df = df.dropna(subset=["Close"])
                    if len(df) < 30:
                        continue

                    close  = df["Close"]
                    high   = df["High"]
                    low    = df["Low"]
                    volume = df["Volume"]

                    ltp    = float(close.iloc[-1])
                    prev   = float(close.iloc[-2])
                    open_  = float(df["Open"].iloc[-1])
                    h52    = float(high.max())
                    l52    = float(low.min())
                    vol    = float(volume.iloc[-1])
                    avg_vol= float(volume.tail(30).mean())

                    if ltp <= 0:
                        continue

                    pchg   = round((ltp - prev) / prev * 100, 2)
                    gap    = round((open_ - prev) / prev * 100, 2)

                    # EMA calculations
                    ema9   = float(close.ewm(span=9,  adjust=False).mean().iloc[-1])
                    ema21  = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
                    ema200 = float(close.ewm(span=200,adjust=False).mean().iloc[-1])

                    # RSI (14)
                    delta  = close.diff()
                    gain   = delta.clip(lower=0).rolling(14).mean()
                    loss   = (-delta.clip(upper=0)).rolling(14).mean()
                    rs     = gain / loss.replace(0, 0.001)
                    rsi    = float(100 - (100 / (1 + rs)).iloc[-1])

                    # Volume ratio
                    vol_ratio = vol / avg_vol if avg_vol > 0 else 1

                    # 52W position
                    from_high = (h52 - ltp) / h52 * 100  # % below 52W high
                    from_low  = (ltp - l52) / l52 * 100  # % above 52W low

                    rows.append({
                        "symbol":    sym,
                        "ltp":       ltp,
                        "prev":      prev,
                        "open":      open_,
                        "pchg":      pchg,
                        "gap":       gap,
                        "h52":       h52,
                        "l52":       l52,
                        "vol":       vol,
                        "avg_vol":   avg_vol,
                        "vol_ratio": vol_ratio,
                        "ema9":      ema9,
                        "ema21":     ema21,
                        "ema200":    ema200,
                        "rsi":       rsi,
                        "from_high": from_high,
                        "from_low":  from_low,
                    })
                except Exception:
                    continue
        except Exception:
            continue

    return rows

# ─────────────────────────────────────────────
#  SCORING ALGORITHMS
# ─────────────────────────────────────────────
def intraday_score(s):
    """
    Intraday algorithm:
    - Gap up + hold (momentum)
    - Volume surge (institutional activity)
    - RSI in momentum zone (50-70)
    - Price above EMA9 and EMA21 (uptrend)
    - Not too extended from 52W high
    """
    score = 0
    reasons = []

    # 1. Gap up (most important for intraday)
    if s["gap"] >= 1.5:
        score += 25
        reasons.append(f"Gap up {s['gap']:+.1f}%")
    elif s["gap"] >= 0.5:
        score += 15
        reasons.append(f"Gap up {s['gap']:+.1f}%")
    elif s["gap"] > 0:
        score += 5

    # 2. Positive change today
    if s["pchg"] >= 2:
        score += 20
        reasons.append(f"Strong +{s['pchg']:.1f}% today")
    elif s["pchg"] >= 0.5:
        score += 12
        reasons.append(f"+{s['pchg']:.1f}% today")

    # 3. Volume surge (institutional buying)
    if s["vol_ratio"] >= 2.5:
        score += 20
        reasons.append(f"Volume {s['vol_ratio']:.1f}x avg 🔥")
    elif s["vol_ratio"] >= 1.5:
        score += 12
        reasons.append(f"Volume {s['vol_ratio']:.1f}x avg")

    # 4. RSI in momentum zone
    if 55 <= s["rsi"] <= 70:
        score += 15
        reasons.append(f"RSI {s['rsi']:.0f} (momentum)")
    elif 50 <= s["rsi"] < 55:
        score += 8

    # 5. Price above both EMAs (uptrend)
    if s["ltp"] > s["ema9"] > s["ema21"]:
        score += 15
        reasons.append("Above EMA9 & EMA21")
    elif s["ltp"] > s["ema21"]:
        score += 7

    # 6. Near 52W high (strength)
    if s["from_high"] <= 3:
        score += 5
        reasons.append("Near 52W High")

    # PENALTY: RSI overbought
    if s["rsi"] > 80:
        score -= 15
        reasons.append("⚠️ RSI overbought")

    # PENALTY: Gap down
    if s["gap"] < -0.5:
        score -= 20

    return score, " | ".join(reasons) if reasons else "Moderate setup"


def swing_score(s):
    """
    Swing trade algorithm (hold 3-7 days):
    - 52W high breakout (William O'Neil method)
    - EMA9 > EMA21 crossover (trend confirmation)
    - RSI not overbought (45-65 ideal)
    - Price above EMA200 (bull market filter)
    - Volume accumulation
    """
    score = 0
    reasons = []

    # 1. Near 52W high breakout (most powerful swing signal)
    if s["from_high"] <= 2:
        score += 30
        reasons.append("52W High Breakout 🚀")
    elif s["from_high"] <= 5:
        score += 22
        reasons.append(f"Near 52W High ({s['from_high']:.1f}% below)")
    elif s["from_high"] <= 10:
        score += 12
        reasons.append(f"Within 10% of 52W High")

    # 2. EMA trend (9 EMA > 21 EMA = uptrend)
    if s["ema9"] > s["ema21"]:
        score += 20
        reasons.append("EMA9 > EMA21 ✅")
    else:
        score -= 10  # Downtrend — avoid for swing

    # 3. RSI ideal zone
    if 50 <= s["rsi"] <= 65:
        score += 20
        reasons.append(f"RSI {s['rsi']:.0f} (ideal)")
    elif 45 <= s["rsi"] < 50:
        score += 10
        reasons.append(f"RSI {s['rsi']:.0f} (ok)")
    elif s["rsi"] > 75:
        score -= 15
        reasons.append(f"⚠️ RSI {s['rsi']:.0f} overbought")

    # 4. Price above EMA200 (bull market)
    if s["ltp"] > s["ema200"]:
        score += 15
        reasons.append("Above 200 EMA (bull)")
    else:
        score -= 10

    # 5. Volume accumulation
    if s["vol_ratio"] >= 1.5:
        score += 15
        reasons.append(f"Volume {s['vol_ratio']:.1f}x avg")
    elif s["vol_ratio"] >= 1.2:
        score += 8

    # PENALTY: Too far below 52W high (weak stock)
    if s["from_high"] > 30:
        score -= 20

    return score, " | ".join(reasons) if reasons else "Moderate setup"


def compute_targets(ltp, trade_type):
    """Compute entry, targets and stop loss."""
    if trade_type == "intraday":
        sl     = round(ltp * 0.992, 2)   # 0.8% stop loss
        t1     = round(ltp * 1.012, 2)   # 1.2% target 1
        t2     = round(ltp * 1.022, 2)   # 2.2% target 2
        rr     = round((t1 - ltp) / (ltp - sl), 1) if ltp > sl else 0
    else:  # swing
        sl     = round(ltp * 0.97, 2)    # 3% stop loss
        t1     = round(ltp * 1.05, 2)    # 5% target 1
        t2     = round(ltp * 1.10, 2)    # 10% target 2
        rr     = round((t1 - ltp) / (ltp - sl), 1) if ltp > sl else 0
    return sl, t1, t2, rr


def get_picks(stocks):
    """Score all stocks and return top intraday + swing picks."""
    intraday_picks = []
    swing_picks    = []

    for s in stocks:
        i_score, i_reason = intraday_score(s)
        sw_score, sw_reason = swing_score(s)

        ltp = s["ltp"]
        sl_i, t1_i, t2_i, rr_i    = compute_targets(ltp, "intraday")
        sl_s, t1_s, t2_s, rr_s    = compute_targets(ltp, "swing")

        if i_score >= 55:
            intraday_picks.append({
                "Symbol":    s["symbol"],
                "LTP":       f"₹{ltp:,.2f}",
                "Change%":   f"{s['pchg']:+.2f}%",
                "Score":     i_score,
                "Entry":     f"₹{ltp:,.2f}",
                "Target 1":  f"₹{t1_i:,.2f}",
                "Target 2":  f"₹{t2_i:,.2f}",
                "Stop Loss": f"₹{sl_i:,.2f}",
                "R:R":       f"1:{rr_i}",
                "RSI":       f"{s['rsi']:.0f}",
                "Vol Ratio": f"{s['vol_ratio']:.1f}x",
                "Why":       i_reason,
                "_score":    i_score,
            })

        if sw_score >= 60:
            swing_picks.append({
                "Symbol":    s["symbol"],
                "LTP":       f"₹{ltp:,.2f}",
                "Change%":   f"{s['pchg']:+.2f}%",
                "Score":     sw_score,
                "Entry":     f"₹{ltp:,.2f}",
                "Target 1":  f"₹{t1_s:,.2f}",
                "Target 2":  f"₹{t2_s:,.2f}",
                "Stop Loss": f"₹{sl_s:,.2f}",
                "R:R":       f"1:{rr_s}",
                "RSI":       f"{s['rsi']:.0f}",
                "EMA Trend": "✅ Up" if s["ema9"] > s["ema21"] else "❌ Down",
                "Why":       sw_reason,
                "_score":    sw_score,
            })

    # Sort by score descending
    intraday_picks.sort(key=lambda x: x["_score"], reverse=True)
    swing_picks.sort(key=lambda x: x["_score"], reverse=True)

    # Remove internal score column
    for p in intraday_picks: del p["_score"]
    for p in swing_picks:    del p["_score"]

    return intraday_picks[:10], swing_picks[:10]

# ─────────────────────────────────────────────
#  MAIN UI
# ─────────────────────────────────────────────

# Header
st.markdown('<p class="main-title">📈 Trading Picks</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Intraday & Swing Trade Signals — Powered by Momentum + Breakout + EMA Algorithms</p>',
            unsafe_allow_html=True)

# Market status + time
ist_time = datetime.now(IST)
is_open  = market_open()
col1, col2, col3 = st.columns([2,2,2])
with col1:
    if is_open:
        st.markdown('<span class="market-open">🟢 MARKET OPEN</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="market-closed">🔴 MARKET CLOSED</span>', unsafe_allow_html=True)
with col2:
    st.markdown(f"🕐 **{ist_time.strftime('%d %b %Y %H:%M:%S IST')}**")
with col3:
    if st.button("🔄 Refresh Picks", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# Fetch data
with st.spinner("⏳ Fetching live data and computing signals... (~20 seconds first time)"):
    stocks = fetch_stock_data()

if not stocks:
    st.error("❌ Unable to fetch data. Check internet connection and try again.")
    st.stop()

intraday_picks, swing_picks = get_picks(stocks)

st.success(f"✅ Analysed {len(stocks)} NSE stocks | "
           f"Found {len(intraday_picks)} intraday + {len(swing_picks)} swing picks")

st.markdown("---")

# ── INTRADAY SECTION ──────────────────────────────────────────────────────────
st.markdown("""
<div class="section-intraday">
<p class="section-title-intraday">⚡ INTRADAY PICKS — Buy Today, Sell Today</p>
<span style="color:#8899bb;font-size:0.82rem;">
Algorithm: Gap Up + Volume Surge + RSI Momentum + EMA Uptrend &nbsp;|&nbsp;
Stop Loss: 0.8% &nbsp;|&nbsp; Target: 1.2% - 2.2% &nbsp;|&nbsp; Exit before 3:20 PM
</span>
</div>
""", unsafe_allow_html=True)

if intraday_picks:
    df_i = pd.DataFrame(intraday_picks)
    st.dataframe(
        df_i,
        use_container_width=True,
        height=min(400, 60 + len(df_i)*38),
        hide_index=True,
        column_config={
            "Score":    st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            "Why":      st.column_config.TextColumn("Why", width="large"),
            "Change%":  st.column_config.TextColumn("Change%", width="small"),
        }
    )
    st.markdown("""
    <div style="background:#0d1a0d;border-radius:6px;padding:8px 14px;font-size:0.78rem;color:#667;margin-top:4px;">
    ⚠️ <b>Intraday rules:</b> Buy after 9:30 AM when price holds above yesterday's close.
    Strictly exit before 3:20 PM. Always use stop loss. Never average down intraday.
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("No strong intraday picks right now. Market may be closed or low momentum. Refresh after 9:30 AM.")

st.markdown("<br>", unsafe_allow_html=True)

# ── SWING SECTION ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="section-swing">
<p class="section-title-swing">🌙 SWING TRADE PICKS — Hold 3 to 7 Days</p>
<span style="color:#8899bb;font-size:0.82rem;">
Algorithm: 52W High Breakout + EMA9/21 Crossover + RSI Zone + Volume Accumulation + 200 EMA Bull Filter &nbsp;|&nbsp;
Stop Loss: 3% &nbsp;|&nbsp; Target: 5% - 10%
</span>
</div>
""", unsafe_allow_html=True)

if swing_picks:
    df_s = pd.DataFrame(swing_picks)
    st.dataframe(
        df_s,
        use_container_width=True,
        height=min(400, 60 + len(df_s)*38),
        hide_index=True,
        column_config={
            "Score":     st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            "Why":       st.column_config.TextColumn("Why", width="large"),
            "EMA Trend": st.column_config.TextColumn("EMA Trend", width="small"),
        }
    )
    st.markdown("""
    <div style="background:#0d0d1a;border-radius:6px;padding:8px 14px;font-size:0.78rem;color:#667;margin-top:4px;">
    ⚠️ <b>Swing rules:</b> Buy at end of day or next morning dip.
    Hold 3-7 days. Exit at Target 1 (book 50%) and let rest run to Target 2.
    Exit immediately if Stop Loss is hit — no emotions.
    </div>
    """, unsafe_allow_html=True)
else:
    st.info("No strong swing setups right now. Market may be in correction. Check after market opens.")

# ── DISCLAIMER ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="disclaimer">
⚠️ <b>Not SEBI Investment Advice.</b> For educational purposes only.
Always do your own research. Past performance does not guarantee future results.
Use strict stop losses. Never invest more than you can afford to lose.
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  MY TRADES TRACKER — Exit Signal Engine
# ─────────────────────────────────────────────

import json, os

TRADES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "my_trades.json")

def load_trades():
    try:
        if os.path.exists(TRADES_FILE):
            with open(TRADES_FILE,"r") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_trades(trades):
    try:
        with open(TRADES_FILE,"w") as f:
            json.dump(trades, f, indent=2)
    except Exception:
        pass

def get_exit_signal(symbol, buy_price, stop_loss, target1, target2, stocks_dict):
    """
    Check current conditions and tell user:
    HOLD / WATCH / EXIT NOW / TAKE PROFIT
    """
    s = stocks_dict.get(symbol)
    if not s:
        return "❓ NO DATA", "Cannot fetch current data", "#666"

    ltp      = s["ltp"]
    pnl_pct  = round((ltp - buy_price) / buy_price * 100, 2)
    ema9     = s["ema9"]
    ema21    = s["ema21"]
    rsi      = s["rsi"]

    reasons = []
    status  = "HOLD"
    color   = "#26de81"

    # ── EXIT CONDITIONS (highest priority) ───────────────
    if ltp <= stop_loss:
        return "🔴 EXIT NOW", f"STOP LOSS HIT! Price ₹{ltp:,.2f} ≤ SL ₹{stop_loss:,.2f} | Loss: {pnl_pct:.1f}% — Exit immediately, no emotions!", "#ff4757"

    if ema9 < ema21:
        reasons.append(f"EMA9 crossed below EMA21 — trend reversed")
        status = "EXIT"
        color  = "#ff4757"

    if rsi > 80:
        reasons.append(f"RSI {rsi:.0f} — extremely overbought")
        status = "EXIT"
        color  = "#ff4757"

    if pnl_pct < -2.5:
        reasons.append(f"Down {pnl_pct:.1f}% — approaching stop loss")
        status = "EXIT"
        color  = "#ff4757"

    # ── PROFIT CONDITIONS ─────────────────────────────────
    if ltp >= target2:
        return "💰 EXIT FULL", f"TARGET 2 HIT! +{pnl_pct:.1f}% profit — Sell all quantity now!", "#f9ca24"

    if ltp >= target1:
        return "💰 PARTIAL EXIT", f"TARGET 1 HIT! +{pnl_pct:.1f}% — Sell 50% now, keep 50% for Target 2 (₹{target2:,.2f})", "#f9ca24"

    # ── WATCH CONDITIONS ──────────────────────────────────
    if status != "EXIT":
        if rsi > 72:
            reasons.append(f"RSI {rsi:.0f} getting high — watch closely")
            status = "WATCH"
            color  = "#f7b731"
        elif pnl_pct < -1.5:
            reasons.append(f"Down {pnl_pct:.1f}% — monitor stop loss")
            status = "WATCH"
            color  = "#f7b731"

    # ── HOLD ─────────────────────────────────────────────
    if status == "HOLD":
        if pnl_pct > 0:
            reasons.append(f"Profit +{pnl_pct:.1f}% | EMA trend up | RSI {rsi:.0f} — all good")
        else:
            reasons.append(f"P&L {pnl_pct:.1f}% | Above SL | Trend intact — hold")

    if status == "EXIT":
        label = "🔴 EXIT NOW"
    elif status == "WATCH":
        label = "🟡 WATCH"
    else:
        label = "🟢 HOLD"

    return label, " | ".join(reasons), color


st.markdown("---")
st.markdown("## 📒 My Trades — Exit Signal Tracker")
st.markdown("""
<div style="background:#0d1020;border:1px solid #2a3a5a;border-radius:8px;
padding:12px 16px;font-size:0.83rem;color:#8899bb;margin-bottom:12px">
<b>How to use:</b> Add your open swing trades below. The app will tell you
<b>HOLD / WATCH / EXIT NOW</b> based on current price, EMA trend, RSI and your targets.
You never need to guess — just follow the signal.
</div>
""", unsafe_allow_html=True)

# Build stocks dict for quick lookup
stocks_dict = {s["symbol"]: s for s in stocks}

trades = load_trades()

# ── ADD NEW TRADE ─────────────────────────────────────────
with st.expander("➕ Add New Trade", expanded=len(trades)==0):
    c1,c2,c3 = st.columns(3)
    with c1:
        new_sym  = st.text_input("Symbol (e.g. RELIANCE)", placeholder="RELIANCE").upper().strip()
        new_qty  = st.number_input("Quantity", min_value=1, value=10, step=1)
    with c2:
        new_buy  = st.number_input("Buy Price ₹", min_value=1.0, value=100.0, step=0.5)
        new_sl   = st.number_input("Stop Loss ₹", min_value=1.0, value=97.0, step=0.5)
    with c3:
        new_t1   = st.number_input("Target 1 ₹", min_value=1.0, value=105.0, step=0.5)
        new_t2   = st.number_input("Target 2 ₹", min_value=1.0, value=110.0, step=0.5)
        new_date = st.date_input("Buy Date", value=datetime.now(IST).date())

    if st.button("✅ Add Trade", type="primary", use_container_width=True):
        if new_sym:
            trades.append({
                "symbol":    new_sym,
                "qty":       int(new_qty),
                "buy_price": float(new_buy),
                "stop_loss": float(new_sl),
                "target1":   float(new_t1),
                "target2":   float(new_t2),
                "buy_date":  str(new_date),
            })
            save_trades(trades)
            st.success(f"✅ {new_sym} trade added!")
            st.rerun()

# ── SHOW OPEN TRADES ─────────────────────────────────────
if trades:
    st.markdown(f"**{len(trades)} Open Trade(s):**")
    
    for i, t in enumerate(trades):
        sym       = t["symbol"]
        buy_price = t["buy_price"]
        buy_date  = t["buy_date"]
        qty       = t["qty"]
        sl        = t["stop_loss"]
        t1        = t["target1"]
        t2        = t["target2"]

        # Days held
        try:
            bd = datetime.strptime(buy_date, "%Y-%m-%d").date()
            days_held = (datetime.now(IST).date() - bd).days
        except Exception:
            days_held = 0

        # Get exit signal
        s_data    = stocks_dict.get(sym)
        ltp       = s_data["ltp"] if s_data else buy_price
        pnl_amt   = round((ltp - buy_price) * qty, 2)
        pnl_pct   = round((ltp - buy_price) / buy_price * 100, 2)
        signal, reason, sig_color = get_exit_signal(sym, buy_price, sl, t1, t2, stocks_dict)

        # Card
        border_color = sig_color
        st.markdown(f"""
        <div style="background:#0d1020;border:2px solid {border_color};
        border-radius:10px;padding:14px 18px;margin-bottom:10px">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap">
                <span style="font-size:1.2rem;font-weight:800;color:#e0e6f0">{sym}</span>
                <span style="font-size:1.1rem;font-weight:800;color:{sig_color}">{signal}</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:10px 0;font-size:0.82rem">
                <div><span style="color:#667">Buy Price</span><br><b>₹{buy_price:,.2f}</b></div>
                <div><span style="color:#667">Current</span><br><b>₹{ltp:,.2f}</b></div>
                <div><span style="color:#667">P&L</span><br>
                    <b style="color:{'#26de81' if pnl_pct>=0 else '#ff4757'}">
                    {'+'if pnl_pct>=0 else ''}{pnl_pct:.2f}% (₹{pnl_amt:+,.0f})
                    </b>
                </div>
                <div><span style="color:#667">Days Held</span><br><b>Day {days_held+1}</b></div>
                <div><span style="color:#667">Stop Loss</span><br><b style="color:#ff4757">₹{sl:,.2f}</b></div>
                <div><span style="color:#667">Target 1</span><br><b style="color:#f9ca24">₹{t1:,.2f}</b></div>
                <div><span style="color:#667">Target 2</span><br><b style="color:#26de81">₹{t2:,.2f}</b></div>
                <div><span style="color:#667">Qty</span><br><b>{qty} shares</b></div>
            </div>
            <div style="background:#0a0e1a;border-radius:6px;padding:6px 10px;
            font-size:0.8rem;color:{sig_color}">
                💡 {reason}
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_del, col_close = st.columns([1,4])
        with col_del:
            if st.button(f"🗑️ Remove", key=f"del_{i}"):
                trades.pop(i)
                save_trades(trades)
                st.rerun()
        with col_close:
            if st.button(f"✅ Mark Closed (P&L: ₹{pnl_amt:+,.0f})", key=f"close_{i}"):
                trades.pop(i)
                save_trades(trades)
                st.success(f"Trade closed! P&L: ₹{pnl_amt:+,.0f}")
                st.rerun()

else:
    st.info("No open trades yet. Add a trade above to track exit signals.")
