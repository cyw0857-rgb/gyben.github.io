#!/usr/bin/env python3
"""台指期 HTML 看板產生器 — 暗色主題，手機電腦通用"""

import json, os, subprocess
import pandas as pd
from datetime import datetime

RECORDS_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "records.csv")
SIGNAL_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "signal.json")
STOCK_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stock_2645.json")
OUTPUT_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

def load_data():
    signal = {}
    if os.path.exists(SIGNAL_PATH):
        with open(SIGNAL_PATH, encoding="utf-8") as f:
            signal = json.load(f)

    records = pd.DataFrame()
    if os.path.exists(RECORDS_PATH):
        df = pd.read_csv(RECORDS_PATH, dtype=str)
        df["pnl"]      = pd.to_numeric(df["pnl_nts"],    errors="coerce").fillna(0)
        df["pts"]      = pd.to_numeric(df["pnl_points"], errors="coerce").fillna(0)
        df["entry"]    = pd.to_numeric(df["entry_price"], errors="coerce")
        df["exit_p"]   = pd.to_numeric(df["exit_price"],  errors="coerce")
        df["win_bool"] = df["win"].map({"True": True, "False": False}).fillna(False)
        df["date"]     = pd.to_datetime(df["trade_date"], errors="coerce")
        records = df.sort_values("date")

    stock = {}
    if os.path.exists(STOCK_PATH):
        with open(STOCK_PATH, encoding="utf-8") as f:
            stock = json.load(f)

    return signal, records, stock

def e(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def pnl_color(v):
    return "#10b981" if v >= 0 else "#ef4444"

def stock_card_html(stock):
    """長榮航太 (2645.TW) 看板卡片"""
    if not stock:
        return ""

    name        = stock.get("name", "長榮航太")
    symbol      = stock.get("symbol", "2645.TW")
    last_close  = stock.get("last_close", 0)
    chg_pct     = stock.get("chg_pct", 0)
    signal_text = stock.get("signal_text", "─")
    sig_color   = stock.get("signal_color", "#9ca3af")
    hold_advice = stock.get("hold_advice", "─")
    hold_color  = stock.get("hold_color",  "#9ca3af")
    score       = stock.get("score", 0)
    rsi         = stock.get("rsi", 0)
    ma5         = stock.get("ma5", 0)
    ma10        = stock.get("ma10", 0)
    ma20        = stock.get("ma20", 0)
    reasons     = stock.get("reasons", [])
    updated     = stock.get("updated", "")
    trend_label = stock.get("trend_label", "")
    support     = stock.get("support", 0)
    resistance  = stock.get("resistance", 0)
    forecast    = stock.get("forecast", [])
    daily_vol   = stock.get("daily_vol_pct", 0)

    chg_color = "#10b981" if chg_pct >= 0 else "#ef4444"
    chg_arrow = "▲" if chg_pct >= 0 else "▼"
    score_color = "#10b981" if score >= 0 else "#ef4444"

    # 原因列表
    reason_html = "".join(
        f'<div style="font-size:.72rem;color:#94a3b8;padding:2px 0">• {e(r)}</div>'
        for r in reasons
    )

    # 半年走勢表
    def trend_arrow(t):
        return "▲" if t == "up" else ("▼" if t == "down" else "─")
    def trend_col(t):
        return "#10b981" if t == "up" else ("#ef4444" if t == "down" else "#9ca3af")

    fc_rows = ""
    for fc in forecast:
        ta = trend_arrow(fc["trend"])
        tc = trend_col(fc["trend"])
        chg = fc["chg_pct"]
        cc  = "#10b981" if chg >= 0 else "#ef4444"
        fc_rows += (
            f'<tr>'
            f'<td style="color:#94a3b8">{fc["month"]}</td>'
            f'<td style="color:{tc};font-weight:700">{ta} {fc["price"]}</td>'
            f'<td style="color:{cc}">{chg:+.1f}%</td>'
            f'<td style="color:#6b7280;font-size:.7rem">{fc["price_low"]} ~ {fc["price_high"]}</td>'
            f'</tr>'
        )

    return f"""
<div class="card" style="border:1px solid #334155">
  <div class="stitle">✈️ {e(name)} ({e(symbol)}) &nbsp;·&nbsp; {e(updated)} 更新</div>

  <!-- 目前價格 -->
  <div style="display:flex;align-items:baseline;gap:10px;margin-bottom:12px">
    <div style="font-size:1.8rem;font-weight:800">NT${last_close:.2f}</div>
    <div style="font-size:1rem;font-weight:700;color:{chg_color}">{chg_arrow} {chg_pct:+.2f}%</div>
  </div>

  <!-- 明日預測 + 續抱建議 -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">
    <div style="background:#0f172a;border-radius:10px;padding:12px;text-align:center">
      <div style="font-size:.65rem;color:#6b7280;margin-bottom:4px">明日預測</div>
      <div style="font-size:1.1rem;font-weight:800;color:{sig_color}">{e(signal_text)}</div>
      <div style="font-size:.72rem;color:{score_color};margin-top:4px">評分 {score:+d}</div>
    </div>
    <div style="background:#0f172a;border-radius:10px;padding:12px;text-align:center">
      <div style="font-size:.65rem;color:#6b7280;margin-bottom:4px">續抱建議</div>
      <div style="font-size:.82rem;font-weight:700;color:{hold_color};line-height:1.35">{e(hold_advice)}</div>
    </div>
  </div>

  <!-- 技術指標 -->
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:10px">
    <div style="background:#0f172a;border-radius:8px;padding:8px;text-align:center">
      <div style="font-size:.6rem;color:#6b7280">RSI</div>
      <div style="font-size:.9rem;font-weight:700;color:{'#10b981' if 45<rsi<72 else '#f59e0b' if rsi>=72 else '#ef4444'}">{rsi:.0f}</div>
    </div>
    <div style="background:#0f172a;border-radius:8px;padding:8px;text-align:center">
      <div style="font-size:.6rem;color:#6b7280">支撐</div>
      <div style="font-size:.9rem;font-weight:700;color:#10b981">{support}</div>
    </div>
    <div style="background:#0f172a;border-radius:8px;padding:8px;text-align:center">
      <div style="font-size:.6rem;color:#6b7280">壓力</div>
      <div style="font-size:.9rem;font-weight:700;color:#ef4444">{resistance}</div>
    </div>
  </div>

  <!-- 信號依據 -->
  <div style="margin-bottom:12px">
    {reason_html}
  </div>

  <!-- 半年走勢預測 -->
  <div style="border-top:1px solid #334155;padding-top:10px">
    <div style="font-size:.68rem;color:#6b7280;margin-bottom:8px;letter-spacing:.08em">
      📅 半年走勢預測 &nbsp;·&nbsp; {e(trend_label)} &nbsp;·&nbsp; 日波動率 {daily_vol:.1f}%
    </div>
    <table style="font-size:.78rem">
      <tr>
        <th style="color:#6b7280;font-size:.65rem;padding:3px 4px">月份</th>
        <th style="color:#6b7280;font-size:.65rem;padding:3px 4px">預估價</th>
        <th style="color:#6b7280;font-size:.65rem;padding:3px 4px">變動</th>
        <th style="color:#6b7280;font-size:.65rem;padding:3px 4px">區間（±1σ）</th>
      </tr>
      {fc_rows}
    </table>
    <div style="font-size:.62rem;color:#4b5563;margin-top:6px">
      ⚠️ 走勢預測基於線性回歸 + 技術指標，僅供參考，不構成投資建議
    </div>
  </div>
</div>"""


def generate_html(signal, records, stock=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── 分類記錄 ─────────────────────────────────────────
    def _filter(st):
        return records[records["status"] == st].copy() if not records.empty else pd.DataFrame()

    real_df       = _filter("completed")
    sim_df        = _filter("simulated")
    sim_v70_df    = _filter("sim_v70")
    sim_v60_df    = _filter("sim_v60")
    sim_v50_df    = _filter("sim_v50")
    real_v100_df  = _filter("real_v100")
    real_v70_df   = _filter("real_v70")
    real_v60_df   = _filter("real_v60")
    real_v50_df   = _filter("real_v50")

    # ── 信號資料 ─────────────────────────────────────────
    direction  = signal.get("direction", 0)
    total_sc   = signal.get("total_score", 0)
    trade_date = signal.get("trade_date", "─")
    thresh     = signal.get("threshold", 4)
    tw_s       = signal.get("tw_score", 0)
    int_s      = signal.get("intl_score", 0)
    nws_s      = signal.get("news_score", 0)
    last_close = signal.get("tw_last_close", 0)
    tw_rsi     = signal.get("tw_rsi", 0)

    # ── 今日狀態卡 ───────────────────────────────────────
    today_str  = datetime.now().strftime("%Y-%m-%d")
    today_card = ""
    if not records.empty:
        # 找 trade_date = 今天 的那筆
        today_rec = records[records["date"].dt.strftime("%Y-%m-%d") == today_str]
        if not today_rec.empty:
            tr = today_rec.iloc[-1]
            st = tr.get("status", "")
            ep = tr["entry"]
            xp = tr["exit_p"]
            pv = tr["pnl"]
            ppt= tr["pts"]
            won= tr["win_bool"]
            d  = int(tr.get("direction","0")) if str(tr.get("direction","0")).lstrip("-").isdigit() else 0
            dir_label = "做多▲" if d==1 else ("做空▼" if d==-1 else "觀望")
            if st == "completed":
                bg  = "rgba(16,185,129,.15)" if won else "rgba(239,68,68,.15)"
                col = "#10b981" if won else "#ef4444"
                ico = "✅ 賺了" if won else "❌ 虧了"
                today_card = f"""<div class="card" style="border:1px solid {col}">
                  <div class="stitle">📅 今日 {today_str} — {dir_label} 已結算</div>
                  <div class="row2">
                    <div class="box2"><div class="lbl">買進（開盤）</div>
                      <div class="big-num">{ep:,.0f}</div></div>
                    <div style="font-size:1.5rem;color:#6b7280;align-self:center">→</div>
                    <div class="box2"><div class="lbl">賣出（收盤）</div>
                      <div class="big-num">{xp:,.0f}</div></div>
                  </div>
                  <div style="background:{bg};color:{col};border-radius:10px;padding:12px;
                              text-align:center;font-size:1.4rem;font-weight:800;margin-top:10px">
                    {ico} NT${abs(pv):,.0f}
                    <span style="font-size:.85rem;opacity:.8">&ensp;({ppt:+.0f} 點)</span>
                  </div>
                </div>"""
            elif st == "pending":
                today_card = f"""<div class="card" style="border:1px solid #f59e0b">
                  <div class="stitle">📅 今日 {today_str} — {dir_label} 交易中</div>
                  <div style="color:#f59e0b;font-size:1rem;font-weight:700;padding:8px 0">
                    ⏳ 今天已建倉，等待 13:30 收盤結算...</div>
                  <div style="color:#9ca3af;font-size:.82rem">
                    買進價格：{f'{ep:,.0f}' if pd.notna(ep) and ep>0 else '等開盤確認'}<br>
                    收盤後請執行「台指期收盤結算」捷徑更新結果
                  </div>
                </div>"""
            elif st == "skip":
                today_card = f"""<div class="card">
                  <div class="stitle">📅 今日 {today_str} — 觀望（不交易）</div>
                  <div style="color:#9ca3af;font-size:.9rem;padding:4px 0">
                    今天訊號強度不足，系統選擇跳過，等待明天再評估</div>
                </div>"""
        else:
            today_card = f"""<div class="card">
              <div class="stitle">📅 今日 {today_str}</div>
              <div style="color:#9ca3af;font-size:.9rem;padding:4px 0">
                尚未產生今日記錄，請執行早盤信號程式</div>
            </div>"""

    # ── 夜盤預覽卡 ───────────────────────────────────────
    night_html = ""
    np_dir   = signal.get("night_preview")
    np_score = signal.get("night_score", 0)
    np_gen   = signal.get("night_generated", "")
    np_note  = signal.get("night_note", "")
    if np_dir is not None:
        if np_dir == 1:
            nbg = "linear-gradient(135deg,#065f46,#10b981)"; nice = "🌙🟢 夜盤數據偏多"
        elif np_dir == -1:
            nbg = "linear-gradient(135deg,#7f1d1d,#ef4444)"; nice = "🌙🔴 夜盤數據偏空"
        else:
            nbg = "#1e293b"; nice = "🌙⚪ 夜盤數據中性"
        ni_s = signal.get("night_int_s", 0)
        ng_s = signal.get("night_gold_s", 0)
        nn_s = signal.get("night_nws_s", 0)
        night_html = f"""
        <div style="background:{nbg};border-radius:14px;padding:14px 18px;margin-bottom:14px;color:#fff">
          <div style="font-size:.68rem;opacity:.7;letter-spacing:.08em">🌙 夜盤數據預覽（不交易，{np_gen} 更新）</div>
          <div style="font-size:1.2rem;font-weight:800;margin:5px 0">{nice} · 總分 {np_score:+d}</div>
          <div style="font-size:.78rem;opacity:.85">
            美股 {ni_s:+d} ｜ 黃金 {ng_s:+d} ｜ 新聞 {nn_s:+d}
            &ensp;·&ensp; 正式信號以明早 8:30 為準
          </div>
        </div>"""

    # ── 黃金警示卡 ───────────────────────────────────────
    gold       = signal.get("gold", {})
    gold_html  = ""
    if gold:
        gp   = gold.get("price_usd", 0)
        gc   = gold.get("chg_pct", 0)
        glvl = gold.get("level", "neutral")
        gwarn= e(gold.get("warning", ""))
        gcard_colors = {
            "danger":  ("linear-gradient(135deg,#7f1d1d,#ef4444)", "#fff"),
            "warn":    ("linear-gradient(135deg,#78350f,#f59e0b)", "#fff"),
            "good":    ("linear-gradient(135deg,#064e3b,#10b981)", "#fff"),
            "ok":      ("linear-gradient(135deg,#14532d,#22c55e)", "#fff"),
            "neutral": ("#1f2937", "#9ca3af"),
        }
        gbg, gtxt = gcard_colors.get(glvl, gcard_colors["neutral"])
        gold_html = f"""
        <div style="background:{gbg};color:{gtxt};border-radius:14px;
                    padding:14px 18px;margin-bottom:14px">
          <div style="font-size:.7rem;opacity:.8;letter-spacing:.1em">🥇 黃金貴金屬即時警示</div>
          <div style="font-size:1.4rem;font-weight:800;margin:6px 0">
            ${gp:,.0f} / oz &ensp;
            <span style="font-size:1rem">{"▲" if gc >= 0 else "▼"} {gc:+.2f}%</span>
          </div>
          <div style="font-size:.88rem;opacity:.9">{gwarn}</div>
        </div>"""

    # ── 明日信號卡 ───────────────────────────────────────
    if direction == 1:
        sig_bg     = "linear-gradient(135deg,#059669,#10b981)"
        sig_label  = "🟢 明天做多（買進）"
        sig_action = "8:45 買進 1口 &ensp;｜&ensp; 13:30 賣出平倉"
    elif direction == -1:
        sig_bg     = "linear-gradient(135deg,#dc2626,#ef4444)"
        sig_label  = "🔴 明天做空（賣出）"
        sig_action = "8:45 賣出 1口 &ensp;｜&ensp; 13:30 買回平倉"
    else:
        sig_bg     = "linear-gradient(135deg,#374151,#4b5563)"
        sig_label  = "⚪ 明天觀望（不交易）"
        sig_action = f"訊號不足，總分 {total_sc:+d}，未達門檻 ±{thresh}"

    gold_contribution = signal.get("gold", {}).get("signal", 0)
    score_detail = (f"台灣技術 {tw_s:+d} ＋ 國際市場 {int_s:+d} ＋ 新聞 {nws_s:+d}"
                    f"{'＋ 黃金 ' + f'{gold_contribution:+d}' if gold_contribution != 0 else ''}"
                    f" ＝ 總分 {total_sc:+d}（門檻 ±{thresh}）")

    # ── 三版本各自計算今日買賣方向 ───────────────────────
    rsi       = signal.get("tw_rsi", 50)
    macd      = signal.get("tw_macd", 0)
    macds     = signal.get("tw_macds", 0)
    ma5       = signal.get("tw_ma5", 0)
    ma10      = signal.get("tw_ma10", 0)
    ma20      = signal.get("tw_ma20", 0)
    ma5_p2    = signal.get("tw_ma5_p2", 0)
    ma10_p2   = signal.get("tw_ma10_p2", 0)
    ma20_p2   = signal.get("tw_ma20_p2", 0)
    prev_k_up = signal.get("tw_prev_close_up", False)
    intl_data = signal.get("intl_data", {})
    sox_chg   = intl_data.get("費城半導體", {}).get("chg_pct", 0)
    spx_chg   = intl_data.get("S&P500",   {}).get("chg_pct", 0)
    lc        = signal.get("tw_last_close", 0)

    ma1_bull = ma5 > ma10 > ma20
    ma1_bear = ma5 < ma10 < ma20
    ma2_bull = ma1_bull and (ma5_p2 > ma10_p2 > ma20_p2)
    ma2_bear = ma1_bear and (ma5_p2 < ma10_p2 < ma20_p2)
    macd_b   = macd > macds
    macd_s   = macd < macds

    # 精準版 (100%): MA2日+RSI<72+SOX>0.5+SPX>0
    if   ma2_bull and 45 < rsi < 72 and sox_chg > 0.5 and spx_chg > 0: dir_v100 = 1
    elif ma2_bear and 28 < rsi < 55 and sox_chg < -0.5 and spx_chg < 0: dir_v100 = -1
    else: dir_v100 = 0

    # 優化版 (90%): MA1日+MACD+前K收紅+RSI<80+SOX>0+SPX>0
    if   ma1_bull and macd_b and prev_k_up and 40 < rsi < 80 and sox_chg > 0 and spx_chg > 0: dir_v70 = 1
    elif ma1_bear and macd_s and (not prev_k_up) and 20 < rsi < 60 and sox_chg < 0 and spx_chg < 0: dir_v70 = -1
    else: dir_v70 = 0

    # 高頻版 (73%): MA1日+MACD+前K收紅
    if   ma1_bull and macd_b and prev_k_up and 30 < rsi < 80: dir_v60 = 1
    elif ma1_bear and macd_s and (not prev_k_up) and 20 < rsi < 70: dir_v60 = -1
    else: dir_v60 = 0

    # 超高頻版 (60%): MA1日對齊+RSI only
    if   ma1_bull and 30 < rsi < 85: dir_v50 = 1
    elif ma1_bear and 15 < rsi < 70: dir_v50 = -1
    else: dir_v50 = 0

    def _ver_card(ver_dir, win_rate, n_trades, label, desc, real_df_v=None):
        """單個版本的買賣建議小卡（含實倉統計）"""
        if ver_dir == 1:
            bg   = "rgba(16,185,129,.12)"; border = "#10b981"
            ico  = "🟢"; act = "買進"; act_detail = "8:45 買進 · 13:25 賣出"
            price_hint = f"{lc:,.0f} ～ {lc+80:,.0f}"
        elif ver_dir == -1:
            bg   = "rgba(239,68,68,.12)"; border = "#ef4444"
            ico  = "🔴"; act = "賣出"; act_detail = "8:45 放空 · 13:25 買回"
            price_hint = f"{lc-80:,.0f} ～ {lc:,.0f}"
        else:
            bg   = "rgba(107,114,128,.10)"; border = "#374151"
            ico  = "⚪"; act = "觀望"; act_detail = "今日條件不足，不交易"
            price_hint = "—"
        wr_color = "#10b981" if win_rate >= 80 else ("#f59e0b" if win_rate >= 65 else "#9ca3af")

        # 實倉統計行
        real_line = ""
        if real_df_v is not None and not real_df_v.empty:
            rv = real_df_v.copy()
            rv["pnl"]      = pd.to_numeric(rv["pnl_nts"], errors="coerce").fillna(0)
            rv["win_bool"] = rv["win"].map({"True": True, "False": False}).fillna(False)
            rv_traded = rv[rv["pnl"] != 0]
            if not rv_traded.empty:
                rt  = len(rv_traded)
                rw  = int(rv_traded["win_bool"].sum())
                rwr = rw / rt * 100
                rp  = rv_traded["pnl"].sum()
                rwr_c = "#10b981" if rwr >= 70 else ("#f59e0b" if rwr >= 50 else "#ef4444")
                rp_c  = "#10b981" if rp >= 0 else "#ef4444"
                real_line = (f'<div style="display:flex;justify-content:space-between;'
                             f'margin-top:6px;padding-top:6px;border-top:1px solid rgba(255,255,255,.06)">'
                             f'<span style="font-size:.62rem;color:#6b7280">實倉 {rt}筆</span>'
                             f'<span style="font-size:.72rem;font-weight:700;color:{rwr_c}">{rwr:.0f}%勝</span>'
                             f'<span style="font-size:.72rem;font-weight:700;color:{rp_c}">NT${rp:,.0f}</span>'
                             f'</div>')

        return f"""
        <div style="background:{bg};border:1.5px solid {border};border-radius:12px;padding:14px 16px;flex:1;min-width:0">
          <div style="font-size:.68rem;color:#9ca3af;margin-bottom:6px">{label}</div>
          <div style="font-size:1.5rem;font-weight:900;color:{border}">{ico} {act}</div>
          <div style="font-size:.75rem;color:#d1d5db;margin:5px 0">{act_detail}</div>
          <div style="display:flex;justify-content:space-between;margin-top:8px;
                      border-top:1px solid rgba(255,255,255,.08);padding-top:8px">
            <div>
              <div style="font-size:.62rem;color:#6b7280">參考進場價</div>
              <div style="font-size:.82rem;font-weight:700;color:#e2e8f0">{price_hint}</div>
            </div>
            <div style="text-align:right">
              <div style="font-size:.62rem;color:#6b7280">模擬勝率 ({n_trades}筆)</div>
              <div style="font-size:.9rem;font-weight:800;color:{wr_color}">{win_rate:.0f}%</div>
            </div>
          </div>
          {real_line}
          <div style="font-size:.62rem;color:#6b7280;margin-top:6px">{desc}</div>
        </div>"""

    # 從stats取四版本筆數和勝率（已有實際backtest結果）
    s100 = signal.get("stats_sim",  {}); n100 = s100.get("total", 13); wr100 = s100.get("win_rate", 100)
    s70  = signal.get("stats_v70",  {}); n70  = s70.get("total",  21); wr70  = s70.get("win_rate", 90)
    s60  = signal.get("stats_v60",  {}); n60  = s60.get("total",  37); wr60  = s60.get("win_rate", 73)
    s50  = signal.get("stats_v50",  {}); n50  = s50.get("total",  66); wr50  = s50.get("win_rate", 60)

    four_cards = (
        _ver_card(dir_v100, wr100, n100, "🎯 精準版 — MA2日+SOX>0.5%+RSI<72", "條件最嚴，少量高確信度",  real_v100_df) +
        _ver_card(dir_v70,  wr70,  n70,  "📊 優化版 — MA1日+MACD+前K+SOX",    "條件均衡，每月3-4筆",     real_v70_df) +
        _ver_card(dir_v60,  wr60,  n60,  "📈 高頻版 — MA1日+MACD+前K收紅",    "條件寬鬆，每月5-7筆",     real_v60_df) +
        _ver_card(dir_v50,  wr50,  n50,  "🔁 超高頻版 — MA1日對齊+RSI",        "條件最寬，每月8-12筆",    real_v50_df)
    )

    buy_sell_html = f"""
    <div class="card">
      <div class="stitle">📋 四版本今日買賣建議</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        {four_cards}
      </div>
      <div style="font-size:.65rem;color:#4b5563;margin-top:10px;text-align:center">
        ⚠️ 以上為回測信號，不保證獲利｜交易時間 08:45 進場 · 13:25 出場｜昨收 {lc:,.0f}
      </div>
    </div>"""

    # ── 最近一筆實際交易結算 ─────────────────────────────
    today_html = ""
    if not real_df.empty:
        last   = real_df.iloc[-1]
        ep     = last["entry"]
        xp     = last["exit_p"]
        pnl_v  = last["pnl"]
        pts_v  = last["pts"]
        won    = last["win_bool"]
        tdate  = last["date"].strftime("%m/%d") if pd.notna(last["date"]) else "─"
        dir_zh = e(last.get("direction_zh", "─"))

        if pd.notna(ep) and ep > 0:
            res_bg    = "rgba(16,185,129,.15)" if won else "rgba(239,68,68,.15)"
            res_color = "#10b981" if won else "#ef4444"
            res_icon  = "✅ 賺了" if won else "❌ 虧了"
            today_html = f"""
            <div class="card">
              <div class="stitle">最近一筆實際交易 · {tdate} {dir_zh}</div>
              <div class="row2">
                <div class="box2">
                  <div class="lbl">買進價格（開盤）</div>
                  <div class="big-num">{ep:,.0f}</div>
                </div>
                <div style="font-size:1.5rem;color:#6b7280;align-self:center">→</div>
                <div class="box2">
                  <div class="lbl">賣出價格（收盤）</div>
                  <div class="big-num">{xp:,.0f}</div>
                </div>
              </div>
              <div style="background:{res_bg};color:{res_color};border-radius:10px;
                          padding:14px;text-align:center;font-size:1.5rem;font-weight:800;margin-top:12px">
                {res_icon} NT${abs(pnl_v):,.0f}
                <span style="font-size:.9rem;opacity:.8">&ensp;（{pts_v:+.0f} 點）</span>
              </div>
            </div>"""
        else:
            today_html = """<div class="card">
              <div class="stitle">今日交易尚未結算</div>
              <p style="color:#9ca3af;font-size:.9rem;padding:4px 0">
                收盤 13:45 後自動更新，或手動執行「台指期收盤結算」捷徑</p>
            </div>"""
    else:
        today_html = """<div class="card">
          <div class="stitle">⚡ 實際交易記錄</div>
          <p style="color:#9ca3af;font-size:.9rem;padding:4px 0">
            今天剛開始！第一筆交易收盤後會自動出現在這裡</p>
        </div>"""

    # ── 實際交易累計統計 ─────────────────────────────────
    real_stats_html = ""
    if not real_df.empty:
        rt  = len(real_df)
        rw  = int(real_df["win_bool"].sum())
        rwr = rw / rt * 100
        rp  = real_df["pnl"].sum()
        real_stats_html = f"""
        <div class="card">
          <div class="stitle">✅ 實際交易累計</div>
          <div class="row3">
            <div class="box3" style="border-color:{pnl_color(rwr-50)}">
              <div class="big-num" style="color:{pnl_color(rwr-50)}">{rwr:.0f}%</div>
              <div class="lbl">勝率<br>{rw}勝 {rt-rw}敗</div>
            </div>
            <div class="box3" style="border-color:{pnl_color(rp)}">
              <div class="big-num" style="color:{pnl_color(rp)}">NT${rp:,.0f}</div>
              <div class="lbl">累計損益</div>
            </div>
            <div class="box3">
              <div class="big-num">{rt}</div>
              <div class="lbl">總交易次數</div>
            </div>
          </div>
        </div>"""
    else:
        real_stats_html = """<div class="card">
          <div class="stitle">✅ 實際交易累計</div>
          <p style="color:#9ca3af;font-size:.9rem;padding:4px 0">今天才剛開始，等第一筆交易完成後就會更新</p>
        </div>"""

    def _real_row_html(real_dfv):
        """若實倉有資料，生成一行實倉摘要HTML"""
        if real_dfv is None or real_dfv.empty:
            return '<p style="color:#4b5563;font-size:.72rem;margin-top:6px">📌 實倉：尚無記錄（今日起累計）</p>'
        rv = real_dfv.copy()
        rv["pnl"]      = pd.to_numeric(rv["pnl_nts"], errors="coerce").fillna(0)
        rv["win_bool"] = rv["win"].map({"True": True, "False": False}).fillna(False)
        rv_t = rv[rv["pnl"] != 0]
        if rv_t.empty:
            return '<p style="color:#4b5563;font-size:.72rem;margin-top:6px">📌 實倉：尚無完成交易</p>'
        rt  = len(rv_t)
        rw  = int(rv_t["win_bool"].sum())
        rwr = rw / rt * 100
        rp  = rv_t["pnl"].sum()
        rwr_c = "#10b981" if rwr >= 70 else ("#f59e0b" if rwr >= 50 else "#ef4444")
        rp_c  = "#10b981" if rp >= 0 else "#ef4444"
        return (f'<div style="display:flex;gap:12px;margin-top:8px;padding-top:8px;'
                f'border-top:1px dashed #374151;font-size:.75rem">'
                f'<span style="color:#9ca3af">📌 實倉 {rt}筆</span>'
                f'<span style="font-weight:700;color:{rwr_c}">{rwr:.0f}% 勝率</span>'
                f'<span style="font-weight:700;color:{rp_c}">NT${rp:,.0f}</span>'
                f'</div>')

    # ── 模擬回測統計 A：100% 高勝率版 ─────────────────
    sim_stats_html = ""
    if not sim_df.empty:
        sim_only = sim_df[sim_df["pnl"] != 0]
        if not sim_only.empty:
            st  = len(sim_only)
            sw  = int(sim_only["win_bool"].sum())
            swr = sw / st * 100
            sp  = sim_only["pnl"].sum()
            sim_stats_html = f"""
            <div class="card" style="opacity:.85;border:1px dashed #22c55e">
              <div class="stitle">🎯 精準版回測 — MA2日+RSI&lt;72+SOX共振</div>
              <div class="row3">
                <div class="box3">
                  <div class="big-num" style="font-size:1.3rem;color:{pnl_color(swr-50)}">{swr:.0f}%</div>
                  <div class="lbl">模擬勝率<br>{sw}勝 {st-sw}敗</div>
                </div>
                <div class="box3">
                  <div class="big-num" style="font-size:1.1rem;color:{pnl_color(sp)}">NT${sp:,.0f}</div>
                  <div class="lbl">模擬損益</div>
                </div>
                <div class="box3">
                  <div class="big-num" style="font-size:1.1rem">{st}</div>
                  <div class="lbl">回測筆數<br><span style="font-size:.65rem;color:#9ca3af">嚴格少量</span></div>
                </div>
              </div>
              {_real_row_html(real_v100_df)}
              <p style="color:#6b7280;font-size:.72rem;margin-top:6px">
                ⚠️ 歷史回測（非真實交易）｜條件嚴格，每月約2筆高確定性交易
              </p>
            </div>"""

    # ── 模擬回測統計 B：70% 高頻率版 ─────────────────
    sim_v70_stats_html = ""
    if not sim_v70_df.empty:
        sv70 = sim_v70_df.copy()
        sv70["pnl"]      = pd.to_numeric(sv70["pnl_nts"], errors="coerce").fillna(0)
        sv70["win_bool"] = sv70["win"].map({"True": True, "False": False}).fillna(False)
        sv70_only = sv70[sv70["pnl"] != 0]
        if not sv70_only.empty:
            vt  = len(sv70_only)
            vw  = int(sv70_only["win_bool"].sum())
            vwr = vw / vt * 100
            vp  = sv70_only["pnl"].sum()
            sim_v70_stats_html = f"""
            <div class="card" style="opacity:.80;border:1px dashed #f59e0b">
              <div class="stitle">📊 優化版回測 — MA1日+MACD+前K+SOX</div>
              <div class="row3">
                <div class="box3">
                  <div class="big-num" style="font-size:1.3rem;color:{pnl_color(vwr-50)}">{vwr:.0f}%</div>
                  <div class="lbl">歷史勝率<br>{vw}勝 {vt-vw}敗</div>
                </div>
                <div class="box3">
                  <div class="big-num" style="font-size:1.1rem;color:{pnl_color(vp)}">NT${vp:,.0f}</div>
                  <div class="lbl">模擬損益</div>
                </div>
                <div class="box3">
                  <div class="big-num" style="font-size:1.1rem">{vt}</div>
                  <div class="lbl">回測筆數<br><span style="font-size:.65rem;color:#9ca3af">寬鬆多量</span></div>
                </div>
              </div>
              {_real_row_html(real_v70_df)}
              <p style="color:#6b7280;font-size:.72rem;margin-top:6px">
                ⚠️ 歷史回測（非真實交易）｜條件寬鬆，每月約4-6筆參考
              </p>
            </div>"""

    # ── 模擬回測統計 C：60% 高頻版 ─────────────────
    sim_v60_stats_html = ""
    if not sim_v60_df.empty:
        sv60 = sim_v60_df.copy()
        sv60["pnl"]      = pd.to_numeric(sv60["pnl_nts"], errors="coerce").fillna(0)
        sv60["win_bool"] = sv60["win"].map({"True": True, "False": False}).fillna(False)
        sv60_only = sv60[sv60["pnl"] != 0]
        if not sv60_only.empty:
            vt  = len(sv60_only)
            vw  = int(sv60_only["win_bool"].sum())
            vwr = vw / vt * 100
            vp  = sv60_only["pnl"].sum()
            sim_v60_stats_html = f"""
            <div class="card" style="opacity:.75;border:1px dashed #6b7280">
              <div class="stitle">📈 高頻版回測 — MA1日+MACD+前K收紅</div>
              <div class="row3">
                <div class="box3">
                  <div class="big-num" style="font-size:1.3rem;color:{pnl_color(vwr-50)}">{vwr:.0f}%</div>
                  <div class="lbl">歷史勝率<br>{vw}勝 {vt-vw}敗</div>
                </div>
                <div class="box3">
                  <div class="big-num" style="font-size:1.1rem;color:{pnl_color(vp)}">NT${vp:,.0f}</div>
                  <div class="lbl">模擬損益</div>
                </div>
                <div class="box3">
                  <div class="big-num" style="font-size:1.1rem">{vt}</div>
                  <div class="lbl">回測筆數<br><span style="font-size:.65rem;color:#9ca3af">最多量</span></div>
                </div>
              </div>
              {_real_row_html(real_v60_df)}
              <p style="color:#6b7280;font-size:.72rem;margin-top:6px">
                ⚠️ 歷史回測（非真實交易）｜條件最寬，每月約8-12筆高頻參考
              </p>
            </div>"""

    # ── 模擬回測統計 D：超高頻版 (v50) ─────────────────
    sim_v50_stats_html = ""
    if not sim_v50_df.empty:
        sv50 = sim_v50_df.copy()
        sv50["pnl"]      = pd.to_numeric(sv50["pnl_nts"], errors="coerce").fillna(0)
        sv50["win_bool"] = sv50["win"].map({"True": True, "False": False}).fillna(False)
        sv50_only = sv50[sv50["pnl"] != 0]
        if not sv50_only.empty:
            vt  = len(sv50_only)
            vw  = int(sv50_only["win_bool"].sum())
            vwr = vw / vt * 100
            vp  = sv50_only["pnl"].sum()
            sim_v50_stats_html = f"""
            <div class="card" style="opacity:.70;border:1px dashed #4b5563">
              <div class="stitle">🔁 超高頻版回測 — MA1日對齊+RSI</div>
              <div class="row3">
                <div class="box3">
                  <div class="big-num" style="font-size:1.3rem;color:{pnl_color(vwr-50)}">{vwr:.0f}%</div>
                  <div class="lbl">歷史勝率<br>{vw}勝 {vt-vw}敗</div>
                </div>
                <div class="box3">
                  <div class="big-num" style="font-size:1.1rem;color:{pnl_color(vp)}">NT${vp:,.0f}</div>
                  <div class="lbl">模擬損益</div>
                </div>
                <div class="box3">
                  <div class="big-num" style="font-size:1.1rem">{vt}</div>
                  <div class="lbl">回測筆數<br><span style="font-size:.65rem;color:#9ca3af">超高頻</span></div>
                </div>
              </div>
              {_real_row_html(real_v50_df)}
              <p style="color:#6b7280;font-size:.72rem;margin-top:6px">
                ⚠️ 歷史回測（非真實交易）｜條件最寬鬆，每月約10-15筆超高頻參考
              </p>
            </div>"""

    # ── 金十數據快訊（JS 自動刷新，靜態初始值由 JSON 讀入）─
    jin10_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "jin10_news.json")
    jin10_init = "{}"
    if os.path.exists(jin10_path):
        with open(jin10_path, encoding="utf-8") as _f:
            jin10_init = _f.read().replace("</", "<\\/")   # 防止 HTML 注入

    jin10_html = f"""
<div class="card" id="jin10-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <div class="stitle" style="margin-bottom:0">⚡ 金十數據即時快訊</div>
    <div style="font-size:.65rem;color:#6b7280" id="jin10-meta">載入中…</div>
  </div>
  <div id="jin10-mood" style="margin-bottom:10px"></div>
  <div id="jin10-list"></div>
  <div style="font-size:.62rem;color:#4b5563;margin-top:8px;text-align:center">
    每5分鐘自動更新 · <span id="jin10-countdown">5:00</span> 後刷新
  </div>
</div>

<script>
(function(){{
  var INIT = {jin10_init};
  var BASE = window.location.href.replace(/\\/[^\\/]*$/, '');

  function tagCss(css){{
    if(css==='pos') return 'background:rgba(16,185,129,.2);color:#10b981';
    if(css==='neg') return 'background:rgba(239,68,68,.2);color:#ef4444';
    return 'background:rgba(148,163,184,.12);color:#94a3b8';
  }}

  function render(d){{
    if(!d || !d.items) return;
    var mc = d.mood_color || '#9ca3af';
    document.getElementById('jin10-mood').innerHTML =
      '<div style="display:flex;gap:10px;align-items:center">'
      +'<div style="background:'+mc+';color:#fff;border-radius:8px;padding:6px 14px;font-size:.9rem;font-weight:800">'+d.mood+'</div>'
      +'<div style="font-size:.75rem;color:#9ca3af">多:'+d.bull+' 空:'+d.bear+' 淨:'+((d.score>=0?'+':'')+d.score)+'</div>'
      +'</div>';
    var html = '';
    d.items.slice(0,15).forEach(function(it){{
      html += '<div style="padding:7px 0;border-bottom:1px solid #1e293b;font-size:.8rem;line-height:1.4">'
        +'<span style="'+tagCss(it.tag_css)+';font-size:.65rem;padding:1px 5px;border-radius:4px;margin-right:5px;white-space:nowrap">'+it.tag+'</span>'
        +'<span style="color:#94a3b8;font-size:.68rem;margin-right:5px">'+it.time.slice(11,16)+'</span>'
        +it.content
        +'</div>';
    }});
    document.getElementById('jin10-list').innerHTML = html;
    document.getElementById('jin10-meta').textContent = d.updated+' 更新';
  }}

  function fetchNews(){{
    fetch('data/jin10_news.json?t='+Date.now())
      .then(function(r){{ return r.json(); }})
      .then(function(d){{ render(d); }})
      .catch(function(){{}});
  }}

  // 初始渲染（靜態資料）
  render(INIT);

  // 倒計時 + 5分鐘自動刷新
  var secs = 300;
  setInterval(function(){{
    secs--;
    if(secs <= 0){{ secs = 300; fetchNews(); }}
    var m = Math.floor(secs/60);
    var s = secs%60;
    var el = document.getElementById('jin10-countdown');
    if(el) el.textContent = m+':'+(s<10?'0':'')+s;
  }}, 1000);
}})();
</script>"""

    # ── 近期損益橫條（只顯示實際交易，若無則顯示模擬）─
    show_for_bars = real_df if not real_df.empty else sim_df
    bars_label    = "實際交易" if not real_df.empty else "模擬回測（尚無實際交易）"
    bars_html = ""
    if not show_for_bars.empty:
        trading = show_for_bars[show_for_bars["pnl"] != 0].tail(15)
        if not trading.empty:
            max_abs = max(abs(trading["pnl"].max()), abs(trading["pnl"].min()), 1)
            rows = []
            for _, r in trading.iterrows():
                p   = r["pnl"]
                pct = abs(p) / max_abs * 82
                css = "bar-win" if r["win_bool"] else "bar-lose"
                ico = "✅" if r["win_bool"] else "❌"
                dtxt = r["date"].strftime("%m/%d") if pd.notna(r["date"]) else "─"
                rows.append(f"""<div class="bar-row">
                  <span class="bar-date">{dtxt}</span>
                  <div class="bar-wrap">
                    <div class="bar-fill {css}" style="width:{pct:.1f}%">
                      <span>{ico} NT${p:,.0f}</span>
                    </div>
                  </div>
                </div>""")
            bars_html = f"""<div class="card">
              <div class="stitle">近15筆損益 — {bars_label}</div>
              {"".join(rows)}
            </div>"""

    # ── 完整交易記錄表 ───────────────────────────────────
    # 實際交易在上面，模擬回測在下面（灰色）
    def make_table_rows(df, is_sim=False):
        if df.empty:
            return ""
        rows = []
        for _, r in df.sort_values("date", ascending=False).head(15).iterrows():
            dtxt  = r["date"].strftime("%m/%d") if pd.notna(r["date"]) else "─"
            d_int = int(r.get("direction", "0")) if str(r.get("direction","0")).lstrip("-").isdigit() else 0
            badge = ('<span class="badge-buy">做多</span>' if d_int == 1
                     else '<span class="badge-sell">做空</span>' if d_int == -1
                     else '<span class="badge-hold">觀望</span>')
            ep  = r["entry"]
            xp  = r["exit_p"]
            pnl = r["pnl"]
            won = r["win_bool"]
            ep_s = f"{ep:,.0f}" if pd.notna(ep) and ep > 0 else "─"
            xp_s = f"{xp:,.0f}" if pd.notna(xp) and xp > 0 else "─"
            pnl_s = (f'<span style="color:{"#10b981" if won else "#ef4444"};font-weight:700">'
                     f'NT${pnl:,.0f}</span>' if pnl != 0 else '<span style="color:#6b7280">─</span>')
            ico_s = ("✅" if won else "❌") if pnl != 0 else "─"
            op    = "0.55" if is_sim else "1"
            rows.append(f'<tr style="opacity:{op}"><td>{dtxt}</td><td>{badge}</td>'
                        f'<td>{ep_s}</td><td>{xp_s}</td><td>{pnl_s}</td><td style="text-align:center">{ico_s}</td></tr>')
        return "".join(rows)

    real_rows = make_table_rows(real_df, is_sim=False)
    sim_rows  = make_table_rows(sim_df,  is_sim=True)

    table_html = f"""<div class="card">
      <div class="stitle">完整交易記錄</div>
      <table>
        <tr><th>日期</th><th>方向</th><th>買進</th><th>賣出</th><th>損益</th><th>結果</th></tr>
        {real_rows if real_rows else '<tr><td colspan="6" style="color:#6b7280;text-align:center;padding:16px">尚無實際交易</td></tr>'}
        {(f'<tr><td colspan="6" style="color:#6b7280;font-size:.72rem;padding:6px 4px;border-top:1px dashed #374151">── 以下為模擬回測（非真實交易）──</td></tr>' + sim_rows) if sim_rows else ""}
      </table>
    </div>"""

    # ── 國際市場 ─────────────────────────────────────────
    intl_html = ""
    if signal.get("intl_data"):
        items = []
        for name, d in signal["intl_data"].items():
            sv    = d["signal"]
            chg   = d["chg_pct"]
            arrow = "▲" if sv == 1 else ("▼" if sv == -1 else "─")
            color = "#10b981" if sv == 1 else ("#ef4444" if sv == -1 else "#9ca3af")
            items.append(f"""<div class="intl-item">
              <div class="lbl">{e(name)}</div>
              <div style="font-size:1.05rem;font-weight:700;color:{color}">{arrow} {chg:+.2f}%</div>
              <div style="font-size:.68rem;color:#6b7280">{e(d['desc'])}</div>
            </div>""")
        intl_html = f"""<div class="card">
          <div class="stitle">🌐 國際市場概況</div>
          <div class="intl-grid">{"".join(items)}</div>
        </div>"""

    # ── 新聞 ─────────────────────────────────────────────
    news_html = ""
    if signal.get("news"):
        rows = []
        for n in signal["news"][:12]:
            sv  = n.get("sent_val", 0)
            css = "tag-pos" if sv == 1 else ("tag-neg" if sv == -1 else "tag-neu")
            ico = "✅" if sv == 1 else ("⚠️" if sv == -1 else "⚪")
            rows.append(f"""<div class="news-row">
              <span class="news-tag {css}">{ico} {e(n.get('label',''))}</span>
              {e(n.get('title',''))}
            </div>""")
        news_html = f"""<div class="card">
          <div class="stitle">📰 川普動態 & 市場新聞</div>
          {"".join(rows)}
        </div>"""

    # ── 長榮航太看板 ─────────────────────────────────────
    stock_html = stock_card_html(stock or {})

    # ── 評分明細 ─────────────────────────────────────────
    def sbar(label, val, max_abs):
        pct    = (val + max_abs) / (2 * max_abs) * 100
        center = 50
        if val >= 0:
            left, width = center, pct - center
        else:
            left, width = pct, center - pct
        color = "#10b981" if val >= 0 else "#ef4444"
        vc    = "#10b981" if val >= 0 else "#ef4444"
        return f"""<div class="srow">
          <span class="slbl">{label}</span>
          <div class="sbar-wrap">
            <div style="position:absolute;left:50%;width:1px;height:100%;background:#374151"></div>
            <div style="position:absolute;left:{left:.1f}%;width:{width:.1f}%;
                        height:100%;background:{color};opacity:.85;border-radius:3px"></div>
          </div>
          <span style="font-size:.85rem;font-weight:700;color:{vc};width:26px;text-align:right">{val:+d}</span>
        </div>"""

    score_html = (sbar("台灣技術", tw_s, 5)
                 + sbar("國際市場", int_s, 7)
                 + sbar("新聞情緒", nws_s, 2)
                 + (sbar("黃金警示", gold_contribution, 2) if gold else ""))

    # ── 組合 ─────────────────────────────────────────────
    gold_contribution = gold.get("signal", 0)

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>台指期看板</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#0f172a;--card:#1e293b;--card2:#334155;
      --g:#10b981;--r:#ef4444;--txt:#f1f5f9;--muted:#94a3b8;--border:#334155}}
body{{background:var(--bg);color:var(--txt);
  font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif;
  padding:14px;max-width:520px;margin:0 auto;-webkit-font-smoothing:antialiased}}
.card{{background:var(--card);border-radius:14px;padding:16px;margin-bottom:12px}}
.stitle{{font-size:.68rem;color:var(--muted);text-transform:uppercase;
  letter-spacing:.1em;margin-bottom:10px}}
.lbl{{font-size:.75rem;color:var(--muted);margin-bottom:2px}}
.big-num{{font-size:1.6rem;font-weight:800}}
.row2{{display:grid;grid-template-columns:1fr auto 1fr;gap:8px;align-items:start}}
.box2{{background:var(--card2);border-radius:10px;padding:12px}}
.row3{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}
.box3{{background:var(--card2);border-radius:10px;padding:12px;text-align:center;
  border-top:3px solid var(--border)}}
.bar-row{{display:flex;align-items:center;gap:6px;margin-bottom:5px}}
.bar-date{{width:34px;color:var(--muted);font-size:.72rem;text-align:right;flex-shrink:0}}
.bar-wrap{{flex:1;height:22px;background:var(--card2);border-radius:4px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:4px;display:flex;align-items:center;
  padding:0 6px;min-width:40px}}
.bar-fill span{{font-size:.72rem;font-weight:600;white-space:nowrap;color:#fff}}
.bar-win{{background:linear-gradient(90deg,#059669,#10b981)}}
.bar-lose{{background:linear-gradient(90deg,#b91c1c,#ef4444)}}
table{{width:100%;border-collapse:collapse;font-size:.82rem}}
th{{color:var(--muted);font-weight:600;font-size:.68rem;text-align:left;
  padding:5px 4px;border-bottom:1px solid var(--border)}}
td{{padding:8px 4px;border-bottom:1px solid var(--border);vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
.badge-buy{{background:rgba(16,185,129,.2);color:var(--g);
  padding:2px 8px;border-radius:20px;font-size:.73rem;font-weight:600;white-space:nowrap}}
.badge-sell{{background:rgba(239,68,68,.2);color:var(--r);
  padding:2px 8px;border-radius:20px;font-size:.73rem;font-weight:600;white-space:nowrap}}
.badge-hold{{background:rgba(148,163,184,.15);color:var(--muted);
  padding:2px 8px;border-radius:20px;font-size:.73rem;white-space:nowrap}}
.intl-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}
.intl-item{{background:var(--card2);border-radius:10px;padding:10px 12px}}
.news-row{{padding:9px 0;border-bottom:1px solid var(--border);
  font-size:.82rem;line-height:1.4}}
.news-row:last-child{{border-bottom:none}}
.news-tag{{display:inline-block;font-size:.68rem;padding:1px 6px;border-radius:4px;
  margin-right:5px;vertical-align:middle;white-space:nowrap}}
.tag-pos{{background:rgba(16,185,129,.2);color:var(--g)}}
.tag-neg{{background:rgba(239,68,68,.2);color:var(--r)}}
.tag-neu{{background:rgba(148,163,184,.12);color:var(--muted)}}
.srow{{display:flex;align-items:center;gap:8px;margin-bottom:9px}}
.slbl{{width:62px;font-size:.76rem;color:var(--muted);flex-shrink:0}}
.sbar-wrap{{flex:1;height:18px;background:var(--card2);border-radius:4px;position:relative}}
</style>
</head>
<body>

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
  <div style="font-size:1.2rem;font-weight:700">📈 台指期智能看板</div>
  <div style="font-size:.72rem;color:var(--muted)">{now} 更新</div>
</div>

<!-- 夜盤預覽 -->
{night_html}

<!-- 黃金警示 -->
{gold_html}

<!-- 今日狀態 -->
{today_card}

<!-- 明日信號 -->
<div style="background:{sig_bg};border-radius:16px;padding:22px 18px;
            margin-bottom:12px;text-align:center">
  <div style="font-size:1.85rem;font-weight:800">{sig_label}</div>
  <div style="font-size:.95rem;opacity:.9;margin-top:6px">{trade_date}</div>
  <div style="font-size:.85rem;opacity:.85;background:rgba(0,0,0,.2);
              border-radius:8px;padding:8px 12px;margin-top:10px">{sig_action}</div>
  <div style="font-size:.73rem;opacity:.7;margin-top:6px">{score_detail}</div>
</div>

<!-- 長榮航太 -->
{stock_html}

<!-- 買賣操作建議 -->
{buy_sell_html}

<!-- 今日結算 -->
{today_html}

<!-- 實際累計 -->
{real_stats_html}

<!-- 模擬回測 精準版 -->
{sim_stats_html}

<!-- 模擬回測 寬鬆版 -->
{sim_v70_stats_html}

<!-- 模擬回測 高頻版 -->
{sim_v60_stats_html}

<!-- 模擬回測 超高頻版 -->
{sim_v50_stats_html}

<!-- 評分明細 -->
<div class="card">
  <div class="stitle">今日評分明細</div>
  {score_html}
</div>

<!-- 近期損益條 -->
{bars_html}

<!-- 交易記錄 -->
{table_html}

<!-- 國際市場 -->
{intl_html}

<!-- 新聞 -->
{news_html}

<!-- 金十數據即時快訊 -->
{jin10_html}

<div style="text-align:center;color:var(--muted);font-size:.68rem;padding:18px 0 6px">
  ⚠️ 本看板為輔助參考，不構成投資建議<br>
  微型台指(MXF)每點 NT$10 ｜ 建議停損 20~30 點（NT$200~300）
</div>

</body>
</html>"""


def main():
    print("📂 載入資料...", flush=True)
    signal, records, stock = load_data()
    print("🎨 產生看板...", flush=True)
    html = generate_html(signal, records, stock)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 看板已儲存: {OUTPUT_PATH}")
    # CI: skip browser open

if __name__ == "__main__":
    main()
