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

# 3. 執行看板產生
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "dashboard_gen.py")],
    cwd=HERE
)
if r.returncode != 0:
    print("❌ 看板產生失敗"); sys.exit(1)

print("✅ index.html 已更新")
