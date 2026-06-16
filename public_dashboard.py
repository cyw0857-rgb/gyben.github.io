#!/usr/bin/env python3
"""
台指期每日信號看板 — 公開版
GitHub Actions 每天 08:30（台灣時間）自動更新
"""
import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ── 技術指標 ─────────────────────────────────────────────────
def add_indicators(df):
    c = df["Close"]
    df["MA5"]  = c.rolling(5).mean()
    df["MA10"] = c.rolling(10).mean()
    df["MA20"] = c.rolling(20).mean()
    delta = c.diff()
    g = delta.clip(lower=0)
    l = (-delta).clip(lower=0)
    df["RSI"] = 100 - 100 / (1 + g.ewm(com=13, adjust=False).mean() /
                                  l.ewm(com=13, adjust=False).mean())
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"]  = ema12 - ema26
    df["MACDs"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["Chg"]   = c.pct_change() * 100
    return df.dropna(subset=["MA20","RSI","MACD"])

# ── 下載資料 ─────────────────────────────────────────────────
def fetch(sym, period="3mo"):
    try:
        df = yf.download(sym, period=period, interval="1d",
                         auto_adjust=True, progress=False)
        if hasattr(df.columns, "get_level_values"):
            df.columns = df.columns.get_level_values(0)
        return df.dropna(how="all")
    except Exception:
        return pd.DataFrame()

# ── 信號計算 ─────────────────────────────────────────────────
def compute_signals(tw, sox_chg, spx_chg):
    if len(tw) < 3:
        return 0, 0, 0, 0, {}

    prev  = tw.iloc[-1]   # 昨日（最後一筆已收盤）
    p2    = tw.iloc[-2]   # 前日

    rsi  = float(prev["RSI"])
    ma5  = float(prev["MA5"]);  ma10 = float(prev["MA10"]);  ma20 = float(prev["MA20"])
    ma5p = float(p2["MA5"]);    ma10p= float(p2["MA10"]);    ma20p= float(p2["MA20"])
    macd  = float(prev["MACD"]); macds = float(prev["MACDs"])
    pk_up = float(p2["Close"]) > float(p2["Open"])

    ma1_b = ma5 > ma10 > ma20
    ma1_s = ma5 < ma10 < ma20
    ma2_b = ma1_b and (ma5p > ma10p > ma20p)
    ma2_s = ma1_s and (ma5p < ma10p < ma20p)
    macd_b = macd > macds
    macd_s = macd < macds

    # 精準版
    if   ma2_b and 45 < rsi < 72 and sox_chg > 0.5 and spx_chg > 0: d100 = 1
    elif ma2_s and 28 < rsi < 55 and sox_chg < -0.5 and spx_chg < 0: d100 = -1
    else: d100 = 0

    # 優化版
    if   ma1_b and macd_b and pk_up and 40 < rsi < 80 and sox_chg > 0 and spx_chg > 0: d70 = 1
    elif ma1_s and macd_s and not pk_up and 20 < rsi < 60 and sox_chg < 0 and spx_chg < 0: d70 = -1
    else: d70 = 0

    # 高頻版
    if   ma1_b and macd_b and pk_up and 30 < rsi < 80: d60 = 1
    elif ma1_s and macd_s and not pk_up and 20 < rsi < 70: d60 = -1
    else: d60 = 0

    # 超高頻版
    if   ma1_b and 30 < rsi < 85: d50 = 1
    elif ma1_s and 15 < rsi < 70: d50 = -1
    else: d50 = 0

    info = {
        "close":  float(prev["Close"]),
        "chg":    float(prev["Chg"]),
        "rsi":    rsi,
        "ma5": ma5, "ma10": ma10, "ma20": ma20,
        "macd": macd, "macds": macds,
        "ma1_b": ma1_b, "ma1_s": ma1_s,
        "ma2_b": ma2_b, "ma2_s": ma2_s,
    }
    return d100, d70, d60, d50, info

# ── HTML 生成 ────────────────────────────────────────────────
def make_card(direction, label, desc, win_rate, n_trades, lc):
    if direction == 1:
        bg = "rgba(16,185,129,.14)"; bdr = "#10b981"
        ico = "🟢"; act = "買進"; detail = "08:45 買進 · 13:25 賣出"
    elif direction == -1:
        bg = "rgba(239,68,68,.14)"; bdr = "#ef4444"
        ico = "🔴"; act = "放空"; detail = "08:45 放空 · 13:25 買回"
    else:
        bg = "rgba(71,85,105,.15)"; bdr = "#475569"
        ico = "⚪"; act = "觀望"; detail = "今日條件不足，不交易"
    wc = "#10b981" if win_rate >= 80 else ("#f59e0b" if win_rate >= 65 else "#94a3b8")
    return f"""
<div style="background:{bg};border:1.5px solid {bdr};border-radius:14px;
            padding:16px;margin-bottom:10px">
  <div style="font-size:.68rem;color:#64748b;margin-bottom:4px">{label}</div>
  <div style="font-size:2rem;font-weight:900;color:{bdr};line-height:1">{ico} {act}</div>
  <div style="font-size:.8rem;color:#cbd5e1;margin:6px 0 10px">{detail}</div>
  <div style="display:flex;justify-content:space-between;align-items:flex-end;
              border-top:1px solid rgba(255,255,255,.07);padding-top:8px">
    <span style="font-size:.68rem;color:#475569">{desc}</span>
    <div style="text-align:right">
      <div style="font-size:.62rem;color:#475569">模擬回測 ({n_trades}筆)</div>
      <div style="font-size:1rem;font-weight:800;color:{wc}">{win_rate:.0f}%</div>
    </div>
  </div>
</div>"""

def intl_item(name, chg, sym=""):
    c = "#10b981" if chg > 0 else ("#ef4444" if chg < 0 else "#64748b")
    arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")
    return f"""<div style="background:#1e293b;border-radius:10px;padding:10px 12px">
  <div style="font-size:.68rem;color:#64748b">{name}</div>
  <div style="font-size:.95rem;font-weight:700;color:{c}">{arrow} {chg:+.2f}%</div>
</div>"""

def generate_html(d100, d70, d60, d50, info, intl, now_str, trade_date):
    lc  = info.get("close", 0)
    chg = info.get("chg", 0)
    rsi = info.get("rsi", 50)
    chg_c = "#10b981" if chg >= 0 else "#ef4444"
    chg_a = "▲" if chg >= 0 else "▼"

    cards = (
        make_card(d100, "🎯 精準版 — MA2日+SOX>0.5%+RSI<72", "最嚴格，每月~2筆", 100, 13, lc) +
        make_card(d70,  "📊 優化版 — MA1日+MACD+前K+SOX",    "均衡，每月~4筆",   90,  21, lc) +
        make_card(d60,  "📈 高頻版 — MA1日+MACD+前K收紅",    "寬鬆，每月~6筆",   73,  37, lc) +
        make_card(d50,  "🔁 超高頻版 — MA1日+RSI",            "最寬，每月~12筆",  65,  69, lc)
    )

    sox_chg  = intl.get("sox",  0)
    spx_chg  = intl.get("spx",  0)
    vix      = intl.get("vix",  0)
    vix_chg  = intl.get("vix_chg", 0)

    intl_html = (
        intl_item("費城半導體 SOX", sox_chg) +
        intl_item("S&P 500",       spx_chg) +
        intl_item(f"VIX 恐慌 ({vix:.0f})", vix_chg)
    )

    ma1_txt = "多頭排列 ✅" if info.get("ma1_b") else ("空頭排列 ❌" if info.get("ma1_s") else "無方向 ─")
    ma2_txt = "連2日多頭 ✅" if info.get("ma2_b") else ("連2日空頭 ❌" if info.get("ma2_s") else "─")

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>台指期信號</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f172a;color:#f1f5f9;
  font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif;
  padding:16px;max-width:460px;margin:0 auto;-webkit-font-smoothing:antialiased}}
</style>
</head>
<body>

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px">
  <div>
    <div style="font-size:1.15rem;font-weight:700">📈 台指期信號</div>
    <div style="font-size:.68rem;color:#475569;margin-top:2px">{now_str} 更新</div>
  </div>
  <div style="text-align:right">
    <div style="font-size:1.4rem;font-weight:800;color:{chg_c}">{lc:,.0f}</div>
    <div style="font-size:.8rem;color:{chg_c}">{chg_a} {abs(chg):.2f}%</div>
  </div>
</div>

<!-- 技術面摘要 -->
<div style="background:#1e293b;border-radius:12px;padding:12px 14px;margin-bottom:14px;
            display:flex;gap:16px;flex-wrap:wrap">
  <div><span style="color:#475569;font-size:.68rem">均線</span>
       <span style="font-size:.8rem;margin-left:4px">{ma1_txt}</span></div>
  <div><span style="color:#475569;font-size:.68rem">2日</span>
       <span style="font-size:.8rem;margin-left:4px">{ma2_txt}</span></div>
  <div><span style="color:#475569;font-size:.68rem">RSI</span>
       <span style="font-size:.8rem;margin-left:4px">{rsi:.1f}</span></div>
</div>

<!-- 明日信號 -->
<div style="font-size:.68rem;color:#475569;text-transform:uppercase;
            letter-spacing:.1em;margin-bottom:8px">📋 {trade_date} 操作建議</div>
{cards}

<!-- 國際市場 -->
<div style="font-size:.68rem;color:#475569;text-transform:uppercase;
            letter-spacing:.1em;margin:14px 0 8px">🌐 昨日美股收盤</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px">
  {intl_html}
</div>

<div style="text-align:center;color:#334155;font-size:.65rem;padding-bottom:8px">
  ⚠️ 模擬回測信號，不構成投資建議｜微型台指(MXF)每點 NT$10<br>
  資料來源: Yahoo Finance · 每個交易日 08:30 自動更新
</div>

</body>
</html>"""


# ── 主程式 ───────────────────────────────────────────────────
def main():
    now = datetime.utcnow() + timedelta(hours=8)   # 台灣時間
    now_str = now.strftime("%Y-%m-%d %H:%M")

    print("📡 下載台灣加權指數...", flush=True)
    tw_raw = fetch("^TWII", period="3mo")
    if tw_raw.empty:
        print("❌ 無法取得 TWII 資料"); return
    tw = add_indicators(tw_raw.copy())

    print("🌐 下載國際指數...", flush=True)
    sox_raw = fetch("^SOX", period="5d")
    spx_raw = fetch("^GSPC", period="5d")
    vix_raw = fetch("^VIX", period="5d")

    def last_chg(df):
        if df.empty or len(df) < 2: return 0.0
        c = df["Close"].dropna()
        return float((c.iloc[-1] / c.iloc[-2] - 1) * 100) if len(c) >= 2 else 0.0

    sox_chg = last_chg(sox_raw)
    spx_chg = last_chg(spx_raw)
    vix_chg = last_chg(vix_raw)
    vix_val = float(vix_raw["Close"].dropna().iloc[-1]) if not vix_raw.empty else 0

    intl = {"sox": sox_chg, "spx": spx_chg, "vix": vix_val, "vix_chg": vix_chg}

    # 判斷交易日：若今天是週末或台灣市場已關，顯示「下一交易日」
    weekday = now.weekday()  # 0=Mon, 6=Sun
    if weekday == 5:
        trade_date = (now + timedelta(days=2)).strftime("%m/%d（一）")
    elif weekday == 6:
        trade_date = (now + timedelta(days=1)).strftime("%m/%d（一）")
    else:
        trade_date = now.strftime("%m/%d（今日）")

    print("🧮 計算信號...", flush=True)
    d100, d70, d60, d50, info = compute_signals(tw, sox_chg, spx_chg)

    print("🎨 產生 index.html...", flush=True)
    html = generate_html(d100, d70, d60, d50, info, intl, now_str, trade_date)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ 完成")

if __name__ == "__main__":
    main()
