#!/usr/bin/env python3
"""國際市場指數獨立抓取 — yfinance，每10分鐘執行
   美股開盤時間(台灣)：22:30-04:00，使用5分K即時價格
"""

import json, os, math
from datetime import datetime, timezone, timedelta
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "data", "intl.json")

MARKETS = [
    ("S&P500",    "^GSPC",    "美股",   "美股漲→台股漲"),
    ("道瓊",      "^DJI",     "美股",   "藍籌股風向球"),
    ("NASDAQ",    "^IXIC",    "美股",   "科技股連動"),
    ("費城半導體", "^SOX",     "半導體", "對台股影響最大"),
    ("VIX恐慌",   "^VIX",     "情緒",   "<20樂觀 >25恐慌"),
    ("日經225",   "^N225",    "亞股",   "亞股風向球"),
    ("韓KOSPI",   "^KS11",    "亞股",   "半導體競爭對手"),
    ("恒生指數",  "^HSI",     "亞股",   "港股/中概股連動"),
    ("上證指數",  "000001.SS","A股",    "中國市場情緒"),
    ("台股加權",  "^TWII",    "台股",   "台股現貨參考"),
    ("美元指數",  "DX-Y.NYB", "外匯",   "強美元→外資匯出"),
    ("黃金",      "GC=F",     "商品",   "避險情緒指標"),
    ("原油",      "CL=F",     "商品",   "油漲→通膨預期"),
    ("美債10Y",   "^TNX",     "債券",   "殖利率高→股市壓力"),
    ("比特幣",    "BTC-USD",  "加密",   "風險偏好指標"),
]


def safe(v):
    try:
        f = float(v)
        return 0.0 if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return 0.0


def get_prices(symbol):
    """取得前日收盤 & 當前最新價（單一 API 呼叫）。
    用 5分K period=5d 一次拿完所有資料。
    回傳 (prev_close, current_price) 或 (0, 0)
    """
    ticker = yf.Ticker(symbol)
    try:
        # 一次抓5天5分K（含盤中最新）
        hist = ticker.history(period="5d", interval="5m")
        if len(hist) < 2:
            raise ValueError("not enough bars")
        curr = safe(hist.iloc[-1]["Close"])
        # 找前一個交易日最後一根
        today = hist.index[-1].date()
        prev_bars = hist[hist.index.date < today]
        if len(prev_bars) == 0:
            raise ValueError("no prev day")
        prev = safe(prev_bars.iloc[-1]["Close"])
        if prev > 0 and curr > 0:
            return prev, curr
    except Exception:
        pass
    # fallback: 日K
    try:
        daily = ticker.history(period="5d")
        if len(daily) >= 2:
            return safe(daily.iloc[-2]["Close"]), safe(daily.iloc[-1]["Close"])
    except Exception:
        pass
    return 0.0, 0.0


def run():
    tst = datetime.now(timezone(timedelta(hours=8)))
    print(f"🌐 抓取國際市場指數... ({tst.strftime('%H:%M')} TST)", flush=True)

    # 讀取舊資料，抓失敗時保留舊值
    old_data = {}
    if os.path.exists(OUT):
        try:
            old_data = json.load(open(OUT, encoding="utf-8")).get("data", {})
        except Exception:
            pass

    results = {}
    for name, symbol, category, desc in MARKETS:
        try:
            prev, curr = get_prices(symbol)
            if prev <= 0 or curr <= 0:
                if name in old_data:
                    results[name] = old_data[name]   # 保留舊值
                    print(f"  ⏩ {name} 沿用舊值")
                else:
                    print(f"  ⚠️ {name} 資料異常，略過")
                continue

            chg = (curr - prev) / prev * 100

            if name == "VIX恐慌":
                sig  = 1 if curr < 20 else (-1 if curr > 25 else 0)
                note = f"VIX={curr:.1f}({'低恐慌' if curr < 20 else '高恐慌⚠️' if curr > 25 else '中性'})"
            elif name == "美元指數":
                sig  = -1 if chg > 0.3 else (1 if chg < -0.3 else 0)
                note = f"{chg:+.2f}%({'偏空' if sig==-1 else '偏多' if sig==1 else '中性'})"
            elif name == "美債10Y":
                sig  = -1 if chg > 3 else (1 if chg < -3 else 0)
                note = f"{curr:.2f}%({chg:+.2f}%)"
            elif name in ("黃金", "比特幣", "原油"):
                sig  = 1 if chg > 0.5 else (-1 if chg < -0.5 else 0)
                note = f"{chg:+.2f}%"
            elif name in ("上證指數", "台股加權"):
                sig  = 1 if chg > 0.3 else (-1 if chg < -0.3 else 0)
                note = f"{chg:+.2f}%"
            else:
                sig  = 1 if chg > 0 else (-1 if chg < 0 else 0)
                note = f"{chg:+.2f}%"

            results[name] = {
                "category": category,
                "price":    round(curr, 2),
                "chg_pct":  round(chg, 2),
                "signal":   sig,
                "note":     note,
                "desc":     desc,
            }
            arrow = "▲" if sig == 1 else ("▼" if sig == -1 else "─")
            print(f"  {arrow} {name:<9} {note}", flush=True)
        except Exception as ex:
            print(f"  ❌ {name} 失敗: {ex}")
            if name in old_data:
                results[name] = old_data[name]

    # 無論如何都寫檔（保持 updated 時間戳新鮮）
    out = {
        "updated": tst.strftime("%Y-%m-%d %H:%M"),
        "data":    results or old_data,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ 國際市場更新完成：{len(results)} 個指數", flush=True)


if __name__ == "__main__":
    run()
