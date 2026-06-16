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

# 3. 執行看板產生
r = subprocess.run(
    [sys.executable, os.path.join(HERE, "dashboard_gen.py")],
    cwd=HERE
)
if r.returncode != 0:
    print("❌ 看板產生失敗"); sys.exit(1)

print("✅ index.html 已更新")
