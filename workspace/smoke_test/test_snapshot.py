#!/usr/bin/env python3
"""
Snapshot 固化验证 —— 对应 workspace/smoke_test/snapshot.md 的实现。

流程：
  1. 建材实例：裸模板 -> git clone CUA-Gym-Hub -> 31-app 白名单部署（install+build+tmux起 vite preview）
  2. 验证 31 个端口可访问
  3. create_snapshot()
  4. 从 snapshot_id 新建一个全新沙箱，验证文件系统 / 进程 / 端口是否原样保留，记录耗时
  5. kill 掉建材实例，验证快照是否仍然可用（持久化）

Usage:
    python workspace/smoke_test/test_snapshot.py
"""
import sys
import time
import traceback
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE))

from e2b import Sandbox

TEMPLATE = "sdt-2nn0tz4x"
REPO_URL = "https://github.com/xlang-ai/CUA-Gym-Hub"
SNAPSHOT_NAME = "cua-gym-hub-31apps-v1"
BOOTSTRAP_TIMEOUT = 2400   # clone + 31x install + 31x build，给足余量
SNAPSHOT_SANDBOX_TIMEOUT = 300

# 与 gym/bench/url_variables.json 对应的 31 个 app，字母序 == 端口 8000..8030
MOCKS = [
    "asana", "discord", "docusign", "facebook", "github", "gitlab", "gmail",
    "google_calendar", "google_docs", "google_drive", "google_sheets",
    "hubspot", "instacart", "instagram", "jira", "linkedin",
    "microsoft_teams", "monday", "notion", "outlook_web", "pinterest",
    "postman", "reddit", "salesforce", "shopify_admin", "slack",
    "stripe_dashboard", "trello", "twitter", "uber_eats", "wechat",
]

_cleanup_ids: list[str] = []


def _section(title: str):
    print(f"\n{'─' * 70}")
    print(f"  {title}")
    print('─' * 70)


def _ok(msg: str = ""):
    print(f"  [PASS]" + (f"  {msg}" if msg else ""))


def _fail(msg: str, exc: Exception | None = None):
    print(f"  [FAIL]  {msg}")
    if exc:
        traceback.print_exc()


def _run(sbx: Sandbox, cmd: str, timeout: float = 120, **kw):
    res = sbx.commands.run(cmd, timeout=timeout, **kw)
    return res


def _check_ports(sbx: Sandbox, label: str):
    res = _run(
        sbx,
        "for p in $(seq 8000 8030); do "
        "code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 http://127.0.0.1:$p/); "
        "echo \"$p:$code\"; done",
        timeout=120,
    )
    lines = [l for l in res.stdout.strip().splitlines() if l]
    ok = sum(1 for l in lines if l.endswith(":200"))
    print(f"  [{label}] {ok}/{len(lines)} 端口返回 200")
    bad = [l for l in lines if not l.endswith(":200")]
    if bad:
        print(f"  未通过: {bad}")
    return ok, len(lines)


DEPLOY_SCRIPT = f"""#!/bin/bash
set -uo pipefail
cd "$HOME/CUA-Gym-Hub" || exit 1
WEBSITES_DIR="$(pwd)/websites"
[ -s "$HOME/.nvm/nvm.sh" ] && . "$HOME/.nvm/nvm.sh"
TMUX_SESSION="cua-hub"
BASE_PORT=8000
MOCKS=({' '.join(m + '_mock' for m in MOCKS)})

echo "Installing deps for ${{#MOCKS[@]}} apps..."
for MOCK in "${{MOCKS[@]}}"; do
    (cd "$WEBSITES_DIR/$MOCK" && npm install --silent) || echo "  [INSTALL-ERR] $MOCK"
done
echo "Install phase done."

echo "Building ${{#MOCKS[@]}} apps in parallel..."
for MOCK in "${{MOCKS[@]}}"; do
    (cd "$WEBSITES_DIR/$MOCK" && npm run build --silent > /tmp/build_$MOCK.log 2>&1 && echo "  [OK] $MOCK" || echo "  [BUILD-ERR] $MOCK") &
done
wait
echo "Build phase done."

tmux has-session -t "$TMUX_SESSION" 2>/dev/null && tmux kill-session -t "$TMUX_SESSION"
tmux new-session -d -s "$TMUX_SESSION" -n "_idle" "bash"
PORT=$BASE_PORT
for MOCK in "${{MOCKS[@]}}"; do
    tmux new-window -t "$TMUX_SESSION" -n "$MOCK" \\
        "cd '$WEBSITES_DIR/$MOCK' && npm run preview -- --host 0.0.0.0 --port $PORT; exec bash"
    PORT=$((PORT + 1))
done
sleep 5
echo "DEPLOY_DONE"
"""


def main():
    print("=== Snapshot 固化验证 ===")
    print(f"template : {TEMPLATE}")
    print(f"repo     : {REPO_URL}")

    sbx = None
    try:
        # ── 1. 建材实例 ──────────────────────────────────────────────
        _section("1. Sandbox.create (建材实例)")
        try:
            sbx = Sandbox.create(
                template=TEMPLATE, timeout=BOOTSTRAP_TIMEOUT,
                metadata={"pool": "snapshot_test", "stage": "bootstrap"},
            )
            _cleanup_ids.append(sbx.sandbox_id)
            _ok(f"sandbox_id={sbx.sandbox_id}")
        except Exception as e:
            _fail("建材实例创建失败，无法继续", e)
            return

        # ── 1.5 系统依赖检查 + 安装 ──────────────────────────────────
        # 裸模板 sdt-2nn0tz4x 实测：有 node（apt 装的，无 npm），没有 git、没有 tmux。
        # 普通用户无 sudo 密码但 `sudo -n` / user="root" 可直接跑 root 命令。
        _section("1.5 安装系统依赖 (git / tmux / npm)")
        try:
            info = _run(sbx, "whoami && echo HOME=$HOME && node --version", timeout=30)
            print("  " + info.stdout.replace("\n", "\n  "))
        except Exception as e:
            _fail("基础环境检查失败", e)

        t0 = time.time()
        try:
            apt_res = _run(
                sbx,
                "apt-get update -qq && "
                "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git tmux npm",
                timeout=300, user="root",
            )
            _ok(f"apt-get install 耗时 {time.time()-t0:.1f}s")
        except Exception as e:
            _fail(f"apt-get install 失败（耗时 {time.time()-t0:.1f}s），后续步骤大概率会连锁失败", e)

        try:
            ver = _run(sbx, "git --version && tmux -V && npm --version", timeout=20)
            print("  " + ver.stdout.replace("\n", "\n  "))
        except Exception as e:
            _fail("依赖版本检查失败——git/tmux/npm 可能没装成功", e)
            return

        # ── 2. git clone ─────────────────────────────────────────────
        _section("2. git clone CUA-Gym-Hub")
        t0 = time.time()
        try:
            clone_res = _run(sbx, f'git clone --depth 1 {REPO_URL} "$HOME/CUA-Gym-Hub"', timeout=300)
            clone_time = time.time() - t0
            if clone_res.exit_code == 0:
                _ok(f"clone 耗时 {clone_time:.1f}s")
            else:
                _fail(f"clone exit_code={clone_res.exit_code}\nstderr={clone_res.stderr[-2000:]}")
                return
        except Exception as e:
            _fail("clone 失败/超时", e)
            return

        # ── 3. 31-app 白名单部署 ─────────────────────────────────────
        _section("3. 31-app 白名单部署（install + build + tmux 起 vite preview）")
        sbx.files.write("deploy_31.sh", DEPLOY_SCRIPT)
        _run(sbx, "chmod +x deploy_31.sh", timeout=10)
        t0 = time.time()
        try:
            deploy_res = _run(sbx, "./deploy_31.sh", timeout=1800)
            deploy_time = time.time() - t0
            print("  --- stdout tail ---")
            print("  " + deploy_res.stdout[-4000:].replace("\n", "\n  "))
            if deploy_res.exit_code == 0 and "DEPLOY_DONE" in deploy_res.stdout:
                _ok(f"部署脚本耗时 {deploy_time:.1f}s")
            else:
                _fail(f"部署脚本 exit_code={deploy_res.exit_code}（继续往下检查端口，可能部分 app 失败）")
        except Exception as e:
            _fail(f"部署脚本执行异常/超时（耗时 {time.time()-t0:.1f}s）", e)

        # ── 4. 验证端口 ──────────────────────────────────────────────
        _section("4. 验证 31 个端口（建材实例）")
        time.sleep(3)
        _check_ports(sbx, "建材实例")

        # ── 5. create_snapshot ───────────────────────────────────────
        _section("5. sbx.create_snapshot()")
        snapshot_id = None
        try:
            t0 = time.time()
            snapshot_info = sbx.create_snapshot(name=SNAPSHOT_NAME)
            snap_time = time.time() - t0
            print(f"  raw snapshot_info = {snapshot_info!r}")
            snapshot_id = getattr(snapshot_info, "snapshot_id", None) \
                or getattr(snapshot_info, "template_id", None) \
                or getattr(snapshot_info, "id", None)
            if snapshot_id:
                _ok(f"snapshot_id={snapshot_id}  耗时 {snap_time:.1f}s")
            else:
                _fail(f"拿到返回对象但没找到 snapshot_id 字段，字段列表: {dir(snapshot_info)}")
        except Exception as e:
            _fail("create_snapshot 失败", e)

        if not snapshot_id:
            print("\n  无 snapshot_id，跳过后续步骤 6/7。")
        else:
            # ── 6. 从快照新建沙箱 ────────────────────────────────────
            _section("6. 从 snapshot_id 新建沙箱，验证冷启动")
            sbx2 = None
            try:
                t0 = time.time()
                sbx2 = Sandbox.create(
                    template=snapshot_id, timeout=SNAPSHOT_SANDBOX_TIMEOUT,
                    metadata={"pool": "snapshot_test", "stage": "from_snapshot"},
                )
                boot_time = time.time() - t0
                _cleanup_ids.append(sbx2.sandbox_id)
                _ok(f"从快照新建耗时 {boot_time:.1f}s  sandbox_id={sbx2.sandbox_id}")

                fs_check = _run(
                    sbx2,
                    'ls "$HOME/CUA-Gym-Hub/websites" 2>&1 | wc -l; '
                    'tmux list-sessions 2>&1; '
                    "ps aux | grep -c '[v]ite preview'",
                    timeout=30,
                )
                print("  文件系统/进程检查:\n  " + fs_check.stdout.replace("\n", "\n  "))

                ok, total = _check_ports(sbx2, "快照新建实例")
                if ok == 31:
                    _ok("31/31 端口原样可用 —— 进程状态被快照保留，无需任何手动重启")
                elif ok > 0:
                    _fail(f"仅 {ok}/{total} 端口可用，进程可能未被完整保留，需要退化到'快照+自启动脚本'方案")
                else:
                    _fail("0 端口可用，snapshot 可能只保留了文件系统，进程需要重新拉起")
            except Exception as e:
                _fail("从快照新建沙箱失败", e)

            # ── 7. kill 建材实例，验证快照持久性 ─────────────────────
            _section("7. kill 建材实例，验证快照是否仍然可用")
            try:
                Sandbox.kill(sbx.sandbox_id)
                _cleanup_ids.remove(sbx.sandbox_id)
                _ok(f"已 kill 建材实例 {sbx.sandbox_id}")
                sbx = None
            except Exception as e:
                _fail("kill 建材实例失败", e)

            try:
                sbx3 = Sandbox.create(
                    template=snapshot_id, timeout=120,
                    metadata={"pool": "snapshot_test", "stage": "post_kill_verify"},
                )
                _cleanup_ids.append(sbx3.sandbox_id)
                _ok(f"建材实例销毁后，仍能从 snapshot_id 新建沙箱：{sbx3.sandbox_id}（快照持久化确认）")
            except Exception as e:
                _fail("建材实例销毁后，从 snapshot_id 新建失败 —— 快照可能依赖原实例存活", e)

    finally:
        _section("cleanup")
        for sid in _cleanup_ids:
            try:
                Sandbox.kill(sid)
                print(f"  killed  {sid}")
            except Exception as e:
                print(f"  could not kill {sid}: {e}")

    print("\n=== done ===")


if __name__ == "__main__":
    main()
