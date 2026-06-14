import streamlit as st
import requests
import pandas as pd
import yfinance as yf
import numpy as np
import time
import warnings
import logging
import json
import os
from datetime import datetime, timedelta, time as dtime
import pytz

warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# ═══════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="📈 Trading Picks",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ═══════════════════════════════════════════════════════════════
#  STYLE
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<style>
body, .stApp { background:#0a0e1a; color:#e0e6f0; }
.main-title {
    text-align:center; font-size:2.2rem; font-weight:800;
    background:linear-gradient(90deg,#00d2ff,#7b2ff7);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    margin-bottom:0;
}
.sub-title { text-align:center; color:#8899bb; font-size:0.9rem; margin-bottom:1rem; }
.section-box {
    border-radius:12px; padding:14px 18px; margin-bottom:8px;
}
.intraday-box { background:#0d1f0d; border:1.5px solid #26de81; }
.swing-box    { background:#0d0d2a; border:1.5px solid #7b2ff7; }
.tracker-box  { background:#1a1000; border:1.5px solid #f9ca24; }
.watch-box    { background:#0d1a2a; border:1.5px solid #00d2ff; }
.rule-box     { background:#080c18; border:1px solid #1a2a4a; border-radius:8px; padding:10px 14px; margin:6px 0; font-size:0.82rem; color:#8899bb; }
.rule-title   { color:#e0e6f0; font-weight:700; font-size:0.95rem; margin-bottom:4px; }
.sec-title    { font-size:1.15rem; font-weight:800; margin:0 0 3px 0; }
.intraday-col { color:#26de81; }
.swing-col    { color:#a78bfa; }
.tracker-col  { color:#f9ca24; }
.watch-col    { color:#00d2ff; }
.market-open  { background:#0d2a0d; border:1px solid #26de81; border-radius:8px; padding:5px 14px; color:#26de81; font-weight:700; display:inline-block; }
.market-closed{ background:#2a0d0d; border:1px solid #ff4757; border-radius:8px; padding:5px 14px; color:#ff4757; font-weight:700; display:inline-block; }
.disclaimer   { background:#0d1020; border:1px solid #1a2a4a; border-radius:8px; padding:10px 16px; color:#556; font-size:0.74rem; text-align:center; margin-top:16px; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════
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

IST       = pytz.timezone("Asia/Kolkata")
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trading_data.json")

# ═══════════════════════════════════════════════════════════════
#  PERSISTENT STORAGE  (survives refresh + app restart)
# ═══════════════════════════════════════════════════════════════
def load_data():
    """Load trades + watchlist from local file. Never lost on refresh."""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE,"r") as f:
                d = json.load(f)
            return d.get("trades",[]), d.get("watchlist",[]), d.get("closed",[])
    except Exception:
        pass
    return [], [], []

def save_data(trades, watchlist, closed):
    """Save trades + watchlist to local file. Persists across restarts."""
    try:
        with open(DATA_FILE,"w") as f:
            json.dump({"trades": trades,
                       "watchlist": watchlist,
                       "closed": closed}, f, indent=2)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════
def market_open():
    now = datetime.now(IST)
    if now.weekday() >= 5: return False
    t = now.time()
    return dtime(9,15) <= t <= dtime(15,30)

def ist_now():
    return datetime.now(IST)

# ═══════════════════════════════════════════════════════════════
#  DATA FETCH  (cached 10 min)
# ═══════════════════════════════════════════════════════════════
@st.cache_data(ttl=600, show_spinner=False)
def fetch_stock_data():
    rows    = []
    syms_ns = [s+".NS" for s in NSE_SYMBOLS]
    mid     = len(syms_ns)//2
    for chunk in [syms_ns[:mid], syms_ns[mid:]]:
        try:
            data = yf.download(chunk, period="1y", interval="1d",
                               group_by="ticker", auto_adjust=True,
                               progress=False, threads=True, timeout=30)
            for sym_ns in chunk:
                sym = sym_ns.replace(".NS","")
                try:
                    df  = data[sym_ns] if len(chunk)>1 else data
                    df  = df.dropna(subset=["Close"])
                    if len(df) < 30: continue
                    close  = df["Close"]; high=df["High"]
                    low    = df["Low"];   volume=df["Volume"]
                    ltp    = float(close.iloc[-1])
                    prev   = float(close.iloc[-2])
                    open_  = float(df["Open"].iloc[-1])
                    h52    = float(high.max())
                    l52    = float(low.min())
                    vol    = float(volume.iloc[-1])
                    avg_vol= float(volume.tail(30).mean())
                    if ltp<=0: continue
                    pchg   = round((ltp-prev)/prev*100,2)
                    gap    = round((open_-prev)/prev*100,2)
                    ema9   = float(close.ewm(span=9,  adjust=False).mean().iloc[-1])
                    ema21  = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
                    ema200 = float(close.ewm(span=200,adjust=False).mean().iloc[-1])
                    delta  = close.diff()
                    gain   = delta.clip(lower=0).rolling(14).mean()
                    loss   = (-delta.clip(upper=0)).rolling(14).mean()
                    rs     = gain/loss.replace(0,0.001)
                    rsi    = float((100-(100/(1+rs))).iloc[-1])
                    vol_ratio  = vol/avg_vol if avg_vol>0 else 1
                    from_high  = (h52-ltp)/h52*100
                    rows.append({"symbol":sym,"ltp":ltp,"prev":prev,"open":open_,
                                 "pchg":pchg,"gap":gap,"h52":h52,"l52":l52,
                                 "vol":vol,"avg_vol":avg_vol,"vol_ratio":vol_ratio,
                                 "ema9":ema9,"ema21":ema21,"ema200":ema200,
                                 "rsi":rsi,"from_high":from_high})
                except Exception: continue
        except Exception: continue
    return rows

# ═══════════════════════════════════════════════════════════════
#  SCORING ALGORITHMS
# ═══════════════════════════════════════════════════════════════
def intraday_score(s):
    score=0; reasons=[]
    if s["gap"]>=1.5:   score+=25; reasons.append(f"Gap up {s['gap']:+.1f}%")
    elif s["gap"]>=0.5: score+=15; reasons.append(f"Gap up {s['gap']:+.1f}%")
    elif s["gap"]>0:    score+=5
    if s["pchg"]>=2:    score+=20; reasons.append(f"Strong +{s['pchg']:.1f}%")
    elif s["pchg"]>=0.5:score+=12; reasons.append(f"+{s['pchg']:.1f}% today")
    if s["vol_ratio"]>=2.5: score+=20; reasons.append(f"Volume {s['vol_ratio']:.1f}x 🔥")
    elif s["vol_ratio"]>=1.5:score+=12; reasons.append(f"Vol {s['vol_ratio']:.1f}x avg")
    if 55<=s["rsi"]<=70:  score+=15; reasons.append(f"RSI {s['rsi']:.0f} momentum")
    elif 50<=s["rsi"]<55: score+=8
    if s["ltp"]>s["ema9"]>s["ema21"]: score+=15; reasons.append("Above EMA9 & EMA21")
    elif s["ltp"]>s["ema21"]:          score+=7
    if s["from_high"]<=3: score+=5; reasons.append("Near 52W High")
    if s["rsi"]>80:  score-=15; reasons.append("⚠️ RSI overbought")
    if s["gap"]<-0.5:score-=20
    return score, " | ".join(reasons) if reasons else "Moderate setup"

def swing_score(s):
    score=0; reasons=[]
    if s["from_high"]<=2:   score+=30; reasons.append("52W High Breakout 🚀")
    elif s["from_high"]<=5: score+=22; reasons.append(f"Near 52W High ({s['from_high']:.1f}% below)")
    elif s["from_high"]<=10:score+=12; reasons.append("Within 10% of 52W High")
    if s["ema9"]>s["ema21"]:  score+=20; reasons.append("EMA9>EMA21 ✅ Uptrend")
    else:                      score-=10
    if 50<=s["rsi"]<=65:   score+=20; reasons.append(f"RSI {s['rsi']:.0f} ideal zone")
    elif 45<=s["rsi"]<50:  score+=10; reasons.append(f"RSI {s['rsi']:.0f} ok")
    elif s["rsi"]>75:      score-=15; reasons.append(f"⚠️ RSI {s['rsi']:.0f} overbought")
    if s["ltp"]>s["ema200"]:score+=15; reasons.append("Above 200 EMA (bull)")
    else:                   score-=10
    if s["vol_ratio"]>=1.5: score+=15; reasons.append(f"Vol {s['vol_ratio']:.1f}x avg")
    elif s["vol_ratio"]>=1.2:score+=8
    if s["from_high"]>30:  score-=20
    return score, " | ".join(reasons) if reasons else "Moderate setup"

def compute_targets(ltp, trade_type):
    if trade_type=="intraday":
        sl=round(ltp*0.992,2); t1=round(ltp*1.012,2); t2=round(ltp*1.022,2)
    else:
        sl=round(ltp*0.97,2);  t1=round(ltp*1.05,2);  t2=round(ltp*1.10,2)
    rr=round((t1-ltp)/(ltp-sl),1) if ltp>sl else 0
    return sl,t1,t2,rr

def get_picks(stocks):
    ip=[]; sw=[]
    for s in stocks:
        ltp=s["ltp"]
        i_sc,i_why=intraday_score(s)
        sw_sc,sw_why=swing_score(s)
        sl_i,t1_i,t2_i,rr_i=compute_targets(ltp,"intraday")
        sl_s,t1_s,t2_s,rr_s=compute_targets(ltp,"swing")
        if i_sc>=55:
            ip.append({"Symbol":s["symbol"],"LTP":f"₹{ltp:,.2f}",
                "Change%":f"{s['pchg']:+.2f}%","Score":i_sc,
                "Entry":f"₹{ltp:,.2f}","Target 1":f"₹{t1_i:,.2f}",
                "Target 2":f"₹{t2_i:,.2f}","Stop Loss":f"₹{sl_i:,.2f}",
                "R:R":f"1:{rr_i}","RSI":f"{s['rsi']:.0f}",
                "Vol":f"{s['vol_ratio']:.1f}x","Why":i_why,"_s":i_sc})
        if sw_sc>=60:
            sw.append({"Symbol":s["symbol"],"LTP":f"₹{ltp:,.2f}",
                "Change%":f"{s['pchg']:+.2f}%","Score":sw_sc,
                "Entry":f"₹{ltp:,.2f}","Target 1":f"₹{t1_s:,.2f}",
                "Target 2":f"₹{t2_s:,.2f}","Stop Loss":f"₹{sl_s:,.2f}",
                "R:R":f"1:{rr_s}","RSI":f"{s['rsi']:.0f}",
                "EMA":("✅ Up" if s["ema9"]>s["ema21"] else "❌ Down"),
                "Why":sw_why,"_s":sw_sc})
    ip.sort(key=lambda x:x["_s"],reverse=True)
    sw.sort(key=lambda x:x["_s"],reverse=True)
    for p in ip: del p["_s"]
    for p in sw: del p["_s"]
    return ip[:10],sw[:10]

def exit_signal(sym, buy_price, sl, t1, t2, sd):
    s=sd.get(sym)
    if not s: return "❓","Cannot fetch data","#666"
    ltp=s["ltp"]
    pnl=round((ltp-buy_price)/buy_price*100,2)
    reasons=[]
    if ltp<=sl:
        return "🔴 EXIT NOW",f"STOP LOSS HIT! ₹{ltp:,.2f} ≤ ₹{sl:,.2f} | Loss {pnl:.1f}% — Sell immediately!","#ff4757"
    if ltp>=t2:
        return "💰 EXIT FULL",f"TARGET 2 HIT! +{pnl:.1f}% — Sell ALL shares now!","#f9ca24"
    if ltp>=t1:
        return "💰 PARTIAL",f"TARGET 1 HIT! +{pnl:.1f}% — Sell 50% now, hold 50% for T2 ₹{t2:,.2f}","#f9ca24"
    if s["ema9"]<s["ema21"]:
        reasons.append("EMA9 crossed below EMA21 — trend reversed")
        return "🔴 EXIT NOW"," | ".join(reasons),"#ff4757"
    if s["rsi"]>80:
        reasons.append(f"RSI {s['rsi']:.0f} extremely overbought")
        return "🔴 EXIT NOW"," | ".join(reasons),"#ff4757"
    if pnl<-2.5:
        return "🔴 EXIT NOW",f"Down {pnl:.1f}% — near stop loss, exit now","#ff4757"
    if s["rsi"]>72: reasons.append(f"RSI {s['rsi']:.0f} getting high — watch")
    if pnl<-1.5:    reasons.append(f"Down {pnl:.1f}% — monitor SL")
    if reasons:
        return "🟡 WATCH"," | ".join(reasons),"#f7b731"
    msg = f"+{pnl:.1f}% profit | EMA up | RSI {s['rsi']:.0f} — all conditions good" if pnl>=0 else f"{pnl:.1f}% | Above SL | Trend intact — hold"
    return "🟢 HOLD",msg,"#26de81"

# ═══════════════════════════════════════════════════════════════
#  MAIN UI
# ═══════════════════════════════════════════════════════════════
st.markdown('<p class="main-title">📈 Stock Trading Picks</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Intraday · Swing Trading · Exit Signals · Watchlist — All in One Place</p>', unsafe_allow_html=True)

# Top bar
now     = ist_now()
is_open = market_open()
c1,c2,c3 = st.columns([2,3,2])
with c1:
    if is_open:
        st.markdown('<span class="market-open">🟢 MARKET OPEN</span>',   unsafe_allow_html=True)
    else:
        st.markdown('<span class="market-closed">🔴 MARKET CLOSED</span>',unsafe_allow_html=True)
with c2:
    st.markdown(f"🕐 **{now.strftime('%d %b %Y  %H:%M:%S IST')}**")
with c3:
    if st.button("🔄 Refresh All Data", width='stretch', type="primary"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# Fetch data
with st.spinner("⏳ Fetching market data and computing signals... (~20 sec first time, instant after)"):
    stocks = fetch_stock_data()

if not stocks:
    st.error("❌ Cannot fetch data. Check internet and try again.")
    st.stop()

intraday_picks, swing_picks = get_picks(stocks)
stocks_dict = {s["symbol"]:s for s in stocks}
trades, watchlist, closed_trades = load_data()

st.success(f"✅ {len(stocks)} stocks analysed | {len(intraday_picks)} intraday picks | {len(swing_picks)} swing picks | Data cached 10 min")
st.markdown("")

# ═══════════════════════════════════════════════════════════════
#  SECTION 1 — HOW TO USE THIS APP
# ═══════════════════════════════════════════════════════════════
with st.expander("📖 HOW TO USE THIS APP — Read This First (tap to expand)", expanded=False):
    st.markdown("""
    <div class="rule-box">
    <div class="rule-title">🌅 MORNING ROUTINE (Before 9:30 AM)</div>
    1. Open app → click <b>Refresh All Data</b><br>
    2. Check <b>⚡ Intraday Picks</b> section below<br>
    3. Pick <b>1 or 2 stocks</b> with Score > 70 only<br>
    4. Open your broker app (Zerodha/Upstox) → check live price<br>
    5. <b>Buy only after 9:30 AM</b> when price holds above yesterday's close<br>
    6. <b>SET STOP LOSS IMMEDIATELY</b> on broker app after buying
    </div>

    <div class="rule-box">
    <div class="rule-title">☀️ DURING MARKET HOURS (Every 30 Min)</div>
    1. Come back to app → check <b>📒 My Trades</b> section<br>
    2. If signal shows <b style="color:#ff4757">🔴 EXIT NOW</b> → sell immediately, no waiting<br>
    3. If signal shows <b style="color:#f9ca24">💰 TAKE PROFIT</b> → book profit as instructed<br>
    4. If signal shows <b style="color:#26de81">🟢 HOLD</b> → do nothing, wait<br>
    5. <b>Strictly exit all intraday trades before 3:20 PM</b> — no exception
    </div>

    <div class="rule-box">
    <div class="rule-title">🌙 EVENING ROUTINE (After 3:30 PM)</div>
    1. Click <b>Refresh All Data</b><br>
    2. Check <b>🌙 Swing Trade Picks</b> section<br>
    3. Pick <b>1 or 2 stocks</b> with Score > 75 only<br>
    4. <b>Buy next morning</b> at open — do not buy same evening<br>
    5. Add trade to <b>📒 My Trades</b> tracker with stop loss<br>
    6. Hold until app shows EXIT signal — can be Day 1 or Day 7
    </div>

    <div class="rule-box">
    <div class="rule-title">📋 SWING TRADE EXIT RULES (very important)</div>
    ✅ Hold as long as app shows <b style="color:#26de81">🟢 HOLD</b><br>
    ✅ At Target 1 (+5%) → sell 50% quantity, hold 50%<br>
    ✅ At Target 2 (+10%) → sell remaining 50%<br>
    🔴 If app shows <b style="color:#ff4757">EXIT NOW</b> → sell same day, no waiting<br>
    ❌ Never hold swing trade more than 10 days even if profitable
    </div>

    <div class="rule-box">
    <div class="rule-title">🛡️ GOLDEN RULES — Never Break These</div>
    ✅ <b>Always set stop loss</b> on broker app after every buy<br>
    ✅ <b>Never invest more than 10%</b> of capital in one stock<br>
    ✅ <b>Max 2 trades at a time</b> when starting out<br>
    ✅ <b>Only buy stocks from this app's pick list</b> — no tips from friends/WhatsApp<br>
    ❌ Never average down (never buy more if stock falls)<br>
    ❌ Never hold intraday stock overnight<br>
    ❌ Never trade on days when NIFTY is down more than 1%<br>
    ❌ Never invest money you need in next 3 months
    </div>

    <div class="rule-box">
    <div class="rule-title">📊 HOW TO READ THE SCORE</div>
    Score 85-100 → <b>Very strong setup</b> — high confidence<br>
    Score 70-84  → <b>Good setup</b> — take this trade<br>
    Score 55-69  → <b>Moderate</b> — only if market is strong<br>
    Score below 55 → <b>Skip</b> — not shown in picks<br><br>
    R:R means Risk:Reward. <b>Always prefer R:R of 1:2 or higher.</b><br>
    Example: Risk ₹1,000 to make ₹2,000 = R:R of 1:2
    </div>
    """, unsafe_allow_html=True)

st.markdown("")

# ═══════════════════════════════════════════════════════════════
#  SECTION 2 — INTRADAY PICKS
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<div class="section-box intraday-box">
<p class="sec-title intraday-col">⚡ SECTION 1 — INTRADAY PICKS</p>
<span style="color:#8899bb;font-size:0.8rem;">
<b>What this is:</b> Stocks with best chance of going UP today. Buy in morning, sell same day before 3:20 PM.<br>
<b>Algorithm used:</b> Gap Up detection + Volume Surge (2x avg) + RSI Momentum Zone (55–70) + EMA Uptrend<br>
<b>Stop Loss:</b> 0.8% below entry &nbsp;|&nbsp; <b>Target:</b> 1.2% → 2.2% &nbsp;|&nbsp;
<b>⚠️ Rule:</b> Never carry intraday stock to next day. Always exit before 3:20 PM.
</span>
</div>
""", unsafe_allow_html=True)

if intraday_picks:
    df_i = pd.DataFrame(intraday_picks)
    st.dataframe(df_i, width='stretch',
                 height=min(420, 60+len(df_i)*38),
                 hide_index=True,
                 column_config={
                     "Score":   st.column_config.ProgressColumn("Score",min_value=0,max_value=100,format="%d"),
                     "Why":     st.column_config.TextColumn("Why",width="large"),
                     "Change%": st.column_config.TextColumn("Change%",width="small"),
                 })
    st.markdown("""
    <div style="background:#060f06;border-radius:6px;padding:7px 12px;font-size:0.78rem;color:#557755;margin-top:2px">
    💡 <b>How to pick:</b> Choose stocks with Score > 70. Prefer Vol > 1.5x. 
    Buy only after 9:30 AM. Check live price on broker app before buying.
    </div>""", unsafe_allow_html=True)
else:
    st.info("⚡ No strong intraday picks right now. Market may be closed or stocks have low momentum. Refresh after 9:30 AM on a trading day.")

st.markdown("")

# ═══════════════════════════════════════════════════════════════
#  SECTION 3 — SWING TRADE PICKS
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<div class="section-box swing-box">
<p class="sec-title swing-col">🌙 SECTION 2 — SWING TRADE PICKS</p>
<span style="color:#8899bb;font-size:0.8rem;">
<b>What this is:</b> Stocks in strong uptrend — hold for 3 to 7 days for bigger profit.<br>
<b>Algorithm used:</b> 52-Week High Breakout + EMA9/21 Crossover + RSI Zone (50–65) + Price above 200 EMA + Volume Accumulation<br>
<b>Stop Loss:</b> 3% below entry &nbsp;|&nbsp; <b>Target 1:</b> +5% (sell half) &nbsp;|&nbsp; <b>Target 2:</b> +10% (sell rest)<br>
<b>⚠️ Rule:</b> Add to My Trades tracker below after buying. App will tell you exactly when to exit.
</span>
</div>
""", unsafe_allow_html=True)

if swing_picks:
    df_s = pd.DataFrame(swing_picks)
    st.dataframe(df_s, width='stretch',
                 height=min(420, 60+len(df_s)*38),
                 hide_index=True,
                 column_config={
                     "Score": st.column_config.ProgressColumn("Score",min_value=0,max_value=100,format="%d"),
                     "Why":   st.column_config.TextColumn("Why",width="large"),
                     "EMA":   st.column_config.TextColumn("EMA Trend",width="small"),
                 })
    st.markdown("""
    <div style="background:#06060f;border-radius:6px;padding:7px 12px;font-size:0.78rem;color:#665588;margin-top:2px">
    💡 <b>How to pick:</b> Choose stocks with Score > 75 and EMA = ✅ Up. 
    Buy tomorrow morning at open. Immediately add to My Trades tracker below so app tracks exit signal for you.
    </div>""", unsafe_allow_html=True)
else:
    st.info("🌙 No strong swing setups right now. Market may be in correction phase. Check after market opens or on a green market day.")

st.markdown("")

# ═══════════════════════════════════════════════════════════════
#  SECTION 4 — MY TRADES (Exit Signal Tracker)
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<div class="section-box tracker-box">
<p class="sec-title tracker-col">📒 SECTION 3 — MY TRADES (Exit Signal Tracker)</p>
<span style="color:#8899bb;font-size:0.8rem;">
<b>What this is:</b> Add your open trades here. App tells you HOLD / WATCH / EXIT based on current price + EMA + RSI.<br>
<b>How to use:</b> After buying any stock → add it below with buy price and targets. 
Check this section every day to know exactly when to exit.<br>
<b>✅ Your data is saved permanently</b> — never lost when you refresh or restart the app.
</span>
</div>
""", unsafe_allow_html=True)

# Add trade form
with st.expander("➕ Add New Trade (click to open)", expanded=len(trades)==0):
    st.markdown("**Enter the details of a stock you just bought:**")
    c1,c2,c3 = st.columns(3)
    with c1:
        new_sym  = st.text_input("Stock Symbol", placeholder="e.g. RELIANCE").upper().strip()
        new_type = st.selectbox("Trade Type", ["Swing","Intraday"])
        new_qty  = st.number_input("Quantity (shares)", min_value=1, value=10)
    with c2:
        new_buy  = st.number_input("Your Buy Price ₹", min_value=1.0, value=100.0, step=0.5,
                                    help="The price at which you bought")
        new_sl   = st.number_input("Stop Loss ₹", min_value=1.0, value=97.0, step=0.5,
                                    help="Exit immediately if price falls to this")
    with c3:
        new_t1   = st.number_input("Target 1 ₹ (sell 50%)", min_value=1.0, value=105.0, step=0.5)
        new_t2   = st.number_input("Target 2 ₹ (sell rest)", min_value=1.0, value=110.0, step=0.5)
        new_date = st.date_input("Buy Date", value=datetime.now(IST).date())

    if st.button("✅ Save Trade", type="primary", width='stretch'):
        if new_sym:
            trades.append({"symbol":new_sym,"type":new_type,"qty":int(new_qty),
                           "buy_price":float(new_buy),"stop_loss":float(new_sl),
                           "target1":float(new_t1),"target2":float(new_t2),
                           "buy_date":str(new_date)})
            save_data(trades, watchlist, closed_trades)
            st.success(f"✅ {new_sym} saved! It will appear below.")
            st.rerun()
        else:
            st.warning("Please enter stock symbol")

# Show open trades
if trades:
    st.markdown(f"**{len(trades)} open trade(s) — checked against live data:**")
    for i,t in enumerate(trades):
        sym=t["symbol"]; buy=t["buy_price"]; qty=t["qty"]
        sl=t["stop_loss"]; t1=t["target1"]; t2=t["target2"]
        ttype=t.get("type","Swing")
        try:
            bd=datetime.strptime(t["buy_date"],"%Y-%m-%d").date()
            days=(datetime.now(IST).date()-bd).days
        except: days=0

        s_data=stocks_dict.get(sym)
        ltp=s_data["ltp"] if s_data else buy
        pnl_pct=round((ltp-buy)/buy*100,2)
        pnl_amt=round((ltp-buy)*qty,2)
        signal,reason,sig_col=exit_signal(sym,buy,sl,t1,t2,stocks_dict)

        st.markdown(f"""
        <div style="background:#0d1020;border:2px solid {sig_col};
        border-radius:10px;padding:14px 18px;margin-bottom:8px">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
                <div>
                    <span style="font-size:1.2rem;font-weight:800;color:#e0e6f0">{sym}</span>
                    <span style="font-size:0.75rem;color:#667;margin-left:8px">{ttype} · Day {days+1} · {qty} shares</span>
                </div>
                <span style="font-size:1.1rem;font-weight:800;color:{sig_col};background:#0a0e1a;
                padding:4px 14px;border-radius:20px;border:1px solid {sig_col}">{signal}</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0;font-size:0.82rem">
                <div style="background:#080c18;border-radius:6px;padding:6px 10px">
                    <div style="color:#667;font-size:0.72rem">Buy Price</div>
                    <div style="font-weight:700">₹{buy:,.2f}</div>
                </div>
                <div style="background:#080c18;border-radius:6px;padding:6px 10px">
                    <div style="color:#667;font-size:0.72rem">Current Price</div>
                    <div style="font-weight:700">₹{ltp:,.2f}</div>
                </div>
                <div style="background:#080c18;border-radius:6px;padding:6px 10px">
                    <div style="color:#667;font-size:0.72rem">P&L</div>
                    <div style="font-weight:700;color:{'#26de81' if pnl_pct>=0 else '#ff4757'}">
                    {'+'if pnl_pct>=0 else ''}{pnl_pct:.2f}% &nbsp; ₹{pnl_amt:+,.0f}
                    </div>
                </div>
                <div style="background:#080c18;border-radius:6px;padding:6px 10px">
                    <div style="color:#667;font-size:0.72rem">Stop Loss</div>
                    <div style="font-weight:700;color:#ff4757">₹{sl:,.2f}</div>
                </div>
                <div style="background:#080c18;border-radius:6px;padding:6px 10px">
                    <div style="color:#667;font-size:0.72rem">Target 1 (50%)</div>
                    <div style="font-weight:700;color:#f9ca24">₹{t1:,.2f}</div>
                </div>
                <div style="background:#080c18;border-radius:6px;padding:6px 10px">
                    <div style="color:#667;font-size:0.72rem">Target 2 (rest)</div>
                    <div style="font-weight:700;color:#26de81">₹{t2:,.2f}</div>
                </div>
                <div style="background:#080c18;border-radius:6px;padding:6px 10px">
                    <div style="color:#667;font-size:0.72rem">RSI Now</div>
                    <div style="font-weight:700">{(f"{s_data['rsi']:.0f}" if s_data else 'N/A')}</div>
                </div>
                <div style="background:#080c18;border-radius:6px;padding:6px 10px">
                    <div style="color:#667;font-size:0.72rem">EMA Trend</div>
                    <div style="font-weight:700">{'✅ Up' if s_data and s_data['ema9']>s_data['ema21'] else '❌ Down'}</div>
                </div>
            </div>
            <div style="background:#080c18;border-radius:6px;padding:8px 12px;
            font-size:0.8rem;color:{sig_col};border-left:3px solid {sig_col}">
                💡 {reason}
            </div>
        </div>
        """, unsafe_allow_html=True)

        ca,cb,cc=st.columns([1,1,3])
        with ca:
            if st.button("🗑️ Remove",key=f"del_{i}",width='stretch'):
                trades.pop(i); save_data(trades,watchlist,closed_trades); st.rerun()
        with cb:
            if st.button(f"✅ Closed",key=f"cls_{i}",width='stretch'):
                closed_trades.append({**t,"close_price":ltp,"close_date":str(datetime.now(IST).date()),"pnl_pct":pnl_pct,"pnl_amt":pnl_amt})
                trades.pop(i); save_data(trades,watchlist,closed_trades); st.rerun()
else:
    st.info("No open trades yet. Add a trade above after you buy a stock. App will then track exit signal automatically.")

st.markdown("")

# ═══════════════════════════════════════════════════════════════
#  SECTION 5 — WATCHLIST
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<div class="section-box watch-box">
<p class="sec-title watch-col">👁️ SECTION 4 — MY WATCHLIST</p>
<span style="color:#8899bb;font-size:0.8rem;">
<b>What this is:</b> Stocks you want to keep an eye on every day — not bought yet but interested in.<br>
<b>How to use:</b> Add any stock here. App shows current price, RSI, EMA trend and whether it's ready to buy.<br>
<b>✅ Your watchlist is saved permanently</b> — never lost on refresh or restart.
</span>
</div>
""", unsafe_allow_html=True)

# Add to watchlist
wc1,wc2=st.columns([3,1])
with wc1:
    new_watch=st.text_input("Add stock to watchlist", placeholder="Type symbol e.g. WIPRO", label_visibility="collapsed").upper().strip()
with wc2:
    if st.button("➕ Add to Watchlist", width='stretch'):
        if new_watch and new_watch not in watchlist:
            watchlist.append(new_watch)
            save_data(trades, watchlist, closed_trades)
            st.success(f"✅ {new_watch} added to watchlist")
            st.rerun()
        elif new_watch in watchlist:
            st.warning(f"{new_watch} already in watchlist")

# Show watchlist
if watchlist:
    wl_rows=[]
    for sym in watchlist:
        s=stocks_dict.get(sym)
        if s:
            i_sc,_=intraday_score(s)
            sw_sc,_=swing_score(s)
            sl_s,t1_s,t2_s,_=compute_targets(s["ltp"],"swing")
            wl_rows.append({
                "Symbol":sym,
                "LTP":f"₹{s['ltp']:,.2f}",
                "Change%":f"{s['pchg']:+.2f}%",
                "RSI":f"{s['rsi']:.0f}",
                "EMA Trend":"✅ Up" if s["ema9"]>s["ema21"] else "❌ Down",
                "Vol Ratio":f"{s['vol_ratio']:.1f}x",
                "52W High%":f"{100-s['from_high']:.1f}%",
                "Intraday Score":i_sc,
                "Swing Score":sw_sc,
                "Swing SL":f"₹{sl_s:,.2f}",
                "Swing T1":f"₹{t1_s:,.2f}",
                "Ready?":"🟢 BUY NOW" if sw_sc>=70 else ("🟡 WATCH" if sw_sc>=55 else "⚪ Not yet"),
            })
        else:
            wl_rows.append({"Symbol":sym,"LTP":"N/A","Change%":"N/A","RSI":"N/A",
                           "EMA Trend":"N/A","Vol Ratio":"N/A","52W High%":"N/A",
                           "Intraday Score":0,"Swing Score":0,
                           "Swing SL":"N/A","Swing T1":"N/A","Ready?":"❓ No data"})

    df_wl=pd.DataFrame(wl_rows)
    st.dataframe(df_wl,width='stretch',
                 height=min(420,60+len(df_wl)*38),
                 hide_index=True,
                 column_config={
                     "Intraday Score":st.column_config.ProgressColumn("Intraday",min_value=0,max_value=100,format="%d"),
                     "Swing Score":   st.column_config.ProgressColumn("Swing",   min_value=0,max_value=100,format="%d"),
                     "Ready?":        st.column_config.TextColumn("Ready to Buy?",width="medium"),
                 })

    # Remove from watchlist
    rem=st.selectbox("Remove from watchlist:",["-- select --"]+watchlist)
    if rem!="-- select --":
        if st.button(f"🗑️ Remove {rem} from watchlist"):
            watchlist.remove(rem)
            save_data(trades,watchlist,closed_trades)
            st.rerun()
    st.markdown("""
    <div style="background:#060e18;border-radius:6px;padding:7px 12px;font-size:0.78rem;color:#336688;margin-top:4px">
    💡 <b>Ready to Buy? = 🟢 BUY NOW</b> means swing score > 70 — strong setup. 
    Add it to My Trades after buying. <b>🟡 WATCH</b> = getting close, check daily.
    </div>""", unsafe_allow_html=True)
else:
    st.info("Watchlist is empty. Add stocks above to track them daily.")

st.markdown("")

# ═══════════════════════════════════════════════════════════════
#  SECTION 6 — TRADE HISTORY
# ═══════════════════════════════════════════════════════════════
if closed_trades:
    with st.expander(f"📊 Trade History — {len(closed_trades)} closed trades", expanded=False):
        st.markdown("""
        <div style="color:#8899bb;font-size:0.8rem;margin-bottom:8px">
        All your closed trades. Use this to track your win rate and improve over time.
        </div>""", unsafe_allow_html=True)
        total_pnl=sum(t.get("pnl_amt",0) for t in closed_trades)
        wins=[t for t in closed_trades if t.get("pnl_pct",0)>0]
        losses=[t for t in closed_trades if t.get("pnl_pct",0)<=0]
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Total Trades",len(closed_trades))
        m2.metric("Wins",len(wins))
        m3.metric("Losses",len(losses))
        m4.metric("Total P&L",f"₹{total_pnl:+,.0f}",delta=f"{len(wins)/len(closed_trades)*100:.0f}% win rate")
        hist_rows=[{"Symbol":t["symbol"],"Type":t.get("type","Swing"),
                    "Buy":f"₹{t['buy_price']:,.2f}","Sell":f"₹{t.get('close_price',0):,.2f}",
                    "P&L %":f"{t.get('pnl_pct',0):+.2f}%",
                    "P&L ₹":f"₹{t.get('pnl_amt',0):+,.0f}",
                    "Date":t.get("buy_date",""),"Result":"✅ Win" if t.get("pnl_pct",0)>0 else "❌ Loss"}
                   for t in closed_trades]
        st.dataframe(pd.DataFrame(hist_rows),width='stretch',hide_index=True)
        if st.button("🗑️ Clear History"):
            closed_trades.clear()
            save_data(trades,watchlist,closed_trades)
            st.rerun()

# ═══════════════════════════════════════════════════════════════
#  FOOTER
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<div class="disclaimer">
⚠️ <b>Not SEBI Investment Advice.</b> For educational purposes only.
Always do your own research. Past performance does not guarantee future results.
Use strict stop losses on every trade. Never invest more than you can afford to lose.<br>
Data source: Yahoo Finance (15-min delay) / NSE India when available locally.
</div>
""", unsafe_allow_html=True)
