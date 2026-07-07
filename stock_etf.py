#!/usr/bin/env python3
"""月月配高股息 ETF 三劍客卡片資料引擎
   0056 + 00878 + 00919：三檔季配、除息月份錯開，湊成一年 12 個月月月有息。
   技術面規格比照長榮航太 / 南亞科（RSI/MACD/KD/MA/評分/信號）。
   另加：每次配息金額、上線後累計配息、（有持股時）累計配息金額與殖利率。
   輸出：data/stock_etf.json
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "data", "stock_etf.json")

# ── 上線基準日：從這天起（含）之後的每一次除息才計入「累計配息」 ──
START_DATE = "2026-07-07"

# ── 三檔設定：yfinance 代碼、名稱、除息月份、風格 ──
ETFS = {
    "0056":  {"yf": "0056.TW",  "name": "元大高股息",       "months": [1, 4, 7, 10],
              "style": "選未來一年高殖利率股，偏電子/AI，攻擊性較強"},
    "00878": {"yf": "00878.TW", "name": "國泰永續高股息",   "months": [2, 5, 8, 11],
              "style": "ESG＋三年均殖利率，金融+穩健電子，最抗跌"},
    "00919": {"yf": "00919.TW", "name": "群益台灣精選高息", "months": [3, 6, 9, 12],
              "style": "主打宣告股利精準卡位，殖利率最高"},
}

# ── 持股設定（使用者之後填）──
#   shares : 目前持有股數（0 = 純觀察，不算損益）
#   cost   : 每股平均成本
#   buys   : 定期定額買進紀錄 [{"date":"2026-07-15","shares":100}, ...]
#            有填 buys 時，累計配息金額會用「該次除息日當下實際持股」精算；
#            沒填時，退回用目前 shares 估算（會略為高估早期配息）。
HOLDINGS = {
    "0056":  {"shares": 0, "cost": 0.0, "buys": []},
    "00878": {"shares": 0, "cost": 0.0, "buys": []},
    "00919": {"shares": 0, "cost": 0.0, "buys": []},
}


# ═══════════════ 技術面（沿用航太/南亞科同一套評分）═══════════════
def fetch_tech(yf_sym, months=9):
    df = yf.Ticker(yf_sym).history(period=f"{months}mo")
    if df.empty:
        return None
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df["MA5"]  = df["Close"].rolling(5).mean()
    df["MA10"] = df["Close"].rolling(10).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()
    delta = df["Close"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta).clip(lower=0).rolling(14).mean()
    df["RSI"]   = 100 - 100 / (1 + gain / loss)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"]  = ema12 - ema26
    df["MACDs"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["ChgPct"] = df["Close"].pct_change() * 100
    return df.dropna()


def tech_signal(df):
    prev = df.iloc[-1]
    tech_details = []
    def rec(pts, txt):
        tech_details.append({"icon": "📈" if pts > 0 else "📉" if pts < 0 else "•",
                             "text": txt, "score": pts})
    ma_bull = float(prev["MA5"]) > float(prev["MA10"]) > float(prev["MA20"])
    ma_bear = float(prev["MA5"]) < float(prev["MA10"]) < float(prev["MA20"])
    if ma_bull:                                   rec(3, "均線多頭排列 MA5>MA10>MA20")
    elif ma_bear:                                 rec(-3, "均線空頭排列 MA5<MA10<MA20")
    elif float(prev["MA5"]) > float(prev["MA10"]):rec(1, "MA5>MA10 短線偏多")
    else:                                         rec(-1, "MA5<MA10 短線偏空")
    rsi = float(prev["RSI"])
    if   50 < rsi < 72: rec(2, f"RSI={rsi:.0f} 多頭健康區")
    elif rsi >= 72:     rec(0, f"RSI={rsi:.0f} 偏高注意壓回")
    elif 40 < rsi <= 50:rec(-1, f"RSI={rsi:.0f} 中性偏空")
    else:               rec(-2, f"RSI={rsi:.0f} 弱勢區")
    macd, macds = float(prev["MACD"]), float(prev["MACDs"])
    if   macd > macds and macd > 0: rec(2, "MACD金叉零軸上")
    elif macd > macds:              rec(1, "MACD金叉（零軸下）")
    elif macd < macds and macd < 0: rec(-2, "MACD死叉零軸下")
    else:                           rec(-1, "MACD死叉（零軸上）")
    if float(prev["Close"]) > float(prev["MA20"]): rec(1, "站上MA20支撐")
    else:                                          rec(-1, "跌破MA20壓力")

    score = sum(d["score"] for d in tech_details)
    if   score >= 4: direction, signal_text, signal_color = 1, "🟢 明日看漲", "#10b981"
    elif score <= -4:direction, signal_text, signal_color = -1, "🔴 明日看跌", "#ef4444"
    else:            direction, signal_text, signal_color = 0, "⚪ 暫時整理", "#9ca3af"
    if   score >= 6: hold_advice, hold_color = "🟢 買進 / 加碼 — 多頭強勢", "#10b981"
    elif score >= 4: hold_advice, hold_color = "🟢 續抱偏多 — 逢回可買、不追高", "#10b981"
    elif score >= 1: hold_advice, hold_color = "🟡 續抱 — 偏多但不強", "#f59e0b"
    elif score == 0: hold_advice, hold_color = "⚪ 中性 — 續抱、空手等訊號", "#9ca3af"
    elif score >= -2:hold_advice, hold_color = "🟠 偏弱 — 逢高調節", "#f59e0b"
    elif score >= -3:hold_advice, hold_color = "🟠 減碼 — 趨勢轉弱", "#f59e0b"
    else:            hold_advice, hold_color = "🔴 賣出 / 停損 — 空頭轉強", "#ef4444"

    try:
        low9, high9 = df["Low"].rolling(9).min(), df["High"].rolling(9).max()
        rsv   = (df["Close"] - low9) / (high9 - low9) * 100
        k_ser = rsv.ewm(com=2, adjust=False).mean()
        d_ser = k_ser.ewm(com=2, adjust=False).mean()
        k_val, d_val = round(float(k_ser.iloc[-1]), 1), round(float(d_ser.iloc[-1]), 1)
    except Exception:
        k_val = d_val = 0.0

    return {
        "direction": direction, "signal_text": signal_text, "signal_color": signal_color,
        "hold_advice": hold_advice, "hold_color": hold_color,
        "score": score, "tech_details": tech_details,
        "rsi": round(rsi, 1), "macd": round(macd, 2), "macds": round(macds, 2),
        "k": k_val, "d": d_val,
        "ma5": round(float(prev["MA5"]), 2), "ma10": round(float(prev["MA10"]), 2),
        "ma20": round(float(prev["MA20"]), 2),
        "ma60": round(float(prev["MA60"]), 2) if not pd.isna(prev["MA60"]) else 0,
        "last_close": round(float(prev["Close"]), 2), "chg_pct": round(float(prev["ChgPct"]), 2),
    }


# ═══════════════ 配息：每次金額、殖利率、上線後累計 ═══════════════
def shares_as_of(hold, ex_date):
    """定期定額：算某個除息日當下實際持有的股數。
       有 buys 明細 → 累加該日(含)之前買進的股數；否則退回目前 shares。"""
    buys = hold.get("buys") or []
    if not buys:
        return hold.get("shares", 0)
    total = 0
    for b in buys:
        if pd.to_datetime(b["date"]) <= ex_date:
            total += b["shares"]
    return total


def dividend_block(yf_sym, price, hold):
    t = yf.Ticker(yf_sym)
    div = t.dividends
    if div is None or len(div) == 0:
        return {"recent": [], "latest": None, "yield_ttm": 0.0,
                "cum_per_share": 0.0, "cum_amount": 0.0, "cum_count": 0, "cum_list": []}
    div.index = pd.to_datetime(div.index).tz_localize(None)

    # 近 6 次配息明細（除息日 + 每股金額）
    recent = [{"ex_date": ix.strftime("%Y-%m-%d"), "amount": round(float(v), 4)}
              for ix, v in div.items()][-6:]
    latest = recent[-1] if recent else None

    # 年化殖利率（採 ChatGPT 建議的穩健版）：近 12 個月（365 天）配息總和 / 現價
    # 比「近4次」通用，不受月配/季配/半年配影響；資料未滿一年時退回近4次年化估算
    now = pd.Timestamp.now().normalize()
    ttm = div[div.index >= now - pd.Timedelta(days=365)]
    if len(ttm) > 0 and (now - div.index.min()).days >= 360:
        yield_ttm = round(float(ttm.sum()) / price * 100, 2) if price else 0.0
        yield_label = "近12個月"
    else:
        last4 = [float(v) for v in div.values][-4:]
        yield_ttm = round(sum(last4) / price * 100, 2) if price else 0.0
        yield_label = "近4次年化估算"

    # 上線後累計配息：除息日 >= START_DATE 才計入
    start = pd.to_datetime(START_DATE)
    cum_list, cum_ps, cum_amt = [], 0.0, 0.0
    for ix, v in div.items():
        if ix >= start:
            amt_ps = float(v)
            sh     = shares_as_of(hold, ix)          # 定期定額 → 用當下持股
            amt    = amt_ps * sh
            cum_ps  += amt_ps
            cum_amt += amt
            cum_list.append({"ex_date": ix.strftime("%Y-%m-%d"),
                             "amount": round(amt_ps, 4),
                             "shares": sh, "cash": round(amt, 1)})
    return {"recent": recent, "latest": latest,
            "yield_ttm": yield_ttm, "yield_label": yield_label,
            "cum_per_share": round(cum_ps, 4), "cum_amount": round(cum_amt, 1),
            "cum_count": len(cum_list), "cum_list": cum_list}


def build_etf(key, cfg):
    yf_sym = cfg["yf"]
    df = fetch_tech(yf_sym)
    if df is None or len(df) < 30:
        print(f"❌ {key} 技術資料不足"); return None
    sig   = tech_signal(df)
    price = sig["last_close"]

    # 一年回檔幅度：距近一年高點跌多少
    hi_1y = float(df["Close"][-250:].max()) if len(df) >= 30 else price
    drawdown = round((price - hi_1y) / hi_1y * 100, 1) if hi_1y else 0.0

    div  = dividend_block(yf_sym, price, HOLDINGS.get(key, {}))
    hold = HOLDINGS.get(key, {})
    shares, cost = hold.get("shares", 0), hold.get("cost", 0.0)
    pnl = None
    if shares > 0 and cost > 0:
        pnl = {"shares": shares, "cost": cost,
               "market_value": round(price * shares, 1),
               "unreal_pnl": round((price - cost) * shares, 1),
               "unreal_pct": round((price - cost) / cost * 100, 2)}

    return {
        "code": key, "symbol": yf_sym, "name": cfg["name"],
        "months": cfg["months"], "style": cfg["style"],
        "drawdown_pct": drawdown, "high_1y": round(hi_1y, 2),
        **sig, "dividend": div, "holding": pnl,
    }


def monthly_calendar():
    """逐月除息表：1~12 月分別由哪一檔除息。"""
    cal = {m: [] for m in range(1, 13)}
    for key, cfg in ETFS.items():
        for m in cfg["months"]:
            cal[m].append(key)
    return [{"month": m, "etfs": cal[m]} for m in range(1, 13)]


def run():
    print("💾 抓取 月月配三劍客 (0056/00878/00919) ...", flush=True)
    etfs, port_ps, port_cash, port_cnt = [], 0.0, 0.0, 0
    for key, cfg in ETFS.items():
        try:
            e = build_etf(key, cfg)
            if e:
                etfs.append(e)
                port_ps   += e["dividend"]["cum_per_share"]
                port_cash += e["dividend"]["cum_amount"]
                port_cnt  += e["dividend"]["cum_count"]
                print(f"   {key} {cfg['name']}  {e['last_close']}  "
                      f"殖利率{e['dividend']['yield_ttm']}%  {e['signal_text']}")
        except Exception as ex:
            print(f"⚠️  {key} 失敗: {ex}")
    result = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "start_date": START_DATE,
        "etfs": etfs,
        "monthly_calendar": monthly_calendar(),
        "portfolio": {
            "cum_per_share_sum": round(port_ps, 4),   # 三檔每股累計配息加總
            "cum_cash_total": round(port_cash, 1),     # 上線後累計領到的現金（有持股才>0）
            "cum_count_total": port_cnt,
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ stock_etf.json 已更新（{len(etfs)} 檔，上線後累計現金 {port_cash:.0f} 元）", flush=True)


if __name__ == "__main__":
    run()
