#!/usr/bin/env python3
"""長榮航太 (2645) 籌碼面抓取 — TWSE 免費 API
   產生 data/stock_chips.json，供 dashboard 合併進 2645 卡片：
   - 三大法人買賣超（最近 ~12 個交易日，外資/投信/自營/合計）
   - 融資融券餘額與變化（最近 ~8 個交易日）

   資料來源（公開、免費）：
   - 三大法人：TWSE fund/T86（逐日全市場，篩 2645）
   - 融資融券：TWSE marginTrading/MI_MARGN（逐日全市場，篩 2645）
   注意：盤中/集保大戶/分點券商屬付費資料，免費無法取得。
"""
import json, os, ssl, time
import urllib.request
from datetime import datetime, date, timedelta, timezone

HERE   = os.path.dirname(os.path.abspath(__file__))
OUT    = os.path.join(HERE, "data", "stock_chips.json")
CODE   = "2645"
N_INST = 12   # 三大法人天數
N_MARG = 8    # 融資融券天數

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers=_UA)
    return urllib.request.urlopen(req, timeout=timeout, context=_CTX).read().decode("utf-8", "ignore")


def _to_int(s):
    try:
        return int(str(s).replace(",", "").strip() or 0)
    except Exception:
        return 0


def _trading_dates(back_days=30):
    """從今天往回列日期字串（含週末，呼叫端遇空資料自動略過）"""
    tw_today = datetime.now(timezone(timedelta(hours=8))).date()
    return [(tw_today - timedelta(days=i)).strftime("%Y%m%d") for i in range(back_days)]


def fetch_inst(n_days=N_INST):
    """三大法人買賣超（股），最近 n_days 個交易日，新到舊"""
    rows = []
    seen = set()
    for ds in _trading_dates(40):
        if len(rows) >= n_days:
            break
        try:
            j = json.loads(_get(f"https://www.twse.com.tw/rwd/zh/fund/T86?"
                                f"date={ds}&selectType=ALL&response=json"))
        except Exception:
            continue
        if j.get("stat") != "OK":
            continue
        # 用回應內的實際資料日期（非交易日查詢可能回傳前一交易日資料）
        real = str(j.get("date") or ds)
        if real in seen:
            continue
        seen.add(real)
        for r in j.get("data", []):
            if str(r[0]).strip() == CODE:
                foreign = _to_int(r[4]) + _to_int(r[7])   # 外陸資 + 外資自營商
                trust   = _to_int(r[10])                   # 投信
                dealer  = _to_int(r[11])                   # 自營商合計
                total   = _to_int(r[18])                   # 三大法人合計
                rows.append({
                    "date":    f"{real[4:6]}/{real[6:8]}",
                    "foreign": foreign, "trust": trust,
                    "dealer":  dealer,  "total": total,
                })
                break
        time.sleep(0.15)
    return rows


def fetch_margin(n_days=N_MARG):
    """融資融券餘額（張），最近 n_days 個交易日，新到舊"""
    rows = []
    seen = set()
    for ds in _trading_dates(30):
        if len(rows) >= n_days:
            break
        try:
            j = json.loads(_get(f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?"
                                f"date={ds}&selectType=ALL&response=json"))
        except Exception:
            continue
        if j.get("stat") != "OK":
            continue
        real = str(j.get("date") or ds)
        if real in seen:
            continue
        seen.add(real)
        tbl = None
        for t in j.get("tables", []):
            if t.get("fields") and "代號" in t["fields"]:
                tbl = t; break
        if not tbl:
            continue
        for r in tbl["data"]:
            if str(r[0]).strip() == CODE:
                # 融資：買進3 賣出4 償還5 前日6 今日7 ；融券：買進9 賣出10 償還11 前日12 今日13
                fin_bal  = _to_int(r[6])    # 融資今日餘額(張)
                fin_prev = _to_int(r[5])    # 融資前日餘額(張)
                sho_bal  = _to_int(r[12])   # 融券今日餘額(張)
                sho_prev = _to_int(r[11])   # 融券前日餘額(張)
                rows.append({
                    "date":     f"{real[4:6]}/{real[6:8]}",
                    "fin_bal":  fin_bal,  "fin_chg": fin_bal - fin_prev,
                    "sho_bal":  sho_bal,  "sho_chg": sho_bal - sho_prev,
                })
                break
        time.sleep(0.15)
    return rows


def run():
    print(f"🔍 抓取 {CODE} 籌碼面（三大法人 + 融資融券）...", flush=True)

    inst_rows = fetch_inst()
    marg_rows = fetch_margin()

    if not inst_rows and not marg_rows:
        print("⚠️ 籌碼資料皆抓不到，保留舊檔")
        return False

    # 三大法人彙整（5日）
    inst = {}
    if inst_rows:
        last5 = inst_rows[:5]
        tf = sum(r["foreign"] for r in last5)
        tt = sum(r["trust"]   for r in last5)
        td = sum(r["dealer"]  for r in last5)
        net5 = tf + tt + td
        mood = "偏多" if net5 > 0 else ("偏空" if net5 < 0 else "中性")
        inst = {
            "rows": inst_rows,
            "total_foreign": tf, "total_trust": tt, "total_dealer": td,
            "net5": net5, "mood": mood,
        }

    # 融資融券彙整
    margin = {}
    if marg_rows:
        latest = marg_rows[0]
        fin_5chg = sum(r["fin_chg"] for r in marg_rows[:5])
        sho_5chg = sum(r["sho_chg"] for r in marg_rows[:5])
        # 融資增=散戶加碼追高（短線偏空訊號）；融資減=散戶退場
        if fin_5chg > 0:
            mtext, mcolor = "融資5日增加（散戶追價，留意追高）", "#f59e0b"
        elif fin_5chg < 0:
            mtext, mcolor = "融資5日減少（散戶退場，籌碼沉澱）", "#10b981"
        else:
            mtext, mcolor = "融資持平", "#9ca3af"
        margin = {
            "rows": marg_rows,
            "fin_bal": latest["fin_bal"], "sho_bal": latest["sho_bal"],
            "fin_5chg": fin_5chg, "sho_5chg": sho_5chg,
            "note": mtext, "note_color": mcolor,
        }

    result = {
        "updated": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
        "inst":    inst,
        "margin":  margin,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 籌碼更新：三大法人 {len(inst_rows)} 日（5日合計 {inst.get('net5',0):+,} 股 {inst.get('mood','')}）"
          f"｜融資餘額 {margin.get('fin_bal',0):,} 張", flush=True)
    return True


if __name__ == "__main__":
    run()
