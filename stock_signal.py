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
    """日K用於每日信號，固定抓9個月足夠計算日線指標"""
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


def fetch_full_data():
    """抓上市以來全部日K + 外部因素（波音/原油/長榮海運/台股）"""
    df = yf.Ticker(SYMBOL).history(period="max")
    if df.empty:
        return pd.DataFrame(), {}
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df[["Close", "Volume"]].dropna()
    df["MA5"]  = df["Close"].rolling(5).mean()
    df["MA10"] = df["Close"].rolling(10).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()

    # 外部因素（月報酬）
    EXT_SYMBOLS = {
        "波音":    "BA",
        "原油":    "CL=F",
        "長榮海運": "2603.TW",
        "台股加權": "^TWII",
    }
    ext = {}
    for name, sym in EXT_SYMBOLS.items():
        try:
            d = yf.Ticker(sym).history(period="max")
            d.index = pd.to_datetime(d.index).tz_localize(None)
            ext[name] = d[["Close"]].dropna()
        except Exception:
            pass
    return df, ext


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


def forecast_model(df_full, ext=None):
    """
    月度多因素方向預測模型
    信號: MA交叉 + RSI/MACD + 波音/原油/長榮海運/台股
    回測準確率: 68% (±3.5門檻,19筆) / 80% (±4.5門檻,10筆)
    """
    if df_full is None or df_full.empty or len(df_full) < 60:
        return _fallback_forecast(df_full if df_full is not None else pd.DataFrame())
    if ext is None:
        ext = {}

    # ── 月底快照 ──────────────────────────────────────
    m = df_full.resample("ME").last().copy()
    delta = df_full["Close"].diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta).clip(lower=0).rolling(14).mean()
    rsi_d = 100 - 100 / (1 + gain / loss)
    ema12 = df_full["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df_full["Close"].ewm(span=26, adjust=False).mean()
    macd_d  = ema12 - ema26
    macds_d = macd_d.ewm(span=9, adjust=False).mean()

    m["RSI"]   = rsi_d.resample("ME").last()
    m["MACD"]  = macd_d.resample("ME").last()
    m["MACDs"] = macds_d.resample("ME").last()
    m["mom3"]  = m["Close"].pct_change(3)
    m["ma5_lag1"]  = m["MA5"].shift(1)
    m["ma10_lag1"] = m["MA10"].shift(1)

    # 外部因素月報酬
    for name, df_e in ext.items():
        m[f"{name}_ret"] = df_e.resample("ME").last()["Close"].pct_change().reindex(m.index)

    # ── 評分函式 ──────────────────────────────────────
    W = {"ma_cross": 2.5, "ma_trend": 1.0, "ma60": 0.5,
         "rsi": 0.5, "macd": 0.5, "mom3": 0.5,
         "ev_ship": 0.5, "boeing": 1.0, "oil": 1.0, "twii": 0.5}
    THRESHOLD = 3.5

    def score_row(row):
        s = 0.0
        c_up   = row["MA5"] > row["MA10"] and row["ma5_lag1"] <= row["ma10_lag1"]
        c_down = row["MA5"] < row["MA10"] and row["ma5_lag1"] >= row["ma10_lag1"]
        if c_up:   s += W["ma_cross"]
        elif c_down: s -= W["ma_cross"]
        s += W["ma_trend"] if row["MA5"] > row["MA10"] else -W["ma_trend"]
        s += W["ma60"] if row["Close"] > row["MA60"] else -W["ma60"]
        rsi = row.get("RSI", 55)
        if 45 < rsi < 70: s += W["rsi"]
        elif rsi > 75: s -= W["rsi"]
        elif rsi < 35: s -= W["rsi"] / 2
        if row.get("MACD", 0) > row.get("MACDs", 0) and row.get("MACD", 0) > 0:
            s += W["macd"]
        elif row.get("MACD", 0) > row.get("MACDs", 0):
            s += W["macd"] * 0.5
        elif row.get("MACD", 0) < row.get("MACDs", 0) and row.get("MACD", 0) < 0:
            s -= W["macd"]
        else:
            s -= W["macd"] * 0.5
        mom3 = row.get("mom3", 0)
        if mom3 > 0.08: s += W["mom3"]
        elif mom3 < -0.08: s -= W["mom3"]
        ship = row.get("長榮海運_ret", 0) or 0
        if ship > 0.03: s += W["ev_ship"]
        elif ship < -0.03: s -= W["ev_ship"]
        ba = row.get("波音_ret", 0) or 0
        if ba > 0.03: s += W["boeing"]
        elif ba < -0.03: s -= W["boeing"]
        oil = row.get("原油_ret", 0) or 0
        if oil < -0.05: s += W["oil"]
        elif oil > 0.05: s -= W["oil"]
        twii = row.get("台股加權_ret", 0) or 0
        if twii > 0.02: s += W["twii"]
        elif twii < -0.02: s -= W["twii"]
        return s

    # ── 歷史回測 ──────────────────────────────────────
    m_bt = m.copy()
    m_bt["next_ret"] = m_bt["Close"].pct_change(1).shift(-1)
    m_bt["actual"]   = m_bt["next_ret"].apply(
        lambda r: 1 if r > 0.02 else (-1 if r < -0.02 else 0)
    )
    m_bt = m_bt.dropna(subset=["next_ret", "ma5_lag1", "RSI"])
    correct, total_w = 0, 0
    for _, row in m_bt.iterrows():
        if row["actual"] == 0: continue
        sc   = score_row(row)
        pred = 1 if sc >= THRESHOLD else (-1 if sc <= -THRESHOLD else 0)
        if pred != 0:
            total_w += 1
            if pred == row["actual"]: correct += 1
    bt_acc = (correct / total_w * 100) if total_w > 0 else 0

    # ── 當前狀態 + 預測 ───────────────────────────────
    last_row   = m.iloc[-1]
    curr_close = float(last_row["Close"])
    curr_ma5   = float(last_row["MA5"])
    curr_ma10  = float(last_row["MA10"])
    curr_ma20  = float(last_row["MA20"])
    curr_ma60  = float(last_row["MA60"])
    last_date  = m.index[-1]
    curr_score = score_row(last_row)
    curr_pred  = 1 if curr_score >= THRESHOLD else (-1 if curr_score <= -THRESHOLD else 0)

    daily_vol = float(df_full["Close"].pct_change().dropna().values[-60:].std())
    monthly_bull = curr_ma5 > curr_ma10

    # 本月已知因素（只用於下個月的說明，之後不重複）
    ba_curr  = float(last_row.get("波音_ret",  0) or 0)
    oil_curr = float(last_row.get("原油_ret",  0) or 0)
    ship_curr= float(last_row.get("長榮海運_ret", 0) or 0)
    ma_cross_str = ""
    prev_ma5  = float(m["MA5"].shift(1).iloc[-1]  or curr_ma5)
    prev_ma10 = float(m["MA10"].shift(1).iloc[-1] or curr_ma10)
    if curr_ma5 > curr_ma10 and prev_ma5 <= prev_ma10: ma_cross_str = "金叉↑"
    elif curr_ma5 < curr_ma10 and prev_ma5 >= prev_ma10: ma_cross_str = "死叉↓"

    def month_note(i):
        """i=1 顯示本月已知因素；i>1 只顯示技術趨勢，因為外部數據未知"""
        trend_base = "MA5>MA10 多頭" if monthly_bull else "MA5<MA10 空頭"
        if i == 1:
            # 下個月：可用本月已知的外部數據
            parts = [ma_cross_str] if ma_cross_str else [trend_base]
            if abs(ba_curr)  > 0.03: parts.append(f"波音{'↑' if ba_curr>0 else '↓'}{ba_curr*100:+.0f}%")
            if abs(oil_curr) > 0.05: parts.append(f"油{'↓利多' if oil_curr<0 else '↑壓力'}{oil_curr*100:+.0f}%")
            if abs(ship_curr)> 0.03: parts.append(f"海運{'↑' if ship_curr>0 else '↓'}{ship_curr*100:+.0f}%")
            return "  ".join(parts)
        else:
            # 未來月份：只知道趨勢方向，外部因素每月重新判斷
            return f"{trend_base}（外部因素待觀察）"

    # 未來6個月預測
    forecast = []
    for i in range(1, 7):
        yr  = last_date.year + (last_date.month + i - 1) // 12
        mo  = (last_date.month + i - 1) % 12 + 1
        label     = f"{yr:04d}-{mo:02d}"
        vol_range = curr_close * daily_vol * float(np.sqrt(i * 21)) * 1.5
        trend     = "up" if curr_pred == 1 else ("down" if curr_pred == -1 else "neutral")
        dir_icon  = "📈" if curr_pred == 1 else ("📉" if curr_pred == -1 else "⚪")
        note      = f"{dir_icon} {month_note(i)}" if curr_pred != 0 else f"⚪ 觀望（分{curr_score:+.1f}）"
        forecast.append({
            "month":      label,
            "price":      round(curr_close, 2),
            "price_high": round(max(curr_close + vol_range, 1.0), 2),
            "price_low":  round(max(curr_close - vol_range, 1.0), 2),
            "chg_pct":    0.0,
            "trend":      trend,
            "model_note": note,
            "score":      round(curr_score, 1),
        })

    # 支撐/壓力
    recent = df_full["Close"].values[-63:] if len(df_full) >= 63 else df_full["Close"].values
    support    = round(float(np.percentile(recent, 15)), 2)
    resistance = round(float(np.percentile(recent, 85)), 2)

    # 長期趨勢標籤
    if curr_ma5 > curr_ma10 > curr_ma20:
        trend_label = "月線均線多頭排列 📈"
    elif curr_ma5 < curr_ma10 < curr_ma20:
        trend_label = "月線均線空頭排列 📉"
    elif monthly_bull:
        trend_label = "月線 MA5>MA10 偏多 📈"
    else:
        trend_label = "月線 MA5<MA10 偏空 📉"

    first_close = float(df_full["Close"].dropna().iloc[0])
    total_ret   = (curr_close - first_close) / first_close * 100
    slope_all   = float(np.polyfit(np.arange(len(df_full)), df_full["Close"].values, 1)[0])

    return {
        "forecast":       forecast,
        "trend_label":    trend_label,
        "support":        support,
        "resistance":     resistance,
        "daily_vol_pct":  round(daily_vol * 100, 2),
        "slope_per_day":  round(slope_all, 3),
        "model_accuracy": round(bt_acc, 1),
        "model_samples":  total_w,
        "total_return":   round(total_ret, 1),
        "ipo_date":       df_full.index[0].strftime("%Y-%m-%d"),
        "model_score":    round(curr_score, 1),
        "model_threshold": THRESHOLD,
        "model_factors":  month_note(1),
    }


def _fallback_forecast(df):
    """資料不足時的線性回歸備用"""
    closes = df["Close"].values if not df.empty else [100]
    n = len(closes)
    if n < 2:
        return {"forecast": [], "trend_label": "─", "support": 0, "resistance": 0,
                "daily_vol_pct": 1.5, "slope_per_day": 0,
                "model_accuracy": 0, "model_samples": 0, "total_return": 0, "ipo_date": "─"}
    slope = float(np.polyfit(np.arange(n), closes, 1)[0])
    intercept = closes[-1] - slope * (n - 1)
    daily_vol = float(df["Close"].pct_change().dropna().std()) if n >= 3 else 0.015
    last_close = float(closes[-1])
    last_date  = df.index[-1]
    forecast = []
    for m in range(1, 7):
        trading_days = m * 21
        proj_date  = last_date + timedelta(days=m * 30)
        proj_price = intercept + slope * (n - 1 + trading_days)
        vol_range  = last_close * daily_vol * float(np.sqrt(trading_days))
        chg_pct    = (proj_price - last_close) / last_close * 100
        trend = "up" if chg_pct > 3 else ("down" if chg_pct < -3 else "neutral")
        forecast.append({"month": proj_date.strftime("%Y-%m"), "price": round(max(proj_price, 0.1), 2),
                          "price_high": round(max(proj_price + vol_range, 0.1), 2),
                          "price_low": round(max(proj_price - vol_range, 0.1), 2),
                          "chg_pct": round(chg_pct, 1), "trend": trend})
    return {"forecast": forecast,
            "trend_label": "上漲趨勢 📈" if slope > 0.05 else ("下跌趨勢 📉" if slope < -0.05 else "橫盤整理 ➡️"),
            "support": round(float(np.percentile(closes[-63:] if n >= 63 else closes, 15)), 2),
            "resistance": round(float(np.percentile(closes[-63:] if n >= 63 else closes, 85)), 2),
            "daily_vol_pct": round(daily_vol * 100, 2), "slope_per_day": round(slope, 3),
            "model_accuracy": 0, "model_samples": 0, "total_return": 0, "ipo_date": "─"}


def run():
    print(f"✈️  抓取 {NAME} ({SYMBOL}) 資料...", flush=True)
    try:
        # 日K（用於每日買賣信號）
        df = fetch_data()
        if df.empty or len(df) < 30:
            print(f"❌ {NAME} 資料不足"); return

        # 全期日K + 外部因素（用於月度方向預測模型）
        df_full, ext = fetch_full_data()

        sig = daily_signal(df)
        fc  = forecast_model(df_full, ext) if not df_full.empty else _fallback_forecast(df)

        print(f"   月度模型: 回測準確率 {fc.get('model_accuracy', 0):.1f}% ({fc.get('model_samples', 0)} 筆)")
        print(f"   上市以來累計報酬: {fc.get('total_return', 0):+.1f}%")

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
