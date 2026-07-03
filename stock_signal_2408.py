#!/usr/bin/env python3
"""南亞科 (2408.TW) 每日方向信號 + 半年走勢預測
   規格比照長榮航太 stock_signal.py；外部因素改為 DRAM 連動（美光/費半/台股）。
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json, os

SYMBOL = "2408.TW"
NAME   = "南亞科"
HERE   = os.path.dirname(os.path.abspath(__file__))
OUT    = os.path.join(HERE, "data", "stock_2408.json")

# 外部連動因素（DRAM 記憶體股）
EXT_SYMBOLS = {
    "美光":    "MU",      # 全球 DRAM 龍頭，連動最強（比照航太的波音）
    "費半":    "^SOX",    # 費城半導體指數
    "台股加權": "^TWII",
}


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


def fetch_full_data():
    df = yf.Ticker(SYMBOL).history(period="max")
    if df.empty:
        return pd.DataFrame(), {}
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df[["Close", "Volume"]].dropna()
    df["MA5"]  = df["Close"].rolling(5).mean()
    df["MA10"] = df["Close"].rolling(10).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()
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
    tech_details = []
    def rec(pts, txt):
        tech_details.append({"icon": "📈" if pts > 0 else "📉" if pts < 0 else "•",
                             "text": txt, "score": pts})

    ma_bull = float(prev["MA5"]) > float(prev["MA10"]) > float(prev["MA20"])
    ma_bear = float(prev["MA5"]) < float(prev["MA10"]) < float(prev["MA20"])
    if ma_bull:
        rec(3, "均線多頭排列 MA5>MA10>MA20")
    elif ma_bear:
        rec(-3, "均線空頭排列 MA5<MA10<MA20")
    elif float(prev["MA5"]) > float(prev["MA10"]):
        rec(1, "MA5>MA10 短線偏多")
    else:
        rec(-1, "MA5<MA10 短線偏空")

    rsi = float(prev["RSI"])
    if 50 < rsi < 72:
        rec(2, f"RSI={rsi:.0f} 多頭健康區")
    elif rsi >= 72:
        rec(0, f"RSI={rsi:.0f} 偏高注意壓回")
    elif 40 < rsi <= 50:
        rec(-1, f"RSI={rsi:.0f} 中性偏空")
    else:
        rec(-2, f"RSI={rsi:.0f} 弱勢區")

    macd  = float(prev["MACD"])
    macds = float(prev["MACDs"])
    if macd > macds and macd > 0:
        rec(2, "MACD金叉零軸上")
    elif macd > macds:
        rec(1, "MACD金叉（零軸下）")
    elif macd < macds and macd < 0:
        rec(-2, "MACD死叉零軸下")
    else:
        rec(-1, "MACD死叉（零軸上）")

    if float(prev["Close"]) > float(prev["MA20"]):
        rec(1, "站上MA20支撐")
    else:
        rec(-1, "跌破MA20壓力")

    score   = sum(d["score"] for d in tech_details)
    reasons = [d["text"] for d in tech_details]

    if score >= 4:
        direction, signal_text, signal_color = 1, "🟢 明日看漲", "#10b981"
    elif score <= -4:
        direction, signal_text, signal_color = -1, "🔴 明日看跌", "#ef4444"
    else:
        direction, signal_text, signal_color = 0, "⚪ 暫時整理", "#9ca3af"

    # 明確的買/賣/續抱動作（持股人一眼看得懂該怎麼做，不再只有「觀望」）
    if score >= 6:
        hold_advice, hold_color = "🟢 買進 / 加碼 — 多頭強勢，可續抱加碼", "#10b981"
    elif score >= 4:
        hold_advice, hold_color = "🟢 續抱偏多 — 逢回可買、不追高", "#10b981"
    elif score >= 1:
        hold_advice, hold_color = "🟡 續抱 — 偏多但不強，持股抱牢、勿加碼", "#f59e0b"
    elif score == 0:
        hold_advice, hold_color = "⚪ 中性 — 持股續抱、空手觀望等訊號", "#9ca3af"
    elif score >= -2:
        hold_advice, hold_color = "🟠 偏弱 — 中性偏空，逢高調節、嚴設停損", "#f59e0b"
    elif score >= -3:
        hold_advice, hold_color = "🟠 減碼 — 趨勢轉弱，降低部位、嚴設停損", "#f59e0b"
    else:
        hold_advice, hold_color = "🔴 賣出 / 停損 — 空頭轉強，建議出場", "#ef4444"

    try:
        low9  = df["Low"].rolling(9).min()
        high9 = df["High"].rolling(9).max()
        rsv   = (df["Close"] - low9) / (high9 - low9) * 100
        k_ser = rsv.ewm(com=2, adjust=False).mean()
        d_ser = k_ser.ewm(com=2, adjust=False).mean()
        k_val = round(float(k_ser.iloc[-1]), 1)
        d_val = round(float(d_ser.iloc[-1]), 1)
    except Exception:
        k_val = d_val = 0.0

    try:
        vol_ma20 = float(df["Volume"].rolling(20).mean().iloc[-1])
        vol_now  = float(df["Volume"].iloc[-1])
        vol_ratio = round(vol_now / vol_ma20, 2) if vol_ma20 > 0 else 1.0
    except Exception:
        vol_ratio = 1.0
    if   vol_ratio >= 1.8: retail_mood = "過熱（爆量）"
    elif vol_ratio >= 1.3: retail_mood = "偏熱（增溫）"
    elif vol_ratio <= 0.7: retail_mood = "冷清（量縮）"
    else:                  retail_mood = "量能正常"
    retail_signals = []
    if vol_ratio >= 1.8: retail_signals.append({"icon": "🔥", "text": f"爆量 {vol_ratio:.1f}倍，注意追高風險"})
    elif vol_ratio <= 0.7: retail_signals.append({"icon": "💤", "text": f"量縮 {vol_ratio:.1f}倍，觀望氣氛濃"})

    return {
        "direction": direction, "signal_text": signal_text, "signal_color": signal_color,
        "hold_advice": hold_advice, "hold_color": hold_color,
        "score": score, "total_score": score, "tech_score": score,
        "reasons": reasons, "tech_details": tech_details,
        "rsi": round(rsi, 1), "macd": round(macd, 2), "macds": round(macds, 2),
        "k": k_val, "d": d_val,
        "ma5": round(float(prev["MA5"]), 2), "ma10": round(float(prev["MA10"]), 2),
        "ma20": round(float(prev["MA20"]), 2),
        "ma60": round(float(prev["MA60"]), 2) if not pd.isna(prev["MA60"]) else 0,
        "last_close": round(float(prev["Close"]), 2), "chg_pct": round(float(prev["ChgPct"]), 2),
        "ma_bull": ma_bull, "ma_bear": ma_bear,
        "retail": {"mood": retail_mood, "vol_ratio": vol_ratio, "score": 0, "signals": retail_signals},
    }


def forecast_model(df_full, ext=None):
    """月度多因素方向預測；外部因素：美光/費半/台股（DRAM 連動）"""
    if df_full is None or df_full.empty or len(df_full) < 60:
        return _fallback_forecast(df_full if df_full is not None else pd.DataFrame())
    if ext is None:
        ext = {}

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
    for name, df_e in ext.items():
        m[f"{name}_ret"] = df_e.resample("ME").last()["Close"].pct_change().reindex(m.index)

    slope_all = float(np.polyfit(np.arange(len(df_full)), df_full["Close"].values, 1)[0])

    W = {"ma_cross": 2.5, "ma_trend": 1.0, "ma60": 0.5,
         "rsi": 0.5, "macd": 0.5, "mom3": 0.5,
         "micron": 1.0, "sox": 1.0, "twii": 0.5}
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
        # DRAM 連動：正相關
        mu = row.get("美光_ret", 0) or 0
        if mu > 0.05: s += W["micron"]
        elif mu < -0.05: s -= W["micron"]
        sox = row.get("費半_ret", 0) or 0
        if sox > 0.03: s += W["sox"]
        elif sox < -0.03: s -= W["sox"]
        twii = row.get("台股加權_ret", 0) or 0
        if twii > 0.02: s += W["twii"]
        elif twii < -0.02: s -= W["twii"]
        return s

    m_bt = m.copy()
    m_bt["next_ret"] = m_bt["Close"].pct_change(1).shift(-1)
    m_bt["actual"]   = m_bt["next_ret"].apply(lambda r: 1 if r > 0.02 else (-1 if r < -0.02 else 0))
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

    mu_curr  = float(last_row.get("美光_ret",  0) or 0)
    sox_curr = float(last_row.get("費半_ret",  0) or 0)
    twii_curr= float(last_row.get("台股加權_ret", 0) or 0)
    ma_cross_str = ""
    prev_ma5  = float(m["MA5"].shift(1).iloc[-1]  or curr_ma5)
    prev_ma10 = float(m["MA10"].shift(1).iloc[-1] or curr_ma10)
    if curr_ma5 > curr_ma10 and prev_ma5 <= prev_ma10: ma_cross_str = "金叉↑"
    elif curr_ma5 < curr_ma10 and prev_ma5 >= prev_ma10: ma_cross_str = "死叉↓"

    def month_note(i):
        trend_base = "MA5>MA10 多頭" if monthly_bull else "MA5<MA10 空頭"
        if i == 1:
            parts = [ma_cross_str] if ma_cross_str else [trend_base]
            if abs(mu_curr)  > 0.05: parts.append(f"美光{'↑' if mu_curr>0 else '↓'}{mu_curr*100:+.0f}%")
            if abs(sox_curr) > 0.03: parts.append(f"費半{'↑' if sox_curr>0 else '↓'}{sox_curr*100:+.0f}%")
            if abs(twii_curr)> 0.02: parts.append(f"台股{'↑' if twii_curr>0 else '↓'}{twii_curr*100:+.0f}%")
            return "  ".join(parts)
        else:
            return f"{trend_base}（外部因素待觀察）"

    closes_all = df_full["Close"].dropna().values
    if len(closes_all) >= 126:
        mom_6m = closes_all[-1] / closes_all[-126] - 1.0
        drift_raw = mom_6m / 6.0
    elif curr_close:
        drift_raw = slope_all * 21 / curr_close
    else:
        drift_raw = 0.0
    if   curr_pred == 1:  monthly_drift =  abs(drift_raw)
    elif curr_pred == -1: monthly_drift = -abs(drift_raw)
    else:                 monthly_drift =  max(-0.015, min(0.015, drift_raw * 0.2))  # 觀望→近乎持平，不再噴出假漲幅
    monthly_drift = max(-0.06, min(0.06, monthly_drift))

    forecast = []
    for i in range(1, 7):
        yr  = last_date.year + (last_date.month + i - 1) // 12
        mo  = (last_date.month + i - 1) % 12 + 1
        label     = f"{yr:04d}-{mo:02d}"
        proj      = curr_close * (1 + monthly_drift) ** i
        chg_pct   = (proj / curr_close - 1) * 100 if curr_close else 0.0
        # 波動區間：√t 標準差，但上限 ±40% 避免高波動股(南亞科)區間爆炸、低點掉到地板價
        band_ratio = min(daily_vol * float(np.sqrt(i * 21)), 0.40)
        vol_range = proj * band_ratio
        trend     = "up" if curr_pred == 1 else ("down" if curr_pred == -1 else "neutral")
        dir_icon  = "📈" if curr_pred == 1 else ("📉" if curr_pred == -1 else "⚪")
        note      = f"{dir_icon} {month_note(i)}" if curr_pred != 0 else f"⚪ 觀望（分{curr_score:+.1f}）"
        forecast.append({
            "month": label, "price": round(proj, 2),
            "price_high": round(max(proj + vol_range, 1.0), 2),
            "price_low":  round(max(proj - vol_range, 1.0), 2),
            "chg_pct": round(chg_pct, 1), "trend": trend,
            "model_note": note, "score": round(curr_score, 1),
        })

    recent = df_full["Close"].values[-63:] if len(df_full) >= 63 else df_full["Close"].values
    support    = round(float(np.percentile(recent, 15)), 2)
    resistance = round(float(np.percentile(recent, 85)), 2)

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

    _vr5 = curr_close * daily_vol * float(np.sqrt(5))
    _ctr = curr_close
    weekly = {
        "proj_center": round(_ctr, 2), "proj_high": round(_ctr + _vr5, 2),
        "proj_low": round(max(_ctr - _vr5, 0.1), 2),
        "support": support, "resistance": resistance,
        "trend_bias": ("偏多" if slope_all > 0.05 else "偏空" if slope_all < -0.05 else "中性"),
        "op_hint": ("逢回偏多操作" if slope_all > 0.05 else "逢高偏空操作" if slope_all < -0.05 else "區間操作"),
    }

    return {
        "forecast": forecast, "trend_label": trend_label,
        "support": support, "resistance": resistance, "weekly": weekly,
        "daily_vol_pct": round(daily_vol * 100, 2), "slope_per_day": round(slope_all, 3),
        "model_accuracy": round(bt_acc, 1), "model_samples": total_w,
        "total_return": round(total_ret, 1),
        "ipo_date": df_full.index[0].strftime("%Y-%m-%d"),
        "model_score": round(curr_score, 1), "model_threshold": THRESHOLD,
        "model_factors": month_note(1),
    }


def _fallback_forecast(df):
    closes = df["Close"].values if not df.empty else [100]
    n = len(closes)
    if n < 2:
        return {"forecast": [], "trend_label": "─", "support": 0, "resistance": 0,
                "weekly": {"proj_center": 0, "proj_high": 0, "proj_low": 0, "support": 0,
                           "resistance": 0, "trend_bias": "中性", "op_hint": "資料不足"},
                "daily_vol_pct": 1.5, "slope_per_day": 0,
                "model_accuracy": 0, "model_samples": 0, "total_return": 0, "ipo_date": "─"}
    slope = float(np.polyfit(np.arange(n), closes, 1)[0])
    intercept = closes[-1] - slope * (n - 1)
    daily_vol = float(df["Close"].pct_change().dropna().std()) if n >= 3 else 0.015
    last_close = float(closes[-1])
    last_date  = df.index[-1]
    forecast = []
    for mth in range(1, 7):
        trading_days = mth * 21
        proj_date  = last_date + timedelta(days=mth * 30)
        proj_price = intercept + slope * (n - 1 + trading_days)
        vol_range  = last_close * daily_vol * float(np.sqrt(trading_days))
        chg_pct    = (proj_price - last_close) / last_close * 100
        trend = "up" if chg_pct > 3 else ("down" if chg_pct < -3 else "neutral")
        forecast.append({"month": proj_date.strftime("%Y-%m"), "price": round(max(proj_price, 0.1), 2),
                          "price_high": round(max(proj_price + vol_range, 0.1), 2),
                          "price_low": round(max(proj_price - vol_range, 0.1), 2),
                          "chg_pct": round(chg_pct, 1), "trend": trend})
    _sup = round(float(np.percentile(closes[-63:] if n >= 63 else closes, 15)), 2)
    _res = round(float(np.percentile(closes[-63:] if n >= 63 else closes, 85)), 2)
    _vr5 = last_close * daily_vol * float(np.sqrt(5))
    _ctr = last_close
    return {"forecast": forecast,
            "trend_label": "上漲趨勢 📈" if slope > 0.05 else ("下跌趨勢 📉" if slope < -0.05 else "橫盤整理 ➡️"),
            "support": _sup, "resistance": _res,
            "weekly": {"proj_center": round(_ctr, 2), "proj_high": round(_ctr + _vr5, 2),
                       "proj_low": round(max(_ctr - _vr5, 0.1), 2), "support": _sup, "resistance": _res,
                       "trend_bias": ("偏多" if slope > 0.05 else "偏空" if slope < -0.05 else "中性"),
                       "op_hint": ("逢回偏多操作" if slope > 0.05 else "逢高偏空操作" if slope < -0.05 else "區間操作")},
            "daily_vol_pct": round(daily_vol * 100, 2), "slope_per_day": round(slope, 3),
            "model_accuracy": 0, "model_samples": 0, "total_return": 0, "ipo_date": "─"}


def run():
    print(f"💾 抓取 {NAME} ({SYMBOL}) 資料...", flush=True)
    try:
        df = fetch_data()
        if df.empty or len(df) < 30:
            print(f"❌ {NAME} 資料不足"); return
        df_full, ext = fetch_full_data()
        sig = daily_signal(df)
        fc  = forecast_model(df_full, ext) if not df_full.empty else _fallback_forecast(df)
        print(f"   月度模型: 回測準確率 {fc.get('model_accuracy', 0):.1f}% ({fc.get('model_samples', 0)} 筆)")
        print(f"   上市以來累計報酬: {fc.get('total_return', 0):+.1f}%")
        result = {"symbol": SYMBOL, "name": NAME,
                  "updated": datetime.now().strftime("%Y-%m-%d %H:%M"), **sig, **fc}
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✅ {NAME}  {sig['signal_text']}  評分:{sig['score']:+d}  {sig['hold_advice']}", flush=True)
    except Exception as ex:
        print(f"❌ {NAME} 信號失敗: {ex}", flush=True)
        import traceback; traceback.print_exc()


if __name__ == "__main__":
    run()
