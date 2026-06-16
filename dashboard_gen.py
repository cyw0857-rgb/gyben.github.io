#!/usr/bin/env python3
"""台指期 HTML 看板產生器 — 暗色主題，手機電腦通用"""

import json, os, subprocess, math
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
    """長榮航太 (2645.TW) 看板卡片 — 左右雙欄美化版"""
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
    total_score = stock.get("total_score", stock.get("score", 0))
    tech_score  = stock.get("tech_score", 0)
    updated     = stock.get("updated", "")
    rsi         = stock.get("rsi", 0)
    k_val       = stock.get("k", 0)
    d_val       = stock.get("d", 0)
    macd        = stock.get("macd", 0)
    macds       = stock.get("macds", 0)
    ma5         = stock.get("ma5", 0)
    ma20        = stock.get("ma20", 0)
    ma60        = stock.get("ma60", 0)
    tech_details = stock.get("tech_details", [])
    inst        = stock.get("inst", {})
    retail      = stock.get("retail", {})
    weekly      = stock.get("weekly", {})
    forecast    = stock.get("forecast", [])
    trend_label = stock.get("trend_label", "")
    daily_vol   = stock.get("daily_vol_pct", 0)

    chg_color   = "#10b981" if chg_pct >= 0 else "#ef4444"
    chg_arrow   = "▲" if chg_pct >= 0 else "▼"
    score_color = "#10b981" if total_score >= 0 else "#ef4444"
    rsi_color   = "#10b981" if 45 < rsi < 72 else ("#f59e0b" if rsi >= 72 else "#ef4444")

    # ── 三大法人 5日表格 ──────────────────────────────────
    def num_fmt(v):
        if v > 0:   return f'<span style="color:#10b981">+{v//1000:.0f}k</span>'
        if v < 0:   return f'<span style="color:#ef4444">{v//1000:.0f}k</span>'
        return '<span style="color:#6b7280">─</span>'

    inst_rows_html = ""
    for row in inst.get("rows", []):
        inst_rows_html += (
            f'<tr>'
            f'<td style="color:#94a3b8;padding:4px 3px">{row["date"]}</td>'
            f'<td style="text-align:right;padding:4px 3px">{num_fmt(row["foreign"])}</td>'
            f'<td style="text-align:right;padding:4px 3px">{num_fmt(row["trust"])}</td>'
            f'<td style="text-align:right;padding:4px 3px">{num_fmt(row["dealer"])}</td>'
            f'<td style="text-align:right;padding:4px 3px;font-weight:700">{num_fmt(row["total"])}</td>'
            f'</tr>'
        )

    t5f  = inst.get("total_foreign", 0)
    t5t  = inst.get("total_trust", 0)
    t5d  = inst.get("total_dealer", 0)
    inst_mood       = inst.get("mood", "─")
    inst_mood_color = "#10b981" if inst_mood == "偏多" else ("#ef4444" if inst_mood == "偏空" else "#9ca3af")

    # ── 散戶情緒 ─────────────────────────────────────────
    retail_mood       = retail.get("mood", "─")
    retail_mood_color = "#10b981" if "樂觀" in retail_mood else ("#ef4444" if "悲觀" in retail_mood else "#9ca3af")
    vol_ratio         = retail.get("vol_ratio", 1.0)
    vol_bar_w         = min(int(vol_ratio / 3.0 * 100), 100)
    vol_color         = "#f59e0b" if vol_ratio > 1.5 else ("#10b981" if vol_ratio >= 0.8 else "#6b7280")
    retail_signals    = retail.get("signals", [])
    retail_sig_html   = "".join(
        f'<div style="font-size:.72rem;color:#94a3b8;padding:2px 0">{s["icon"]} {e(s["text"])}</div>'
        for s in retail_signals
    )

    # ── 技術面細節 ────────────────────────────────────────
    tech_detail_html = "".join(
        f'<div style="font-size:.72rem;padding:3px 0;border-bottom:1px solid #0f172a">'
        f'<span style="margin-right:4px">{d["icon"]}</span>'
        f'<span style="color:#cbd5e1">{e(d["text"])}</span>'
        f'<span style="float:right;color:{"#10b981" if d["score"]>0 else "#ef4444" if d["score"]<0 else "#6b7280"}'
        f';font-weight:700">{d["score"]:+d}</span>'
        f'</div>'
        for d in tech_details
    )

    # ── 下週預估 ─────────────────────────────────────────
    wp_low    = weekly.get("proj_low", 0)
    wp_high   = weekly.get("proj_high", 0)
    wp_center = weekly.get("proj_center", 0)
    wp_trend  = weekly.get("trend_bias", "")
    wp_hint   = weekly.get("op_hint", "")
    wp_sup    = weekly.get("support", 0)
    wp_res    = weekly.get("resistance", 0)
    trend_color = "#10b981" if "多" in wp_trend else ("#ef4444" if "空" in wp_trend else "#9ca3af")

    # ── 半年走勢 ─────────────────────────────────────────
    def ta(t): return "▲" if t == "up" else ("▼" if t == "down" else "─")
    def tc(t): return "#10b981" if t == "up" else ("#ef4444" if t == "down" else "#9ca3af")

    fc_rows = ""
    for fc in forecast:
        chg = fc["chg_pct"]
        cc  = "#10b981" if chg >= 0 else "#ef4444"
        fc_rows += (
            f'<tr>'
            f'<td style="color:#94a3b8;padding:4px 3px">{fc["month"]}</td>'
            f'<td style="color:{tc(fc["trend"])};font-weight:700;padding:4px 3px">{ta(fc["trend"])} {fc["price"]}</td>'
            f'<td style="color:{cc};padding:4px 3px">{chg:+.1f}%</td>'
            f'<td style="color:#6b7280;font-size:.68rem;padding:4px 3px">{fc["price_low"]}~{fc["price_high"]}</td>'
            f'</tr>'
        )

    return f"""
<div class="card stock-premium-card" style="padding:0;overflow:hidden">

  <!-- 標題列 -->
  <div style="background:linear-gradient(90deg,#162032,#0e1829);
              padding:12px 16px;display:flex;justify-content:space-between;align-items:center">
    <div style="font-size:.78rem;font-weight:700;color:#f1f5f9">✈️ {e(name)} ({e(symbol)})</div>
    <div style="display:flex;align-items:center;gap:6px">
      <span style="font-size:.6rem;color:#64748b">{e(updated)} 更新</span>
      <button onclick="window.location.reload()" style="background:rgba(59,130,246,.12);border:1px solid rgba(59,130,246,.35);color:#60a5fa;border-radius:5px;padding:2px 8px;font-size:.6rem;cursor:pointer;line-height:1.6">🔄</button>
    </div>
  </div>

  <div style="padding:14px 14px 0">

  <!-- 左右雙欄 -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px">

    <!-- 左：價格 + 信號 + 指標 -->
    <div>
      <div style="background:#080f1e;border-radius:10px;padding:12px;margin-bottom:8px;text-align:center">
        <div style="font-size:1.7rem;font-weight:900;letter-spacing:-.5px">NT${last_close:.1f}</div>
        <div style="font-size:.9rem;font-weight:700;color:{chg_color};margin-top:2px">{chg_arrow} {chg_pct:+.2f}%</div>
        <div style="font-size:.6rem;color:#475569;margin-top:4px">MA5 {ma5:.1f} · MA20 {ma20:.1f} · MA60 {ma60:.1f}</div>
      </div>
      <div style="background:{sig_color}1a;border:1.5px solid {sig_color};
                  border-radius:10px;padding:10px;margin-bottom:8px;text-align:center">
        <div style="font-size:.6rem;color:#6b7280;margin-bottom:3px">明日預測</div>
        <div style="font-size:1rem;font-weight:900;color:{sig_color}">{e(signal_text)}</div>
        <div style="font-size:.65rem;margin-top:4px">
          <span style="color:{score_color};font-weight:700">綜合 {total_score:+d}</span>
          <span style="color:#475569"> · 技術 {tech_score:+d} · 法人 {inst.get("score",0):+d} · 散戶 {retail.get("score",0):+d}</span>
        </div>
      </div>
      <div style="background:#080f1e;border-radius:10px;padding:10px;margin-bottom:8px">
        <div style="font-size:.6rem;color:#6b7280;margin-bottom:3px">續抱建議</div>
        <div style="font-size:.75rem;font-weight:700;color:{hold_color};line-height:1.4">{e(hold_advice)}</div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:5px">
        <div style="background:#080f1e;border-radius:8px;padding:7px;text-align:center">
          <div style="font-size:.58rem;color:#6b7280">RSI</div>
          <div style="font-size:.88rem;font-weight:800;color:{rsi_color}">{rsi:.0f}</div>
        </div>
        <div style="background:#080f1e;border-radius:8px;padding:7px;text-align:center">
          <div style="font-size:.58rem;color:#6b7280">K/D</div>
          <div style="font-size:.72rem;font-weight:700;color:#f59e0b">{k_val:.0f}/{d_val:.0f}</div>
        </div>
        <div style="background:#080f1e;border-radius:8px;padding:7px;text-align:center">
          <div style="font-size:.58rem;color:#6b7280">MACD</div>
          <div style="font-size:.72rem;font-weight:700;color:{"#10b981" if macd > macds else "#ef4444"}">{"金叉" if macd > macds else "死叉"}</div>
        </div>
      </div>
    </div>

    <!-- 右：三大法人 -->
    <div>
      <div style="background:#080f1e;border-radius:10px;padding:10px;height:100%">
        <div style="font-size:.6rem;color:#6b7280;margin-bottom:6px;letter-spacing:.05em">
          🏦 三大法人 近5日（千股）
        </div>
        <table style="width:100%;border-collapse:collapse;font-size:.66rem">
          <tr>
            <th style="color:#475569;padding:2px 2px;text-align:left">日期</th>
            <th style="color:#3b82f6;padding:2px 2px;text-align:right">外資</th>
            <th style="color:#8b5cf6;padding:2px 2px;text-align:right">投信</th>
            <th style="color:#f59e0b;padding:2px 2px;text-align:right">自營</th>
            <th style="color:#94a3b8;padding:2px 2px;text-align:right">合計</th>
          </tr>
          {inst_rows_html if inst_rows_html else '<tr><td colspan="5" style="color:#4b5563;text-align:center;padding:8px">暫無資料</td></tr>'}
        </table>
        <div style="margin-top:8px;padding-top:7px;border-top:1px solid #1e3050">
          <div style="font-size:.58rem;color:#6b7280;margin-bottom:4px">5日累計</div>
          <div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:6px">
            <span style="font-size:.62rem">外資 {num_fmt(t5f)}</span>
            <span style="font-size:.62rem">投信 {num_fmt(t5t)}</span>
            <span style="font-size:.62rem">自營 {num_fmt(t5d)}</span>
          </div>
          <div style="display:flex;gap:5px;flex-wrap:wrap">
            <div style="background:{inst_mood_color}22;border:1px solid {inst_mood_color};
                        border-radius:5px;padding:2px 7px;font-size:.65rem;
                        font-weight:700;color:{inst_mood_color}">法人 {inst_mood}</div>
            <div style="background:{retail_mood_color}22;border:1px solid {retail_mood_color};
                        border-radius:5px;padding:2px 7px;font-size:.65rem;
                        font-weight:700;color:{retail_mood_color}">散戶 {retail_mood}</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 散戶情緒 -->
  <div style="background:#080f1e;border-radius:10px;padding:10px;margin-bottom:10px">
    <div style="font-size:.6rem;color:#6b7280;margin-bottom:6px">👥 散戶情緒推估</div>
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
      <div style="font-size:.8rem;font-weight:700;color:{retail_mood_color}">{retail_mood}</div>
      <div style="flex:1">
        <div style="font-size:.58rem;color:#475569;margin-bottom:2px">成交量 / 20日均量</div>
        <div style="background:#162032;border-radius:4px;height:7px;overflow:hidden">
          <div style="background:{vol_color};height:100%;width:{vol_bar_w}%;border-radius:4px"></div>
        </div>
      </div>
      <div style="font-size:.75rem;font-weight:700;color:{vol_color}">{vol_ratio:.1f}x</div>
    </div>
    {retail_sig_html if retail_sig_html else '<div style="font-size:.7rem;color:#475569">量能正常，無特殊訊號</div>'}
  </div>

  <!-- 技術面評分依據 -->
  <div style="background:#080f1e;border-radius:10px;padding:10px;margin-bottom:10px">
    <div style="font-size:.6rem;color:#6b7280;margin-bottom:6px">📊 技術面評分依據</div>
    {tech_detail_html if tech_detail_html else '<div style="font-size:.7rem;color:#475569">技術資料載入中</div>'}
  </div>

  <!-- 下週走勢預估 -->
  <div style="background:#080f1e;border-radius:10px;padding:10px;margin-bottom:10px">
    <div style="font-size:.6rem;color:#6b7280;margin-bottom:8px">📅 下週走勢預估（5個交易日）</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">
      <div style="background:#162032;border-radius:8px;padding:8px">
        <div style="font-size:.58rem;color:#6b7280;margin-bottom:3px">預估區間</div>
        <div style="font-size:.85rem;font-weight:800">
          <span style="color:#10b981">{wp_low}</span>
          <span style="color:#475569"> ~ </span>
          <span style="color:#ef4444">{wp_high}</span>
        </div>
        <div style="font-size:.62rem;color:#475569;margin-top:2px">中心 {wp_center}</div>
      </div>
      <div style="background:#162032;border-radius:8px;padding:8px">
        <div style="font-size:.58rem;color:#6b7280;margin-bottom:3px">支撐 / 壓力</div>
        <div style="font-size:.75rem;font-weight:700">
          <span style="color:#10b981">{wp_sup}</span>
          <span style="color:#475569"> / </span>
          <span style="color:#ef4444">{wp_res}</span>
        </div>
        <div style="font-size:.62rem;color:{trend_color};margin-top:2px;font-weight:600">{wp_trend}</div>
      </div>
    </div>
    <div style="background:rgba(99,102,241,.08);border-left:3px solid #6366f1;
                padding:7px 10px;border-radius:0 6px 6px 0;font-size:.7rem;color:#a5b4fc">
      💡 {e(wp_hint)}
    </div>
  </div>

  <!-- 半年走勢預測 -->
  <div style="background:#080f1e;border-radius:10px;padding:10px;margin-bottom:14px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <div style="font-size:.6rem;color:#6b7280">📈 半年走勢預測</div>
      <div style="font-size:.6rem;color:#475569">{e(trend_label)} · 日波動率 {daily_vol:.1f}%</div>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:.75rem">
      <tr style="border-bottom:1px solid #1e3050">
        <th style="color:#475569;font-size:.6rem;padding:3px 3px;text-align:left">月份</th>
        <th style="color:#475569;font-size:.6rem;padding:3px 3px;text-align:right">預估價</th>
        <th style="color:#475569;font-size:.6rem;padding:3px 3px;text-align:right">變動</th>
        <th style="color:#475569;font-size:.6rem;padding:3px 3px;text-align:right">±1σ區間</th>
      </tr>
      {fc_rows}
    </table>
    <div style="font-size:.6rem;color:#374151;margin-top:6px;text-align:center">
      ⚠️ 線性回歸預測，僅供參考，不構成投資建議
    </div>
  </div>

  </div>
</div>"""


def generate_html(signal, records, stock=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    sig_generated_at = signal.get("generated_at", now)
    stock_updated    = (stock or {}).get("updated", "─")

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

    # ── 金十數據快訊（瀏覽器直連 jin10.com，不依賴 GitHub Actions）─
    jin10_html = """
<div class="card j10-card" id="jin10-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <div class="stitle" style="margin-bottom:0">⚡ 金十數據即時快訊</div>
    <div style="display:flex;align-items:center;gap:8px">
      <span id="jin10-status-dot" style="display:inline-block;width:7px;height:7px;
            border-radius:50%;background:#f59e0b;animation:blink 1s infinite"></span>
      <span style="font-size:.62rem;color:#64748b" id="jin10-meta">載入中…</span>
    </div>
  </div>
  <div id="jin10-mood" style="margin-bottom:10px">
    <div style="color:#475569;font-size:.78rem;padding:8px 0">⏳ 直連金十數據…</div>
  </div>
  <div id="jin10-list"></div>
  <div style="display:flex;justify-content:space-between;align-items:center;
              margin-top:10px;padding-top:8px;border-top:1px solid #1e3050">
    <div style="font-size:.62rem;color:#475569">每5分鐘自動更新</div>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="font-size:.62rem;color:#475569"><span id="jin10-countdown">5:00</span> 後刷新</span>
      <button onclick="window.j10Load&&window.j10Load()" style="background:rgba(59,130,246,.12);border:1px solid rgba(59,130,246,.35);color:#60a5fa;border-radius:5px;padding:2px 8px;font-size:.6rem;cursor:pointer;line-height:1.6">🔄 立即刷新</button>
    </div>
  </div>
</div>

<script>
(function(){
  var BULL=['上漲','上涨','漲','涨','突破','走強','走强','利好','降息','增長','增长',
    '新高','反彈','反弹','走高','強勁','强劲','超預期','超预期','多頭','多头',
    '做多','上行','回升','好轉','好转','樂觀','乐观','刺激','寬鬆','宽松',
    '復甦','复苏','擴張','扩张','增速','就業','就业','非農','利多',
    'surge','rally','gain','rise','bull','strong','beat','record','optimism',
    'stimulus','cut','ease','growth','rebound'];
  var BEAR=['下跌','跌','走弱','利空','加息','衰退','下滑','萎縮','萎缩','崩','拋售','抛售',
    '通脹','通胀','風險','风险','緊縮','紧缩','下行','惡化','恶化','悲觀','悲观',
    '衝突','冲突','制裁','危機','危机','違約','违约','破產','破产','失業','失业',
    'fall','drop','plunge','crash','recession','inflation','fear','risk','tension',
    'tariff','sanction','ban','war','decline','slowdown','miss','layoff'];
  var SKIP=['【提示】','【广告】','【招聘】'];

  function stripHtml(s){ return s.replace(/<[^>]+>/g,'').trim(); }

  function sentiment(txt){
    var lo=txt.toLowerCase(),b=0,br=0;
    BULL.forEach(function(w){ if(lo.indexOf(w)>=0) b++; });
    BEAR.forEach(function(w){ if(lo.indexOf(w)>=0) br++; });
    return b>br?1:br>b?-1:0;
  }

  function tagStyle(css){
    if(css==='pos') return 'background:rgba(16,185,129,.15);color:#10b981;border:1px solid rgba(16,185,129,.25)';
    if(css==='neg') return 'background:rgba(239,68,68,.15);color:#ef4444;border:1px solid rgba(239,68,68,.25)';
    return 'background:rgba(100,116,139,.12);color:#64748b;border:1px solid rgba(100,116,139,.2)';
  }

  function setDot(state){
    var dot=document.getElementById('jin10-status-dot');
    if(!dot) return;
    dot.style.background=state==='ok'?'#10b981':state==='err'?'#ef4444':'#f59e0b';
    dot.style.animation=state==='fetching'?'blink 1s infinite':'none';
  }

  function j10Process(raw){
    var items=[],bull=0,bear=0;
    raw.forEach(function(it){
      var td=it.data||{};
      var c=stripHtml(td.title||td.content||'');
      if(!c||c.length<5) return;
      for(var i=0;i<SKIP.length;i++){ if(c.indexOf(SKIP[i])>=0) return; }
      var sv=sentiment(c);
      if(sv===1) bull++;else if(sv===-1) bear++;
      items.push({time:(it.time||'').slice(0,16),content:c.slice(0,120),
        sentiment:sv,tag:sv===1?'✅偏多':sv===-1?'⚠️偏空':'⚪中性',
        tag_css:sv===1?'pos':sv===-1?'neg':'neu'});
    });
    items=items.slice(0,30);
    var tot=bull-bear,mood,mc;
    if(tot>=3){mood='偏多 📈';mc='#10b981';}
    else if(tot>=1){mood='略偏多';mc='#34d399';}
    else if(tot<=-3){mood='偏空 📉';mc='#ef4444';}
    else if(tot<=-1){mood='略偏空';mc='#f87171';}
    else{mood='中性 ─';mc='#9ca3af';}
    var now=new Date(),hh=String(now.getHours()).padStart(2,'0'),mm=String(now.getMinutes()).padStart(2,'0');
    return {items:items,bull:bull,bear:bear,score:tot,mood:mood,mood_color:mc,updated:hh+':'+mm};
  }

  function render(d){
    if(!d||!d.items||!d.items.length){
      document.getElementById('jin10-mood').innerHTML=
        '<div style="color:#475569;font-size:.78rem;padding:8px 0">⚠️ 金十數據載入失敗，請稍後刷新</div>';
      document.getElementById('jin10-meta').textContent='載入失敗';
      setDot('err');return;
    }
    var mc=d.mood_color||'#64748b';
    document.getElementById('jin10-mood').innerHTML=
      '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
      +'<div style="background:'+mc+'22;border:1.5px solid '+mc+';color:'+mc+
         ';border-radius:8px;padding:5px 12px;font-size:.88rem;font-weight:800">'+d.mood+'</div>'
      +'<div style="font-size:.73rem;color:#94a3b8">多 <b style="color:#10b981">'+d.bull+'</b>'
      +' ／ 空 <b style="color:#ef4444">'+d.bear+'</b>'
      +' ／ 淨 <b>'+((d.score>=0?'+':'')+d.score)+'</b></div>'
      +'</div>';
    var html='';
    d.items.slice(0,15).forEach(function(it,i){
      html+='<div style="padding:7px 0;border-bottom:1px solid rgba(30,48,80,.5);'
        +'font-size:.78rem;line-height:1.45">'
        +'<span style="'+tagStyle(it.tag_css)+';font-size:.62rem;padding:1px 6px;'
        +'border-radius:4px;margin-right:5px;white-space:nowrap;font-weight:600">'+it.tag+'</span>'
        +'<span style="color:#475569;font-size:.66rem;margin-right:5px">'+it.time.slice(11,16)+'</span>'
        +'<span id="jt-'+i+'" style="color:#cbd5e1">'+it.content+'</span>'
        +'</div>';
    });
    document.getElementById('jin10-list').innerHTML=html;
    document.getElementById('jin10-meta').textContent=d.updated+' 更新';
    setDot('ok');
    /* 簡體→繁體翻譯 */
    var contents=d.items.slice(0,15).map(function(it){return it.content;});
    var joined=contents.join('\\n');
    fetch('https://translate.googleapis.com/translate_a/single?client=gtx&sl=zh-CN&tl=zh-TW&dt=t&q='+encodeURIComponent(joined))
      .then(function(r){return r.json();})
      .then(function(data){
        var full=(data[0]||[]).map(function(s){return s[0]||'';}).join('');
        var parts=full.split('\\n');
        contents.forEach(function(_,i){
          var el=document.getElementById('jt-'+i);
          if(el&&parts[i]&&parts[i].trim()) el.textContent=parts[i].trim();
        });
      })
      .catch(function(){});
  }

  function j10Load(){
    var old=document.getElementById('_j10s');
    if(old) old.parentNode.removeChild(old);
    window.newest=null;
    setDot('fetching');
    var s=document.createElement('script');
    s.id='_j10s';
    s.src='https://www.jin10.com/flash_newest.js?_='+Date.now();
    s.onload=function(){
      if(window.newest&&Array.isArray(window.newest))
        render(j10Process(window.newest));
      else{
        document.getElementById('jin10-meta').textContent='資料格式異常';
        setDot('err');
      }
    };
    s.onerror=function(){
      document.getElementById('jin10-meta').textContent='連接失敗，重試中';
      setDot('err');
    };
    document.head.appendChild(s);
  }

  window.j10Load=j10Load;
  j10Load();
  var secs=300;
  setInterval(function(){
    secs--;
    if(secs<=0){secs=300;j10Load();}
    var m=Math.floor(secs/60),s=secs%60;
    var el=document.getElementById('jin10-countdown');
    if(el) el.textContent=m+':'+(s<10?'0':'')+s;
  },1000);
})();
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

    # ── 國際市場（JS 即時渲染，從 data/intl.json 取資料）──────
    intl_html = """<div class="card" id="intl-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <div class="stitle" style="margin-bottom:0">🌐 國際市場概況</div>
    <div style="display:flex;align-items:center;gap:6px">
      <span style="font-size:.6rem;color:#64748b" id="intl-meta">載入中…</span>
      <button onclick="intlLoad()" style="background:rgba(59,130,246,.12);border:1px solid rgba(59,130,246,.35);color:#60a5fa;border-radius:5px;padding:2px 8px;font-size:.6rem;cursor:pointer;line-height:1.6">🔄</button>
    </div>
  </div>
  <div id="intl-grid" class="intl-grid">
    <div style="color:#475569;font-size:.78rem;padding:8px 0;grid-column:1/-1">⏳ 載入中…</div>
  </div>
  <div style="font-size:.58rem;color:#334155;margin-top:8px">每10分鐘自動更新</div>
</div>

<script>
(function(){
  function render(d){
    if(!d||!d.data){
      document.getElementById('intl-meta').textContent='載入失敗';
      return;
    }
    var html='';
    Object.keys(d.data).forEach(function(name){
      var it=d.data[name];
      var sv=it.signal||0;
      var chg=it.chg_pct||0;
      var ic=sv===1?'#10b981':sv===-1?'#ef4444':'#64748b';
      var arrow=sv===1?'▲':sv===-1?'▼':'─';
      var bg=sv===1?'rgba(16,185,129,.08)':sv===-1?'rgba(239,68,68,.08)':'transparent';
      html+='<div class="intl-item" style="background:'+bg+'">'
        +'<div style="font-size:.65rem;color:#64748b;margin-bottom:3px">'+name+'</div>'
        +'<div style="font-size:1rem;font-weight:800;color:'+ic+'">'+arrow+' '+(chg>=0?'+':'')+chg.toFixed(2)+'%</div>'
        +'<div style="font-size:.65rem;color:#475569;margin-top:2px">'+it.desc+'</div>'
        +'</div>';
    });
    document.getElementById('intl-grid').innerHTML=html;
    document.getElementById('intl-meta').textContent=d.updated+' 更新';
  }
  window.intlLoad=function(){
    document.getElementById('intl-meta').textContent='更新中…';
    fetch('data/intl.json?_='+Date.now())
      .then(function(r){return r.json();})
      .then(render)
      .catch(function(){document.getElementById('intl-meta').textContent='載入失敗';});
  };
  intlLoad();
  setInterval(intlLoad,600000);   /* 每10分鐘 */
})();
</script>"""

    # ── 新聞（JS 即時渲染，從 data/news.json 取資料）────────
    news_html = """<div class="card" id="news-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <div class="stitle" style="margin-bottom:0">📰 川普動態 & 市場新聞</div>
    <div style="display:flex;align-items:center;gap:6px">
      <span style="font-size:.6rem;color:#64748b" id="news-meta">載入中…</span>
      <button onclick="newsLoad()" style="background:rgba(59,130,246,.12);border:1px solid rgba(59,130,246,.35);color:#60a5fa;border-radius:5px;padding:2px 8px;font-size:.6rem;cursor:pointer;line-height:1.6">🔄</button>
    </div>
  </div>
  <div id="news-mood" style="margin-bottom:8px"></div>
  <div id="news-list"><div style="color:#475569;font-size:.78rem;padding:8px 0">⏳ 載入新聞中…</div></div>
  <div style="font-size:.58rem;color:#334155;margin-top:8px">每15分鐘自動更新 · 標題自動翻譯為繁體中文</div>
</div>

<script>
(function(){
  function tagStyle(sv){
    if(sv===1)  return 'background:rgba(16,185,129,.15);color:#10b981;border:1px solid rgba(16,185,129,.25)';
    if(sv===-1) return 'background:rgba(239,68,68,.15);color:#ef4444;border:1px solid rgba(239,68,68,.25)';
    return 'background:rgba(100,116,139,.12);color:#64748b;border:1px solid rgba(100,116,139,.2)';
  }

  function renderNews(items){
    var html='';
    items.slice(0,14).forEach(function(n,i){
      var sv=n.sent_val||0;
      html+='<div class="news-row">'
        +'<span style="'+tagStyle(sv)+';font-size:.62rem;padding:1px 6px;border-radius:4px;margin-right:5px;white-space:nowrap;font-weight:600">'+n.sentiment+'</span>'
        +'<span style="font-size:.7rem;color:#64748b;margin-right:4px">['+n.label+']</span>'
        +'<span id="nt-'+i+'" style="font-size:.75rem;color:#cbd5e1">'+n.title+'</span>'
        +'</div>';
    });
    document.getElementById('news-list').innerHTML=html;
  }

  function translateTitles(items){
    var list=items.slice(0,14);
    var joined=list.map(function(n){return n.title;}).join('\\n');
    var url='https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-TW&dt=t&q='+encodeURIComponent(joined);
    fetch(url)
      .then(function(r){return r.json();})
      .then(function(data){
        var full=(data[0]||[]).map(function(s){return s[0]||'';}).join('');
        var parts=full.split('\\n');
        list.forEach(function(n,i){
          var el=document.getElementById('nt-'+i);
          if(el&&parts[i]&&parts[i].trim()) el.textContent=parts[i].trim();
        });
      })
      .catch(function(){});  /* 翻譯失敗保留英文 */
  }

  function render(d){
    if(!d||!d.items||!d.items.length){
      document.getElementById('news-meta').textContent='載入失敗';
      document.getElementById('news-list').innerHTML='<div style="color:#475569;font-size:.78rem;padding:8px 0">⚠️ 新聞載入失敗，請稍後再試</div>';
      return;
    }
    var mc=d.mood_color||'#64748b';
    document.getElementById('news-mood').innerHTML=
      '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
      +'<div style="background:'+mc+'22;border:1.5px solid '+mc+';color:'+mc+';border-radius:8px;padding:4px 10px;font-size:.82rem;font-weight:800">'+d.mood+'</div>'
      +'<div style="font-size:.72rem;color:#94a3b8">多 <b style="color:#10b981">'+d.bull+'</b>'
      +' ／ 空 <b style="color:#ef4444">'+d.bear+'</b>'
      +' ／ 淨 <b>'+((d.score>=0?'+':'')+d.score)+'</b></div>'
      +'</div>';
    renderNews(d.items);
    document.getElementById('news-meta').textContent=d.updated+' 更新（翻譯中…）';
    translateTitles(d.items);
    /* 翻譯完成後更新 meta（用延遲估算） */
    setTimeout(function(){
      var el=document.getElementById('news-meta');
      if(el&&el.textContent.indexOf('翻譯中')>=0) el.textContent=d.updated+' 更新';
    },3000);
  }

  window.newsLoad=function(){
    document.getElementById('news-meta').textContent='更新中…';
    fetch('data/news.json?_='+Date.now())
      .then(function(r){return r.json();})
      .then(render)
      .catch(function(){document.getElementById('news-meta').textContent='載入失敗';});
  };
  newsLoad();
  setInterval(newsLoad,900000);
})();
</script>"""

    # ── 長榮航太看板 ─────────────────────────────────────
    stock_html = stock_card_html(stock or {})

    # ── 評分視覺化 ───────────────────────────────────────
    gold_contribution = gold.get("signal", 0)

    def dim_bar(label, val, max_abs, icon=""):
        """單維度小條（台灣色系：多=紅，空=綠）"""
        safe_max = max_abs if max_abs > 0 else 1
        clamped  = max(-safe_max, min(safe_max, val))
        center   = 50.0
        fill_pct = abs(clamped) / safe_max * 48   # 最大48%
        if val >= 0:
            l, w = center, fill_pct
            fc = "#ef4444"   # 多頭=紅（台灣色系）
            vc = "#ef4444"
        else:
            l, w = center - fill_pct, fill_pct
            fc = "#22c55e"   # 空頭=綠（台灣色系）
            vc = "#22c55e"
        bar_tag = (f'<div style="position:absolute;left:{l:.1f}%;width:{w:.1f}%;'
                   f'height:100%;background:{fc};border-radius:3px;'
                   f'transition:width .4s ease"></div>')
        return (f'<div class="srow">'
                f'<span class="slbl">{icon}{label}</span>'
                f'<div class="sbar-wrap">'
                f'<div style="position:absolute;left:50%;width:1px;height:100%;background:#1e3050"></div>'
                f'{bar_tag}'
                f'</div>'
                f'<span style="font-size:.82rem;font-weight:700;color:{vc};'
                f'width:28px;text-align:right;flex-shrink:0">{val:+d}</span>'
                f'</div>')

    dim_bars_html = (
        dim_bar("台灣技術", tw_s,           5,  "📊 ")
        + dim_bar("國際市場", int_s,         7,  "🌐 ")
        + dim_bar("新聞情緒", nws_s,         2,  "📰 ")
        + (dim_bar("黃金警示", gold_contribution, 2, "🥇 ") if gold else "")
    )

    # 總分大計儀表盤
    _max_total = 16
    _clamped   = max(-_max_total, min(_max_total, total_sc))
    _thresh_pct_lo = (-thresh + _max_total) / (2 * _max_total) * 100
    _thresh_pct_hi = (thresh  + _max_total) / (2 * _max_total) * 100
    _score_pct     = (_clamped + _max_total) / (2 * _max_total) * 100
    _center_pct    = 50.0
    if total_sc >= 0:
        _fl, _fw = _center_pct, _score_pct - _center_pct
        _fc = "#ef4444"; _fc2 = "#b91c1c"
    else:
        _fl, _fw = _score_pct, _center_pct - _score_pct
        _fc = "#22c55e"; _fc2 = "#15803d"
    _score_label = ("🔴 偏多" if total_sc >= thresh else
                    "🟢 偏空" if total_sc <= -thresh else "⚪ 中性")
    _score_color = ("#ef4444" if total_sc >= thresh else
                    "#22c55e" if total_sc <= -thresh else "#64748b")

    score_meter_html = f"""
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <div class="stitle" style="margin-bottom:0">📊 五維評分系統</div>
    <div style="display:flex;align-items:center;gap:6px">
      <span style="font-size:.6rem;color:#64748b">{sig_generated_at}</span>
      <button onclick="window.location.reload()" style="background:rgba(59,130,246,.12);border:1px solid rgba(59,130,246,.35);color:#60a5fa;border-radius:5px;padding:2px 8px;font-size:.6rem;cursor:pointer;line-height:1.6">🔄</button>
    </div>
  </div>

  <!-- 總分大計儀表 -->
  <div style="margin-bottom:14px">
    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">
      <div style="font-size:.65rem;color:#64748b">總評分</div>
      <div style="display:flex;align-items:center;gap:8px">
        <span style="font-size:1.4rem;font-weight:900;color:{_score_color}">{total_sc:+d}</span>
        <span style="font-size:.78rem;font-weight:700;color:{_score_color}">{_score_label}</span>
        <span style="font-size:.65rem;color:#475569">門檻 ±{thresh}</span>
      </div>
    </div>
    <!-- 主進度條 -->
    <div style="position:relative;height:22px;background:#0d1829;border-radius:6px;
                overflow:visible;border:1px solid #1e3050">
      <!-- 空頭標籤 -->
      <div style="position:absolute;left:3px;top:50%;transform:translateY(-50%);
                  font-size:.55rem;color:#22c55e;z-index:2">空</div>
      <!-- 多頭標籤 -->
      <div style="position:absolute;right:3px;top:50%;transform:translateY(-50%);
                  font-size:.55rem;color:#ef4444;z-index:2">多</div>
      <!-- 填充 -->
      <div style="position:absolute;left:{_fl:.1f}%;width:{max(_fw,0):.1f}%;height:100%;
                  background:linear-gradient(90deg,{_fc2},{_fc});
                  border-radius:5px;opacity:.9;transition:all .5s ease"></div>
      <!-- 中線 -->
      <div style="position:absolute;left:50%;width:2px;height:100%;
                  background:#334155;transform:translateX(-50%)"></div>
      <!-- 門檻線 -->
      <div style="position:absolute;left:{_thresh_pct_lo:.1f}%;width:1px;height:100%;
                  background:#475569;opacity:.6;border-right:1px dashed #475569"></div>
      <div style="position:absolute;left:{_thresh_pct_hi:.1f}%;width:1px;height:100%;
                  background:#475569;opacity:.6;border-right:1px dashed #475569"></div>
      <!-- 分數氣泡 -->
      <div style="position:absolute;left:{_score_pct:.1f}%;top:-18px;transform:translateX(-50%);
                  background:{_fc};color:#fff;font-size:.6rem;font-weight:700;
                  padding:1px 5px;border-radius:4px;white-space:nowrap;z-index:3">
        {total_sc:+d}
        <div style="position:absolute;bottom:-4px;left:50%;transform:translateX(-50%);
                    width:0;height:0;border-left:4px solid transparent;
                    border-right:4px solid transparent;border-top:4px solid {_fc}"></div>
      </div>
    </div>
    <div style="display:flex;justify-content:space-between;margin-top:4px;font-size:.58rem;color:#334155">
      <span>-{_max_total}</span><span>-{thresh}</span><span>0</span><span>+{thresh}</span><span>+{_max_total}</span>
    </div>
  </div>

  <!-- 各維度條 -->
  {dim_bars_html}
</div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>台指期智能看板</title>
<style>
/* ── Reset & Variables ─────────────────────────────── */
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:     #060d1a;
  --surf:   #0b1628;
  --card:   #0d1b2e;
  --card2:  #132236;
  --card3:  #1a2d45;
  --border: #1e3254;
  --blt:    #253d5e;     /* border light */

  --g:   #10b981;  /* 綠（西方多頭 / 台灣空頭）*/
  --r:   #ef4444;  /* 紅（西方空頭 / 台灣多頭）*/
  --y:   #f59e0b;
  --b:   #3b82f6;
  --p:   #8b5cf6;
  --c:   #06b6d4;

  --txt:     #e2e8f0;
  --txt2:    #94a3b8;
  --muted:   #5a7494;

  --shadow: 0 4px 24px rgba(0,0,0,.5);
  --r-sm:8px; --r-md:12px; --r-lg:16px; --r-xl:20px;
}}

/* ── Base ─────────────────────────────────────────── */
html{{scroll-behavior:smooth;font-size:16px}}
body{{
  background:var(--bg);
  background-image:
    radial-gradient(ellipse 70% 40% at 15% 0%,rgba(30,80,150,.22),transparent),
    radial-gradient(ellipse 50% 30% at 85% 100%,rgba(16,185,129,.06),transparent);
  color:var(--txt);
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","Helvetica Neue",
               "PingFang TC","Microsoft JhengHei",sans-serif;
  min-height:100vh;
  -webkit-font-smoothing:antialiased;
  line-height:1.5;
}}

/* ── Card ─────────────────────────────────────────── */
.card{{
  background:var(--card);
  border-radius:var(--r-lg);
  padding:16px;
  margin-bottom:12px;
  border:1px solid var(--border);
  box-shadow:var(--shadow);
  transition:border-color .2s,box-shadow .2s;
  position:relative;
  overflow:hidden;
}}
.card::before{{
  content:'';position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(135deg,rgba(255,255,255,.025),transparent 50%);
}}
.card:hover{{border-color:var(--blt);box-shadow:0 6px 32px rgba(0,0,0,.6)}}

/* 長榮航太 精緻卡（與台指期主題視覺隔離）*/
.stock-premium-card{{
  background:linear-gradient(145deg,#0a1929 0%,#0d1f35 100%);
  border-color:#1d3553;
}}
.stock-premium-card:hover{{border-color:#2a4a6e}}

/* ── Typography ────────────────────────────────────── */
.stitle{{
  font-size:.62rem;font-weight:700;color:var(--muted);
  text-transform:uppercase;letter-spacing:.14em;
  margin-bottom:12px;
  display:flex;align-items:center;gap:6px;
}}
.stitle::before{{
  content:'';flex-shrink:0;
  width:3px;height:12px;
  background:var(--b);border-radius:2px;
}}
.lbl{{font-size:.7rem;color:var(--txt2);margin-bottom:2px;line-height:1.3}}
.big-num{{font-size:1.55rem;font-weight:800;letter-spacing:-.6px;line-height:1.1}}

/* ── Layout Primitives ─────────────────────────────── */
.row2{{display:grid;grid-template-columns:1fr auto 1fr;gap:8px;align-items:start}}
.box2{{background:var(--card2);border-radius:var(--r-md);padding:12px}}
.row3{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}
.box3{{
  background:var(--card2);border-radius:var(--r-md);padding:12px;
  text-align:center;border-top:3px solid var(--border);
}}

/* ── Tables ────────────────────────────────────────── */
.tbl-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{width:100%;border-collapse:collapse;font-size:.78rem}}
th{{
  color:var(--muted);font-weight:600;font-size:.62rem;
  text-align:left;padding:7px 5px;
  border-bottom:1px solid var(--border);white-space:nowrap;
}}
td{{padding:8px 5px;border-bottom:1px solid rgba(30,50,84,.4);vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:rgba(255,255,255,.014)}}

/* ── Badges ────────────────────────────────────────── */
.badge-buy{{
  background:rgba(16,185,129,.12);color:var(--g);
  border:1px solid rgba(16,185,129,.25);
  padding:2px 8px;border-radius:20px;font-size:.68rem;font-weight:600;white-space:nowrap;
}}
.badge-sell{{
  background:rgba(239,68,68,.12);color:var(--r);
  border:1px solid rgba(239,68,68,.25);
  padding:2px 8px;border-radius:20px;font-size:.68rem;font-weight:600;white-space:nowrap;
}}
.badge-hold{{
  background:rgba(90,116,148,.12);color:var(--muted);
  border:1px solid var(--border);
  padding:2px 8px;border-radius:20px;font-size:.68rem;white-space:nowrap;
}}

/* ── News tags ─────────────────────────────────────── */
.news-row{{padding:9px 0;border-bottom:1px solid rgba(30,50,84,.4);font-size:.78rem;line-height:1.48}}
.news-row:last-child{{border-bottom:none}}
.news-tag{{
  display:inline-block;font-size:.62rem;padding:2px 6px;border-radius:5px;
  margin-right:5px;vertical-align:middle;white-space:nowrap;font-weight:600;
}}
.tag-pos{{background:rgba(16,185,129,.12);color:var(--g);border:1px solid rgba(16,185,129,.2)}}
.tag-neg{{background:rgba(239,68,68,.12);color:var(--r);border:1px solid rgba(239,68,68,.2)}}
.tag-neu{{background:rgba(90,116,148,.1);color:var(--muted);border:1px solid var(--border)}}

/* ── International grid ────────────────────────────── */
.intl-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}
.intl-item{{
  background:var(--card2);border-radius:var(--r-md);
  padding:10px 12px;border:1px solid var(--border);
  transition:border-color .2s,background .2s;
}}
.intl-item:hover{{border-color:var(--blt);background:var(--card3)}}

/* ── Score bars ────────────────────────────────────── */
.srow{{display:flex;align-items:center;gap:8px;margin-bottom:9px}}
.slbl{{width:72px;font-size:.72rem;color:var(--txt2);flex-shrink:0}}
.sbar-wrap{{flex:1;height:14px;background:var(--card2);border-radius:4px;position:relative;overflow:hidden}}

/* ── PnL bars ──────────────────────────────────────── */
.bar-row{{display:flex;align-items:center;gap:6px;margin-bottom:4px}}
.bar-date{{width:30px;color:var(--muted);font-size:.68rem;text-align:right;flex-shrink:0}}
.bar-wrap{{flex:1;height:22px;background:var(--card2);border-radius:5px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:5px;display:flex;align-items:center;padding:0 8px;min-width:44px}}
.bar-fill span{{font-size:.68rem;font-weight:600;white-space:nowrap;color:#fff}}
.bar-win{{background:linear-gradient(90deg,#065f46,#10b981)}}
.bar-lose{{background:linear-gradient(90deg,#7f1d1d,#ef4444)}}

/* ── Chip tags ─────────────────────────────────────── */
.chip{{
  display:inline-flex;align-items:center;gap:3px;
  border-radius:20px;padding:3px 10px;font-size:.65rem;font-weight:600;
}}
.chip-g{{background:rgba(16,185,129,.12);color:var(--g);border:1px solid rgba(16,185,129,.2)}}
.chip-b{{background:rgba(59,130,246,.12);color:var(--b);border:1px solid rgba(59,130,246,.2)}}
.chip-y{{background:rgba(245,158,11,.12);color:var(--y);border:1px solid rgba(245,158,11,.2)}}
.chip-r{{background:rgba(239,68,68,.12);color:var(--r);border:1px solid rgba(239,68,68,.2)}}

/* ── Hero signal card ──────────────────────────────── */
.signal-hero{{
  border-radius:var(--r-xl);padding:24px 20px;margin-bottom:12px;
  text-align:center;position:relative;overflow:hidden;
}}
.signal-hero::before{{
  content:'';position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(135deg,rgba(255,255,255,.07),transparent 55%);
}}
.signal-hero::after{{
  content:'';position:absolute;bottom:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.15),transparent);
}}

/* ── Tabs ──────────────────────────────────────────── */
.tab-nav{{
  display:flex;gap:4px;margin-bottom:12px;
  background:var(--card2);border-radius:10px;padding:4px;
  border:1px solid var(--border);
}}
.tab-btn{{
  flex:1;padding:7px 4px;border-radius:7px;border:none;
  background:transparent;color:var(--muted);
  font-size:.7rem;font-weight:600;cursor:pointer;
  transition:background .2s,color .2s;white-space:nowrap;
}}
.tab-btn.active{{
  background:var(--card3);color:var(--txt);
  box-shadow:0 1px 4px rgba(0,0,0,.3);
}}
.tab-btn:hover:not(.active){{color:var(--txt2);background:rgba(255,255,255,.04)}}
.tab-pane{{display:none}}
.tab-pane.active{{display:block}}

/* ── Accordion ─────────────────────────────────────── */
.acc-btn{{
  width:100%;display:flex;justify-content:space-between;align-items:center;
  padding:10px 14px;background:var(--card2);border:1px solid var(--border);
  border-radius:var(--r-md);color:var(--txt2);font-size:.75rem;font-weight:600;
  cursor:pointer;transition:background .2s;margin-bottom:8px;
}}
.acc-btn:hover{{background:var(--card3)}}
.acc-body{{display:none;margin-bottom:8px}}
.acc-body.open{{display:block}}
.acc-arrow{{transition:transform .25s;font-size:.7rem}}
.acc-btn.open .acc-arrow{{transform:rotate(180deg)}}

/* ── Jin10 dot blink ───────────────────────────────── */
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}

/* ── Layout ────────────────────────────────────────── */
.pw{{max-width:720px;margin:0 auto;padding:16px 14px}}

/* ── Responsive ────────────────────────────────────── */
@media(max-width:700px){{
  .row3{{grid-template-columns:repeat(3,1fr)}}
  .intl-grid{{grid-template-columns:repeat(2,1fr)}}
}}
@media(max-width:400px){{
  .row3{{grid-template-columns:1fr 1fr}}
  body{{font-size:15px}}
}}
</style>
</head>
<body>
<div class="pw">

<!-- ══════════════ TOP BAR ══════════════════════════ -->
<div style="display:flex;justify-content:space-between;align-items:center;
            margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid var(--border)">
  <div>
    <div style="font-size:1.1rem;font-weight:800;letter-spacing:-.3px">
      📈 台指期智能看板
    </div>
    <div style="font-size:.62rem;color:var(--muted);margin-top:3px">
      微型台指期貨 MXF &nbsp;·&nbsp; 每點 NT$10
    </div>
  </div>
  <div style="text-align:right">
    <div style="font-size:.6rem;color:var(--muted);margin-bottom:5px">
      資料：{sig_generated_at} &nbsp;·&nbsp; 現在：<span id="live-clock" style="color:#60a5fa">──:──:──</span>
    </div>
    <div style="display:flex;gap:5px;justify-content:flex-end;flex-wrap:wrap">
      <span class="chip chip-b">台指 {last_close:,.0f}</span>
      <span class="chip chip-{'g' if tw_rsi < 70 else 'y' if tw_rsi < 80 else 'r'}">RSI {tw_rsi:.0f}</span>
      <span class="chip chip-{'r' if total_sc >= thresh else 'g' if total_sc <= -thresh else 'chip-b'}">
        {'多' if total_sc >= thresh else '空' if total_sc <= -thresh else '中'} {total_sc:+d}
      </span>
    </div>
  </div>
</div>

<!-- ══════════════ 更新通知條 ══════════════════════ -->
<div id="update-banner" onclick="window.location.reload()"
     style="display:none;background:rgba(59,130,246,.12);border:1px solid #3b82f6;
            border-radius:10px;padding:10px 14px;margin-bottom:12px;cursor:pointer;
            justify-content:space-between;align-items:center">
  <span style="font-size:.82rem;color:#93c5fd">📡 資料已更新，點此重新載入看板</span>
  <span style="font-size:.75rem;color:#60a5fa">🔄 重新載入</span>
</div>

<!-- ══════════════ FULL-WIDTH ALERTS ════════════════ -->
{night_html}
{gold_html}
{today_card}

<!-- ══════════════ 金十數據（置頂）════════════════════ -->
{jin10_html}

<!-- ══════════════ 台指期主力區 ═══════════════════════ -->

<!-- 明日信號英雄卡 -->
<div class="signal-hero" style="background:{sig_bg};margin-bottom:12px">
  <div style="font-size:1.95rem;font-weight:900;line-height:1.1;letter-spacing:-.5px">
    {sig_label}
  </div>
  <div style="font-size:.85rem;opacity:.85;margin-top:6px">{trade_date}</div>
  <div style="background:rgba(0,0,0,.28);border-radius:10px;
              padding:9px 14px;margin-top:11px;font-size:.8rem;line-height:1.5;opacity:.92">
    {sig_action}
  </div>
  <div style="font-size:.67rem;opacity:.55;margin-top:8px;line-height:1.4">{score_detail}</div>
  <div style="margin-top:10px;display:flex;justify-content:space-between;align-items:center">
    <span style="font-size:.58rem;opacity:.45">{sig_generated_at} 更新</span>
    <button onclick="window.location.reload()" style="background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);color:rgba(255,255,255,.75);border-radius:5px;padding:2px 8px;font-size:.58rem;cursor:pointer;line-height:1.6">🔄 刷新</button>
  </div>
</div>

<!-- 五維評分儀表 -->
{score_meter_html}

<!-- ══ TABS: 今日訊號 / 回測統計 / 交易記錄 ══════ -->
<div class="card" style="padding:12px">

  <div style="display:flex;justify-content:flex-end;align-items:center;gap:6px;margin-bottom:8px">
    <span style="font-size:.6rem;color:#64748b">{sig_generated_at}</span>
    <button onclick="window.location.reload()" style="background:rgba(59,130,246,.12);border:1px solid rgba(59,130,246,.35);color:#60a5fa;border-radius:5px;padding:2px 8px;font-size:.6rem;cursor:pointer;line-height:1.6">🔄 刷新</button>
  </div>

  <!-- Tab 導航 -->
  <div class="tab-nav" id="main-tabs">
    <button class="tab-btn active" onclick="switchTab('t-signals',this,'main-tabs')">
      📋 今日訊號
    </button>
    <button class="tab-btn" onclick="switchTab('t-backtest',this,'main-tabs')">
      📊 回測統計
    </button>
    <button class="tab-btn" onclick="switchTab('t-records',this,'main-tabs')">
      📁 交易記錄
    </button>
  </div>

  <!-- Tab 1：今日四版本買賣訊號 + 實際累計 -->
  <div class="tab-pane active" id="t-signals">
    {today_html}
    {real_stats_html}
    {buy_sell_html}
  </div>

  <!-- Tab 2：歷史回測統計（預設收納） -->
  <div class="tab-pane" id="t-backtest">
    {sim_stats_html}
    {sim_v70_stats_html}
    {sim_v60_stats_html}
    {sim_v50_stats_html}
  </div>

  <!-- Tab 3：近期損益 + 完整記錄 -->
  <div class="tab-pane" id="t-records">
    {bars_html}
    <div class="tbl-wrap">{table_html}</div>
  </div>

</div><!-- card tabs -->

<!-- ══════════════ 長榮航太（台指期下方）══════════════ -->
{stock_html}

<!-- ══════════════ 國際市場 ══════════════════════════ -->
{intl_html}

<!-- ══════════════ 新聞 ══════════════════════════════ -->
{news_html}

<!-- ══════════════ FOOTER ════════════════════════════ -->
<div style="text-align:center;color:var(--muted);font-size:.62rem;
            padding:20px 0 10px;margin-top:8px;border-top:1px solid var(--border);
            line-height:1.8">
  ⚠️ 本看板為輔助參考，不構成投資建議<br>
  微型台指(MXF) 每點 NT$10 ｜ 建議停損 20～30 點（NT$200～$300）<br>
  <span style="color:#334155">台灣色系：紅＝多頭漲勢，綠＝空頭跌勢</span>
</div>

</div><!-- pw -->

<!-- ══════════════ JS ═════════════════════════════════ -->
<script>
/* ── Tab 切換 ─────────────────────────────────────── */
function switchTab(targetId, btn, navId) {{
  var nav = document.getElementById(navId);
  if (!nav) return;
  // 收合所有 pane（找最近的 card 父層）
  var card = nav.closest ? nav.closest('.card') : nav.parentElement;
  var panes = card.querySelectorAll('.tab-pane');
  var btns  = nav.querySelectorAll('.tab-btn');
  panes.forEach(function(p){{ p.classList.remove('active'); }});
  btns.forEach(function(b){{ b.classList.remove('active'); }});
  var target = document.getElementById(targetId);
  if (target) target.classList.add('active');
  if (btn)    btn.classList.add('active');
}}

/* ── Accordion ─────────────────────────────────────── */
function toggleAcc(btnEl) {{
  btnEl.classList.toggle('open');
  var body = btnEl.nextElementSibling;
  if (body) body.classList.toggle('open');
}}

/* ── 即時時鐘 + 新資料偵測 ──────────────────────── */
(function(){{
  /* 時鐘 */
  function tick(){{
    var d=new Date(),h=d.getHours(),m=d.getMinutes(),s=d.getSeconds();
    var el=document.getElementById('live-clock');
    if(el) el.textContent=(h<10?'0':'')+h+':'+(m<10?'0':'')+m+':'+(s<10?'0':'')+s;
  }}
  tick(); setInterval(tick,1000);

  /* 新資料輪詢（每5分鐘） */
  var SIG_AT='{sig_generated_at}',STK_AT='{stock_updated}',notified=false;
  function showBanner(){{
    if(notified) return; notified=true;
    var b=document.getElementById('update-banner');
    if(b) b.style.display='flex';
  }}
  function poll(){{
    fetch('data/signal.json?_='+Date.now())
      .then(function(r){{return r.json();}})
      .then(function(d){{if(d.generated_at&&d.generated_at!==SIG_AT) showBanner();}})
      .catch(function(){{}});
    fetch('data/stock_2645.json?_='+Date.now())
      .then(function(r){{return r.json();}})
      .then(function(d){{if(d.updated&&d.updated!==STK_AT) showBanner();}})
      .catch(function(){{}});
  }}
  setTimeout(poll,120000);      /* 載入後2分鐘先查一次（可能開到舊頁） */
  setInterval(poll,300000);     /* 之後每5分鐘 */
}})();
</script>
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
