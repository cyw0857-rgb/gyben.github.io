#!/usr/bin/env python3
"""市場新聞獨立抓取 — Google News RSS + 情緒分析，每15分鐘執行"""

import json, os
from datetime import datetime

try:
    import feedparser
    HAS_FEED = True
except ImportError:
    HAS_FEED = False

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "data", "news.json")

NEWS_FEEDS = [
    {"label": "川普動態",    "url": "https://news.google.com/rss/search?q=Trump+tariff+OR+Trump+trade+OR+Trump+says&hl=en-US&gl=US&ceid=US:en", "max": 6},
    {"label": "關稅/貿易",   "url": "https://news.google.com/rss/search?q=tariff+trade+war+economy&hl=en-US&gl=US&ceid=US:en", "max": 4},
    {"label": "台股/半導體", "url": "https://news.google.com/rss/search?q=Taiwan+stock+OR+TSMC+OR+semiconductor&hl=en-US&gl=US&ceid=US:en", "max": 4},
    {"label": "聯準會",      "url": "https://news.google.com/rss/search?q=Federal+Reserve+interest+rate+OR+stock+market&hl=en-US&gl=US&ceid=US:en", "max": 4},
]

BULL_WORDS = {"deal","agreement","cut","boost","surge","rally","record","strong",
              "optimism","positive","growth","rise","gain","increase","stimulus",
              "ceasefire","peace","reduce","chip act"}
BEAR_WORDS = {"tariff","sanction","ban","war","threat","crash","recession",
              "inflation","fall","drop","fear","risk","tension","conflict",
              "escalat","collapse","default","crisis","sell-off","warning",
              "impose","penalty","retaliation","shutdown","downgrade",
              "miss","layoff","bankrupt"}


def sentiment(title: str) -> int:
    lower = title.lower()
    bull  = sum(1 for w in BULL_WORDS if w in lower)
    bear  = sum(1 for w in BEAR_WORDS if w in lower)
    return 1 if bull > bear else (-1 if bear > bull else 0)


def run():
    if not HAS_FEED:
        print("❌ feedparser 未安裝"); return

    print("📰 抓取市場新聞...", flush=True)
    items = []
    for cfg in NEWS_FEEDS:
        try:
            feed  = feedparser.parse(cfg["url"])
            count = 0
            for entry in feed.entries:
                if count >= cfg["max"]:
                    break
                title = entry.get("title", "").strip()
                if not title:
                    continue
                sv = sentiment(title)
                items.append({
                    "label":     cfg["label"],
                    "title":     title[:100],
                    "sentiment": "✅偏多" if sv == 1 else ("⚠️偏空" if sv == -1 else "⚪中性"),
                    "sent_val":  sv,
                })
                count += 1
        except Exception as ex:
            print(f"  ⚠️ {cfg['label']} 失敗: {ex}")

    if not items:
        print("❌ 無新聞資料"); return

    # 防重複：比對第一條標題
    old_first = ""
    if os.path.exists(OUT):
        try:
            old       = json.load(open(OUT, encoding="utf-8"))
            old_first = (old.get("items") or [{}])[0].get("title", "")
        except Exception:
            pass

    bull  = sum(1 for i in items if i["sent_val"] ==  1)
    bear  = sum(1 for i in items if i["sent_val"] == -1)
    score = bull - bear
    if   score >= 4:  mood, mc = "偏多 📈", "#10b981"
    elif score >= 2:  mood, mc = "略偏多",  "#34d399"
    elif score <= -4: mood, mc = "偏空 📉", "#ef4444"
    elif score <= -2: mood, mc = "略偏空",  "#f87171"
    else:             mood, mc = "中性 ─",  "#9ca3af"

    result = {
        "updated":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "bull":       bull,
        "bear":       bear,
        "score":      score,
        "mood":       mood,
        "mood_color": mc,
        "items":      items,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 新聞更新：{len(items)}條  多:{bull} 空:{bear}  整體{mood}", flush=True)
    return True


if __name__ == "__main__":
    run()
