#!/usr/bin/env python3
"""長榮航太 (2645.TW) 每日方向信號 + 半年走勢預測"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json, os

SYMBOL = "2645.TW"
NAME   = "長榮航太"
HERE   = os.path.dirname(os.path.abspath(__file__))
OUT    = os.path.join(HERE, "data", "stock_2645.json")


def fetch_data(months=9):
    df = yf.Ticker(SYMBOL).history(period=f"{months}mo")
    if df.empty:
        return pd.DataFrame()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df["MA5"]    = df["Close"].rolling(5).mean()
    df["MA10"]   = df["Close"].rolling(10).mean()
    df["MA20"]   = df["Close"].rolling(20).mean()
    df["MA60"]   = df["Close"].rolling(60).mean()
    delta        = df["Close"].diff()
    gain         = delta.clip(lower=0).rolling(14).mean()
    loss         = (-delta).clip(lower=0).rolling(14).mean()
    df["RSI"]    = 100 - 100 / (1 + gain / loss)
    ema12        = df["Close"].ewm(span=12, adjust=False).mean()
    ema26        = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"]   = ema12 - ema26
    df["MACDs"]  = df["MACD"].ewm(span=9, adjust=False).mean()
    df["ChgPct"] = df["Close"].pct_change() * 100
    return df.dropna()


def daily_signal(df):
    prev  = df.iloc[-1]
    score = 0
    reasons = []

    # 均線排列 (±3)
    ma_bull = float(prev["MA5"]) > float(prev["MA10"]) > float(prev["MA20"])
    ma_bear = float(prev["MA5"]) < float(prev["MA10"]) < float(prev["MA20"])
    if ma_bull:
        score += 3; reasons.append("均線多頭排列 MA5>MA10>MA20")
    elif ma_bear:
        score -= 3; reasons.append("均線空頭排列 MA5<MA10<MA20")
    elif float(prev["MA5"]) > float(prev["MA10"]):
        score += 1; reasons.append("MA5>MA10 短線偏多")
    else:
        score -= 1; reasons.append("MA5<MA10 短線偏空")

    # RSI (±2)
    rsi = float(prev["RSI"])
    if 50 < rsi < 72:
        score += 2; reasons.append(f"RSI={rsi:.0f} 多頭健康區")
    elif rsi >= 72:
        reasons.append(f"RSI={rsi:.0f} 偏高注意壓回")
    elif 40 < rsi <= 50:
        score -= 1; reasons.append(f"RSI={rsi:.0f} 中性偏空")
    else:
        score -= 2; reasons.append(f"RSI={rsi:.0f} 弱勢區")

    # MACD (±2)
    macd  = float(prev["MACD"])
    macds = float(prev["MACDs"])
    if macd > macds and macd > 0:
        score += 2; reasons.append("MACD金叉零軸上")
    elif macd > macds:
        score += 1; reasons.append("MACD金叉（零軸下）")
    elif macd < macds and macd < 0:
        score -= 2; reasons.append("MACD死叉零軸下")
    else:
        score -= 1; reasons.append("MACD死叉（零軸上）")

    # 收盤 vs MA20 (±1)
    if float(prev["Close"]) > float(prev["MA20"]):
        score += 1; reasons.append("站上MA20支撐")
    else:
        score -= 1; reasons.append("跌破MA20壓力")

    # 方向
    if score >= 4:
        direction   = 1
        signal_text = "🟢 明日看漲"
        signal_color = "#10b981"
    elif score <= -4:
        direction   = -1
        signal_text = "🔴 明日看跌"
        signal_color = "#ef4444"
    else:
        direction   = 0
        signal_text = "⚪ 暫時整理"
        signal_color = "#9ca3af"

    # 續抱建議
    if ma_bull and score >= 4:
        hold_advice = "✅ 續抱 — 均線多頭，趨勢完整"
        hold_color  = "#10b981"
    elif score >= 2:
        hold_advice = "⚠️ 輕倉續抱 — 訊號偏多但不強"
        hold_color  = "#f59e0b"
    elif score <= -4:
        hold_advice = "❌ 建議出場 — 趨勢轉弱，停損優先"
        hold_color  = "#ef4444"
    elif score <= -2:
        hold_advice = "⚠️ 謹慎持有 — 訊號偏空，設好停損"
        hold_color  = "#f59e0b"
    else:
        hold_advice = "⚪ 觀望 — 等待方向確認"
        hold_color  = "#9ca3af"

    return {
        "direction":    direction,
        "signal_text":  signal_text,
        "signal_color": signal_color,
        "hold_advice":  hold_advice,
        "hold_color":   hold_color,
        "score":        score,
        "reasons":      reasons,
        "rsi":          round(rsi, 1),
        "ma5":          round(float(prev["MA5"]),  2),
        "ma10":         round(float(prev["MA10"]), 2),
        "ma20":         round(float(prev["MA20"]), 2),
        "last_close":   round(float(prev["Close"]), 2),
        "chg_pct":      round(float(prev["ChgPct"]), 2),
        "ma_bull":      ma_bull,
        "ma_bear":      ma_bear,
    }


def forecast_6m(df):
    closes = df["Close"].values
    n      = len(closes)
    x      = np.arange(n, dtype=float)

    coeffs    = np.polyfit(x, closes, 1)
    slope     = float(coeffs[0])
    intercept = float(coeffs[1])

    daily_ret = df["Close"].pct_change().dropna().values[-60:]
    daily_vol = float(np.std(daily_ret)) if len(daily_ret) > 0 else 0.01

    last_close = float(df["Close"].iloc[-1])
    last_date  = df.index[-1]

    forecast = []
    for m in range(1, 7):
        trading_days = m * 21
        proj_date    = last_date + timedelta(days=m * 30)
        proj_price   = intercept + slope * (n - 1 + trading_days)
        vol_range    = last_close * daily_vol * float(np.sqrt(trading_days))
        chg_pct      = (proj_price - last_close) / last_close * 100

        if chg_pct > 3:    trend = "up"
        elif chg_pct < -3: trend = "down"
        else:              trend = "neutral"

        forecast.append({
            "month":      proj_date.strftime("%Y-%m"),
            "price":      round(max(proj_price, 0.1), 2),
            "price_high": round(max(proj_price + vol_range, 0.1), 2),
            "price_low":  round(max(proj_price - vol_range, 0.1), 2),
            "chg_pct":    round(chg_pct, 1),
            "trend":      trend,
        })

    recent_90 = df["Close"].values[-63:] if len(df) >= 63 else df["Close"].values
    support    = round(float(np.percentile(recent_90, 15)), 2)
    resistance = round(float(np.percentile(recent_90, 85)), 2)

    if slope > 0.05:   trend_label = "上漲趨勢 📈"
    elif slope < -0.05: trend_label = "下跌趨勢 📉"
    else:               trend_label = "橫盤整理 ➡️"

    return {
        "forecast":       forecast,
        "slope_per_day":  round(slope, 3),
        "trend_label":    trend_label,
        "support":        support,
        "resistance":     resistance,
        "daily_vol_pct":  round(daily_vol * 100, 2),
    }


def run():
    print(f"✈️  抓取 {NAME} ({SYMBOL}) 資料...", flush=True)
    try:
        df = fetch_data()
        if df.empty or len(df) < 30:
            print(f"❌ {NAME} 資料不足"); return

        sig = daily_signal(df)
        fc  = forecast_6m(df)

        result = {
            "symbol":  SYMBOL,
            "name":    NAME,
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            **sig,
            **fc,
        }

        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"✅ {NAME}  {sig['signal_text']}  評分:{sig['score']:+d}  {sig['hold_advice']}", flush=True)

    except Exception as ex:
        print(f"❌ {NAME} 信號失敗: {ex}", flush=True)
        import traceback; traceback.print_exc()


if __name__ == "__main__":
    run()
