#!/usr/bin/env python3
"""
台指期看板 — 一鍵部署到 GitHub Pages（完整版）
用法：python3 deploy.py <GitHub Personal Access Token>

Token 申請：https://github.com/settings/tokens/new
勾選：repo + workflow（兩個大項）
"""
import sys, os, base64, time
import warnings; warnings.filterwarnings("ignore")

try:
    import requests
except ImportError:
    print("❌ pip3 install requests"); sys.exit(1)

if len(sys.argv) < 2 or len(sys.argv[1]) < 10:
    print("""
用法：python3 deploy.py <你的GitHub Token>

Token 申請步驟（2分鐘）：
  1. 打開 https://github.com/settings/tokens/new
  2. Note：填 taiwan-futures
  3. Expiration：No expiration
  4. 勾選 repo 整個大項 + workflow 整個大項
  5. 點 Generate token → 複製 ghp_... 那串
  6. 執行：python3 deploy.py ghp_你的token
""")
    sys.exit(0)

TOKEN = sys.argv[1].strip()
H = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
BASE = "https://api.github.com"

def api(method, path, **kw):
    return requests.request(method, BASE + path, headers=H, timeout=30, **kw)

# ── 1. 驗證 Token ───────────────────────────────────────────
print("🔑 驗證 Token...", flush=True)
r = api("GET", "/user")
if r.status_code != 200:
    print(f"❌ Token 無效（{r.status_code}）：{r.text[:100]}"); sys.exit(1)
user = r.json()["login"]
print(f"✅ 登入成功：@{user}")
REPO = f"{user}.github.io"

# ── 2. 建立 Repository ──────────────────────────────────────
print(f"📦 Repository：{REPO}...", flush=True)
r = api("GET", f"/repos/{user}/{REPO}")
if r.status_code == 200:
    print("  → 已存在，直接更新檔案")
else:
    r = api("POST", "/user/repos", json={
        "name": REPO,
        "description": "台指期每日信號看板",
        "private": False,
        "auto_init": True,
    })
    if r.status_code not in (200, 201):
        print(f"❌ 建立失敗：{r.text}"); sys.exit(1)
    print("  ✅ Repository 建立成功")
    time.sleep(3)

# ── 3. 上傳所有檔案 ─────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))

FILES = [
    # (本地路徑, GitHub 路徑)
    ("index.html",                    "index.html"),
    ("signal_engine.py",              "signal_engine.py"),
    ("dashboard_gen.py",              "dashboard_gen.py"),
    ("run.py",                        "run.py"),
    ("requirements.txt",              "requirements.txt"),
    (".github/workflows/update.yml",  ".github/workflows/update.yml"),
    # 歷史記錄（如果存在）
    ("data/records.csv",              "data/records.csv"),
    ("data/signal.json",              "data/signal.json"),
]

def upload_file(local_rel, remote_path):
    local_abs = os.path.join(HERE, local_rel)
    if not os.path.exists(local_abs):
        return  # 跳過不存在的檔案

    with open(local_abs, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    r = api("GET", f"/repos/{user}/{REPO}/contents/{remote_path}")
    sha = r.json().get("sha") if r.status_code == 200 else None

    payload = {
        "message": f"{'Update' if sha else 'Add'} {os.path.basename(remote_path)}",
        "content": content,
    }
    if sha:
        payload["sha"] = sha

    r = api("PUT", f"/repos/{user}/{REPO}/contents/{remote_path}", json=payload)
    if r.status_code in (200, 201):
        print(f"  ✅ {remote_path}")
    else:
        print(f"  ❌ {remote_path}：{r.status_code} {r.text[:100]}")

print("📤 上傳檔案...", flush=True)
for local, remote in FILES:
    upload_file(local, remote)
    time.sleep(0.4)

# ── 4. 開啟 GitHub Pages ────────────────────────────────────
print("🌐 開啟 GitHub Pages...", flush=True)
time.sleep(2)
r = api("POST", f"/repos/{user}/{REPO}/pages",
        json={"source": {"branch": "main", "path": "/"}})
if r.status_code in (200, 201):
    print("  ✅ GitHub Pages 開啟")
elif r.status_code == 409:
    print("  ✅ GitHub Pages 已開啟")
else:
    print(f"  ⚠️  {r.status_code}：請到 Settings→Pages 手動開啟")

# ── 5. 觸發第一次更新 ───────────────────────────────────────
print("🚀 觸發 Actions 第一次執行...", flush=True)
time.sleep(5)
r = api("GET", f"/repos/{user}/{REPO}/actions/workflows")
wf_id = None
if r.status_code == 200:
    for wf in r.json().get("workflows", []):
        if "update" in wf.get("name","").lower():
            wf_id = wf["id"]; break

if wf_id:
    r = api("POST",
            f"/repos/{user}/{REPO}/actions/workflows/{wf_id}/dispatches",
            json={"ref": "main"})
    if r.status_code == 204:
        print("  ✅ 執行中（約 3 分鐘完成）")
    else:
        print(f"  ⚠️  觸發失敗（{r.status_code}），請到 Actions 頁面手動點 Run workflow")
else:
    print("  ℹ️  請到 Actions 頁面手動點 Run workflow 一次")

# ── 完成 ────────────────────────────────────────────────────
url = f"https://{user}.github.io"
print(f"""
╔══════════════════════════════════════════════════════════╗
║  ✅  部署完成！                                            ║
║                                                          ║
║  網址：{url:<50}║
║                                                          ║
║  • 約 3-5 分鐘後正式上線（首次需要等 Actions 跑完）          ║
║  • 每個交易日 08:30 / 13:45 自動更新                        ║
║  • 看板內容與你本機完全相同（含四版本、統計、新聞）              ║
╚══════════════════════════════════════════════════════════╝
""")
