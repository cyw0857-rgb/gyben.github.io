#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
長榮航太 (2645) 三大法人「估算持有成本均價」引擎
資料源（皆免費）：
  - TWSE STOCK_DAY : 個股每日成交股數/金額 → 當日 VWAP
  - TWSE T86       : 個股每日三大法人買賣超（外資/投信/自營自行）
方法（經 ChatGPT 抓漏驗證）：
  逐日移動加權平均成本；買進用當日VWAP加權，賣出用「成本價」扣減；
  估計持股翻負則歸零重算（不硬掰）。
重大限制（務必顯示免責）：
  - 起算日 = 上市日 2023-03-14，期初持股假設為 0（法人可能持有上市前籌碼，未知）
  - 未做除權息還原，配息/增資/減資會使估值失真
  - 不含當沖、借券放空、自營避險、鉅額交易、ETF 申贖
  → 僅為公開資料統計推估，非真實成本，不可當接刀依據
"""
import urllib.request, urllib.error, json, ssl, time, os, sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(DATA, "_cost_cache.json")   # 已抓日資料快取，避免重複請求
OUT   = os.path.join(DATA, "stock_cost_est.json")

STOCK_NO = "2645"
LIST_DATE = date(2023, 3, 14)   # 2645 轉上市日

_ctx = ssl.create_default_context(); _ctx.check_hostname = False; _ctx.verify_mode = ssl.CERT_NONE

def _get(url, retries=5):
    """TWSE 對快速請求會回 307/HTML 限流，遇到就退避重試。"""
    last = None
    for k in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return json.load(urllib.request.urlopen(req, timeout=25, context=_ctx))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (307, 429, 503):
                time.sleep(2.0 * (k + 1))   # 2,4,6,8,10 秒退避
                continue
            raise
        except Exception as e:
            last = e
            time.sleep(1.5 * (k + 1))
    raise last

def _f(s):
    try: return float(str(s).replace(",", "").strip())
    except: return 0.0

def load_cache():
    if os.path.exists(CACHE):
        try: return json.load(open(CACHE, encoding="utf-8"))
        except: return {}
    return {}

def save_cache(c):
    json.dump(c, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

def fetch_vwap_month(yyyymmdd):
    """STOCK_DAY 一次回整月，回 {YYYY-MM-DD: vwap}"""
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={yyyymmdd}&stockNo={STOCK_NO}&response=json"
    d = _get(url)
    out = {}
    if d.get("stat") != "OK": return out
    for r in d.get("data", []):
        roc = r[0].split("/")            # 114/06/02
        y = int(roc[0]) + 1911
        key = f"{y:04d}-{int(roc[1]):02d}-{int(roc[2]):02d}"
        vol = _f(r[1]); val = _f(r[2])
        if vol > 0: out[key] = val / vol
    return out

def fetch_t86_day(yyyymmdd):
    """T86 單日，回 2645 的 (外資net, 投信net, 自營自行net) 股數；查無回 None"""
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={yyyymmdd}&selectType=ALLBUT0999&response=json"
    d = _get(url)
    if d.get("stat") != "OK": return None
    for r in d.get("data", []):
        if r[0].strip() == STOCK_NO:
            return (_f(r[4]), _f(r[10]), _f(r[14]))   # 外資/投信/自營自行 買賣超
    return None   # 當日該股無法人進出（仍算交易日，net=0 處理）

def moving_cost(events):
    """events: [(net_shares, vwap), ...] 依日序；回 (持股, 成本均價 or None, 投入估計)"""
    Q = 0.0; cost_total = 0.0
    for net, p in events:
        if net >= 0:
            Q += net; cost_total += net * p
        else:
            sell = min(-net, Q)
            avg = (cost_total / Q) if Q > 0 else 0.0
            Q -= sell; cost_total -= sell * avg
            if Q <= 0:                      # 估計部位歸零 → 重算
                Q = 0.0; cost_total = 0.0
    avg = (cost_total / Q) if Q > 0 else None
    return Q, avg, cost_total

def daterange_months(start, end):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield f"{y:04d}{m:02d}01"
        m += 1
        if m > 12: m = 1; y += 1

def run(start=LIST_DATE, end=None, delay=1.0, verbose=True):
    end = end or date.today()
    cache = load_cache()

    # 1) VWAP（整月批次）
    vwap = {}
    for mm in daterange_months(start, end):
        ckey = "VWAP" + mm
        if ckey in cache:
            vwap.update(cache[ckey])
        else:
            try:
                mv = fetch_vwap_month(mm)
                cache[ckey] = mv; vwap.update(mv); save_cache(cache)
                if verbose: print(f"  VWAP {mm[:6]}: {len(mv)} 天", flush=True)
                time.sleep(delay)
            except Exception as ex:
                if verbose: print(f"  VWAP {mm[:6]} 失敗: {ex}", flush=True)

    # 2) T86（逐日）
    events = {"foreign": [], "trust": [], "dealer": []}
    days = sorted(vwap.keys())            # 只在有成交(=交易日)的日子查法人
    for dk in days:
        if dk < start.isoformat() or dk > end.isoformat(): continue
        p = vwap[dk]
        yyyymmdd = dk.replace("-", "")
        ckey = "T86" + yyyymmdd
        if ckey in cache:
            row = cache[ckey]
        else:
            try:
                r = fetch_t86_day(yyyymmdd)
                row = r if r else [0, 0, 0]
                cache[ckey] = row; save_cache(cache)
                time.sleep(delay)
            except Exception as ex:
                if verbose: print(f"  T86 {dk} 失敗: {ex}", flush=True)
                continue
        events["foreign"].append((row[0], p))
        events["trust"].append((row[1], p))
        events["dealer"].append((row[2], p))

    last_price = vwap[days[-1]] if days else 0
    result = {
        "stock_no": STOCK_NO, "name": "長榮航太",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "last_vwap": round(last_price, 2),
        "investors": {}, "trading_days": len(days),
        "disclaimer": ("公開資料統計推估，非法人真實成本；起算=上市日且期初持股假設0，"
                       "未做除權息還原，不含當沖/借券/避險，僅供觀察趨勢，勿作接刀依據"),
    }
    labels = {"foreign": "外資", "trust": "投信", "dealer": "自營(自行)"}
    for k, ev in events.items():
        Q, avg, invest = moving_cost(ev)
        result["investors"][k] = {
            "label": labels[k],
            "est_shares": int(Q),
            "est_lots": round(Q / 1000, 1),
            "est_avg_cost": round(avg, 2) if avg else None,
            "est_invest": round(invest, 0),
            "vs_price_pct": round((last_price - avg) / avg * 100, 1) if avg else None,
        }
    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return result

if __name__ == "__main__":
    # 預設跑完整(上市至今)；測試用：python3 stock_cost_est.py 2025-05-01
    st = LIST_DATE
    if len(sys.argv) > 1:
        y, m, d = map(int, sys.argv[1].split("-")); st = date(y, m, d)
    r = run(start=st)
    print(json.dumps(r["investors"], ensure_ascii=False, indent=2))
    print("last_vwap:", r["last_vwap"], "| 交易日:", r["trading_days"])
