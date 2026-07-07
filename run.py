#!/usr/bin/env python3
"""
台指期看板 — GitHub Actions 執行入口
每天 08:30 / 13:45（台灣時間）自動執行
"""
import sys, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
print(f"🕐 模式：{mode}", flush=True)

# 1. 執行信號腳本
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "signal_engine.py")] +
    (["--close"] if mode == "close" else []),
    cwd=HERE
)
if r.returncode != 0:
    print("❌ 信號腳本執行失敗"); sys.exit(1)

# 2. 執行長榮航太股票信號
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "stock_signal.py")],
    cwd=HERE
)
if r.returncode != 0:
    print("⚠️  長榮航太信號失敗（繼續產生看板）")

# 2a2. 更新長榮航太籌碼面（三大法人 + 融資融券，寫入 data/stock_chips.json）
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "stock_chips.py")],
    cwd=HERE
)
if r.returncode != 0:
    print("⚠️  長榮航太籌碼抓取失敗（繼續產生看板）")

# 2a3. 執行南亞科(2408)股票信號（同規格，寫入 data/stock_2408.json）
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "stock_signal_2408.py")],
    cwd=HERE
)
if r.returncode != 0:
    print("⚠️  南亞科信號失敗（繼續產生看板）")

# 2a4. 更新南亞科(2408)籌碼面（三大法人 + 融資融券，寫入 data/stock_chips_2408.json）
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "stock_chips_2408.py")],
    cwd=HERE
)
if r.returncode != 0:
    print("⚠️  南亞科籌碼抓取失敗（繼續產生看板）")

# 2a5. 執行月月配三劍客 ETF（0056+00878+00919，寫入 data/stock_etf.json）
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "stock_etf.py")],
    cwd=HERE
)
if r.returncode != 0:
    print("⚠️  月月配ETF信號失敗（繼續產生看板）")

# 2b. 更新新聞（同步寫入 data/news.json）
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "news_fetch.py")],
    cwd=HERE
)
if r.returncode != 0:
    print("⚠️  新聞抓取失敗（繼續產生看板）")

# 2c. 更新國際市場指數（同步寫入 data/intl.json）
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "intl_fetch.py")],
    cwd=HERE
)
if r.returncode != 0:
    print("⚠️  國際市場抓取失敗（繼續產生看板）")

# 2d. 更新定期定額追蹤（同步寫入 data/dca.json）
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "dca_fetch.py")],
    cwd=HERE
)
if r.returncode != 0:
    print("⚠️  定期定額抓取失敗（繼續產生看板）")

# 2e. 更新三大法人估算成本均價（增量回補，寫入 data/stock_cost_est.json）
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "stock_cost_est.py")],
    cwd=HERE
)
if r.returncode != 0:
    print("⚠️  法人估算成本抓取失敗（繼續產生看板）")

# 3. 執行看板產生
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "dashboard_gen.py")],
    cwd=HERE
)
if r.returncode != 0:
    print("❌ 看板產生失敗"); sys.exit(1)

print("✅ index.html 已更新")
