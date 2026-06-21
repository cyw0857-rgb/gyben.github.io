#!/usr/bin/env python3
"""台指期 HTML 看板產生器 — 暗色主題，手機電腦通用"""

import json, os, subprocess, math
import pandas as pd
from datetime import datetime

RECORDS_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "records.csv")
SIGNAL_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "signal.json")
STOCK_PATH       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stock_2645.json")
STOCK_CHIPS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stock_chips.json")
DCA_PATH         = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "dca.json")
OUTPUT_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

# 長榮航太(2645) 自有持股（手動設定）— 國泰證券
# fee_rate 手續費率 0.1425%；fee_disc 折數（國泰網路下單 2.8折=0.28）；tax_rate 證交稅 0.3%
STOCK_HOLDING = {"shares": 3435, "avg_cost": 167.3,
                 "fee_rate": 0.001425, "fee_disc": 0.28, "tax_rate": 0.003}

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
        df["win_bool"] = df["win"].astype(str).eq("True")
        df["date"]     = pd.to_datetime(df["trade_date"], errors="coerce")
        records = df.sort_values("date")

    stock = {}
    if os.path.exists(STOCK_PATH):
        with open(STOCK_PATH, encoding="utf-8") as f:
            stock = json.load(f)
    # 合併籌碼面（三大法人 + 融資融券）
    if os.path.exists(STOCK_CHIPS_PATH):
        with open(STOCK_CHIPS_PATH, encoding="utf-8") as f:
            chips = json.load(f)
        if chips.get("inst"):
            stock["inst"] = chips["inst"]
        if chips.get("margin"):
            stock["margin"] = chips["margin"]
        stock["chips_updated"] = chips.get("updated", "")
    # 自有持股
    if stock and STOCK_HOLDING.get("shares"):
        stock["holding"] = dict(STOCK_HOLDING)

    dca = {}
    if os.path.exists(DCA_PATH):
        with open(DCA_PATH, encoding="utf-8") as f:
            dca = json.load(f)

    return signal, records, stock, dca

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
    forecast     = stock.get("forecast", [])
    trend_label  = stock.get("trend_label", "")
    daily_vol    = stock.get("daily_vol_pct", 0)
    model_acc    = stock.get("model_accuracy", 0)
    model_samples= stock.get("model_samples", 0)
    total_ret    = stock.get("total_return", 0)
    ipo_date     = stock.get("ipo_date", "─")
    margin       = stock.get("margin", {})
    holding      = stock.get("holding", {})

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
    for row in inst.get("rows", [])[:8]:
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

    # ── 月度走勢預測 ─────────────────────────────────────
    def ta(t): return "▲" if t == "up" else ("▼" if t == "down" else "─")
    def tc(t): return "#10b981" if t == "up" else ("#ef4444" if t == "down" else "#9ca3af")

    fc_rows = ""
    for fc in forecast:
        note = fc.get("model_note", "")
        fc_rows += (
            f'<tr>'
            f'<td style="color:#94a3b8;padding:4px 3px">{fc["month"]}</td>'
            f'<td style="color:{tc(fc["trend"])};font-weight:700;padding:4px 3px">{ta(fc["trend"])} {note or fc["price"]}</td>'
            f'<td style="color:#6b7280;font-size:.68rem;padding:4px 3px">{fc["price_low"]}~{fc["price_high"]}</td>'
            f'</tr>'
        )

    # ── 我的持股 ─────────────────────────────────────────
    holding_html = ""
    if holding.get("shares"):
        h_sh   = holding["shares"]
        h_cost = holding["avg_cost"]
        h_fee  = holding.get("fee_rate", 0.001425)
        h_disc = holding.get("fee_disc", 1.0)
        h_tax  = holding.get("tax_rate", 0.003)
        h_invest = h_sh * h_cost
        h_value  = h_sh * last_close
        # 淨損益 = 賣出市值 − 賣手續費 − 證交稅 − 買進成本 − 買手續費（手續費含折數）
        buy_fee  = h_invest * h_fee * h_disc
        sell_fee = h_value  * h_fee * h_disc
        sell_tax = h_value  * h_tax
        h_pnl    = h_value - sell_fee - sell_tax - h_invest - buy_fee
        h_ret    = (h_pnl / h_invest * 100) if h_invest else 0
        h_col    = "#10b981" if h_pnl >= 0 else "#ef4444"
        h_arr    = "▲" if h_pnl >= 0 else "▼"
        holding_html = (
            f'<div style="background:linear-gradient(135deg,#10243a,#0b1628);'
            f'border:1px solid {h_col}66;border-radius:10px;padding:11px 12px;margin-bottom:12px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
            f'<span style="font-size:.7rem;font-weight:800;color:#e2e8f0">💼 我的持股</span>'
            f'<span style="font-size:.62rem;color:#94a3b8">{h_sh:,} 股 · 成本 {h_cost:.1f}</span>'
            f'</div>'
            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;text-align:center">'
            f'<div><div style="font-size:.56rem;color:#64748b">投入成本</div>'
            f'<div style="font-size:.8rem;font-weight:800;color:#cbd5e1">${h_invest:,.0f}</div></div>'
            f'<div><div style="font-size:.56rem;color:#64748b">目前市值</div>'
            f'<div style="font-size:.8rem;font-weight:800;color:#cbd5e1">${h_value:,.0f}</div></div>'
            f'<div><div style="font-size:.56rem;color:#64748b">淨損益</div>'
            f'<div style="font-size:.8rem;font-weight:800;color:{h_col}">{h_arr}${abs(h_pnl):,.0f}</div></div>'
            f'<div><div style="font-size:.56rem;color:#64748b">報酬率</div>'
            f'<div style="font-size:.8rem;font-weight:800;color:{h_col}">{h_ret:+.2f}%</div></div>'
            f'</div>'
            f'<div style="font-size:.54rem;color:#475569;margin-top:6px;text-align:right">'
            f'淨損益＝現價市值已扣手續費(2.8折)+證交稅，貼近國泰實際參考損益</div>'
            f'</div>'
        )

    # ── 融資融券 ─────────────────────────────────────────
    margin_html = ""
    if margin.get("rows"):
        m_fin   = margin.get("fin_bal", 0)
        m_sho   = margin.get("sho_bal", 0)
        m_finc  = margin.get("fin_5chg", 0)
        m_shoc  = margin.get("sho_5chg", 0)
        m_note  = margin.get("note", "")
        m_ncol  = margin.get("note_color", "#9ca3af")
        def _chg(v, invert=False):
            up = "#f59e0b" if not invert else "#10b981"
            dn = "#10b981" if not invert else "#f59e0b"
            if v > 0: return f'<span style="color:{up}">+{v:,}</span>'
            if v < 0: return f'<span style="color:{dn}">{v:,}</span>'
            return '<span style="color:#6b7280">─</span>'
        margin_html = (
            f'<div style="background:#080f1e;border-radius:10px;padding:10px;margin-bottom:10px">'
            f'<div style="font-size:.6rem;color:#6b7280;margin-bottom:6px">💳 融資融券（散戶槓桿）</div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:7px">'
            f'<div style="background:#162032;border-radius:8px;padding:8px">'
            f'<div style="font-size:.56rem;color:#6b7280">融資餘額（張）</div>'
            f'<div style="font-size:.95rem;font-weight:800;color:#e2e8f0">{m_fin:,}</div>'
            f'<div style="font-size:.6rem">5日 {_chg(m_finc)}</div></div>'
            f'<div style="background:#162032;border-radius:8px;padding:8px">'
            f'<div style="font-size:.56rem;color:#6b7280">融券餘額（張）</div>'
            f'<div style="font-size:.95rem;font-weight:800;color:#e2e8f0">{m_sho:,}</div>'
            f'<div style="font-size:.6rem">5日 {_chg(m_shoc, invert=True)}</div></div>'
            f'</div>'
            f'<div style="font-size:.66rem;color:{m_ncol};font-weight:600">{e(m_note)}</div>'
            f'</div>'
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

  {holding_html}

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
          🏦 三大法人買賣超（千股）
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

  {margin_html}

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

  <!-- 月度方向預測 -->
  <div style="background:#080f1e;border-radius:10px;padding:10px;margin-bottom:14px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
      <div style="font-size:.6rem;color:#6b7280">📅 月線方向預測（MA5/MA10 交叉模型）</div>
      <div style="font-size:.6rem;color:{'#10b981' if model_acc>=70 else '#f59e0b'}">準確率 {model_acc:.0f}% / {model_samples}筆</div>
    </div>
    <div style="font-size:.6rem;color:#475569;margin-bottom:6px">
      {e(trend_label)} · 上市({ipo_date})累計 <span style="color:{'#10b981' if total_ret>=0 else '#ef4444'};font-weight:700">{total_ret:+.1f}%</span>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:.75rem">
      <tr style="border-bottom:1px solid #1e3050">
        <th style="color:#475569;font-size:.6rem;padding:3px 3px;text-align:left">月份</th>
        <th style="color:#475569;font-size:.6rem;padding:3px 3px;text-align:left">預測方向</th>
        <th style="color:#475569;font-size:.6rem;padding:3px 3px;text-align:right">±σ波動區間</th>
      </tr>
      {fc_rows}
    </table>
    <div style="font-size:.6rem;color:#374155;margin-top:6px">
      ⚠️ 方向預測（非精確價格）· 每月月底重新判斷 · {model_acc:.0f}%準確率基於{model_samples}筆回測
    </div>
  </div>

  </div>
</div>"""


def _sparkline(hist, up_color="#10b981", w=120, h=34):
    """近30日收盤迷你走勢 SVG"""
    if not hist or len(hist) < 2:
        return ""
    lo, hi = min(hist), max(hist)
    span = (hi - lo) or 1
    n = len(hist)
    pts = []
    for i, v in enumerate(hist):
        x = i / (n - 1) * w
        y = h - (v - lo) / span * (h - 4) - 2
        pts.append(f"{x:.1f},{y:.1f}")
    col = up_color if hist[-1] >= hist[0] else "#ef4444"
    poly = " ".join(pts)
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'style="display:block">'
            f'<polyline points="{poly}" fill="none" stroke="{col}" '
            f'stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>'
            f'</svg>')


def dca_card_html(dca):
    """定期定額追蹤卡片 — 009816 + 00992A 每月25號各 NT$22,500"""
    if not dca:
        return ""

    updated      = dca.get("updated", "")
    monthly      = dca.get("monthly_total", 45000)
    buy_day      = dca.get("buy_day", 25)
    next_buy     = dca.get("next_buy", "─")
    days_to_next = dca.get("days_to_next", 0)
    total_cost   = dca.get("total_cost", 0)
    total_value  = dca.get("total_value", 0)
    total_pnl    = dca.get("total_pnl", 0)
    total_ret    = dca.get("total_ret", 0)
    holdings     = dca.get("holdings", [])
    purchases    = dca.get("purchases", [])
    has_pos      = total_cost > 0

    # ── 總覽橫幅 ─────────────────────────────────────────
    if has_pos:
        pcol = "#10b981" if total_pnl >= 0 else "#ef4444"
        arrow = "▲" if total_pnl >= 0 else "▼"
        summary_html = (
            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;'
            f'background:#0b1628;border:1px solid #1e3050;border-radius:12px;'
            f'padding:12px 10px;margin:10px 0 14px">'
            f'<div style="text-align:center"><div style="font-size:.62rem;color:#64748b">總投入</div>'
            f'<div style="font-size:1.02rem;font-weight:800;color:#e2e8f0">${total_cost:,.0f}</div></div>'
            f'<div style="text-align:center"><div style="font-size:.62rem;color:#64748b">總市值</div>'
            f'<div style="font-size:1.02rem;font-weight:800;color:#e2e8f0">${total_value:,.0f}</div></div>'
            f'<div style="text-align:center"><div style="font-size:.62rem;color:#64748b">損益</div>'
            f'<div style="font-size:1.02rem;font-weight:800;color:{pcol}">{arrow}${abs(total_pnl):,.0f}</div></div>'
            f'<div style="text-align:center"><div style="font-size:.62rem;color:#64748b">報酬率</div>'
            f'<div style="font-size:1.02rem;font-weight:800;color:{pcol}">{total_ret:+.2f}%</div></div>'
            f'</div>'
        )
    else:
        summary_html = (
            f'<div style="background:linear-gradient(135deg,#0e1c34,#0b1628);'
            f'border:1px solid #1e3050;border-radius:12px;padding:14px;'
            f'margin:10px 0 14px;text-align:center">'
            f'<div style="font-size:.78rem;color:#cbd5e1">尚未扣款 · 首次扣款日 '
            f'<span style="color:#fbbf24;font-weight:800">{e(next_buy)}</span>'
            f'（{days_to_next} 天後）</div>'
            f'<div style="font-size:.66rem;color:#64748b;margin-top:4px">'
            f'屆時將各買進 NT${monthly//2:,}，下方為目前參考股價</div>'
            f'<div style="font-size:.64rem;color:#10b981;margin-top:6px">'
            f'✅ {e(next_buy)} 自動扣款後，這裡會顯示損益／報酬率，每個交易日收盤更新</div>'
            f'</div>'
        )

    # ── 雙欄持倉 ─────────────────────────────────────────
    cols = ""
    for h in holdings:
        sym   = h.get("symbol", "")
        nm    = h.get("name", "")
        last  = h.get("last", 0)
        chg   = h.get("chg_pct", 0)
        ccol  = "#10b981" if chg >= 0 else "#ef4444"
        carr  = "▲" if chg >= 0 else "▼"
        spark = _sparkline(h.get("hist", []))

        if has_pos and h.get("shares", 0) > 0:
            pcol2 = "#10b981" if h.get("pnl", 0) >= 0 else "#ef4444"
            pos_html = (
                f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 8px;'
                f'margin-top:8px;font-size:.72rem">'
                f'<div style="color:#64748b">持有股數</div>'
                f'<div style="text-align:right;color:#e2e8f0;font-weight:700">{h["shares"]:,.2f}</div>'
                f'<div style="color:#64748b">平均成本</div>'
                f'<div style="text-align:right;color:#e2e8f0">${h["avg_cost"]:.2f}</div>'
                f'<div style="color:#64748b">投入金額</div>'
                f'<div style="text-align:right;color:#e2e8f0">${h["cost"]:,.0f}</div>'
                f'<div style="color:#64748b">目前市值</div>'
                f'<div style="text-align:right;color:#e2e8f0">${h["value"]:,.0f}</div>'
                f'<div style="color:#64748b">損益</div>'
                f'<div style="text-align:right;color:{pcol2};font-weight:800">'
                f'${h["pnl"]:+,.0f}（{h["ret_pct"]:+.2f}%）</div>'
                f'</div>'
                f'<div style="font-size:.6rem;color:#475569;margin-top:5px">'
                f'已扣款 {h.get("n_buys",0)} 次</div>'
            )
        else:
            pos_html = (
                f'<div style="font-size:.68rem;color:#64748b;margin-top:8px;'
                f'padding:6px 0;border-top:1px dashed #1e3050">'
                f'尚未持有 · 計畫每月投入 ${monthly//2:,}</div>'
            )

        cols += (
            f'<div style="background:#0b1628;border:1px solid #1e3050;'
            f'border-radius:12px;padding:12px">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline">'
            f'<div><div style="font-weight:800;color:#e2e8f0;font-size:.92rem">{e(nm)}</div>'
            f'<div style="font-size:.62rem;color:#64748b">{e(sym)}</div></div>'
            f'<div style="text-align:right">'
            f'<div style="font-size:1.1rem;font-weight:800;color:#e2e8f0">{last:.2f}</div>'
            f'<div style="font-size:.7rem;font-weight:700;color:{ccol}">{carr}{abs(chg):.2f}%</div>'
            f'</div></div>'
            f'<div style="margin-top:8px">{spark}</div>'
            f'<div style="font-size:.56rem;color:#475569;text-align:right">近30日</div>'
            f'{pos_html}'
            f'</div>'
        )

    # ── 扣款記錄 ─────────────────────────────────────────
    rec_html = ""
    if purchases:
        rows = ""
        name_map = {h["symbol"]: h["name"] for h in holdings}
        for p in reversed(purchases):
            rows += (
                f'<tr>'
                f'<td style="color:#94a3b8;padding:4px 3px">{e(p["date"])}</td>'
                f'<td style="padding:4px 3px;color:#cbd5e1">{e(name_map.get(p["symbol"], p["symbol"]))}</td>'
                f'<td style="text-align:right;padding:4px 3px;color:#cbd5e1">${p["amount"]:,.0f}</td>'
                f'<td style="text-align:right;padding:4px 3px;color:#cbd5e1">{p["price"]:.2f}</td>'
                f'<td style="text-align:right;padding:4px 3px;color:#e2e8f0;font-weight:700">{p["shares"]:,.2f}</td>'
                f'</tr>'
            )
        rec_html = (
            f'<div style="margin-top:14px">'
            f'<div style="font-size:.74rem;font-weight:700;color:#94a3b8;margin-bottom:5px">扣款記錄</div>'
            f'<table style="width:100%;border-collapse:collapse;font-size:.7rem">'
            f'<tr style="color:#64748b;border-bottom:1px solid #1e3050">'
            f'<td style="padding:4px 3px">日期</td><td style="padding:4px 3px">標的</td>'
            f'<td style="text-align:right;padding:4px 3px">投入</td>'
            f'<td style="text-align:right;padding:4px 3px">成交價</td>'
            f'<td style="text-align:right;padding:4px 3px">股數</td></tr>'
            f'{rows}</table></div>'
        )

    return f"""
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px">
    <h2 style="margin:0">💰 定期定額追蹤</h2>
    <span style="font-size:.62rem;color:#94a3b8;background:#0b1628;border:1px solid #1e3050;
                 border-radius:999px;padding:2px 9px">📅 資料時間 {e(updated)}</span>
  </div>
  <div style="font-size:.7rem;color:#94a3b8;margin-top:2px">
    每月 {buy_day} 號投入 NT${monthly:,}（009816 + 00992A 各 NT${monthly//2:,}）
  </div>
  {summary_html}
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
    {cols}
  </div>
  {rec_html}
  <div style="font-size:.58rem;color:#374155;margin-top:10px">
    ⚠️ 定期定額為長期投資，短期帳面損益僅供參考 · 股價每日更新
  </div>
</div>"""


def generate_html(signal, records, stock=None, dca=None):
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
    sim_vsel_df   = _filter("sim_vsel")
    real_v100_df  = _filter("real_v100")
    real_v70_df   = _filter("real_v70")
    real_v60_df   = _filter("real_v60")
    real_v50_df   = _filter("real_v50")
    real_vsel_df  = _filter("real_vsel")

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
    veto_msg   = signal.get("veto_msg", "")

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
        # 即時油價（WTI 原油）— 與黃金左右對稱兩欄
        oil_col = ""
        if gold.get("oil_usd"):
            op  = gold.get("oil_usd", 0)
            oc  = gold.get("oil_chg", 0)
            oil_col = f"""
            <div style="flex:1;border-left:1px solid rgba(255,255,255,.2);padding-left:16px">
              <div style="font-size:.62rem;opacity:.75;letter-spacing:.05em">🛢 WTI 原油</div>
              <div style="font-size:1.25rem;font-weight:800;margin-top:4px">${op:,.1f}</div>
              <div style="font-size:.78rem;opacity:.9">{"▲" if oc >= 0 else "▼"} {oc:+.2f}%</div>
            </div>"""
        gold_html = f"""
        <div style="background:{gbg};color:{gtxt};border-radius:14px;
                    padding:14px 18px;margin-bottom:14px">
          <div style="font-size:.7rem;opacity:.8;letter-spacing:.1em">🥇 黃金貴金屬即時警示</div>
          <div style="display:flex;align-items:flex-start;gap:16px;margin:8px 0">
            <div style="flex:1">
              <div style="font-size:.62rem;opacity:.75;letter-spacing:.05em">🥇 黃金</div>
              <div style="font-size:1.25rem;font-weight:800;margin-top:4px">${gp:,.0f}<span style="font-size:.72rem;opacity:.8"> / oz</span></div>
              <div style="font-size:.78rem;opacity:.9">{"▲" if gc >= 0 else "▼"} {gc:+.2f}%</div>
            </div>
            {oil_col}
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
        if veto_msg:
            # 總分已達門檻、但被安全濾網擋下 → 顯示真正原因，而非誤導的「未達門檻」
            sig_action = e(veto_msg)
        else:
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

    # 精準版 (100%): MA2日+RSI<72+SOX>0.5+SPX>0+MACD金叉+前K（最嚴 → 必為其他版本的超集，確保單調性）
    if   ma2_bull and 45 < rsi < 72 and sox_chg > 0.5 and spx_chg > 0 and macd_b and prev_k_up: dir_v100 = 1
    elif ma2_bear and 28 < rsi < 55 and sox_chg < -0.5 and spx_chg < 0 and macd_s and (not prev_k_up): dir_v100 = -1
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

    # 精選版 (vsel): MA2日 + 趨勢強度(MA5距MA20>0.6%) + MACD + 前K + RSI窄帶（最嚴，重質不重量）
    spread_d = (ma5 - ma20) / ma20 if ma20 else 0.0
    if   ma2_bull and spread_d > 0.006 and macd_b and prev_k_up and 58 < rsi < 66: dir_vsel = 1
    elif ma2_bear and spread_d < -0.006 and macd_s and (not prev_k_up) and 34 < rsi < 42: dir_vsel = -1
    else: dir_vsel = 0

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
        <div style="background:{bg};border:1.5px solid {border};border-radius:12px;padding:12px 12px;min-width:0">
          <div style="font-size:.66rem;color:#9ca3af;margin-bottom:6px;line-height:1.3">{label}</div>
          <div style="font-size:1.35rem;font-weight:900;color:{border}">{ico} {act}</div>
          <div style="font-size:.72rem;color:#d1d5db;margin:5px 0">{act_detail}</div>
          <div style="margin-top:8px;border-top:1px solid rgba(255,255,255,.08);padding-top:8px">
            <div style="font-size:.6rem;color:#6b7280">參考進場價</div>
            <div style="font-size:.8rem;font-weight:700;color:#e2e8f0">{price_hint}</div>
            <div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:6px">
              <span style="font-size:.6rem;color:#6b7280">模擬勝率<br><span style="font-size:.56rem">{n_trades}筆</span></span>
              <span style="font-size:1.05rem;font-weight:800;color:{wr_color}">{win_rate:.0f}%</span>
            </div>
          </div>
          {real_line}
          <div style="font-size:.6rem;color:#6b7280;margin-top:6px;line-height:1.3">{desc}</div>
        </div>"""

    # 從stats取五版本筆數和勝率（已有實際backtest結果）
    s100 = signal.get("stats_sim",  {}); n100 = s100.get("total", 13); wr100 = s100.get("win_rate", 100)
    s70  = signal.get("stats_v70",  {}); n70  = s70.get("total",  21); wr70  = s70.get("win_rate", 90)
    s60  = signal.get("stats_v60",  {}); n60  = s60.get("total",  37); wr60  = s60.get("win_rate", 73)
    s50  = signal.get("stats_v50",  {}); n50  = s50.get("total",  66); wr50  = s50.get("win_rate", 60)
    ssel = signal.get("stats_vsel", {}); nsel = ssel.get("total", 194); wrsel = ssel.get("win_rate", 51)

    five_cards = (
        _ver_card(dir_vsel, wrsel, nsel, "⭐ 精選版 — MA2日+趨勢強+RSI窄帶", "重質不重量，正期望值，約每年7筆", real_vsel_df) +
        _ver_card(dir_v100, wr100, n100, "🎯 精準版 — MA2日+SOX>0.5%+RSI<72", "條件最嚴，少量高確信度",  real_v100_df) +
        _ver_card(dir_v70,  wr70,  n70,  "📊 優化版 — MA1日+MACD+前K+SOX",    "條件均衡，每月3-4筆",     real_v70_df) +
        _ver_card(dir_v60,  wr60,  n60,  "📈 高頻版 — MA1日+MACD+前K收紅",    "條件寬鬆，每月5-7筆",     real_v60_df) +
        _ver_card(dir_v50,  wr50,  n50,  "🔁 超高頻版 — MA1日對齊+RSI",        "條件最寬，每月8-12筆",    real_v50_df)
    )

    buy_sell_html = f"""
    <div class="card">
      <div class="stitle">📋 五版本今日買賣建議</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px">
        {five_cards}
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

    # ── 模擬回測統計 E：精選版 (vsel) ─────────────────
    sim_vsel_stats_html = ""
    if not sim_vsel_df.empty:
        svs = sim_vsel_df.copy()
        svs["pnl"]      = pd.to_numeric(svs["pnl_nts"], errors="coerce").fillna(0)
        svs["win_bool"] = svs["win"].map({"True": True, "False": False}).fillna(False)
        svs_only = svs[svs["pnl"] != 0]
        if not svs_only.empty:
            vt  = len(svs_only)
            vw  = int(svs_only["win_bool"].sum())
            vwr = vw / vt * 100
            vp  = svs_only["pnl"].sum()
            win_pnl  = svs_only[svs_only["win_bool"]]["pnl"]
            lose_pnl = svs_only[~svs_only["win_bool"]]["pnl"]
            aw = win_pnl.mean() if not win_pnl.empty else 0
            al = lose_pnl.mean() if not lose_pnl.empty else 0
            rr = (aw / -al) if al < 0 else 0
            sim_vsel_stats_html = f"""
            <div class="card" style="border:1.5px solid #a78bfa">
              <div class="stitle">⭐ 精選版回測 — MA2日+趨勢強度+RSI窄帶（29年真實）</div>
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
                  <div class="lbl">回測筆數<br><span style="font-size:.65rem;color:#a78bfa">重質不重量</span></div>
                </div>
              </div>
              {_real_row_html(real_vsel_df)}
              <p style="color:#a78bfa;font-size:.72rem;margin-top:6px">
                ✅ 全期29年回測｜賺賠比 {rr:.2f}（均賺NT${aw:,.0f}／均賠NT${al:,.0f}）｜
                勝率雖只 {vwr:.0f}%，但靠正期望值（重質不重量、約每年7筆）長期為正
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

    # ── 國際市場（優先 Yahoo Finance 即時 API，每30秒；fallback intl.json）
    intl_html = """<div class="card" id="intl-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <div class="stitle" style="margin-bottom:0">🌐 國際市場概況</div>
    <div style="display:flex;align-items:center;gap:6px">
      <span id="intl-live-dot" style="width:7px;height:7px;background:#475569;border-radius:50%;display:inline-block"></span>
      <span style="font-size:.6rem;color:#64748b" id="intl-meta">載入中…</span>
      <button onclick="window.intlLoad()" style="background:rgba(59,130,246,.12);border:1px solid rgba(59,130,246,.35);color:#60a5fa;border-radius:5px;padding:2px 8px;font-size:.6rem;cursor:pointer;line-height:1.6">🔄</button>
    </div>
  </div>
  <div id="intl-grid" class="intl-grid">
    <div style="color:#475569;font-size:.78rem;padding:8px 0;grid-column:1/-1">⏳ 載入中…</div>
  </div>
</div>

<script>
(function(){
  /* ── 指數設定（symbol→顯示名 + desc）── */
  var MARKETS = [
    {n:'S&P500',    s:'^GSPC',    d:'美股漲→台股漲'},
    {n:'道瓊',      s:'^DJI',     d:'藍籌股風向球'},
    {n:'NASDAQ',    s:'^IXIC',    d:'科技股連動'},
    {n:'費城半導體', s:'^SOX',     d:'對台股影響最大'},
    {n:'VIX恐慌',   s:'^VIX',     d:'<20樂觀 >25恐慌'},
    {n:'日經225',   s:'^N225',    d:'亞股風向球'},
    {n:'韓KOSPI',   s:'^KS11',    d:'半導體競爭對手'},
    {n:'恒生指數',  s:'^HSI',     d:'港股/中概股連動'},
    {n:'台股加權',  s:'^TWII',    d:'台股現貨參考'},
    {n:'美元指數',  s:'DX-Y.NYB', d:'強美元→外資匯出'},
    {n:'黃金',      s:'GC=F',     d:'避險情緒指標'},
    {n:'原油',      s:'CL=F',     d:'油漲→通膨預期'},
    {n:'美債10Y',   s:'^TNX',     d:'殖利率高→股市壓力'},
    {n:'比特幣',    s:'BTC-USD',  d:'風險偏好指標'}
  ];

  function calcSig(name, chgPct, price){
    if(name==='VIX恐慌')   return price<20?1:(price>25?-1:0);
    if(name==='美元指數')  return chgPct>0.3?-1:(chgPct<-0.3?1:0);
    if(name==='美債10Y')   return chgPct>3?-1:(chgPct<-3?1:0);
    if('黃金比特幣原油'.indexOf(name)>=0) return chgPct>0.5?1:(chgPct<-0.5?-1:0);
    return chgPct>0?1:(chgPct<0?-1:0);
  }

  function renderGrid(items, sourceLabel){
    var html='';
    items.forEach(function(it){
      var sv=it.sig, chg=it.chg;
      var ic=sv===1?'#10b981':sv===-1?'#ef4444':'#64748b';
      var arrow=sv===1?'▲':sv===-1?'▼':'─';
      var bg=sv===1?'rgba(16,185,129,.08)':sv===-1?'rgba(239,68,68,.08)':'transparent';
      var px=it.price>0?'<div style="font-size:.6rem;color:#475569;margin-top:1px">'+(it.price<10?it.price.toFixed(2):it.price.toFixed(it.price>100?0:2))+'</div>':'';
      html+='<div class="intl-item" style="background:'+bg+'">'
        +'<div style="font-size:.62rem;color:#94a3b8;margin-bottom:2px">'+it.name+'</div>'
        +'<div style="font-size:1rem;font-weight:800;color:'+ic+'">'+arrow+' '+(chg>=0?'+':'')+chg.toFixed(2)+'%</div>'
        +px
        +'<div style="font-size:.58rem;color:#475569;margin-top:2px">'+it.desc+'</div>'
        +'</div>';
    });
    document.getElementById('intl-grid').innerHTML=html||'<div style="color:#475569;font-size:.78rem;grid-column:1/-1">暫無資料</div>';
    var now=new Date(),h=now.getHours(),m=now.getMinutes(),s=now.getSeconds();
    var ts=(h<10?'0':'')+h+':'+(m<10?'0':'')+m+':'+(s<10?'0':'')+s;
    document.getElementById('intl-meta').textContent=ts+' · '+sourceLabel;
    var dot=document.getElementById('intl-live-dot');
    if(dot){dot.style.background=sourceLabel.indexOf('LIVE')>=0?'#10b981':'#f59e0b';dot.style.animation=sourceLabel.indexOf('LIVE')>=0?'blink 1s infinite':'';}
  }

  /* ── Yahoo Finance 即時 API（多端點 + 多Proxy 輪試）── */
  /* 關鍵：corsproxy.io 直接取 ? 後面整個字串作為目標URL，不需對整個URL再encode
           allorigins.win 用 ?url= 參數，才需要 encodeURIComponent             */
  var _SYM = MARKETS.map(function(m){return m.s.replace(/\^/g,'%5E');}).join('%2C');
  var _YFQ = 'https://query2.finance.yahoo.com/v7/finance/quote?symbols='
           + _SYM + '&lang=en&region=US&corsDomain=finance.yahoo.com';
  var _YFS = 'https://query2.finance.yahoo.com/v7/finance/spark?symbols='
           + _SYM + '&range=1d&interval=1m';

  function _pQ(d){  /* parse quote */
    var res=(d.quoteResponse||{}).result||[];
    if(!res.length) throw new Error('empty');
    var byS={};
    res.forEach(function(q){byS[q.symbol]=q;});
    var its=[];
    MARKETS.forEach(function(m){
      var q=byS[m.s]; if(!q) return;
      var chg=q.regularMarketChangePercent||0, price=q.regularMarketPrice||0;
      its.push({name:m.n,desc:m.d,chg:chg,price:price,sig:calcSig(m.n,chg,price)});
    });
    if(!its.length) throw new Error('no items');
    return its;
  }
  function _pS(d){  /* parse spark */
    var res=(d.spark||{}).result||[];
    if(!res.length) throw new Error('empty');
    var byS={};
    res.forEach(function(r){
      if(r&&r.response&&r.response[0]) byS[r.symbol]=r.response[0].meta;
    });
    var its=[];
    MARKETS.forEach(function(m){
      var meta=byS[m.s]; if(!meta) return;
      var price=meta.regularMarketPrice||0;
      var prev=meta.previousClose||meta.chartPreviousClose||0;
      if(!prev||!price) return;
      var chg=(price-prev)/prev*100;
      its.push({name:m.n,desc:m.d,chg:chg,price:price,sig:calcSig(m.n,chg,price)});
    });
    if(!its.length) throw new Error('no items');
    return its;
  }

  /* 5條路線：直連quote→直連spark→proxy+quote→proxy+spark→allorigins+quote */
  var _AT=[
    {u:_YFQ,  p:_pQ},
    {u:_YFS,  p:_pS},
    {u:'https://corsproxy.io/?'+_YFQ,  p:_pQ},
    {u:'https://corsproxy.io/?'+_YFS,  p:_pS},
    {u:'https://api.allorigins.win/raw?url='+encodeURIComponent(_YFQ), p:_pQ}
  ];
  var _ai=0;  /* 記住上次成功的路線 */
  setInterval(function(){_ai=0;}, 5*60*1000);  /* 每5分鐘重試從頭 */

  function fetchYahoo(){
    function tryFrom(i){
      if(i>=_AT.length) return Promise.reject(new Error('all failed'));
      var a=_AT[i];
      return fetch(a.u).then(function(r){return r.json();})
        .then(function(d){
          var its=a.p(d);
          _ai=i;  /* 記住此成功路線 */
          return its;
        })
        .catch(function(){return tryFrom(i+1);});
    }
    return tryFrom(_ai);
  }

  /* ── Fallback: intl.json ── */
  function fetchJson(){
    return fetch('data/intl.json?_='+Date.now())
      .then(function(r){return r.json();})
      .then(function(d){
        var items=[];
        MARKETS.forEach(function(m){
          var it=(d.data||{})[m.n];
          if(!it) return;
          items.push({name:m.n,desc:m.d,chg:it.chg_pct||0,price:it.price||0,sig:it.signal||0});
        });
        return {items:items, updated:d.updated};
      });
  }

  var _useLive=true;
  /* 每10分鐘重試 Yahoo（若之前因CORS放棄）*/
  setInterval(function(){_useLive=true;}, 10*60*1000);

  function loadOnce(){
    if(_useLive){
      fetchYahoo()
        .then(function(items){renderGrid(items,'● LIVE');})
        .catch(function(){
          _useLive=false;
          fetchJson().then(function(r){renderGrid(r.items,'JSON '+r.updated);}).catch(function(){});
        });
    } else {
      fetchJson().then(function(r){renderGrid(r.items,'JSON '+r.updated);}).catch(function(){});
    }
  }

  window.intlLoad=function(){
    _useLive=true; _ai=0;  /* 手動刷新時重試 */
    loadOnce();
  };

  loadOnce();
  setInterval(loadOnce, 30000);  /* 每30秒 */
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
  <div style="font-size:.58rem;color:#334155;margin-top:8px">瀏覽器即時抓取 · 每5分鐘自動更新 · 標題自動翻譯為繁體中文</div>
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
    window.__liveNews=d;   /* 供「明日交易建議」hero 即時重算新聞情緒分數 */
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

  /* ── 即時抓 Google News RSS（瀏覽器端，不靠 GitHub Action）── */
  var FEEDS=[
    {label:'川普動態',  q:'Trump+tariff+OR+Trump+trade+OR+Trump+says', max:6},
    {label:'關稅/貿易', q:'tariff+trade+war+economy',                 max:4},
    {label:'台股/半導體',q:'Taiwan+stock+OR+TSMC+OR+semiconductor',    max:4},
    {label:'聯準會',    q:'Federal+Reserve+interest+rate+OR+stock+market',max:4}
  ];
  var BULL=['deal','agreement','cut','boost','surge','rally','record','strong','optimism','positive','growth','rise','gain','increase','stimulus','ceasefire','peace','reduce','chip act'];
  var BEAR=['tariff','sanction','ban','war','threat','crash','recession','inflation','fall','drop','fear','risk','tension','conflict','escalat','collapse','default','crisis','sell-off','warning','impose','penalty','retaliation','shutdown','downgrade','miss','layoff','bankrupt'];
  function sentiment(t){
    var s=t.toLowerCase(),b=0,r=0;
    BULL.forEach(function(w){if(s.indexOf(w)>=0)b++;});
    BEAR.forEach(function(w){if(s.indexOf(w)>=0)r++;});
    return b>r?1:(r>b?-1:0);
  }
  function rssUrl(q){ return 'https://news.google.com/rss/search?q='+q+'&hl=en-US&gl=US&ceid=US:en'; }
  /* 多 proxy 容錯：jina.ai(markdown) 主 → allorigins(xml) → corsproxy(xml) */
  var PROXIES=[
    {make:function(raw){return 'https://r.jina.ai/'+raw;}, kind:'md'},
    {make:function(raw){return 'https://api.allorigins.win/raw?url='+encodeURIComponent(raw);}, kind:'xml'},
    {make:function(raw){return 'https://corsproxy.io/?url='+encodeURIComponent(raw);}, kind:'xml'}
  ];
  function extractTitles(text,kind){
    var titles=[];
    if(kind==='xml'){
      var doc=new DOMParser().parseFromString(text,'text/xml');
      var nodes=doc.querySelectorAll('item title');
      for(var i=0;i<nodes.length;i++){var t=(nodes[i].textContent||'').trim();if(t)titles.push(t);}
    }else{ /* jina markdown：每條新聞是  ### [標題](連結) */
      var re=/^#{2,3} \[(.+?)\]\(/gm, m;
      while((m=re.exec(text))!==null){ if(m[1].trim()) titles.push(m[1].trim()); }
    }
    return titles;
  }
  function toItems(titles,cfg){
    var out=[],n=0;
    for(var j=0;j<titles.length && n<cfg.max;j++){
      var title=titles[j]; if(!title)continue;
      var sv=sentiment(title);
      out.push({label:cfg.label,title:title.slice(0,100),
        sentiment:sv===1?'✅偏多':(sv===-1?'⚠️偏空':'⚪中性'),sent_val:sv});
      n++;
    }
    return out;
  }
  function fetchFeed(cfg){
    var raw=rssUrl(cfg.q);
    function tryP(idx){
      if(idx>=PROXIES.length) return Promise.resolve([]);
      var p=PROXIES[idx];
      return fetch(p.make(raw)).then(function(r){
        if(!r.ok) throw new Error('http '+r.status);
        return r.text();
      }).then(function(text){
        var items=toItems(extractTitles(text,p.kind),cfg);
        return items.length ? items : tryP(idx+1);
      }).catch(function(){ return tryP(idx+1); });
    }
    return tryP(0);
  }
  function buildMood(items){
    var bull=0,bear=0;
    items.forEach(function(i){if(i.sent_val===1)bull++;else if(i.sent_val===-1)bear++;});
    var score=bull-bear,mood,mc;
    if(score>=4){mood='偏多 📈';mc='#10b981';}
    else if(score>=2){mood='略偏多';mc='#34d399';}
    else if(score<=-4){mood='偏空 📉';mc='#ef4444';}
    else if(score<=-2){mood='略偏空';mc='#f87171';}
    else{mood='中性 ─';mc='#9ca3af';}
    function pad(n){return n<10?'0'+n:''+n;}
    var d=new Date();
    var ts=d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())+' '+pad(d.getHours())+':'+pad(d.getMinutes());
    return {updated:ts,bull:bull,bear:bear,score:score,mood:mood,mood_color:mc,items:items};
  }
  function fetchLiveNews(){
    return Promise.all(FEEDS.map(fetchFeed)).then(function(lists){
      var items=[];
      lists.forEach(function(l){items=items.concat(l);});
      if(!items.length) return null;          /* 全部 proxy 失敗 → 交給 fallback */
      return buildMood(items);
    });
  }
  window.newsLoad=function(){
    document.getElementById('news-meta').textContent='更新中…';
    fetchLiveNews()
      .then(function(d){
        if(d){ render(d); return; }
        /* fallback：讀靜態 news.json */
        return fetch('data/news.json?_='+Date.now())
          .then(function(r){return r.json();}).then(render);
      })
      .catch(function(){
        fetch('data/news.json?_='+Date.now())
          .then(function(r){return r.json();}).then(render)
          .catch(function(){document.getElementById('news-meta').textContent='載入失敗';});
      });
  };
  newsLoad();
  setInterval(newsLoad,300000);   /* 每5分鐘即時刷新 */
})();
</script>"""

    # ── 長榮航太看板 ─────────────────────────────────────
    stock_html = stock_card_html(stock or {})

    # ── 定期定額追蹤 ─────────────────────────────────────
    dca_html = dca_card_html(dca or {})

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

    _inst_s = int(signal.get("inst_score", 0))
    _static_s = tw_s + _inst_s   # 台灣技術 + 法人籌碼（日線，不即時）
    _fut_net = int(signal.get("foreign_fut_net", 0))   # 外資期貨淨口數（凍結，供前端 veto 用）

    score_meter_html = f"""
<div class="card" id="live-score-card" style="margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <div class="stitle" style="margin-bottom:0">📊 五維評分系統</div>
    <div style="display:flex;align-items:center;gap:6px">
      <span style="width:7px;height:7px;background:#10b981;border-radius:50%;display:inline-block;animation:blink 1s infinite"></span>
      <span style="font-size:.6rem;color:#10b981;font-weight:700">LIVE</span>
      <span id="ls-clock" style="font-size:.6rem;color:#475569"></span>
    </div>
  </div>

  <!-- 總分儀表（JS填充） -->
  <div style="margin-bottom:14px">
    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px">
      <div style="font-size:.65rem;color:#64748b">總評分</div>
      <div style="display:flex;align-items:center;gap:8px">
        <span id="ls-total-num" style="font-size:1.4rem;font-weight:900;color:#64748b">--</span>
        <span id="ls-total-label" style="font-size:.78rem;font-weight:700;color:#64748b">載入中</span>
        <span style="font-size:.65rem;color:#475569">門檻 ±{thresh}</span>
      </div>
    </div>
    <div style="position:relative;height:22px;background:#0d1829;border-radius:6px;overflow:visible;border:1px solid #1e3050">
      <div style="position:absolute;left:3px;top:50%;transform:translateY(-50%);font-size:.55rem;color:#22c55e;z-index:2">空</div>
      <div style="position:absolute;right:3px;top:50%;transform:translateY(-50%);font-size:.55rem;color:#ef4444;z-index:2">多</div>
      <div id="ls-fill" style="position:absolute;left:50%;width:0%;height:100%;border-radius:5px;opacity:.9;transition:all .6s ease"></div>
      <div style="position:absolute;left:50%;width:2px;height:100%;background:#334155;transform:translateX(-50%)"></div>
      <div style="position:absolute;left:{_thresh_pct_lo:.1f}%;width:1px;height:100%;background:#475569;opacity:.6;border-right:1px dashed #475569"></div>
      <div style="position:absolute;left:{_thresh_pct_hi:.1f}%;width:1px;height:100%;background:#475569;opacity:.6;border-right:1px dashed #475569"></div>
      <div id="ls-bubble" style="position:absolute;left:50%;top:-18px;transform:translateX(-50%);background:#475569;color:#fff;font-size:.6rem;font-weight:700;padding:1px 5px;border-radius:4px;white-space:nowrap;z-index:3;transition:all .6s ease">--
        <div style="position:absolute;bottom:-4px;left:50%;transform:translateX(-50%);width:0;height:0;border-left:4px solid transparent;border-right:4px solid transparent;border-top:4px solid #475569" id="ls-bubble-arrow"></div>
      </div>
    </div>
    <div style="display:flex;justify-content:space-between;margin-top:4px;font-size:.58rem;color:#334155">
      <span>-16</span><span>-{thresh}</span><span>0</span><span>+{thresh}</span><span>+16</span>
    </div>
  </div>

  <!-- 維度條（JS填充） -->
  <div id="ls-dims"></div>

  <!-- 四策略勝率 -->
  <div style="margin-top:10px;padding-top:10px;border-top:1px solid #1e3254">
    <div style="font-size:.58rem;color:#475569;margin-bottom:7px;letter-spacing:.06em">四策略勝率（回測）</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px">
      <div style="background:#0d1829;border-radius:8px;padding:8px 10px;border:1px solid #1e3254">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
          <span style="font-size:.62rem;color:#94a3b8">精準版</span>
          <span style="font-size:.8rem;font-weight:800;color:#3b82f6">{wr100:.0f}%</span>
        </div>
        <div style="height:5px;background:#132236;border-radius:3px;overflow:hidden">
          <div style="height:100%;width:{wr100:.0f}%;background:#3b82f6;border-radius:3px"></div>
        </div>
        <div style="font-size:.58rem;color:#334155;margin-top:3px">{n100} 筆</div>
      </div>
      <div style="background:#0d1829;border-radius:8px;padding:8px 10px;border:1px solid #1e3254">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
          <span style="font-size:.62rem;color:#94a3b8">優化版</span>
          <span style="font-size:.8rem;font-weight:800;color:#8b5cf6">{wr70:.0f}%</span>
        </div>
        <div style="height:5px;background:#132236;border-radius:3px;overflow:hidden">
          <div style="height:100%;width:{wr70:.0f}%;background:#8b5cf6;border-radius:3px"></div>
        </div>
        <div style="font-size:.58rem;color:#334155;margin-top:3px">{n70} 筆</div>
      </div>
      <div style="background:#0d1829;border-radius:8px;padding:8px 10px;border:1px solid #1e3254">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
          <span style="font-size:.62rem;color:#94a3b8">高頻版</span>
          <span style="font-size:.8rem;font-weight:800;color:#10b981">{wr60:.0f}%</span>
        </div>
        <div style="height:5px;background:#132236;border-radius:3px;overflow:hidden">
          <div style="height:100%;width:{wr60:.0f}%;background:#10b981;border-radius:3px"></div>
        </div>
        <div style="font-size:.58rem;color:#334155;margin-top:3px">{n60} 筆</div>
      </div>
      <div style="background:#0d1829;border-radius:8px;padding:8px 10px;border:1px solid #1e3254">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
          <span style="font-size:.62rem;color:#94a3b8">超高頻</span>
          <span style="font-size:.8rem;font-weight:800;color:#f59e0b">{wr50:.0f}%</span>
        </div>
        <div style="height:5px;background:#132236;border-radius:3px;overflow:hidden">
          <div style="height:100%;width:{wr50:.0f}%;background:#f59e0b;border-radius:3px"></div>
        </div>
        <div style="font-size:.58rem;color:#334155;margin-top:3px">{n50} 筆</div>
      </div>
    </div>
  </div>

  <!-- 資料時間戳 -->
  <div id="ls-meta" style="font-size:.58rem;color:#334155;margin-top:8px;text-align:right"></div>
</div>

<script>
(function(){{
  var TW_S    = {tw_s};
  var INST_S  = {_inst_s};
  var THRESH  = {thresh};
  var MAX_TOT = 16;
  /* ── 凍結的台灣技術濾網輸入（隔夜不變，與後端 signal_engine 的 veto 完全同步）── */
  var V_RSI={rsi}, V_MA5={ma5}, V_MA10={ma10}, V_MA20={ma20};
  var V_MA5P={ma5_p2}, V_MA10P={ma10_p2}, V_MA20P={ma20_p2};
  var V_MACD={macd}, V_MACDS={macds}, V_FUT={_fut_net};
  var TRADE_DATE_H='{trade_date}';
  function sgn(v){{return (v>=0?'+':'')+v;}}
  function pad2(n){{return n<10?'0'+n:''+n;}}
  function todayStr_(){{var d=new Date();return d.getFullYear()+'-'+pad2(d.getMonth()+1)+'-'+pad2(d.getDate());}}

  /* 即時重算「明日交易建議」方向（與後端 veto 邏輯一致；台灣技術面凍結，國際/新聞即時） */
  function calcDirection(total, int_s){{
    var tw_dir = TW_S>0?1:(TW_S<0?-1:0);
    var int_dir= int_s>0?1:(int_s<0?-1:0);
    var fut_dir= V_FUT>500?1:(V_FUT<-500?-1:0);
    var ma_bull=(V_MA5>V_MA10&&V_MA10>V_MA20)&&(V_MA5P>V_MA10P&&V_MA10P>V_MA20P);
    var ma_bear=(V_MA5<V_MA10&&V_MA10<V_MA20)&&(V_MA5P<V_MA10P&&V_MA10P<V_MA20P);
    var macd_bull=(V_MACD>0&&V_MACD>V_MACDS);
    var macd_bear=(V_MACD<0&&V_MACD<V_MACDS);
    var rsi_bull=(45<V_RSI&&V_RSI<72);
    var rsi_bear=(28<V_RSI&&V_RSI<55);
    var veto='', dir=0;
    if(tw_dir!==0&&int_dir!==0&&tw_dir!==int_dir){{ veto='台灣技術('+sgn(TW_S)+') vs 國際('+sgn(int_s)+') 方向相反 → 觀望'; }}
    else if(total>0&&!rsi_bull){{ veto='RSI='+V_RSI.toFixed(0)+' 過熱(需45~72)或過冷 → 觀望'; }}
    else if(total<0&&!rsi_bear){{ veto='RSI='+V_RSI.toFixed(0)+' 不在空頭區間(28~55) → 觀望'; }}
    else if(total>0&&!(ma_bull&&macd_bull)){{ veto='看多需: 均線連續2日多頭排列 + MACD金叉向上 → 條件不足'; }}
    else if(total<0&&!(ma_bear&&macd_bear)){{ veto='看空需: 均線連續2日空頭排列 + MACD死叉向下 → 條件不足'; }}
    else if(fut_dir!==0&&tw_dir!==0&&fut_dir!==tw_dir){{ dir=(total>=THRESH+3?1:(total<=-(THRESH+3)?-1:0)); }}
    else {{ dir=(total>=THRESH?1:(total<=-THRESH?-1:0)); }}
    return {{dir:dir, veto:veto}};
  }}

  function updateHero(total, int_s, psy_s, gld_s, nws_s){{
    var R=calcDirection(total, int_s);
    var hero=document.getElementById('signal-hero');
    var lbl =document.getElementById('hero-sig-label');
    var act =document.getElementById('hero-sig-action');
    var det =document.getElementById('hero-score-detail');
    var ts  =document.getElementById('hero-live-ts');
    if(!hero||!lbl) return;
    var bg,label,action;
    if(R.dir===1){{ bg='linear-gradient(135deg,#059669,#10b981)'; label='🟢 明天做多（買進）'; action='8:45 買進 1口 ｜ 13:30 賣出平倉'; }}
    else if(R.dir===-1){{ bg='linear-gradient(135deg,#dc2626,#ef4444)'; label='🔴 明天做空（賣出）'; action='8:45 賣出 1口 ｜ 13:30 買回平倉'; }}
    else {{ bg='linear-gradient(135deg,#374151,#4b5563)'; label='⚪ 明天觀望（不交易）'; action=R.veto?R.veto:('訊號不足，總分 '+sgn(total)+'，未達門檻 ±'+THRESH); }}
    /* 跨午夜後「明天」自動變「今天」 */
    if(TRADE_DATE_H && TRADE_DATE_H<=todayStr_()) label=label.replace('明天','今天');
    hero.style.background=bg;
    lbl.textContent=label;
    if(act) act.textContent=action;
    if(det) det.textContent='台灣技術 '+sgn(TW_S)+' ＋ 法人 '+sgn(INST_S)+' ＋ 國際 '+sgn(int_s)
      +' ＋ 心理 '+sgn(psy_s)+' ＋ 黃金 '+sgn(gld_s)+' ＋ 新聞 '+sgn(nws_s)
      +' ＝ 總分 '+sgn(total)+'（門檻 ±'+THRESH+'）';
    var d=new Date();
    if(ts) ts.textContent='即時更新 '+pad2(d.getHours())+':'+pad2(d.getMinutes());
  }}

  var INTL_W = {{
    '費城半導體':3,'NASDAQ':2,'S&P500':2,'道瓊':1,
    '日經225':1,'韓KOSPI':1,'恒生指數':1,
    '上證指數':0,'台股加權':0,'VIX恐慌':0,
    '美元指數':1,'黃金':0,'原油':1,'美債10Y':1,'比特幣':0
  }};

  function calcIntl(intl){{
    var s=0;
    for(var k in intl){{
      var w=(INTL_W[k]!==undefined)?INTL_W[k]:1;
      if(!w) continue;
      s+=(intl[k].signal||0)*w;
    }}
    return s;
  }}

  function calcPsy(intl){{
    var vd=intl['VIX恐慌']||{{}};
    var vix=vd.price||20, vc=vd.chg_pct||0, s=0;
    if(vix<14) s+=2; else if(vix<18) s+=1;
    else if(vix<23) s+=0; else if(vix<28) s-=1;
    else if(vix<35) s-=2; else s-=3;
    if(vc>15) s-=2; else if(vc>8) s-=1; else if(vc<-10) s+=1;
    var gd=intl['黃金']||{{}}, gc=gd.chg_pct||0;
    if(gc>1.5&&vix>25) s-=2; else if(gc<-1&&vix<18) s+=1;
    var dd=intl['美元指數']||{{}}, dc=dd.chg_pct||0;
    if(dc>0.5) s-=1; else if(dc<-0.4) s+=1;
    return s;
  }}

  function calcNews(items){{
    if(!items||!items.length) return 0;
    var b=0,r=0;
    items.forEach(function(n){{if(n.sent_val===1) b++; else if(n.sent_val===-1) r++;}});
    return Math.max(-2,Math.min(2,b-r));
  }}

  function dimBar(label, val, maxAbs, icon){{
    var c=Math.max(-maxAbs,Math.min(maxAbs,val));
    var fill=Math.abs(c)/maxAbs*45;
    var fc=val>=0?'#ef4444':'#22c55e';
    var lp=val>=0?50:50-fill;
    var vs=(val>=0?'+':'')+val;
    return '<div class="srow"><span class="slbl">'+icon+label+'</span>'
      +'<div class="sbar-wrap"><div style="position:absolute;left:50%;width:1px;height:100%;background:#1e3050"></div>'
      +'<div style="position:absolute;left:'+lp.toFixed(1)+'%;width:'+fill.toFixed(1)+'%;height:100%;background:'+fc+';border-radius:3px;transition:width .5s ease,left .5s ease"></div>'
      +'</div><span style="font-size:.82rem;font-weight:700;color:'+fc+';width:28px;text-align:right;flex-shrink:0">'+vs+'</span></div>';
  }}

  function render(intlData, newsData){{
    var intl  = intlData.data || {{}};
    /* 優先用瀏覽器即時抓到的新聞（window.__liveNews），否則用 news.json */
    var items = (window.__liveNews && window.__liveNews.items) || newsData.items || [];
    var int_s = calcIntl(intl);
    var psy_s = calcPsy(intl);
    var gld_s = (intl['黃金']||{{}}).signal || 0;
    var nws_s = calcNews(items);
    var total = TW_S + INST_S + int_s + psy_s + gld_s + nws_s;
    updateHero(total, int_s, psy_s, gld_s, nws_s);
    var clamp = Math.max(-MAX_TOT, Math.min(MAX_TOT, total));
    var sPct  = (clamp + MAX_TOT) / (2*MAX_TOT) * 100;
    var lc, ll, grad, lp, lw;
    if(total >= THRESH)  {{ lc='#ef4444'; ll='🔴 偏多'; }}
    else if(total<=-THRESH) {{ lc='#22c55e'; ll='🟢 偏空'; }}
    else {{ lc='#64748b'; ll='⚪ 中性'; }}
    if(total>=0) {{ grad='linear-gradient(90deg,#b91c1c,#ef4444)'; lp=50; lw=sPct-50; }}
    else         {{ grad='linear-gradient(90deg,#15803d,#22c55e)'; lp=sPct; lw=50-sPct; }}
    lw=Math.max(0,lw);

    var tn=document.getElementById('ls-total-num');
    var tl=document.getElementById('ls-total-label');
    var fill=document.getElementById('ls-fill');
    var bub=document.getElementById('ls-bubble');
    var arr=document.getElementById('ls-bubble-arrow');
    if(tn){{ tn.textContent=(total>=0?'+':'')+total; tn.style.color=lc; }}
    if(tl){{ tl.textContent=ll; tl.style.color=lc; }}
    if(fill){{ fill.style.left=lp+'%'; fill.style.width=lw+'%'; fill.style.background=grad; }}
    if(bub){{ bub.style.left=sPct+'%'; bub.style.background=lc; }}
    if(arr){{ arr.style.borderTopColor=lc; }}
    var bubTxt=bub?bub.firstChild:null;
    if(bubTxt&&bubTxt.nodeType===3) bubTxt.nodeValue=(total>=0?'+':'')+total;

    var vix=((intl['VIX恐慌']||{{}}).price||0).toFixed(1);
    var dims=document.getElementById('ls-dims');
    if(dims) dims.innerHTML=
      dimBar('台灣技術',TW_S,5,'📊 ')+
      dimBar('國際市場',int_s,7,'🌐 ')+
      dimBar('市場心理',psy_s,5,'🧠 ')+
      dimBar('黃金',gld_s,2,'🥇 ')+
      dimBar('新聞情緒',nws_s,2,'📰 ')+
      '<div style="font-size:.58rem;color:#475569;margin-top:4px">VIX='+vix+'</div>';

    var meta=document.getElementById('ls-meta');
    if(meta) meta.textContent='市場 '+intlData.updated+' · 新聞 '+(newsData.updated||'--');

    /* 時鐘 */
    var d=new Date(),h=d.getHours(),m=d.getMinutes(),s=d.getSeconds();
    var cl=document.getElementById('ls-clock');
    if(cl) cl.textContent=(h<10?'0':'')+h+':'+(m<10?'0':'')+m+':'+(s<10?'0':'')+s;
  }}

  var _intl={{updated:'--',data:{{}}}}, _news={{updated:'--',items:[]}};
  var _intlOk=false, _newsOk=false;
  function tryRender(){{
    if(_intlOk||_newsOk) render(_intl,_news);
  }}
  function fetchAll(){{
    var t=Date.now();
    fetch('data/intl.json?_='+t).then(function(r){{return r.json();}}).then(function(d){{
      _intl=d; _intlOk=true; tryRender();
    }}).catch(function(){{}});
    fetch('data/news.json?_='+t).then(function(r){{return r.json();}}).then(function(d){{
      _news=d; _newsOk=true; tryRender();
    }}).catch(function(){{}});
  }}

  fetchAll();
  setInterval(fetchAll, 5000);
}})();
</script>"""

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
.pw{{max-width:900px;margin:0 auto;padding:16px 14px}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:stretch;margin-bottom:0}}
.two-col>.card,.two-col>[id$="-card"],.two-col>.j10-card{{margin-bottom:12px}}
.two-col>div>div.card{{height:100%;box-sizing:border-box}}

/* ── Responsive ────────────────────────────────────── */
@media(max-width:700px){{
  .row3{{grid-template-columns:repeat(3,1fr)}}
  .intl-grid{{grid-template-columns:repeat(2,1fr)}}
  .two-col{{grid-template-columns:1fr}}
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
  <span style="font-size:.82rem;color:#93c5fd" id="update-banner-txt">📡 資料已更新</span>
  <span style="font-size:.75rem;color:#60a5fa">點此立即更新 🔄</span>
</div>

<!-- ══════════════ FULL-WIDTH ALERTS ════════════════ -->
{night_html}
{gold_html}
{today_card}

<!-- ══════════════ 台指期主力區 ═══════════════════════ -->

<!-- 明日信號英雄卡（全寬） -->
<div class="signal-hero" id="signal-hero" style="background:{sig_bg};margin-bottom:12px">
  <div id="hero-sig-label" style="font-size:1.95rem;font-weight:900;line-height:1.1;letter-spacing:-.5px">
    {sig_label}
  </div>
  <div style="font-size:.85rem;opacity:.85;margin-top:6px">{trade_date}</div>
  <div id="hero-sig-action" style="background:rgba(0,0,0,.28);border-radius:10px;
              padding:9px 14px;margin-top:11px;font-size:.8rem;line-height:1.5;opacity:.92">
    {sig_action}
  </div>
  <div id="hero-score-detail" style="font-size:.67rem;opacity:.55;margin-top:8px;line-height:1.4">{score_detail}</div>
  <div style="margin-top:10px;display:flex;justify-content:space-between;align-items:center">
    <span style="font-size:.58rem;opacity:.45" id="hero-live-ts">{sig_generated_at} 更新</span>
    <button onclick="window.location.reload()" style="background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);color:rgba(255,255,255,.75);border-radius:5px;padding:2px 8px;font-size:.58rem;cursor:pointer;line-height:1.6">🔄 刷新</button>
  </div>
</div>

<!-- ══ Row 1: 期貨評分（左）｜ 期貨訊號（右）══ -->
<div class="two-col">

<!-- 左：五維評分儀表 -->
<div>
{score_meter_html}
</div>

<!-- 右：TABS 今日訊號 / 回測統計 / 交易記錄 -->
<div>
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
    {sim_vsel_stats_html}
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
</div>

</div><!-- /two-col 期貨 -->

<!-- ══ Row 2: 金十快訊（左）｜ 國際新聞（右）中段參考 ══ -->
<div class="two-col">
<div>{jin10_html}</div>
<div>{news_html}</div>
</div><!-- /two-col 新聞 -->

<!-- ══════════════ 國際市場（全寬）══════════════════ -->
{intl_html}

<!-- ══════════════ 定期定額（009816 + 00992A）══════════ -->
{dca_html}

<!-- ══════════════ 長榮航太（最後）══════════════════ -->
{stock_html}

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
    var t=document.getElementById('update-banner-txt');
    if(b) b.style.display='flex';
    var secs=10;
    if(t) t.textContent='📡 資料已更新，'+secs+'秒後自動更新...';
    var iv=setInterval(function(){{
      secs--;
      if(t) t.textContent='📡 資料已更新，'+secs+'秒後自動更新...';
      if(secs<=0){{ clearInterval(iv); window.location.reload(); }}
    }},1000);
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
  setTimeout(poll,60000);       /* 載入後1分鐘先查一次（可能開到舊頁） */
  setInterval(poll,180000);     /* 之後每3分鐘查一次新資料 */
}})();

/* ── 自動重載保留捲動位置（手機才不會跳回頂端）──────────── */
(function(){{
  try{{
    var y=sessionStorage.getItem('scrollY');
    if(y!==null){{
      window.addEventListener('load',function(){{
        window.scrollTo(0,parseInt(y,10)||0);
        sessionStorage.removeItem('scrollY');
      }});
    }}
    window.addEventListener('beforeunload',function(){{
      sessionStorage.setItem('scrollY', String(window.scrollY||window.pageYOffset||0));
    }});
  }}catch(e){{}}
}})();

/* ── 明日→今日 標籤自動切換 ───────────────────────── */
(function(){{
  var TRADE_DATE='{trade_date}';  /* e.g. "2026-06-17" */
  function todayStr(){{
    var d=new Date();
    return d.getFullYear()+'-'
      +String(d.getMonth()+1).padStart(2,'0')+'-'
      +String(d.getDate()).padStart(2,'0');
  }}
  function patchLabels(){{
    if(TRADE_DATE>todayStr()) return;  /* 還沒到那天，不換 */
    var el=document.getElementById('hero-sig-label');
    if(el) el.innerHTML=el.innerHTML.replace(/明天/g,'今天');
  }}
  patchLabels();  /* 頁面載入時立即判斷 */
  /* 凌晨零點再執行一次 */
  var now=new Date();
  var msToMid=new Date(now.getFullYear(),now.getMonth(),now.getDate()+1)-now;
  setTimeout(patchLabels, msToMid+500);
}})();
</script>
</body>
</html>"""


def main():
    print("📂 載入資料...", flush=True)
    signal, records, stock, dca = load_data()
    print("🎨 產生看板...", flush=True)
    html = generate_html(signal, records, stock, dca)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 看板已儲存: {OUTPUT_PATH}")
    # CI: skip browser open

if __name__ == "__main__":
    main()
