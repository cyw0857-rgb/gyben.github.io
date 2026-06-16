#!/usr/bin/env python3
"""國際市場指數獨立抓取 — yfinance，每10分鐘執行"""

import json, os, math
from datetime import datetime
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


def run():
    print("🌐 抓取國際市場指數...", flush=True)
    results = {}
    for name, symbol, category, desc in MARKETS:
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            if len(hist) < 2:
                print(f"  ⚠️ {name} 資料不足")
                continue
            prev = safe(hist.iloc[-2]["Close"])
            curr = safe(hist.iloc[-1]["Close"])
            if prev <= 0 or curr <= 0:
                print(f"  ⚠️ {name} 資料異常（價格為0）"); continue
            chg  = (curr - prev) / prev * 100

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

    if not results:
        print("❌ 全部指數抓取失敗"); return

    out = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data":    results,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ 國際市場更新完成：{len(results)} 個指數", flush=True)


if __name__ == "__main__":
    run()
