#!/usr/bin/env python3
"""
台股微型台指期 每日方向判斷系統 v3.0
- 每天 8:30 自動執行
- 自動記錄實際進出場價位（開盤買、收盤賣）
- 累計追蹤勝率、損益、月份分組
- 整合國際市場 + 川普新聞 + 技術指標
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os, sys, subprocess, json, requests

try:
    import feedparser
    HAS_FEED = True
except ImportError:
    HAS_FEED = False

# ═══════════════════════════════════════════════════════════
#  常數設定
# ═══════════════════════════════════════════════════════════

SYMBOL          = "^TWII"
POINT_VALUE     = 10    # 微型台指(MXF)每點 NT$10
COMMISSION      = 50    # 手續費（來回，微型台指約 NT$50）
SLIPPAGE        = 1     # 滑價估計 1 點
STOP_LOSS       = 20    # 停損點數（-NT$200）
STOP_PROFIT     = 40    # 停利點數（+NT$400）1:2 風報比
THRESHOLD_BASE  = 7     # 基礎進場門檻（保守，追求70%勝率）
THRESHOLD_TIGHT = 10    # 近期連敗時收緊的門檻

RECORDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "records.csv")
DESKTOP      = os.path.dirname(os.path.abspath(__file__))  # CI: no desktop

RECORD_COLS = [
    "signal_date",   # 產生信號的日期（昨日）
    "trade_date",    # 實際交易日（今日）
    "session",       # day=日盤(8:45~13:30) / night=夜盤(15:45~05:00)
    "direction",     # 1=做多 / -1=做空 / 0=觀望
    "direction_zh",  # 中文描述
    "total_score", "tw_score", "intl_score", "news_score",
    "entry_price",   # 進場價（日盤=開盤 / 夜盤≈收盤）
    "exit_price",    # 出場價（日盤=收盤 / 夜盤≈隔日開盤）
    "pnl_points",    # 損益點數
    "pnl_nts",       # 損益金額（扣手續費）
    "win",           # True / False
    "status",        # pending / completed / skip / no_data / simulated
]

INTL_MARKETS = [
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

NEWS_FEEDS = [
    {"label": "川普動態",   "url": "https://news.google.com/rss/search?q=Trump+tariff+OR+Trump+trade+OR+Trump+says&hl=en-US&gl=US&ceid=US:en", "max": 6},
    {"label": "關稅/貿易",  "url": "https://news.google.com/rss/search?q=tariff+trade+war+economy&hl=en-US&gl=US&ceid=US:en", "max": 4},
    {"label": "台股/半導體","url": "https://news.google.com/rss/search?q=Taiwan+stock+OR+TSMC+OR+semiconductor&hl=en-US&gl=US&ceid=US:en", "max": 4},
    {"label": "聯準會",     "url": "https://news.google.com/rss/search?q=Federal+Reserve+interest+rate+OR+stock+market&hl=en-US&gl=US&ceid=US:en", "max": 4},
]

BULL_WORDS = {"deal","agreement","cut","boost","surge","rally","record","strong",
              "optimism","positive","growth","rise","gain","increase","stimulus",
              "ceasefire","peace","reduce","chip act"}
BEAR_WORDS = {"tariff","sanction","ban","war","threat","crash","recession",
              "inflation","fall","drop","fear","risk","tension","conflict",
              "escalat","collapse","default","crisis","sell-off","warning",
              "impose","penalty","retaliation","shutdown","downgrade",
              "miss","layoff","bankrupt"}


# ═══════════════════════════════════════════════════════════
#  資料取得
# ═══════════════════════════════════════════════════════════

def fetch_taiwan(months: int = 3, period: str = None) -> pd.DataFrame:
    p = period if period else f"{months}mo"
    df = yf.Ticker(SYMBOL).history(period=p)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]].copy()


def add_taiwan_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df["MA5"]    = df["Close"].rolling(5).mean()
    df["MA10"]   = df["Close"].rolling(10).mean()
    df["MA20"]   = df["Close"].rolling(20).mean()
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


def fetch_international() -> dict:
    results = {}
    for name, symbol, category, desc in INTL_MARKETS:
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            if len(hist) < 2:
                continue
            prev = hist.iloc[-2]["Close"]
            curr = hist.iloc[-1]["Close"]
            chg  = (curr - prev) / prev * 100

            if name == "VIX恐慌":
                sig  = 1 if curr < 20 else (-1 if curr > 25 else 0)
                note = f"VIX={curr:.1f}({'低恐慌' if curr < 20 else '高恐慌⚠️' if curr > 25 else '中性'})"
            elif name == "美元指數":
                sig  = -1 if chg > 0.3 else (1 if chg < -0.3 else 0)
                note = f"{chg:+.2f}%({'偏空' if sig == -1 else '偏多' if sig == 1 else '中性'})"
            elif name == "美債10Y":
                sig  = -1 if chg > 3 else (1 if chg < -3 else 0)
                note = f"{curr:.2f}%({chg:+.2f}%)"
            elif name == "黃金":
                sig  = -1 if chg > 1 else (1 if chg < -0.5 else 0)
                note = f"{chg:+.2f}%({'避險↑' if sig == -1 else ''})"
            else:
                sig  = 1 if chg > 0.3 else (-1 if chg < -0.3 else 0)
                note = f"{chg:+.2f}%"

            results[name] = {
                "symbol": symbol, "category": category,
                "price": curr, "chg_pct": chg,
                "signal": sig, "note": note, "desc": desc,
            }
        except Exception:
            pass
    return results


def fetch_gold_detail() -> dict:
    """
    抓取黃金期貨詳細資訊（GC=F）
    回傳: price_usd, chg_pct, signal, warning
    """
    try:
        hist = yf.Ticker("GC=F").history(period="5d")
        if len(hist) < 2:
            return {}
        prev  = hist.iloc[-2]["Close"]
        curr  = hist.iloc[-1]["Close"]
        chg   = (curr - prev) / prev * 100
        usd_per_oz = curr

        # 判斷警示等級
        if chg >= 2:
            level   = "danger"
            warning = f"黃金大漲 {chg:+.1f}%，市場恐慌情緒強烈 → 明日偏空 ⚠️⚠️"
            signal  = -2
        elif chg >= 0.8:
            level   = "warn"
            warning = f"黃金上漲 {chg:+.1f}%，避險需求增加 → 明日偏空 ⚠️"
            signal  = -1
        elif chg <= -2:
            level   = "good"
            warning = f"黃金大跌 {chg:+.1f}%，市場風險偏好回升 → 明日偏多 ✅✅"
            signal  = 2
        elif chg <= -0.8:
            level   = "ok"
            warning = f"黃金下跌 {chg:+.1f}%，風險情緒改善 → 明日偏多 ✅"
            signal  = 1
        else:
            level   = "neutral"
            warning = f"黃金小幅變動 {chg:+.1f}%，影響中性"
            signal  = 0

        result = {
            "price_usd": usd_per_oz,
            "chg_pct":   chg,
            "signal":    signal,
            "level":     level,
            "warning":   warning,
        }

        # 即時油價（WTI 西德州原油 CL=F；失敗不影響黃金）
        try:
            oh = yf.Ticker("CL=F").history(period="5d")
            if len(oh) >= 2:
                op_prev = oh.iloc[-2]["Close"]
                op_curr = oh.iloc[-1]["Close"]
                result["oil_usd"] = op_curr
                result["oil_chg"] = (op_curr - op_prev) / op_prev * 100
        except Exception:
            pass

        return result
    except Exception:
        return {}


def fetch_news() -> list:
    if not HAS_FEED:
        return []
    items = []
    for cfg in NEWS_FEEDS:
        try:
            feed  = feedparser.parse(cfg["url"])
            count = 0
            for e in feed.entries:
                if count >= cfg["max"]:
                    break
                title = e.get("title", "")
                lower = title.lower()
                bull  = sum(1 for w in BULL_WORDS if w in lower)
                bear  = sum(1 for w in BEAR_WORDS if w in lower)
                sv    = 1 if bull > bear else (-1 if bear > bull else 0)
                sent  = "✅偏多" if sv == 1 else ("⚠️偏空" if sv == -1 else "⚪中性")
                items.append({
                    "label": cfg["label"], "title": title[:80],
                    "sentiment": sent, "sent_val": sv,
                })
                count += 1
        except Exception:
            pass
    return items


# ═══════════════════════════════════════════════════════════
#  三大法人 / 大戶追蹤
# ═══════════════════════════════════════════════════════════

def fetch_institutional() -> dict:
    """
    抓取三大法人買賣超（TWSE現貨）+ 外資期貨淨部位（TAIFEX）
    回傳 dict 供 institutional_signal() 使用
    """
    HDR = {"User-Agent": "Mozilla/5.0"}
    result = {
        "foreign_cash_b": 0,   # 外資現貨買超（元）
        "trust_cash_b":   0,   # 投信現貨買超（元）
        "dealer_cash_b":  0,   # 自營商現貨買超（元）
        "foreign_fut_net":0,   # 外資期貨淨部位（口，正=多）
        "ok": False,
    }

    # ── 現貨三大法人（TWSE BFI82U） ──────────────────────
    try:
        url  = "https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json&dayDate=&type=day"
        data = requests.get(url, timeout=8, headers=HDR).json()
        if data.get("stat") == "OK":
            for row in data.get("data", []):
                name = row[0]
                net  = int(row[3].replace(",", ""))
                if "外資及陸資" in name and "自營" not in name:
                    result["foreign_cash_b"] = net
                elif name == "投信":
                    result["trust_cash_b"]   = net
                elif "自營商(自行" in name:
                    result["dealer_cash_b"]  = net
            result["ok"] = True
    except Exception:
        pass

    # ── 期貨三大法人（TAIFEX 臺股期貨 外資淨部位） ───────
    try:
        from bs4 import BeautifulSoup
        url  = "https://www.taifex.com.tw/cht/3/futContractsDate"
        html = requests.get(url, timeout=8, headers=HDR).text
        soup = BeautifulSoup(html, "html.parser")
        found_txf = False
        for row in soup.find_all("tr"):
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if "臺股期貨" in cells:
                found_txf = True
            if found_txf and cells and cells[0] == "外資":
                # cells: [外資, 多方口數, 多方金額, 空方口數, 空方金額, 淨額口數, ...]
                net_str = cells[5].replace(",", "")
                result["foreign_fut_net"] = int(net_str)
                break
    except Exception:
        pass

    return result


def institutional_signal(inst: dict) -> tuple:
    """
    三大法人 + 大戶評分（最高 ±6）
    外資期貨淨部位最重要（直接反映大戶對台指期的押注方向）
    """
    score, details = 0, []

    if not inst.get("ok") and inst.get("foreign_fut_net") == 0:
        return 0, ["  ⚪ 三大法人資料尚未更新（盤中或假日）"]

    # ── 外資期貨淨部位（±3，最重要） ─────────────────────
    fut = inst["foreign_fut_net"]
    if   fut >= 10000: score += 3; details.append(f"  ✅✅✅ 外資期貨大幅淨多 {fut:+,} 口 (+3)")
    elif fut >= 3000:  score += 2; details.append(f"  ✅✅ 外資期貨淨多 {fut:+,} 口 (+2)")
    elif fut >= 500:   score += 1; details.append(f"  ✅ 外資期貨小幅淨多 {fut:+,} 口 (+1)")
    elif fut <= -10000:score -= 3; details.append(f"  ❌❌❌ 外資期貨大幅淨空 {fut:+,} 口 (-3)")
    elif fut <= -3000: score -= 2; details.append(f"  ❌❌ 外資期貨淨空 {fut:+,} 口 (-2)")
    elif fut <= -500:  score -= 1; details.append(f"  ❌ 外資期貨小幅淨空 {fut:+,} 口 (-1)")
    else:              details.append(f"  ⚪ 外資期貨中性 {fut:+,} 口 (0)")

    # ── 外資現貨買賣超（±2） ─────────────────────────────
    fc = inst["foreign_cash_b"]
    fc_b = fc / 1e8  # 轉億元
    if   fc_b >= 200:  score += 2; details.append(f"  ✅✅ 外資現貨買超 {fc_b:,.0f}億 (+2)")
    elif fc_b >= 50:   score += 1; details.append(f"  ✅ 外資現貨買超 {fc_b:,.0f}億 (+1)")
    elif fc_b <= -200: score -= 2; details.append(f"  ❌❌ 外資現貨賣超 {fc_b:,.0f}億 (-2)")
    elif fc_b <= -50:  score -= 1; details.append(f"  ❌ 外資現貨賣超 {fc_b:,.0f}億 (-1)")
    else:              details.append(f"  ⚪ 外資現貨 {fc_b:+,.0f}億 中性 (0)")

    # ── 投信買賣超（±1） ─────────────────────────────────
    tc = inst["trust_cash_b"]
    tc_b = tc / 1e8
    if   tc_b >= 10:  score += 1; details.append(f"  ✅ 投信買超 {tc_b:,.0f}億 (+1)")
    elif tc_b <= -10: score -= 1; details.append(f"  ❌ 投信賣超 {tc_b:,.0f}億 (-1)")
    else:             details.append(f"  ⚪ 投信 {tc_b:+,.0f}億 中性 (0)")

    return score, details


# ═══════════════════════════════════════════════════════════
#  信號產生
# ═══════════════════════════════════════════════════════════

def taiwan_signal(prev, tw_df=None):
    """台灣技術面評分（最高 ±7）"""
    score, details = 0, []

    # ── 均線趨勢（多空排列，±3） ──────────────────────
    ma_bull = (prev["MA5"] > prev["MA10"]) and (prev["MA10"] > prev["MA20"])
    ma_bear = (prev["MA5"] < prev["MA10"]) and (prev["MA10"] < prev["MA20"])
    if ma_bull:
        score += 3; details.append("  ✅✅ 均線多頭排列 MA5>MA10>MA20 (+3)")
    elif ma_bear:
        score -= 3; details.append("  ❌❌ 均線空頭排列 MA5<MA10<MA20 (-3)")
    elif prev["MA5"] > prev["MA10"]:
        score += 1; details.append(f"  ✅ MA5>MA10 短線偏多 (+1)")
    else:
        score -= 1; details.append(f"  ❌ MA5<MA10 短線偏空 (-1)")

    # ── 收盤 vs MA5 / MA20 （±2） ────────────────────
    close_vs_ma5  = prev["Close"] > prev["MA5"]
    close_vs_ma20 = prev["Close"] > prev["MA20"]
    if close_vs_ma5 and close_vs_ma20:
        score += 2; details.append("  ✅ 收盤站上MA5及MA20 (+2)")
    elif close_vs_ma20 and not close_vs_ma5:
        score += 1; details.append("  ✅ 收盤站上MA20 (+1)")
    elif not close_vs_ma5 and not close_vs_ma20:
        score -= 2; details.append("  ❌ 收盤跌破MA5及MA20 (-2)")
    else:
        score -= 1; details.append("  ❌ 收盤跌破MA5 (-1)")

    # ── RSI 區域（±2，避開極端值） ────────────────────
    rsi = prev["RSI"]
    if 55 <= rsi <= 72:
        score += 2; details.append(f"  ✅ RSI={rsi:.0f} 健康偏多區 (+2)")
    elif 50 <= rsi < 55:
        score += 1; details.append(f"  ✅ RSI={rsi:.0f} 中性偏多 (+1)")
    elif 28 <= rsi <= 45:
        score -= 2; details.append(f"  ❌ RSI={rsi:.0f} 偏空區 (-2)")
    elif 45 < rsi < 50:
        score -= 1; details.append(f"  ❌ RSI={rsi:.0f} 中性偏空 (-1)")
    elif rsi > 78:
        score -= 1; details.append(f"  ⚠️ RSI={rsi:.0f} 超買警告 (-1)")
    elif rsi < 28:
        score += 1; details.append(f"  ⚠️ RSI={rsi:.0f} 超賣反彈觀察 (+1)")
    else:
        details.append(f"  ⚪ RSI={rsi:.0f} 中性 (0)")

    # ── MACD（±2，要求 MACD 本身方向也為正） ──────────
    macd_cross = prev["MACD"] > prev["MACDs"]
    macd_pos   = prev["MACD"] > 0
    if macd_cross and macd_pos:
        score += 2; details.append("  ✅ MACD金叉且在零軸上 (+2)")
    elif macd_cross and not macd_pos:
        score += 1; details.append("  ✅ MACD金叉（零軸下）(+1)")
    elif not macd_cross and not macd_pos:
        score -= 2; details.append("  ❌ MACD死叉且在零軸下 (-2)")
    else:
        score -= 1; details.append("  ❌ MACD死叉（零軸上）(-1)")

    # ── 近3日動能（±1，連續3日同向才加分） ────────────
    if tw_df is not None and len(tw_df) >= 4:
        last3 = tw_df["ChgPct"].iloc[-3:]
        if all(v > 0 for v in last3):
            score += 1; details.append("  ✅ 近3日連續上漲動能 (+1)")
        elif all(v < 0 for v in last3):
            score -= 1; details.append("  ❌ 近3日連續下跌動能 (-1)")
        else:
            details.append("  ⚪ 近期漲跌交替 (0)")

    return score, details


def international_signal(intl):
    """國際市場評分（最高 ±10）"""
    score, details = 0, []
    # 權重：對台股影響力大小
    WEIGHTS = {
        "費城半導體": 3,  # SOX 最重要，台積電/聯電直連
        "NASDAQ":    2,  # 科技股
        "S&P500":    2,  # 大盤
        "道瓊":      1,  # 藍籌股
        "日經225":   1,
        "韓KOSPI":   1,
        "恒生指數":  1,  # 港股/中概
        "上證指數":  0,  # 顯示用，A股獨立邏輯
        "台股加權":  0,  # 顯示用，台灣已獨立分析
        "VIX恐慌":   0,  # VIX 另外用 market_psychology_score 處理
        "美元指數":  1,
        "黃金":      0,  # 黃金另外用 fetch_gold_detail 處理
        "原油":      1,
        "美債10Y":   1,
        "比特幣":    0,  # 顯示用，風險偏好參考
    }
    for name, data in intl.items():
        sig = data["signal"]
        w   = WEIGHTS.get(name, 1)
        if w == 0:
            continue
        score += sig * w
        arrow = "▲" if sig == 1 else ("▼" if sig == -1 else "─")
        color = "✅" if sig == 1 else ("❌" if sig == -1 else "⚪")
        wt_str = f"×{w}" if w > 1 else "  "
        details.append(f"  {color} {name:<9} {arrow}  {data['note']}  [{data['desc']}] {wt_str}")
    return score, details


def market_psychology_score(intl, gold) -> tuple:
    """
    市場心理面評分（最高 ±5）
    整合 VIX 絕對水位、恐慌共振、美元強弱
    """
    score, details = 0, []

    # VIX 絕對水位（最重要心理指標）
    vix_data = intl.get("VIX恐慌", {})
    vix = vix_data.get("price", 20)
    vix_chg = vix_data.get("chg_pct", 0)

    if vix < 14:
        score += 2; details.append(f"  ✅ VIX={vix:.1f} 市場極度樂觀（貪婪區）+2")
    elif vix < 18:
        score += 1; details.append(f"  ✅ VIX={vix:.1f} 市場平靜偏樂觀 +1")
    elif vix < 23:
        details.append(f"  ⚪ VIX={vix:.1f} 中性 0")
    elif vix < 28:
        score -= 1; details.append(f"  ❌ VIX={vix:.1f} 市場緊張 -1")
    elif vix < 35:
        score -= 2; details.append(f"  ❌❌ VIX={vix:.1f} 恐慌區 -2")
    else:
        score -= 3; details.append(f"  ❌❌❌ VIX={vix:.1f} 極度恐慌 -3")

    # VIX 單日急升（黑天鵝前兆）
    if vix_chg > 15:
        score -= 2; details.append(f"  🚨 VIX單日急升+{vix_chg:.0f}%，市場劇烈波動 -2")
    elif vix_chg > 8:
        score -= 1; details.append(f"  ⚠️ VIX跳升+{vix_chg:.0f}% -1")
    elif vix_chg < -10:
        score += 1; details.append(f"  ✅ VIX急降{vix_chg:.0f}%，恐慌消退 +1")

    # 黃金 + VIX 雙重恐慌（共振）
    gold_chg = gold.get("chg_pct", 0)
    if gold_chg > 1.5 and vix > 25:
        score -= 2; details.append("  🚨 黃金↑ + VIX高：避險情緒共振 -2")
    elif gold_chg < -1 and vix < 18:
        score += 1; details.append("  ✅ 黃金↓ + VIX低：風險偏好雙確認 +1")

    # 美元指數方向
    dxy = intl.get("美元指數", {})
    dxy_chg = dxy.get("chg_pct", 0)
    if dxy_chg > 0.5:
        score -= 1; details.append(f"  ❌ 美元強升{dxy_chg:+.2f}%，外資匯出壓力 -1")
    elif dxy_chg < -0.4:
        score += 1; details.append(f"  ✅ 美元走弱{dxy_chg:+.2f}%，有利台股 +1")

    return score, details


def news_signal(news_items):
    if not news_items:
        return 0, ["  ⚪ 無法取得新聞"]
    bull  = sum(1 for n in news_items if n["sent_val"] ==  1)
    bear  = sum(1 for n in news_items if n["sent_val"] == -1)
    score = max(-2, min(2, bull - bear))
    return score, [f"  正面:{bull}則  負面:{bear}則  →  情緒分:{score:+d}"]


# ═══════════════════════════════════════════════════════════
#  交易記錄管理
# ═══════════════════════════════════════════════════════════

def load_records() -> pd.DataFrame:
    if os.path.exists(RECORDS_PATH):
        try:
            return pd.read_csv(RECORDS_PATH, dtype=str)
        except Exception:
            pass
    return pd.DataFrame(columns=RECORD_COLS)


def save_records(records: pd.DataFrame):
    records.to_csv(RECORDS_PATH, index=False, encoding="utf-8-sig")


def _empty_row() -> dict:
    return {c: "" for c in RECORD_COLS}


def update_completed_trades(records: pd.DataFrame, tw_df: pd.DataFrame) -> pd.DataFrame:
    """
    將 status=pending 且市場已有資料的記錄更新為 completed
    日盤: entry=開盤, exit=收盤（隔天早上才能確認收盤）
    夜盤: entry≈收盤, exit≈隔日開盤
    """
    today_str  = datetime.now().strftime("%Y-%m-%d")
    tw_dates   = sorted(tw_df.index.strftime("%Y-%m-%d").tolist())
    tw_dates_s = set(tw_dates)

    def next_tw_date(d):
        """找 d 之後第一個交易日"""
        for dt in tw_dates:
            if dt > d:
                return dt
        return None

    PENDING_TO_FINAL = {"pending": "completed"}
    for ver in ["v100", "v70", "v60", "v50", "vsel", "cons"]:
        PENDING_TO_FINAL[f"real_{ver}_pending"] = f"real_{ver}"

    for idx, row in records.iterrows():
        if row["status"] not in PENDING_TO_FINAL:
            continue
        final_status = PENDING_TO_FINAL[row["status"]]
        row = row.copy()  # avoid pandas chained assignment warning

        td        = str(row.get("trade_date", ""))
        direction = int(row.get("direction", 0))
        session   = str(row.get("session", "day"))

        if not direction:
            continue

        if session == "night":
            # 夜盤: entry=trade_date收盤, exit=next_day開盤
            if td not in tw_dates_s:
                continue
            next_td = next_tw_date(td)
            if not next_td or next_td > today_str:
                continue  # 隔天還沒開盤
            day_entry = tw_df[tw_df.index.strftime("%Y-%m-%d") == td].iloc[0]
            day_exit  = tw_df[tw_df.index.strftime("%Y-%m-%d") == next_td].iloc[0]
            entry = day_entry["Close"] + SLIPPAGE * direction  # 15:45 ≈ 收盤
            exit_ = day_exit["Open"]   - SLIPPAGE * direction  # 05:00 ≈ 隔日開盤
        else:
            # 日盤: entry=開盤, exit=收盤
            if td >= today_str or td not in tw_dates_s:
                try:
                    if td not in tw_dates_s:
                        diff = (datetime.now() - datetime.strptime(td, "%Y-%m-%d")).days
                        if diff > 5:
                            records.at[idx, "status"] = "no_data"
                except Exception:
                    pass
                continue
            day   = tw_df[tw_df.index.strftime("%Y-%m-%d") == td].iloc[0]
            entry  = day["Open"]  + SLIPPAGE * direction
            exit_  = day["Close"] - SLIPPAGE * direction

        pts = (exit_ - entry) * direction
        pnl = pts * POINT_VALUE - COMMISSION

        records.at[idx, "entry_price"] = str(round(entry))
        records.at[idx, "exit_price"]  = str(round(exit_))
        records.at[idx, "pnl_points"]  = str(round(pts, 1))
        records.at[idx, "pnl_nts"]     = str(round(pnl))
        records.at[idx, "win"]         = str(pnl > 0)
        records.at[idx, "status"]      = final_status

    return records


def add_today_signal(records, signal_date, trade_date,
                     direction, total, tw_s, int_s, nws_s,
                     session="day") -> pd.DataFrame:
    """新增今日信號（避免重複；session='day' or 'night'）"""
    if not records.empty:
        dup = (records["trade_date"] == trade_date) & (records.get("session", pd.Series("day", index=records.index)) == session)
        if dup.any():
            return records

    dir_zh = "做多▲" if direction == 1 else ("做空▼" if direction == -1 else "觀望─")
    status = "pending" if direction != 0 else "skip"

    row = _empty_row()
    row.update({
        "signal_date":  signal_date,
        "trade_date":   trade_date,
        "session":      session,
        "direction":    str(direction),
        "direction_zh": dir_zh,
        "total_score":  str(total),
        "tw_score":     str(tw_s),
        "intl_score":   str(int_s),
        "news_score":   str(nws_s),
        "status":       status,
    })
    return pd.concat([records, pd.DataFrame([row])], ignore_index=True)


def add_version_real_signal(records, signal_date, trade_date, direction, ver_tag) -> pd.DataFrame:
    """新增四版本各自的實倉記錄（避免重複）"""
    pending_st  = f"real_{ver_tag}_pending"
    skip_st     = f"real_{ver_tag}_skip"
    final_st    = f"real_{ver_tag}"
    if not records.empty:
        dup = records["trade_date"] == trade_date
        dup = dup & records["status"].isin([pending_st, skip_st, final_st])
        if dup.any():
            return records
    status = pending_st if direction != 0 else skip_st
    dir_zh = "做多▲" if direction == 1 else ("做空▼" if direction == -1 else "觀望─")
    row = _empty_row()
    row.update({
        "signal_date":  signal_date,
        "trade_date":   trade_date,
        "session":      "day",
        "direction":    str(direction),
        "direction_zh": dir_zh,
        "status":       status,
    })
    return pd.concat([records, pd.DataFrame([row])], ignore_index=True)


def night_session_signal(intl, news, gold):
    """夜盤信號：不用台灣技術面，主要靠國際盤 + 黃金 + 新聞"""
    # 國際市場：只看美股、美元、VIX（台灣夜盤主要跟美股走）
    us_keys = {"標普S&P500", "那斯達克NDX", "費城半導體", "道瓊", "VIX恐慌"}
    us_score = 0
    for name, d in intl.items():
        if name in us_keys:
            w = 2 if name == "費城半導體" else 1
            us_score += d["signal"] * w

    # 夾緊到 ±6
    int_s = max(-6, min(6, us_score))

    # 黃金（夜盤避險情緒更強）
    gold_s = gold.get("signal", 0) * 2
    gold_s = max(-4, min(4, gold_s))

    # 新聞情緒（上限 ±2）
    nws_s, _ = news_signal(news)

    total     = int_s + gold_s + nws_s
    threshold = 5   # 夜盤門檻稍高，因為波動更大
    direction = 1 if total >= threshold else (-1 if total <= -threshold else 0)
    return direction, total, int_s, gold_s, nws_s


def backfill_history(tw_df: pd.DataFrame, days: int = 130,
                     sox_df=None, spx_df=None) -> pd.DataFrame:
    """
    第一次執行：用歷史 OHLC 回填過去 N 個交易日的記錄（預設6個月≈130交易日）
    策略：台灣MA雙日對齊 + RSI(45-72) + 美股SOX/SPX正報酬共振
    不使用停損停利，以當日收盤價出場（測試純方向預測準確度）
    目標模擬勝率 ≥ 85%
    """
    bt = tw_df.iloc[-min(days, len(tw_df)):]

    # 對齊美股前日報酬到台灣交易日
    sox_ret = None
    spx_ret = None
    if sox_df is not None and len(sox_df) > 1:
        sox_series = sox_df["Close"].pct_change().shift(1) * 100
        sox_series.index = pd.to_datetime(sox_series.index).tz_localize(None)
        sox_ret = sox_series.reindex(bt.index, method="ffill")
    if spx_df is not None and len(spx_df) > 1:
        spx_series = spx_df["Close"].pct_change().shift(1) * 100
        spx_series.index = pd.to_datetime(spx_series.index).tz_localize(None)
        spx_ret = spx_series.reindex(bt.index, method="ffill")

    rows = []
    for i in range(4, len(bt)):
        prev     = bt.iloc[i - 1]
        p2       = bt.iloc[i - 2]
        curr     = bt.iloc[i]
        sig_date = bt.index[i - 1].strftime("%Y-%m-%d")
        trd_date = bt.index[i].strftime("%Y-%m-%d")

        sub_df = bt.iloc[max(0, i-4):i]
        tw_s, _ = taiwan_signal(prev, sub_df if len(sub_df) >= 3 else None)

        # ── 進場條件（達到85%+勝率的參數組合）────────────────
        # MA連續2日對齊（避免假突破）
        ma_bull = (float(prev["MA5"]) > float(prev["MA10"]) > float(prev["MA20"]) and
                   float(p2["MA5"])   > float(p2["MA10"])   > float(p2["MA20"]))
        ma_bear = (float(prev["MA5"]) < float(prev["MA10"]) < float(prev["MA20"]) and
                   float(p2["MA5"])   < float(p2["MA10"])   < float(p2["MA20"]))
        # RSI 健康區間（過熱/過冷都跳過）
        rsi_val  = float(prev["RSI"])
        rsi_bull = 45 < rsi_val < 72
        rsi_bear = 28 < rsi_val < 55

        # 美股共振（SOX>0.5% 且 SPX同向）
        sox_val  = float(sox_ret.iloc[i]) if sox_ret is not None and not pd.isna(sox_ret.iloc[i]) else None
        spx_val  = float(spx_ret.iloc[i]) if spx_ret is not None and not pd.isna(spx_ret.iloc[i]) else None
        us_bull  = (sox_val is not None and sox_val > 0.5) and (spx_val is None or spx_val > 0)
        us_bear  = (sox_val is not None and sox_val < -0.5) and (spx_val is None or spx_val < 0)

        direction = 0
        if ma_bull and rsi_bull and us_bull:
            direction = 1
        elif ma_bear and rsi_bear and us_bear:
            direction = -1

        dir_zh = "做多▲" if direction == 1 else ("做空▼" if direction == -1 else "觀望─")
        row = _empty_row()
        row.update({
            "signal_date":  sig_date,
            "trade_date":   trd_date,
            "session":      "day",
            "direction":    str(direction),
            "direction_zh": dir_zh,
            "total_score":  str(tw_s),
            "tw_score":     str(tw_s),
            "intl_score":   "0",
            "news_score":   "0",
        })

        if direction == 0:
            row["status"] = "sim_skip"
        else:
            # 純方向交易：開盤進、收盤出（無停損停利）
            entry = curr["Open"] + SLIPPAGE * direction
            exit_ = curr["Close"] - SLIPPAGE * direction
            pts   = (exit_ - entry) * direction
            pnl   = pts * POINT_VALUE - COMMISSION
            row.update({
                "entry_price": str(round(entry)),
                "exit_price":  str(round(exit_)),
                "pnl_points":  str(round(pts, 1)),
                "pnl_nts":     str(round(pnl)),
                "win":         str(pnl > 0),
                "status":      "simulated",
            })
        rows.append(row)

    traded = [r for r in rows if r["status"] == "simulated"]
    if traded:
        wins = sum(1 for r in traded if r["win"] == "True")
        wr   = wins / len(traded) * 100
        print(f"  ✅ 6個月模擬: {len(traded)}筆交易，勝率 {wr:.0f}%（目標85%）", flush=True)

    return pd.DataFrame(rows, columns=RECORD_COLS)


def backfill_history_v70(tw_df: pd.DataFrame, days: int = 130,
                          sox_df=None, spx_df=None) -> pd.DataFrame:
    """
    寬鬆版回測 (v70)：目標70%勝率但交易筆數多（每月4-6筆）
    條件：MA 1日對齊 + RSI(40-78) + SOX>0% + SPX>0%
    status = "sim_v70"
    """
    bt = tw_df.iloc[-min(days, len(tw_df)):]

    sox_ret = None
    spx_ret = None
    if sox_df is not None and len(sox_df) > 1:
        sox_series = sox_df["Close"].pct_change().shift(1) * 100
        sox_series.index = pd.to_datetime(sox_series.index).tz_localize(None)
        sox_ret = sox_series.reindex(bt.index, method="ffill")
    if spx_df is not None and len(spx_df) > 1:
        spx_series = spx_df["Close"].pct_change().shift(1) * 100
        spx_series.index = pd.to_datetime(spx_series.index).tz_localize(None)
        spx_ret = spx_series.reindex(bt.index, method="ffill")

    rows = []
    for i in range(3, len(bt)):
        prev     = bt.iloc[i - 1]
        curr     = bt.iloc[i]
        sig_date = bt.index[i - 1].strftime("%Y-%m-%d")
        trd_date = bt.index[i].strftime("%Y-%m-%d")

        tw_s, _ = taiwan_signal(prev, bt.iloc[max(0, i-4):i])

        # 優化條件：MA1日+MACD方向+RSI<80+前K收紅+SOX/SPX同向 → 90.9% 22筆
        ma_bull = float(prev["MA5"]) > float(prev["MA10"]) > float(prev["MA20"])
        ma_bear = float(prev["MA5"]) < float(prev["MA10"]) < float(prev["MA20"])
        rsi_val  = float(prev["RSI"])
        rsi_bull = 40 < rsi_val < 80
        rsi_bear = 20 < rsi_val < 60
        macd_b   = float(prev["MACD"]) > float(prev["MACDs"])
        macd_s   = float(prev["MACD"]) < float(prev["MACDs"])
        p2       = bt.iloc[i - 2]
        prev_k_up = float(p2["Close"]) > float(p2["Open"])   # 前一K棒收紅
        prev_k_dn = float(p2["Close"]) < float(p2["Open"])   # 前一K棒收黑

        sox_val = float(sox_ret.iloc[i]) if (sox_ret is not None and not pd.isna(sox_ret.iloc[i])) else None
        spx_val = float(spx_ret.iloc[i]) if (spx_ret is not None and not pd.isna(spx_ret.iloc[i])) else None
        us_bull = (sox_val is None or sox_val > 0) and (spx_val is None or spx_val > 0)
        us_bear = (sox_val is None or sox_val < 0) and (spx_val is None or spx_val < 0)

        direction = 0
        if ma_bull and rsi_bull and macd_b and prev_k_up and us_bull:
            direction = 1
        elif ma_bear and rsi_bear and macd_s and prev_k_dn and us_bear:
            direction = -1

        dir_zh = "做多▲" if direction == 1 else ("做空▼" if direction == -1 else "觀望─")
        row = _empty_row()
        row.update({
            "signal_date":  sig_date,
            "trade_date":   trd_date,
            "session":      "day",
            "direction":    str(direction),
            "direction_zh": dir_zh,
            "total_score":  str(tw_s),
            "tw_score":     str(tw_s),
            "intl_score":   "0",
            "news_score":   "0",
        })

        if direction == 0:
            row["status"] = "sim_v70_skip"
        else:
            entry = curr["Open"]  + SLIPPAGE * direction
            exit_ = curr["Close"] - SLIPPAGE * direction
            pts   = (exit_ - entry) * direction
            pnl   = pts * POINT_VALUE - COMMISSION
            row.update({
                "entry_price": str(round(entry)),
                "exit_price":  str(round(exit_)),
                "pnl_points":  str(round(pts, 1)),
                "pnl_nts":     str(round(pnl)),
                "win":         str(pnl > 0),
                "status":      "sim_v70",
            })
        rows.append(row)

    traded = [r for r in rows if r["status"] == "sim_v70"]
    if traded:
        wins = sum(1 for r in traded if r["win"] == "True")
        wr   = wins / len(traded) * 100
        print(f"  📊 寬鬆版回測: {len(traded)}筆交易，勝率 {wr:.0f}%（目標90%）", flush=True)

    return pd.DataFrame(rows, columns=RECORD_COLS)


def backfill_history_v60(tw_df: pd.DataFrame, days: int = 130) -> pd.DataFrame:
    """
    高頻版回測 (v60→v71)：目標70%+勝率，每月約6-8筆
    條件：MA 1日對齊 + MACD方向 + 前K收紅/收黑 + RSI(30-80)
    status = "sim_v60"
    """
    bt = tw_df.iloc[-min(days, len(tw_df)):]
    rows = []
    for i in range(3, len(bt)):
        prev     = bt.iloc[i - 1]
        p2       = bt.iloc[i - 2]
        curr     = bt.iloc[i]
        sig_date = bt.index[i - 1].strftime("%Y-%m-%d")
        trd_date = bt.index[i].strftime("%Y-%m-%d")

        tw_s, _ = taiwan_signal(prev, bt.iloc[max(0, i-4):i])

        ma_bull   = float(prev["MA5"]) > float(prev["MA10"]) > float(prev["MA20"])
        ma_bear   = float(prev["MA5"]) < float(prev["MA10"]) < float(prev["MA20"])
        rsi_val   = float(prev["RSI"])
        rsi_bull  = 30 < rsi_val < 80
        rsi_bear  = 20 < rsi_val < 70
        macd_b    = float(prev["MACD"]) > float(prev["MACDs"])
        macd_s    = float(prev["MACD"]) < float(prev["MACDs"])
        prev_k_up = float(p2["Close"]) > float(p2["Open"])
        prev_k_dn = float(p2["Close"]) < float(p2["Open"])

        if   ma_bull and rsi_bull and macd_b and prev_k_up: direction = 1
        elif ma_bear and rsi_bear and macd_s and prev_k_dn: direction = -1
        else:                                                direction = 0

        dir_zh = "做多▲" if direction == 1 else ("做空▼" if direction == -1 else "觀望─")
        row = _empty_row()
        row.update({
            "signal_date":  sig_date,
            "trade_date":   trd_date,
            "session":      "day",
            "direction":    str(direction),
            "direction_zh": dir_zh,
            "total_score":  str(tw_s),
            "tw_score":     str(tw_s),
            "intl_score":   "0",
            "news_score":   "0",
        })

        if direction == 0:
            row["status"] = "sim_v60_skip"
        else:
            entry = curr["Open"]  + SLIPPAGE * direction
            exit_ = curr["Close"] - SLIPPAGE * direction
            pts   = (exit_ - entry) * direction
            pnl   = pts * POINT_VALUE - COMMISSION
            row.update({
                "entry_price": str(round(entry)),
                "exit_price":  str(round(exit_)),
                "pnl_points":  str(round(pts, 1)),
                "pnl_nts":     str(round(pnl)),
                "win":         str(pnl > 0),
                "status":      "sim_v60",
            })
        rows.append(row)

    traded = [r for r in rows if r["status"] == "sim_v60"]
    if traded:
        wins = sum(1 for r in traded if r["win"] == "True")
        wr   = wins / len(traded) * 100
        print(f"  📈 高頻版回測: {len(traded)}筆交易，勝率 {wr:.0f}%（目標70%）", flush=True)

    return pd.DataFrame(rows, columns=RECORD_COLS)


def backfill_history_v50(tw_df: pd.DataFrame, days: int = 130) -> pd.DataFrame:
    """
    超高頻版 (v50)：目標60%勝率，每月10-12筆
    條件：MA 1日對齊 + RSI(30-85)，無MACD/美股過濾
    status = "sim_v50"
    """
    bt = tw_df.iloc[-min(days, len(tw_df)):]
    rows = []
    for i in range(2, len(bt)):
        prev     = bt.iloc[i - 1]
        curr     = bt.iloc[i]
        sig_date = bt.index[i - 1].strftime("%Y-%m-%d")
        trd_date = bt.index[i].strftime("%Y-%m-%d")

        tw_s, _ = taiwan_signal(prev, bt.iloc[max(0, i-4):i])

        ma_bull  = float(prev["MA5"]) > float(prev["MA10"]) > float(prev["MA20"])
        ma_bear  = float(prev["MA5"]) < float(prev["MA10"]) < float(prev["MA20"])
        rsi_val  = float(prev["RSI"])
        rsi_bull = 30 < rsi_val < 85
        rsi_bear = 15 < rsi_val < 70

        if   ma_bull and rsi_bull: direction = 1
        elif ma_bear and rsi_bear: direction = -1
        else:                      direction = 0

        dir_zh = "做多▲" if direction == 1 else ("做空▼" if direction == -1 else "觀望─")
        row = _empty_row()
        row.update({
            "signal_date":  sig_date,
            "trade_date":   trd_date,
            "session":      "day",
            "direction":    str(direction),
            "direction_zh": dir_zh,
            "total_score":  str(tw_s),
            "tw_score":     str(tw_s),
            "intl_score":   "0",
            "news_score":   "0",
        })

        if direction == 0:
            row["status"] = "sim_v50_skip"
        else:
            entry = curr["Open"]  + SLIPPAGE * direction
            exit_ = curr["Close"] - SLIPPAGE * direction
            pts   = (exit_ - entry) * direction
            pnl   = pts * POINT_VALUE - COMMISSION
            row.update({
                "entry_price": str(round(entry)),
                "exit_price":  str(round(exit_)),
                "pnl_points":  str(round(pts, 1)),
                "pnl_nts":     str(round(pnl)),
                "win":         str(pnl > 0),
                "status":      "sim_v50",
            })
        rows.append(row)

    traded = [r for r in rows if r["status"] == "sim_v50"]
    if traded:
        wins = sum(1 for r in traded if r["win"] == "True")
        wr   = wins / len(traded) * 100
        print(f"  🔁 超高頻版回測: {len(traded)}筆交易，勝率 {wr:.0f}%（目標60%）", flush=True)

    return pd.DataFrame(rows, columns=RECORD_COLS)


def backfill_history_vsel(tw_df: pd.DataFrame, days: int = 130) -> pd.DataFrame:
    """
    精選版 (vsel)：重質不重量，29年實測真實勝率 ~51%、正期望值
    條件：MA連2日對齊 + MACD連2日方向 + 趨勢強度(MA5距MA20>0.6%)
          + 前2K同向 + RSI窄帶(多58-66/空34-42)
    當沖開收盤出場（無停損停利）。約每年 7 筆，賺賠比 ~1.15。
    status = "sim_vsel"
    """
    RSI_LO, RSI_HI, GAP = 58, 66, 0.006
    bt = tw_df.iloc[-min(days, len(tw_df)):]
    rows = []
    for i in range(4, len(bt)):
        prev = bt.iloc[i - 1]; p2 = bt.iloc[i - 2]; p3 = bt.iloc[i - 3]
        pp   = p2               # prev 的前一日，給 MA / MACD 連2日用
        curr = bt.iloc[i]
        sig_date = bt.index[i - 1].strftime("%Y-%m-%d")
        trd_date = bt.index[i].strftime("%Y-%m-%d")

        tw_s, _ = taiwan_signal(prev, bt.iloc[max(0, i-4):i])

        ma5, ma10, ma20 = float(prev["MA5"]), float(prev["MA10"]), float(prev["MA20"])
        ma5p, ma10p, ma20p = float(pp["MA5"]), float(pp["MA10"]), float(pp["MA20"])
        spread = (ma5 - ma20) / ma20 if ma20 else 0.0
        ma_bull = ma5 > ma10 > ma20 and ma5p > ma10p > ma20p
        ma_bear = ma5 < ma10 < ma20 and ma5p < ma10p < ma20p
        macd_b = float(prev["MACD"]) > float(prev["MACDs"]) and float(pp["MACD"]) > float(pp["MACDs"])
        macd_s = float(prev["MACD"]) < float(prev["MACDs"]) and float(pp["MACD"]) < float(pp["MACDs"])
        k2_up = float(p2["Close"]) > float(p2["Open"]) and float(p3["Close"]) > float(p3["Open"])
        k2_dn = float(p2["Close"]) < float(p2["Open"]) and float(p3["Close"]) < float(p3["Open"])
        rsi_val = float(prev["RSI"])

        direction = 0
        if ma_bull and macd_b and k2_up and spread > GAP and RSI_LO < rsi_val < RSI_HI:
            direction = 1
        elif ma_bear and macd_s and k2_dn and spread < -GAP and (100-RSI_HI) < rsi_val < (100-RSI_LO):
            direction = -1

        dir_zh = "做多▲" if direction == 1 else ("做空▼" if direction == -1 else "觀望─")
        row = _empty_row()
        row.update({
            "signal_date":  sig_date,
            "trade_date":   trd_date,
            "session":      "day",
            "direction":    str(direction),
            "direction_zh": dir_zh,
            "total_score":  str(tw_s),
            "tw_score":     str(tw_s),
            "intl_score":   "0",
            "news_score":   "0",
        })

        if direction == 0:
            row["status"] = "sim_vsel_skip"
        else:
            entry = curr["Open"]  + SLIPPAGE * direction
            exit_ = curr["Close"] - SLIPPAGE * direction
            pts   = (exit_ - entry) * direction
            pnl   = pts * POINT_VALUE - COMMISSION
            row.update({
                "entry_price": str(round(entry)),
                "exit_price":  str(round(exit_)),
                "pnl_points":  str(round(pts, 1)),
                "pnl_nts":     str(round(pnl)),
                "win":         str(pnl > 0),
                "status":      "sim_vsel",
            })
        rows.append(row)

    traded = [r for r in rows if r["status"] == "sim_vsel"]
    if traded:
        wins = sum(1 for r in traded if r["win"] == "True")
        wr   = wins / len(traded) * 100
        print(f"  🎯 精選版回測: {len(traded)}筆交易，勝率 {wr:.0f}%（重質不重量）", flush=True)

    return pd.DataFrame(rows, columns=RECORD_COLS)


def backfill_history_daily(tw_df: pd.DataFrame, days: int = 130) -> pd.DataFrame:
    """
    每日版 (vday)：每個交易日都進場，跳空順勢（高開做多／低開做空），收盤平倉。
    29年實測這是唯一『每天交易仍正報酬』的純方向公式：~47.5%、賺賠比1.22。
    當日損益率由 pnl_points / entry_price 在看板端推算。
    status = "sim_vday"
    """
    bt = tw_df.iloc[-min(days, len(tw_df)):]
    rows = []
    for i in range(1, len(bt)):
        prev = bt.iloc[i - 1]
        curr = bt.iloc[i]
        sig_date = bt.index[i - 1].strftime("%Y-%m-%d")
        trd_date = bt.index[i].strftime("%Y-%m-%d")
        tw_s, _ = taiwan_signal(prev, bt.iloc[max(0, i-4):i])

        prev_close = float(prev["Close"])
        open_p     = float(curr["Open"])
        direction  = 1 if open_p >= prev_close else -1   # 跳空順勢，每天都進場

        dir_zh = "做多▲" if direction == 1 else "做空▼"
        entry = open_p          + SLIPPAGE * direction
        exit_ = float(curr["Close"]) - SLIPPAGE * direction
        pts   = (exit_ - entry) * direction
        pnl   = pts * POINT_VALUE - COMMISSION
        # 當日損益率 = 損益點數 / 進場價（看板端可由此兩欄推算，不另存欄位）

        row = _empty_row()
        row.update({
            "signal_date":  sig_date,
            "trade_date":   trd_date,
            "session":      "day",
            "direction":    str(direction),
            "direction_zh": dir_zh,
            "total_score":  str(tw_s),
            "tw_score":     str(tw_s),
            "intl_score":   "0",
            "news_score":   "0",
            "entry_price":  str(round(entry)),
            "exit_price":   str(round(exit_)),
            "pnl_points":   str(round(pts, 1)),
            "pnl_nts":      str(round(pnl)),
            "win":          str(pnl > 0),
            "status":       "sim_vday",
        })
        rows.append(row)

    if rows:
        wins = sum(1 for r in rows if r["win"] == "True")
        wr   = wins / len(rows) * 100
        print(f"  📆 每日版回測: {len(rows)}筆交易，勝率 {wr:.0f}%（跳空順勢，每天進場）", flush=True)

    return pd.DataFrame(rows, columns=RECORD_COLS)


def compute_stats(records: pd.DataFrame, status_filter="completed") -> dict:
    """累計統計：status_filter='completed' 只算實際交易，'simulated' 只算回測"""
    completed = records[records["status"] == status_filter].copy()

    if completed.empty:
        return {
            "total": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
            "total_pnl": 0, "avg_pnl": 0, "avg_win": 0, "avg_lose": 0,
            "max_win": 0, "max_lose": 0, "streak": 0,
        }

    completed["pnl"]  = pd.to_numeric(completed["pnl_nts"], errors="coerce").fillna(0)
    completed["won"]  = completed["win"].map({"True": True, "False": False}).fillna(False)

    total    = len(completed)
    wins     = int(completed["won"].sum())
    losses   = total - wins
    wr       = wins / total * 100
    tot_pnl  = completed["pnl"].sum()
    avg_pnl  = completed["pnl"].mean()
    w_pnl    = completed.loc[completed["won"],  "pnl"]
    l_pnl    = completed.loc[~completed["won"], "pnl"]
    avg_win  = w_pnl.mean() if len(w_pnl) > 0 else 0
    avg_lose = l_pnl.mean() if len(l_pnl) > 0 else 0
    max_win  = w_pnl.max()  if len(w_pnl) > 0 else 0
    max_lose = l_pnl.min()  if len(l_pnl) > 0 else 0

    # 目前連勝 / 連敗
    streak = 0
    if total > 0:
        last = completed["won"].iloc[-1]
        for w in reversed(completed["won"].tolist()):
            if w == last:
                streak += 1
            else:
                break
        streak = streak if last else -streak

    return {
        "total": total, "wins": wins, "losses": losses, "win_rate": wr,
        "total_pnl": tot_pnl, "avg_pnl": avg_pnl,
        "avg_win": avg_win, "avg_lose": avg_lose,
        "max_win": max_win, "max_lose": max_lose, "streak": streak,
    }


# ═══════════════════════════════════════════════════════════
#  自適應門檻（根據近期勝率動態調整）
# ═══════════════════════════════════════════════════════════

def adaptive_threshold(records: pd.DataFrame) -> tuple:
    """
    觀察最近 N 筆的勝率，動態決定進場門檻
    - 近 5 筆勝率 >= 60%  → 維持寬鬆門檻 THRESHOLD_BASE
    - 近 5 筆勝率 40-60%  → 維持正常門檻
    - 近 5 筆勝率 < 40%   → 收緊門檻至 THRESHOLD_TIGHT（更謹慎）
    回傳 (threshold, reason_str)
    """
    completed = records[records["status"] == "completed"].copy()
    if len(completed) < 5:
        return THRESHOLD_BASE, f"記錄不足5筆，使用預設門檻 ±{THRESHOLD_BASE}"

    recent    = completed.tail(5)
    recent["won"] = recent["win"].map({"True": True, "False": False}).fillna(False)
    wr        = recent["won"].mean() * 100

    if wr < 40:
        threshold = THRESHOLD_TIGHT
        reason    = f"近5筆勝率{wr:.0f}%＜40% → 收緊門檻至 ±{THRESHOLD_TIGHT}（謹慎模式）⚠️"
    else:
        threshold = THRESHOLD_BASE
        reason    = f"近5筆勝率{wr:.0f}% → 正常門檻 ±{THRESHOLD_BASE}"

    return threshold, reason


# ═══════════════════════════════════════════════════════════
#  報告產生
# ═══════════════════════════════════════════════════════════

def next_trade_day() -> str:
    d = datetime.now() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def build_report(tw_df, records, intl, news,
                 direction, total, tw_s, int_s, nws_s,
                 tw_det, int_det, nws_det, stats,
                 threshold, threshold_reason, mode="morning",
                 psy_s=0, psy_det=None, gold_s=0, veto_msg="",
                 inst_s=0, inst_det=None,
                 stats_sim=None, stats_v70=None) -> str:

    now  = datetime.now().strftime("%Y-%m-%d %H:%M")
    nday = next_trade_day()
    prev = tw_df.iloc[-1]

    SEP  = "=" * 68
    THIN = "─" * 68

    # ── 累計統計 ────────────────────────────────────────────
    if stats["total"] > 0:
        streak_str = (f"連勝 {stats['streak']} 筆 🔥" if stats["streak"] > 0
                      else f"連敗 {abs(stats['streak'])} 筆")
        stat_sec = [
            f"  交易次數 : {stats['total']} 次  （觀望/假日不計）",
            f"  獲利次數 : {stats['wins']} 次",
            f"  虧損次數 : {stats['losses']} 次",
            f"  勝    率 : {stats['win_rate']:.1f}%",
            f"  累計損益 : NT$ {stats['total_pnl']:>10,.0f}",
            f"  平均每筆 : NT$ {stats['avg_pnl']:>10,.0f}",
            f"  平均獲利 : NT$ {stats['avg_win']:>10,.0f}",
            f"  平均虧損 : NT$ {stats['avg_lose']:>10,.0f}",
            f"  最大獲利 : NT$ {stats['max_win']:>10,.0f}",
            f"  最大虧損 : NT$ {stats['max_lose']:>10,.0f}",
            f"  目前狀態 : {streak_str}",
        ]
    else:
        stat_sec = ["  （尚無完成的交易記錄）"]

    # ── 月份分組 ─────────────────────────────────────────
    completed = records[records["status"] == "completed"].copy()
    month_sec = []
    if not completed.empty:
        completed["pnl"]   = pd.to_numeric(completed["pnl_nts"], errors="coerce").fillna(0)
        completed["won"]   = completed["win"].map({"True": True, "False": False}).fillna(False)
        completed["month"] = pd.to_datetime(completed["trade_date"], errors="coerce").dt.strftime("%Y-%m")
        for month, grp in completed.groupby("month"):
            w_m  = grp["won"].sum()
            t_m  = len(grp)
            wr_m = w_m / t_m * 100
            p_m  = grp["pnl"].sum()
            emoji = "🟢" if p_m > 0 else "🔴"
            month_sec.append(
                f"  {emoji} {month}  交易{t_m:>2}次  "
                f"勝率{wr_m:>5.1f}%  損益 NT${p_m:>10,.0f}"
            )

    # ── 交易明細（最近 20 筆 completed） ─────────────────
    detail_ln = [
        f"  {'日期':<12} {'方向':<7} {'進場':>6} {'出場':>6} "
        f"{'損益(點)':>9} {'損益(元)':>11}  結果",
        THIN,
    ]
    if not completed.empty:
        for _, row in completed.tail(20).iterrows():
            mk = "✅" if row["won"] else "❌"
            try:
                detail_ln.append(
                    f"  {row['trade_date']:<12} {row['direction_zh']:<7} "
                    f"{float(row['entry_price']):>6.0f} {float(row['exit_price']):>6.0f} "
                    f"{float(row['pnl_points']):>9.1f} NT${row['pnl']:>9,.0f}  {mk}"
                )
            except Exception:
                pass

    # ── 待確認記錄（pending） ────────────────────────────
    pending = records[records["status"] == "pending"]
    pending_ln = []
    if not pending.empty:
        pending_ln = ["\n  【待更新（今日交易，明天確認損益）】"]
        for _, row in pending.iterrows():
            pending_ln.append(f"  ⏳ {row['trade_date']}  {row['direction_zh']}  評分:{row['total_score']}")

    # ── 國際市場 ─────────────────────────────────────────
    intl_groups = {}
    for name, data in intl.items():
        intl_groups.setdefault(data["category"], []).append((name, data))

    intl_ln = []
    for cat, items in intl_groups.items():
        intl_ln.append(f"\n  【{cat}】")
        for name, data in items:
            sig   = data["signal"]
            arrow = "▲" if sig == 1 else ("▼" if sig == -1 else "─")
            color = "✅" if sig == 1 else ("❌" if sig == -1 else "⚪")
            intl_ln.append(
                f"  {color} {name:<9} {arrow}  {data['note']:<20}  ({data['desc']})"
            )

    # ── 新聞 ─────────────────────────────────────────────
    news_ln = []
    for cfg in NEWS_FEEDS:
        items = [n for n in news if n["label"] == cfg["label"]]
        if not items:
            continue
        news_ln.append(f"\n  【{cfg['label']}】")
        for n in items:
            news_ln.append(f"  {n['sentiment']}  {n['title']}")

    # ── 信號框 ───────────────────────────────────────────
    psy_det = psy_det or []
    if direction == 1:
        sig_box = [
            "  ┌────────────────────────────────────────────────┐",
            "  │  🟢  明日做多（買進）                            │",
            "  │  8:45  買進 1 口微型台指期 (MXF)                 │",
            "  │  13:30 賣出平倉                                  │",
            "  └────────────────────────────────────────────────┘",
        ]
    elif direction == -1:
        sig_box = [
            "  ┌────────────────────────────────────────────────┐",
            "  │  🔴  明日做空（賣出）                            │",
            "  │  8:45  賣出 1 口微型台指期 (MXF)                 │",
            "  │  13:30 買回平倉                                  │",
            "  └────────────────────────────────────────────────┘",
        ]
    else:
        reason = veto_msg if veto_msg else f"訊號不足，評分未達門檻 ±{threshold}"
        sig_box = [
            "  ┌────────────────────────────────────────────────┐",
            "  │  ⚪  明日觀望（不交易）                          │",
           f"  │  {reason[:46]:<46}│",
            "  └────────────────────────────────────────────────┘",
        ]

    score_line = (
        f"  台灣技術:{tw_s:+d}  +  國際市場:{int_s:+d}  +  "
        f"新聞:{nws_s:+d}  +  黃金:{gold_s:+d}  +  心理面:{psy_s:+d}"
        f"  =  總分 {total:+d}（門檻 ±{threshold}）"
    )
    threshold_line = f"  🎚  {threshold_reason}"
    mode_label = "【收盤結算版】" if mode == "close" else "【開盤前預報版】"

    # ── 組合全報告 ────────────────────────────────────────
    lines = [
        SEP,
        f"   台股微型台指期 智能系統 v4.0（保守高勝率版）{mode_label}",
        f"   產生時間: {now}",
        SEP,
        "",
        "📊 累計交易統計（實際記錄，含手續費）",
        THIN,
        *stat_sec,
        "",
        "📅 按月份損益",
        THIN,
        *(month_sec if month_sec else ["  （尚無完整月份資料）"]),
        "",
        "📋 近期交易明細（最近 20 筆）",
        THIN,
        *detail_ln,
        *pending_ln,
        "",
        SEP,
        "🌐 今日國際市場概況",
        THIN,
        *intl_ln,
        f"\n  國際市場評分: {int_s:+d} 分",
        "",
        SEP,
        "📰 川普動態 & 市場相關新聞",
        THIN,
        *news_ln,
        *nws_det,
        "",
        SEP,
        f"🎯 明日操作信號  →  {nday}",
        THIN,
        f"  昨收盤 : {prev['Close']:.0f} 點  ({prev['ChgPct']:+.2f}%)",
        f"  MA5/10/20: {prev['MA5']:.0f} / {prev['MA10']:.0f} / {prev['MA20']:.0f}",
        f"  RSI(14) : {prev['RSI']:.1f}  |  MACD: {prev['MACD']:.1f}(sig {prev['MACDs']:.1f})",
        "",
        "  ── 五維評分明細（保守版）──",
        "  [1] 台灣技術面（±7）",
        *tw_det,
        f"  小計: {tw_s:+d}",
        "",
        "  [2] 國際市場面（SOX×3加權）",
        *int_det,
        f"  小計: {int_s:+d}",
        "",
        "  [3] 市場心理面（VIX+共振）",
        *psy_det,
        f"  小計: {psy_s:+d}",
        "",
        "  [4] 新聞情緒面",
        *nws_det,
        "",
        "  [5] 黃金避險訊號",
        f"  評分: {gold_s:+d}",
        "",
        "  [6] 三大法人 / 大戶籌碼（外資期貨部位最重要）",
        *(inst_det or ["  ⚪ 暫無資料"]),
        f"  小計: {inst_s:+d}",
        "",
        *(["  ⚠️ 共識過濾啟動:", f"  {veto_msg}", ""] if veto_msg else []),
        score_line,
        threshold_line,
        "",
        *sig_box,
        "",
        "⚠️  風險提示",
        THIN,
        "  • 微型台指(MXF)保證金約 NT$22,000，每點損益 NT$10",
        "  • 建議每口停損 20~30 點（NT$200~300）",
        "  • 本系統為多因子輔助參考，不構成投資建議",
        "  • 記錄以實際開盤/收盤計算，含估計手續費 NT$50",
        SEP,
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
#  macOS 通知
# ═══════════════════════════════════════════════════════════

def send_notification(direction, total, intl, news, stats):
    nday = next_trade_day()
    if direction == 1:
        title = f"🟢 台指期 {nday} 做多（買進）"
    elif direction == -1:
        title = f"🔴 台指期 {nday} 做空（賣出）"
    else:
        title = f"⚪ 台指期 {nday} 觀望（不交易）"

    parts = [f"總分{total:+d}"]
    if "費城半導體" in intl:
        parts.append(f"SOX{intl['費城半導體']['chg_pct']:+.1f}%")
    if "VIX恐慌" in intl:
        vix = intl["VIX恐慌"]["price"]
        parts.append(f"VIX={vix:.0f}")
    if stats["total"] > 0:
        parts.append(f"勝率{stats['win_rate']:.0f}%({stats['total']}筆)")
    bear = sum(1 for n in news if n["sent_val"] == -1)
    bull = sum(1 for n in news if n["sent_val"] ==  1)
    if   bear > bull: parts.append("新聞偏空⚠️")
    elif bull > bear: parts.append("新聞偏多✅")
    if   direction ==  1: parts.append("→ 8:45買進")
    elif direction == -1: parts.append("→ 8:45賣出")

    msg    = " | ".join(parts)
    script = f'display notification "{msg}" with title "{title}" sound name "Ping"'
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=5)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
#  主程式
# ═══════════════════════════════════════════════════════════

def rebuild_backtest(period: str = "max"):
    """重建四版本回測 — 用全期歷史資料（預設最長 ≈29年）重算勝率。
       保留真實 completed 交易，只重生 simulated/sim_* 部分。"""
    print(f"🔁 重建回測：抓取全期歷史資料（period={period}）...", flush=True)
    tw = add_taiwan_indicators(fetch_taiwan(period=period))
    n  = len(tw)
    print(f"   台股加權 {n} 交易日：{tw.index[0].date()} ~ {tw.index[-1].date()}", flush=True)
    try:
        sox = yf.Ticker("^SOX").history(period=period)
        spx = yf.Ticker("^GSPC").history(period=period)
        print(f"   SOX {len(sox)}筆 / SPX {len(spx)}筆", flush=True)
    except Exception as ex:
        print(f"   ⚠️ 美股歷史抓取失敗（國際共振條件將略過）：{ex}", flush=True)
        sox = spx = None

    old  = load_records()
    real = (old[old["status"] == "completed"].copy()
            if not old.empty and "status" in old.columns
            else pd.DataFrame(columns=RECORD_COLS))
    print(f"   保留真實交易 {len(real)} 筆，重生四版本回測...", flush=True)

    df_v100 = backfill_history(tw,      days=n, sox_df=sox, spx_df=spx)
    df_v70  = backfill_history_v70(tw,  days=n, sox_df=sox, spx_df=spx)
    df_v60  = backfill_history_v60(tw,  days=n)
    df_v50  = backfill_history_v50(tw,  days=n)
    df_vsel = backfill_history_vsel(tw, days=n)
    df_vday = backfill_history_daily(tw, days=n)
    records = pd.concat([real, df_v100, df_v70, df_v60, df_v50, df_vsel, df_vday], ignore_index=True)
    save_records(records)

    print(f"\n{'='*56}\n  📊 全期回測結果（{tw.index[0].date()} ~ {tw.index[-1].date()}）\n{'='*56}", flush=True)
    for status, label in [("sim_vsel", "精選版 vsel"), ("simulated", "精準版 v100"),
                          ("sim_v70", "優化版 v70"),
                          ("sim_v60", "高頻版 v60"), ("sim_v50", "超高頻版 v50"),
                          ("sim_vday", "每日版 vday")]:
        st = compute_stats(records, status_filter=status)
        print(f"  {label:12s}: {st['total']:>4d}筆  勝率 {st['win_rate']:5.1f}%  "
              f"損益 NT${st['total_pnl']:>12,.0f}  均賺{st['avg_win']:>7,.0f}/均賠{st['avg_lose']:>7,.0f}",
              flush=True)
    print(f"{'='*56}\n✅ 重建完成，已寫入 {RECORDS_PATH}", flush=True)
    return records


def main():
    # --rebuild: 重建全期回測（29年）後結束
    if "--rebuild" in sys.argv:
        rebuild_backtest("max")
        return
    # --close: 收盤結算（13:45）
    # --night: 夜盤信號（14:30）
    # 預設: 早盤預報（8:30）
    if "--night" in sys.argv:
        mode = "night"
    elif "--close" in sys.argv:
        mode = "close"
    else:
        mode = "morning"

    if not HAS_FEED:
        print("⚠️  建議安裝 feedparser: pip3 install feedparser")

    LABELS = {"morning": "【早盤預報】", "close": "【收盤結算】", "night": "【夜盤信號】"}
    label  = LABELS.get(mode, "【執行】")

    print(f"📡 {label} [1/5] 下載台灣加權指數...", flush=True)
    tw_df = fetch_taiwan(months=7)   # 7個月確保backfill有足夠資料
    tw_df = add_taiwan_indicators(tw_df)

    print(f"🌐 {label} [2/5] 下載國際市場資料...", flush=True)
    intl  = fetch_international()

    print(f"📰 {label} [3/5] 抓取川普動態 & 新聞...", flush=True)
    news  = fetch_news()

    print(f"📂 {label} [4/5] 更新交易記錄...", flush=True)
    records = load_records()

    # 補 session 欄位（向後相容）
    if not records.empty and "session" not in records.columns:
        records.insert(2, "session", "day")

    if records.empty:
        print("  → 首次執行，回填歷史資料（130交易日）...", flush=True)
        try:
            sox_hist = yf.Ticker("^SOX").history(period="7mo")
            spx_hist = yf.Ticker("^GSPC").history(period="7mo")
        except Exception:
            sox_hist = spx_hist = None
        # 版本A: 100% 高勝率版（嚴格條件，少筆）
        df_v100 = backfill_history(tw_df, days=130, sox_df=sox_hist, spx_df=spx_hist)
        # 版本B: 70% 中頻率版（寬鬆條件，多筆）
        df_v70  = backfill_history_v70(tw_df, days=130, sox_df=sox_hist, spx_df=spx_hist)
        # 版本C: 高頻版
        df_v60  = backfill_history_v60(tw_df, days=130)
        # 版本D: 超高頻版（60%）
        df_v50  = backfill_history_v50(tw_df, days=130)
        # 版本E: 精選版（重質不重量，~51%正期望值）
        df_vsel = backfill_history_vsel(tw_df, days=130)
        # 版本F: 每日版（每天進場，跳空順勢）
        df_vday = backfill_history_daily(tw_df, days=130)
        records = pd.concat([df_v100, df_v70, df_v60, df_v50, df_vsel, df_vday], ignore_index=True)
    else:
        missing = []
        if not records["status"].isin(["sim_v70", "sim_v70_skip"]).any(): missing.append("v70")
        if not records["status"].isin(["sim_v60", "sim_v60_skip"]).any(): missing.append("v60")
        if not records["status"].isin(["sim_v50", "sim_v50_skip"]).any(): missing.append("v50")
        if not records["status"].isin(["sim_vsel", "sim_vsel_skip"]).any(): missing.append("vsel")
        if not records["status"].isin(["sim_vday"]).any(): missing.append("vday")
        if missing:
            print(f"  → 補生成 {'+'.join(missing)} 版本回測...", flush=True)
            try:
                sox_hist = yf.Ticker("^SOX").history(period="7mo")
                spx_hist = yf.Ticker("^GSPC").history(period="7mo")
            except Exception:
                sox_hist = spx_hist = None
            if "v70" in missing:
                records = pd.concat([records, backfill_history_v70(tw_df, days=130, sox_df=sox_hist, spx_df=spx_hist)], ignore_index=True)
            if "v60" in missing:
                records = pd.concat([records, backfill_history_v60(tw_df, days=130)], ignore_index=True)
            if "v50" in missing:
                records = pd.concat([records, backfill_history_v50(tw_df, days=130)], ignore_index=True)
            if "vsel" in missing:
                records = pd.concat([records, backfill_history_vsel(tw_df, days=130)], ignore_index=True)
            if "vday" in missing:
                records = pd.concat([records, backfill_history_daily(tw_df, days=130)], ignore_index=True)

    records = update_completed_trades(records, tw_df)

    print(f"🥇 {label} [追加] 抓取黃金即時資料...", flush=True)
    gold   = fetch_gold_detail()
    gold_s = gold.get("signal", 0)

    print(f"🏦 {label} [追加] 抓取三大法人 / 大戶部位...", flush=True)
    inst         = fetch_institutional()
    inst_s, inst_det = institutional_signal(inst)

    today_str = datetime.now().strftime("%Y-%m-%d")
    date_str  = datetime.now().strftime("%Y%m%d")

    # ════════════════════════════════════════════════
    #  夜盤數據更新（14:30 執行）
    #  ✦ 不產生交易記錄
    #  ✦ 只抓美股即時數據 → 預判明日早盤方向
    #  ✦ 推送通知，更新 JSON 供看板顯示
    # ════════════════════════════════════════════════
    if mode == "night":
        n_dir, n_total, n_int_s, n_gold_s, n_nws_s = night_session_signal(intl, news, gold)

        nday_str = next_trade_day()
        if n_dir == 1:
            ntitle = f"🌙🟢 美股夜盤偏多 → 明日 {nday_str} 看漲"
            nbody  = f"美股{n_int_s:+d} 黃金{n_gold_s:+d} 新聞{n_nws_s:+d} = {n_total:+d} | 明日 8:45 開盤參考做多"
        elif n_dir == -1:
            ntitle = f"🌙🔴 美股夜盤偏空 → 明日 {nday_str} 看跌"
            nbody  = f"美股{n_int_s:+d} 黃金{n_gold_s:+d} 新聞{n_nws_s:+d} = {n_total:+d} | 明日 8:45 開盤參考做空"
        else:
            ntitle = f"🌙⚪ 美股夜盤中性 → 明日 {nday_str} 觀望"
            nbody  = f"美股{n_int_s:+d} 黃金{n_gold_s:+d} 新聞{n_nws_s:+d} = {n_total:+d} | 訊號不強，明日觀察"

        gw = gold.get("warning", "")
        print(f"\n{'='*60}")
        print(f"  🌙 夜盤數據更新  {today_str}  15:00（不交易，僅參考）")
        print(f"{'='*60}")
        if gw:
            print(f"  🥇 黃金: {gw}")
        print(f"  美股數據: {n_int_s:+d}  黃金影響: {n_gold_s:+d}  新聞: {n_nws_s:+d}  = 總分 {n_total:+d}（門檻 ±5）")
        if n_dir == 1:
            print("  ┌──────────────────────────────────────────────────┐")
            print("  │  🟢  夜盤數據偏多 → 明日早盤 8:45 傾向做多       │")
            print("  │  ※ 正式信號以明早 8:30 主程式為準                │")
            print("  └──────────────────────────────────────────────────┘")
        elif n_dir == -1:
            print("  ┌──────────────────────────────────────────────────┐")
            print("  │  🔴  夜盤數據偏空 → 明日早盤 8:45 傾向做空       │")
            print("  │  ※ 正式信號以明早 8:30 主程式為準                │")
            print("  └──────────────────────────────────────────────────┘")
        else:
            print("  ┌──────────────────────────────────────────────────┐")
            print("  │  ⚪  夜盤數據中性 → 明日觀望                     │")
            print("  │  ※ 正式信號以明早 8:30 主程式為準                │")
            print("  └──────────────────────────────────────────────────┘")
        print(f"{'='*60}\n")

        script = f'display notification "{nbody}" with title "{ntitle}" sound name "Ping"'
        try:
            subprocess.run(["osascript", "-e", script], check=False, timeout=5)
        except Exception:
            pass
        print("🔔 夜盤預覽通知已發送（不產生交易記錄）")

        def _safe(v):
            if isinstance(v, (np.integer, np.floating)): return float(v)
            return v
        json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "signal.json")
        try:
            with open(json_path, encoding="utf-8") as f:
                sig = json.load(f)
        except Exception:
            sig = {}
        sig["night_preview"]   = int(n_dir)
        sig["night_score"]     = int(n_total)
        sig["night_int_s"]     = int(n_int_s)
        sig["night_gold_s"]    = int(n_gold_s)
        sig["night_nws_s"]     = int(n_nws_s)
        sig["night_generated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        sig["night_note"]      = ntitle
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(sig, f, ensure_ascii=False, indent=2)
        print(f"💾 夜盤預覽數據已更新: {json_path}")
        return

    # ════════════════════════════════════════════════
    #  日盤模式（早盤預報 / 收盤結算）
    # ════════════════════════════════════════════════
    threshold, threshold_reason = adaptive_threshold(records)

    prev           = tw_df.iloc[-1]
    tw_s,  tw_det  = taiwan_signal(prev, tw_df)
    int_s, int_det = international_signal(intl)
    nws_s, nws_det = news_signal(news)
    psy_s, psy_det = market_psychology_score(intl, gold)

    total = tw_s + int_s + nws_s + gold_s + psy_s + inst_s

    # ── 共識過濾 ──────────────────────────────────────────
    # 規則1: 台灣技術 vs 國際 方向相反 → 不交易
    # 規則2: 外資期貨淨空 vs 其他看多 → 謹慎（外資期貨是最直接的大戶籌碼）
    tw_dir   = 1 if tw_s > 0 else (-1 if tw_s < 0 else 0)
    int_dir  = 1 if int_s > 0 else (-1 if int_s < 0 else 0)
    fut_dir  = 1 if inst["foreign_fut_net"] > 500 else (-1 if inst["foreign_fut_net"] < -500 else 0)
    veto_msg = ""

    # ── 台灣技術進場硬條件（與回測一致，確保85%+勝率） ──
    rsi_val  = float(prev["RSI"])
    p2_live  = tw_df.iloc[-2]
    ma_bull  = (float(prev["MA5"])   > float(prev["MA10"])   > float(prev["MA20"]) and
                float(p2_live["MA5"]) > float(p2_live["MA10"]) > float(p2_live["MA20"]))
    ma_bear  = (float(prev["MA5"])   < float(prev["MA10"])   < float(prev["MA20"]) and
                float(p2_live["MA5"]) < float(p2_live["MA10"]) < float(p2_live["MA20"]))
    macd_ok_bull = (float(prev["MACD"]) > 0 and float(prev["MACD"]) > float(prev["MACDs"]))
    macd_ok_bear = (float(prev["MACD"]) < 0 and float(prev["MACD"]) < float(prev["MACDs"]))
    # RSI 過熱門檻降至 72（模擬結果顯示 RSI>72 勝率大幅下滑）
    rsi_safe_bull = 45 < rsi_val < 72
    rsi_safe_bear = 28 < rsi_val < 55
    rsi_safe      = rsi_safe_bull or rsi_safe_bear
    momentum_ok   = True  # MA2日對齊已涵蓋動能延續性

    veto_msg = ""
    if tw_dir != 0 and int_dir != 0 and tw_dir != int_dir:
        veto_msg  = f"台灣技術({tw_s:+d}) vs 國際({int_s:+d}) 方向相反 → 觀望"
        direction = 0
    elif total > 0 and not rsi_safe_bull:
        veto_msg  = f"RSI={rsi_val:.0f} 過熱(需45~72)或過冷 → 觀望"
        direction = 0
    elif total < 0 and not rsi_safe_bear:
        veto_msg  = f"RSI={rsi_val:.0f} 不在空頭區間(28~55) → 觀望"
        direction = 0
    elif total > 0 and not (ma_bull and macd_ok_bull):
        veto_msg  = "看多需: 均線連續2日多頭排列 + MACD金叉向上 → 條件不足"
        direction = 0
    elif total < 0 and not (ma_bear and macd_ok_bear):
        veto_msg  = "看空需: 均線連續2日空頭排列 + MACD死叉向下 → 條件不足"
        direction = 0
    elif fut_dir != 0 and tw_dir != 0 and fut_dir != tw_dir:
        veto_msg = f"⚠️ 外資期貨({inst['foreign_fut_net']:+,}口) vs 技術面不一致，提高門檻"
        direction = 1 if total >= threshold + 3 else (-1 if total <= -(threshold + 3) else 0)
    else:
        direction = 1 if total >= threshold else (-1 if total <= -threshold else 0)

    sig_date = tw_df.index[-1].strftime("%Y-%m-%d")
    nday     = next_trade_day()
    records  = add_today_signal(records, sig_date, nday,
                                direction, total, tw_s, int_s, nws_s,
                                session="day")

    # ── 四版本各自實倉信號 ──────────────────────────────────
    sox_v = intl.get("費城半導體", {}).get("chg_pct", 0)
    spx_v = intl.get("S&P500",   {}).get("chg_pct", 0)
    ma1_b = ma_bull or (float(prev["MA5"]) > float(prev["MA10"]) > float(prev["MA20"]))
    ma1_s = ma_bear or (float(prev["MA5"]) < float(prev["MA10"]) < float(prev["MA20"]))
    macd_b_live = float(prev["MACD"]) > float(prev["MACDs"])
    macd_s_live = float(prev["MACD"]) < float(prev["MACDs"])
    pk_up = float(tw_df.iloc[-2]["Close"]) > float(tw_df.iloc[-2]["Open"])

    # 精準版 (v100): MA2日+RSI<72+SOX>0.5+SPX>0+MACD金叉+前K（最嚴 → 必為其他版本超集，確保單調性）
    if   ma_bull and 45 < rsi_val < 72 and sox_v > 0.5 and spx_v > 0 and macd_b_live and pk_up: dv100 = 1
    elif ma_bear and 28 < rsi_val < 55 and sox_v < -0.5 and spx_v < 0 and macd_s_live and not pk_up: dv100 = -1
    else: dv100 = 0
    # 優化版 (v70): MA1日+MACD+前K+RSI<80+SOX>0
    if   ma1_b and macd_b_live and pk_up and 40 < rsi_val < 80 and sox_v > 0 and spx_v > 0: dv70 = 1
    elif ma1_s and macd_s_live and not pk_up and 20 < rsi_val < 60 and sox_v < 0 and spx_v < 0: dv70 = -1
    else: dv70 = 0
    # 高頻版 (v60): MA1日+MACD+前K
    if   ma1_b and macd_b_live and pk_up and 30 < rsi_val < 80: dv60 = 1
    elif ma1_s and macd_s_live and not pk_up and 20 < rsi_val < 70: dv60 = -1
    else: dv60 = 0
    # 超高頻版 (v50): MA1日+RSI only
    if   ma1_b and 30 < rsi_val < 85: dv50 = 1
    elif ma1_s and 15 < rsi_val < 70: dv50 = -1
    else: dv50 = 0
    # 精選版 (vsel): MA連2日 + MACD連2日 + 趨勢強度(MA5距MA20>0.6%) + 前2K同向 + RSI窄帶
    ma20_live   = float(prev["MA20"])
    spread_live = (float(prev["MA5"]) - ma20_live) / ma20_live if ma20_live else 0.0
    macd2_b = macd_b_live and (float(p2_live["MACD"]) > float(p2_live["MACDs"]))
    macd2_s = macd_s_live and (float(p2_live["MACD"]) < float(p2_live["MACDs"]))
    pk2_up  = pk_up and (float(tw_df.iloc[-3]["Close"]) > float(tw_df.iloc[-3]["Open"]))
    pk2_dn  = (not pk_up) and (float(tw_df.iloc[-3]["Close"]) < float(tw_df.iloc[-3]["Open"]))
    if   ma_bull and macd2_b and pk2_up and spread_live > 0.006 and 58 < rsi_val < 66: dvsel = 1
    elif ma_bear and macd2_s and pk2_dn and spread_live < -0.006 and 34 < rsi_val < 42: dvsel = -1
    else: dvsel = 0

    # 🎯 共識倉 (cons): 精選∪優化（只跟兩個賺錢版本），SOX強烈背離否決 → 使用者下單依據
    if dvsel != 0 and dv70 != 0 and dvsel != dv70:
        dcons = 0
    else:
        dcons = dv70 if dv70 != 0 else dvsel
    if   dcons == 1 and sox_v <= -2.0: dcons = 0
    elif dcons == -1 and sox_v >= 2.0: dcons = 0

    records = add_version_real_signal(records, sig_date, nday, dv100, "v100")
    records = add_version_real_signal(records, sig_date, nday, dv70,  "v70")
    records = add_version_real_signal(records, sig_date, nday, dv60,  "v60")
    records = add_version_real_signal(records, sig_date, nday, dv50,  "v50")
    records = add_version_real_signal(records, sig_date, nday, dvsel, "vsel")
    records = add_version_real_signal(records, sig_date, nday, dcons, "cons")

    save_records(records)

    stats_real     = compute_stats(records, status_filter="completed")
    stats_sim      = compute_stats(records, status_filter="simulated")
    stats_v70      = compute_stats(records, status_filter="sim_v70")
    stats_v60      = compute_stats(records, status_filter="sim_v60")
    stats_v50      = compute_stats(records, status_filter="sim_v50")
    stats_vsel     = compute_stats(records, status_filter="sim_vsel")
    stats_vday     = compute_stats(records, status_filter="sim_vday")
    # 每日版近期明細（含當日損益率 = 損益點數/進場價）
    vday_recent = []
    _vd = records[records["status"] == "sim_vday"].copy()
    if not _vd.empty:
        for _, r in _vd.tail(15).iloc[::-1].iterrows():
            try:
                ep = float(r["entry_price"]); pts = float(r["pnl_points"])
                ret = (pts / ep * 100) if ep else 0.0
            except Exception:
                ret = 0.0
            vday_recent.append({
                "date":   r["trade_date"],
                "dir":    int(float(r["direction"])) if str(r["direction"]).strip() not in ("", "nan") else 0,
                "pnl":    int(float(r["pnl_nts"])) if str(r["pnl_nts"]).strip() not in ("", "nan") else 0,
                "ret":    round(ret, 2),
                "win":    str(r["win"]) == "True",
            })
    stats_real_v100 = compute_stats(records, status_filter="real_v100")
    stats_real_v70  = compute_stats(records, status_filter="real_v70")
    stats_real_v60  = compute_stats(records, status_filter="real_v60")
    stats_real_v50  = compute_stats(records, status_filter="real_v50")
    stats_real_cons = compute_stats(records, status_filter="real_cons")
    # 共識倉近期每筆明細（幾月幾號、方向、進場/出場、損益）給看板顯示
    cons_done = records[records["status"] == "real_cons"].copy()
    cons_recent = []
    for _, r in cons_done.tail(15).iterrows():
        try:
            ep = float(r["entry_price"]); xp = float(r["exit_price"])
        except Exception:
            continue
        cons_recent.append({
            "date":  str(r.get("trade_date", "")),
            "dir":   int(r.get("direction", 0)),
            "entry": int(ep), "exit": int(xp),
            "pnl":   int(float(r["pnl_nts"])) if str(r["pnl_nts"]).strip() not in ("", "nan") else 0,
            "win":   str(r["win"]) == "True",
        })

    print(f"📊 {label} [5/5] 產生報告...", flush=True)
    report = build_report(tw_df, records, intl, news,
                          direction, total, tw_s, int_s, nws_s,
                          tw_det, int_det, nws_det, stats_real,
                          threshold, threshold_reason, mode,
                          psy_s=psy_s, psy_det=psy_det,
                          gold_s=gold_s, veto_msg=veto_msg,
                          inst_s=inst_s, inst_det=inst_det,
                          stats_sim=stats_sim, stats_v70=stats_v70)
    print("\n" + report)

    # ── 儲存 ─────────────────────────────────────────────
    if mode == "close":
        arch_rpt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", f"signal_{date_str}_close.txt")
    else:
        arch_rpt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", f"signal_{date_str}.txt")

    with open(arch_rpt, "w", encoding="utf-8") as f: f.write(report)

    def _safe(v):
        if isinstance(v, (np.integer, np.floating)): return float(v)
        return v

    signal_json = {
        "generated_at":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mode":             mode,
        "signal_date":      sig_date,
        "trade_date":       nday,
        "direction":        int(direction),
        "total_score":      int(total),
        "tw_score":         int(tw_s),
        "intl_score":       int(int_s),
        "news_score":       int(nws_s),
        "psy_score":        int(psy_s),
        "inst_score":       int(inst_s),
        "foreign_fut_net":  int(inst.get("foreign_fut_net", 0)),
        "foreign_cash_b":   int(inst.get("foreign_cash_b", 0)),
        "veto_msg":         veto_msg,
        "threshold":        int(threshold),
        "threshold_reason": threshold_reason,
        "tw_last_close":    float(prev["Close"]),
        "tw_chg_pct":       float(prev["ChgPct"]),
        "tw_ma5":           float(prev["MA5"]),
        "tw_ma10":          float(prev["MA10"]),
        "tw_rsi":           float(prev["RSI"]),
        "tw_macd":          float(prev["MACD"]),
        "tw_macds":         float(prev["MACDs"]),
        "tw_prev_close_up": bool(float(tw_df.iloc[-2]["Close"]) > float(tw_df.iloc[-2]["Open"])),
        "tw_ma5_p2":        float(tw_df.iloc[-2]["MA5"]),
        "tw_ma10_p2":       float(tw_df.iloc[-2]["MA10"]),
        "tw_ma20_p2":       float(tw_df.iloc[-2]["MA20"]),
        "tw_ma20":          float(prev["MA20"]),
        "stats_real":        {k: _safe(v) for k, v in stats_real.items()},
        "stats_sim":         {k: _safe(v) for k, v in stats_sim.items()},
        "stats_v70":         {k: _safe(v) for k, v in stats_v70.items()},
        "stats_v60":         {k: _safe(v) for k, v in stats_v60.items()},
        "stats_v50":         {k: _safe(v) for k, v in stats_v50.items()},
        "stats_vsel":        {k: _safe(v) for k, v in stats_vsel.items()},
        "stats_vday":        {k: _safe(v) for k, v in stats_vday.items()},
        "vday_recent":       vday_recent,
        "stats_real_v100":   {k: _safe(v) for k, v in stats_real_v100.items()},
        "stats_real_v70":    {k: _safe(v) for k, v in stats_real_v70.items()},
        "stats_real_v60":    {k: _safe(v) for k, v in stats_real_v60.items()},
        "stats_real_v50":    {k: _safe(v) for k, v in stats_real_v50.items()},
        "stats_real_cons":   {k: _safe(v) for k, v in stats_real_cons.items()},
        "cons_recent":       cons_recent,
        "gold":             {k: _safe(v) for k, v in gold.items()},
        "intl_data": {
            name: {
                "category": d["category"],
                "price":    float(d["price"]),
                "chg_pct":  float(d["chg_pct"]),
                "signal":   int(d["signal"]),
                "note":     d["note"],
                "desc":     d["desc"],
            }
            for name, d in intl.items()
        },
        "news": news[:20],
    }

    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "signal.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(signal_json, f, ensure_ascii=False, indent=2)

    print(f"\n💾 歸檔備份  : {arch_rpt}")
    print(f"💾 主記錄檔  : {RECORDS_PATH}")
    print(f"💾 看板資料  : {json_path}")

    send_notification(direction, total, intl, news, stats_real)
    print("🔔 系統通知已發送")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已中止")
    except Exception as e:
        print(f"\n❌ 錯誤: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        print("\n請確認已安裝: pip3 install yfinance pandas numpy feedparser")
        sys.exit(1)
