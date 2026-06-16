#!/usr/bin/env python3
"""金十數據快訊抓取 + 多空情緒分析"""

import requests, json, re, os
from datetime import datetime
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "data", "jin10_news.json")
URL  = "https://www.jin10.com/flash_newest.js"

HDR  = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

BULL = {
    # 繁體/簡體中文多頭關鍵字
    "上漲","上涨","漲","涨","突破","走強","走强","利好","降息","增長","增长",
    "新高","反彈","反弹","走高","強勁","强劲","超預期","超预期","多頭","多头",
    "做多","上行","回升","好轉","好转","樂觀","乐观","刺激","寬鬆","宽松",
    "復甦","复苏","擴張","扩张","增速","就業","就业","非農","利多",
    # 英文
    "surge","rally","gain","rise","bull","strong","beat","record","optimism",
    "stimulus","cut","ease","growth","rebound",
}
BEAR = {
    # 繁體/簡體中文空頭關鍵字
    "下跌","跌","走弱","利空","加息","衰退","下滑","萎縮","萎缩","崩","拋售","抛售",
    "通脹","通胀","風險","风险","緊縮","紧缩","下行","惡化","恶化","悲觀","悲观",
    "衝突","冲突","制裁","拋售","危機","危机","違約","违约","破產","破产","失業","失业",
    # 英文
    "fall","drop","plunge","crash","recession","inflation","fear","risk","tension",
    "tariff","sanction","ban","war","decline","slowdown","miss","layoff",
}

# 過濾掉不相關的快訊（只保留市場相關）
SKIP_KEYWORDS = {"【提示】", "【广告】", "【招聘】"}


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
    def handle_data(self, d):
        self.result.append(d)
    def get_text(self):
        return "".join(self.result).strip()


def strip_html(text: str) -> str:
    s = HTMLStripper()
    try:
        s.feed(text)
        return s.get_text()
    except Exception:
        return re.sub(r"<[^>]+>", "", text).strip()


def sentiment(text: str) -> int:
    lower = text.lower()
    bull  = sum(1 for w in BULL if w in lower)
    bear  = sum(1 for w in BEAR if w in lower)
    if   bull > bear: return 1
    elif bear > bull: return -1
    return 0


def fetch() -> list:
    r = requests.get(URL, headers=HDR, timeout=12)
    r.raise_for_status()
    raw  = r.text.strip()
    raw  = re.sub(r"^var\s+newest\s*=\s*", "", raw).rstrip(";")
    data = json.loads(raw)
    items = []
    for it in data:
        content = strip_html(
            it.get("data", {}).get("title") or
            it.get("data", {}).get("content") or ""
        )
        if not content or len(content) < 5:
            continue
        if any(k in content for k in SKIP_KEYWORDS):
            continue
        time_str = it.get("time", "")[:16]
        sv = sentiment(content)
        items.append({
            "time":      time_str,
            "content":   content[:120],
            "sentiment": sv,
            "tag":       "✅偏多" if sv == 1 else ("⚠️偏空" if sv == -1 else "⚪中性"),
            "tag_css":   "pos"    if sv == 1 else ("neg"    if sv == -1 else "neu"),
        })
    return items[:30]   # 最新30條


def run():
    print("📡 抓取金十數據快訊...", flush=True)
    try:
        items = fetch()
        bull  = sum(1 for x in items if x["sentiment"] ==  1)
        bear  = sum(1 for x in items if x["sentiment"] == -1)
        total = bull - bear
        if   total >= 3:  mood, mood_color = "偏多 📈", "#10b981"
        elif total >= 1:  mood, mood_color = "略偏多",  "#34d399"
        elif total <= -3: mood, mood_color = "偏空 📉", "#ef4444"
        elif total <= -1: mood, mood_color = "略偏空",  "#f87171"
        else:             mood, mood_color = "中性 ─",  "#9ca3af"

        # 只在有新資料時才更新（比對最新一條時間）
        old_latest = ""
        if os.path.exists(OUT):
            try:
                old = json.load(open(OUT, encoding="utf-8"))
                old_latest = (old.get("items") or [{}])[0].get("time", "")
            except Exception:
                pass

        new_latest = items[0]["time"] if items else ""
        if new_latest == old_latest:
            print(f"⏭  無新快訊（最新: {new_latest}），跳過更新", flush=True)
            return False   # 無更新

        result = {
            "updated":    datetime.now().strftime("%Y-%m-%d %H:%M"),
            "bull":       bull,
            "bear":       bear,
            "score":      total,
            "mood":       mood,
            "mood_color": mood_color,
            "items":      items,
        }
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✅ 金十快訊更新：{len(items)}條  多:{bull} 空:{bear}  整體{mood}", flush=True)
        return True    # 有更新

    except Exception as ex:
        print(f"❌ 金十快訊失敗: {ex}", flush=True)
        return False


if __name__ == "__main__":
    run()
