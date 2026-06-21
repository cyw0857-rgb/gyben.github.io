#!/usr/bin/env python3
"""定期定額追蹤 — 每月25號各扣 NT$22,500 買 009816 + 00992A
   產生 data/dca.json：每日股價、每月扣款記錄、成本、市值、績效

   邏輯：
   - 每月 25 號（遇假日順延至次一交易日）各檔投入 NT$22,500
   - 購買記錄持久化於 dca.json，重跑不會重複扣
   - 未來月份不預先扣；只補登「已到期」的月份
"""
import json, os
from datetime import datetime, date, timezone, timedelta

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "data", "dca.json")

PLAN = {
    "monthly_total": 45000,
    "buy_day": 25,
    "start_month": "2026-06",   # 本月開始定期定額
    "holdings": [
        {"symbol": "009816.TW", "name": "凱基台灣TOP50",        "alloc": 0.5},
        {"symbol": "00992A.TW", "name": "群益台灣科技創新主動式", "alloc": 0.5},
    ],
}


def month_list(start_ym, end_ym):
    """產生 start_ym ~ end_ym（含）的每月字串 'YYYY-MM'"""
    y, m = map(int, start_ym.split("-"))
    ey, em = map(int, end_ym.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1; y += 1
    return out


def close_on_or_after(df, target):
    """回傳 target（date）當天或之後第一個交易日的 (收盤價, 實際日期)"""
    sub = df[df.index.date >= target]
    if len(sub) == 0:
        return None, None
    return round(float(sub["Close"].iloc[0]), 2), sub.index[0].date()


def run():
    if not HAS_YF:
        print("❌ yfinance 未安裝"); return

    tw_now = datetime.now(timezone(timedelta(hours=8)))
    today  = tw_now.date()
    cur_ym = f"{today.year:04d}-{today.month:02d}"

    # 載入既有購買記錄（持久化）
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            old = {}
    purchases = old.get("purchases", [])
    bought = {(p["symbol"], p["month"]) for p in purchases}

    months = month_list(PLAN["start_month"], cur_ym)

    holdings_out = []
    total_cost = total_value = 0.0

    for h in PLAN["holdings"]:
        sym  = h["symbol"]
        amt  = PLAN["monthly_total"] * h["alloc"]
        print(f"📈 抓取 {sym} ...", flush=True)
        try:
            df = yf.Ticker(sym).history(period="max", auto_adjust=True)
        except Exception as ex:
            print(f"  ⚠️ {sym} 抓取失敗: {ex}")
            df = None

        if df is None or len(df) < 2:
            print(f"  ⚠️ {sym} 無足夠資料，沿用舊值")
            # 沿用舊持倉資料
            prev = next((x for x in old.get("holdings", []) if x["symbol"] == sym), None)
            if prev:
                holdings_out.append(prev)
                total_cost  += prev.get("cost", 0)
                total_value += prev.get("value", 0)
            continue

        last = round(float(df["Close"].iloc[-1]), 2)
        prevc = round(float(df["Close"].iloc[-2]), 2)
        chg_pct = round((last - prevc) / prevc * 100, 2) if prevc else 0.0

        # 補登已到期月份的扣款（每月25號，遇假日順延）
        for ym in months:
            if (sym, ym) in bought:
                continue
            yy, mm = map(int, ym.split("-"))
            target = date(yy, mm, PLAN["buy_day"])
            if target > today:
                continue   # 未到扣款日，不預扣
            price, real_date = close_on_or_after(df, target)
            if price is None:
                continue   # 該日尚無交易資料（可能在最新資料之後）
            shares = round(amt / price, 4)
            purchases.append({
                "symbol": sym, "month": ym,
                "date":   real_date.strftime("%Y-%m-%d"),
                "amount": amt, "price": price, "shares": shares,
            })
            bought.add((sym, ym))
            print(f"  ✅ 補登 {ym} 扣款：{real_date} @ {price} → {shares} 股")

        # 彙整此檔持倉
        my = [p for p in purchases if p["symbol"] == sym]
        sh_sum   = round(sum(p["shares"] for p in my), 4)
        cost_sum = round(sum(p["amount"] for p in my), 2)
        value    = round(sh_sum * last, 2)
        avg_cost = round(cost_sum / sh_sum, 2) if sh_sum else 0.0
        pnl      = round(value - cost_sum, 2)
        ret_pct  = round(pnl / cost_sum * 100, 2) if cost_sum else 0.0

        # 近 30 日收盤（迷你走勢）
        hist = [round(float(c), 2) for c in df["Close"].iloc[-30:].tolist()]

        total_cost  += cost_sum
        total_value += value

        holdings_out.append({
            "symbol": sym, "name": h["name"],
            "last": last, "prev": prevc, "chg_pct": chg_pct,
            "shares": sh_sum, "cost": cost_sum, "avg_cost": avg_cost,
            "value": value, "pnl": pnl, "ret_pct": ret_pct,
            "n_buys": len(my), "hist": hist,
        })

    total_pnl = round(total_value - total_cost, 2)
    total_ret = round(total_pnl / total_cost * 100, 2) if total_cost else 0.0

    # 下次扣款日
    next_ym = cur_ym
    if today.day >= PLAN["buy_day"]:
        ny, nm = today.year, today.month + 1
        if nm > 12:
            nm = 1; ny += 1
        next_ym = f"{ny:04d}-{nm:02d}"
    ny, nm = map(int, next_ym.split("-"))
    next_buy = date(ny, nm, PLAN["buy_day"]).strftime("%Y-%m-%d")
    days_to_next = (date(ny, nm, PLAN["buy_day"]) - today).days

    result = {
        "updated": tw_now.strftime("%Y-%m-%d %H:%M"),
        "monthly_total": PLAN["monthly_total"],
        "buy_day": PLAN["buy_day"],
        "next_buy": next_buy,
        "days_to_next": days_to_next,
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
        "total_pnl": total_pnl,
        "total_ret": total_ret,
        "holdings": holdings_out,
        "purchases": sorted(purchases, key=lambda p: (p["date"], p["symbol"])),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    if total_cost:
        print(f"✅ 定期定額：成本 {total_cost:.0f} 市值 {total_value:.0f} "
              f"損益 {total_pnl:+.0f} ({total_ret:+.2f}%)  下次扣款 {next_buy}", flush=True)
    else:
        print(f"✅ 定期定額：尚未扣款，首次扣款日 {next_buy}（{days_to_next} 天後）", flush=True)
    return True


if __name__ == "__main__":
    run()
