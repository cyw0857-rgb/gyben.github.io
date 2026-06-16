#!/usr/bin/env python3
"""國際市場指數獨立抓取 — yfinance 批次下載，每5分鐘執行
   美股開盤時間(台灣)：22:30-04:00，使用5分K即時價格
"""

import json, os, math
from datetime import datetime, timezone, timedelta
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "data", "intl.json")

MARKETS = [
    ("S&P500",    "^GSPC",     "美股",   "美股漲→台股漲"),
    ("道瓊",      "^DJI",      "美股",   "藍籌股風向球"),
    ("NASDAQ",    "^IXIC",     "美股",   "科技股連動"),
    ("費城半導體", "^SOX",      "半導體", "對台股影響最大"),
    ("VIX恐慌",   "^VIX",      "情緒",   "<20樂觀 >25恐慌"),
    ("日經225",   "^N225",     "亞股",   "亞股風向球"),
    ("韓KOSPI",   "^KS11",     "亞股",   "半導體競爭對手"),
    ("恒生指數",  "^HSI",      "亞股",   "港股/中概股連動"),
    ("上證指數",  "000001.SS", "A股",    "中國市場情緒"),
    ("台股加權",  "^TWII",     "台股",   "台股現貨參考"),
    ("美元指數",  "DX-Y.NYB",  "外匯",   "強美元→外資匯出"),
    ("黃金",      "GC=F",      "商品",   "避險情緒指標"),
    ("原油",      "CL=F",      "商品",   "油漲→通膨預期"),
    ("美債10Y",   "^TNX",      "債券",   "殖利率高→股市壓力"),
    ("比特幣",    "BTC-USD",   "加密",   "風險偏好指標"),
]

NAME_MAP = {sym: name for name, sym, *_ in MARKETS}
DESC_MAP = {name: (sym, cat, desc) for name, sym, cat, desc in MARKETS}


def safe(v):
    try:
        f = float(v)
        return 0.0 if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return 0.0


def run():
    tst = datetime.now(timezone(timedelta(hours=8)))
    print(f"🌐 批次抓取國際市場指數... ({tst.strftime('%H:%M')} TST)", flush=True)

    symbols = [sym for _, sym, *_ in MARKETS]

    # 讀取舊資料，抓失敗時保留舊值
    old_data = {}
    if os.path.exists(OUT):
        try:
            old_data = json.load(open(OUT, encoding="utf-8")).get("data", {})
        except Exception:
            pass

    results = {}

    # ── 嘗試5分K批次下載（最快、最即時）──────────────────
    try:
        raw5 = yf.download(
            tickers=symbols,
            period="5d",
            interval="5m",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
        # 處理單一vs多個ticker回傳格式差異
        single = len(symbols) == 1
        for name, sym, category, desc in MARKETS:
            try:
                df = raw5 if single else raw5[sym]
                df = df.dropna(subset=["Close"])
                if len(df) < 2:
                    raise ValueError("not enough bars")
                curr = safe(df["Close"].iloc[-1])
                today = df.index[-1].date()
                prev_bars = df[df.index.date < today]
                if len(prev_bars) == 0:
                    raise ValueError("no prev day")
                prev = safe(prev_bars["Close"].iloc[-1])
                if prev <= 0 or curr <= 0:
                    raise ValueError("invalid price")
                chg = (curr - prev) / prev * 100
                results[name] = _build(name, sym, category, desc, prev, curr, chg)
                arrow = "▲" if results[name]["signal"] == 1 else ("▼" if results[name]["signal"] == -1 else "─")
                print(f"  {arrow} {name:<9} {results[name]['note']}", flush=True)
            except Exception as e:
                print(f"  ⚠️ {name} 5m失敗: {e}", flush=True)
    except Exception as e:
        print(f"  ❌ 5分K批次失敗: {e}", flush=True)

    # ── 對失敗的符號，回退用日K批次補 ───────────────────
    missing = [sym for _, sym, *_ in MARKETS
               if NAME_MAP[sym] not in results]
    if missing:
        try:
            rawd = yf.download(
                tickers=missing,
                period="5d",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            single = len(missing) == 1
            for name, sym, category, desc in MARKETS:
                if name in results or sym not in missing:
                    continue
                try:
                    df = rawd if single else rawd[sym]
                    df = df.dropna(subset=["Close"])
                    if len(df) < 2:
                        raise ValueError("no data")
                    prev = safe(df["Close"].iloc[-2])
                    curr = safe(df["Close"].iloc[-1])
                    if prev <= 0 or curr <= 0:
                        raise ValueError("invalid price")
                    chg = (curr - prev) / prev * 100
                    results[name] = _build(name, sym, category, desc, prev, curr, chg)
                    arrow = "▲" if results[name]["signal"] == 1 else ("▼" if results[name]["signal"] == -1 else "─")
                    print(f"  {arrow} {name:<9} {results[name]['note']} (日K)", flush=True)
                except Exception as e2:
                    print(f"  ❌ {name} 日K失敗: {e2}", flush=True)
                    if name in old_data:
                        results[name] = old_data[name]
                        print(f"  ⏩ {name} 沿用舊值")
        except Exception as e:
            print(f"  ❌ 日K批次失敗: {e}", flush=True)
            # 所有 missing 用舊值
            for name, sym, *_ in MARKETS:
                if name not in results and name in old_data:
                    results[name] = old_data[name]

    # ── 無論如何都寫檔 ────────────────────────────────────
    out = {
        "updated": tst.strftime("%Y-%m-%d %H:%M"),
        "data":    results or old_data,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"✅ 國際市場更新完成：{len(results)} 個指數", flush=True)


def _build(name, sym, category, desc, prev, curr, chg):
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
    return {
        "category": category,
        "price":    round(curr, 2),
        "chg_pct":  round(chg, 2),
        "signal":   sig,
        "note":     note,
        "desc":     desc,
    }


if __name__ == "__main__":
    run()
