#!/usr/bin/env python3
"""
Volume 持久化验证 —— 测试 e2b Volume 能否解决两个阻塞点：
  1. 根磁盘不足（1.1GB overlay2）
  2. create_snapshot 不可用

流程：
  A. 创建 Volume
  B. 建材实例：挂载 volume -> clone -> 31-app install+build -> vite preview 验证
  C. 冷启动实例：挂载同一 volume，验证文件/进程/端口是否无需重新安装
  D. 并发实例：两个沙箱同时挂载同一 volume（验证是否支持多挂载）
  E. 清理（保留 volume 供下一次直接复用测试）
"""
import sys, time, traceback
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE))

from e2b import Sandbox
from e2b.volume.volume_sync import Volume

TEMPLATE = "sdt-2nn0tz4x"
REPO_URL = "https://github.com/xlang-ai/CUA-Gym-Hub"
VOLUME_NAME = "cua-gym-hub-31apps-v1"
MOUNT_PATH = "/data/cua-hub"
BOOTSTRAP_TIMEOUT = 3600
SANDBOX_TIMEOUT = 600

MOCKS = [
    "asana", "discord", "docusign", "facebook", "github", "gitlab", "gmail",
    "google_calendar", "google_docs", "google_drive", "google_sheets",
    "hubspot", "instacart", "instagram", "jira", "linkedin",
    "microsoft_teams", "monday", "notion", "outlook_web", "pinterest",
    "postman", "reddit", "salesforce", "shopify_admin", "slack",
    "stripe_dashboard", "trello", "twitter", "uber_eats", "wechat",
]

_cleanup_sandbox_ids: list[str] = []
_volume_id: str | None = None


def _section(title):
    print(f"\n{'─'*70}\n  {title}\n{'─'*70}")

def _ok(msg=""): print(f"  [PASS]" + (f"  {msg}" if msg else ""))
def _fail(msg, exc=None):
    print(f"  [FAIL]  {msg}")
    if exc: traceback.print_exc()

def _run(sbx, cmd, timeout=120, **kw):
    return sbx.commands.run(cmd, timeout=timeout, **kw)

def _check_ports(sbx, label):
    res = _run(sbx,
        "for p in $(seq 8000 8030); do "
        "code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 http://127.0.0.1:$p/); "
        "echo \"$p:$code\"; done", timeout=120)
    lines = [l for l in res.stdout.strip().splitlines() if l]
    ok = sum(1 for l in lines if l.endswith(":200"))
    print(f"  [{label}] {ok}/{len(lines)} 端口返回 200")
    bad = [l for l in lines if not l.endswith(":200")]
    if bad: print(f"  未通过: {bad[:6]}{'...' if len(bad)>6 else ''}")
    return ok

def _install_deps(sbx):
    t0 = time.time()
    r = _run(sbx,
        "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git tmux npm",
        timeout=300, user="root")
    _ok(f"apt-get 耗时 {time.time()-t0:.1f}s")
    ver = _run(sbx, "git --version && tmux -V && npm --version", timeout=20)
    print("  " + ver.stdout.replace("\n", "\n  "))
    return r


DEPLOY_SCRIPT = f"""#!/bin/bash
set -uo pipefail
WEBSITES_DIR="{MOUNT_PATH}/websites"
[ -s "$HOME/.nvm/nvm.sh" ] && . "$HOME/.nvm/nvm.sh"
TMUX_SESSION="cua-hub"
BASE_PORT=8000
MOCKS=({' '.join(m + '_mock' for m in MOCKS)})

echo "=== df before install ==="
df -h {MOUNT_PATH}

echo "Installing deps for ${{#MOCKS[@]}} apps..."
for MOCK in "${{MOCKS[@]}}"; do
    (cd "$WEBSITES_DIR/$MOCK" && npm install --silent) \
        && echo "  [OK] $MOCK" \
        || echo "  [INSTALL-ERR] $MOCK"
done
echo "Install phase done."

echo "=== df after install ==="
df -h {MOUNT_PATH} 2>/dev/null || df -h /

echo "Building ${{#MOCKS[@]}} apps in parallel..."
for MOCK in "${{MOCKS[@]}}"; do
    (cd "$WEBSITES_DIR/$MOCK" && npm run build --silent \
        > /tmp/build_$MOCK.log 2>&1 \
        && echo "  [OK] $MOCK" \
        || echo "  [BUILD-ERR] $MOCK") &
done
wait
echo "Build phase done."

echo "=== df after build ==="
df -h {MOUNT_PATH} 2>/dev/null || df -h /

tmux has-session -t "$TMUX_SESSION" 2>/dev/null && tmux kill-session -t "$TMUX_SESSION"
tmux new-session -d -s "$TMUX_SESSION" -n "_idle" "bash"
PORT=$BASE_PORT
for MOCK in "${{MOCKS[@]}}"; do
    tmux new-window -t "$TMUX_SESSION" -n "$MOCK" \
        "cd '$WEBSITES_DIR/$MOCK' && npm run preview -- --host 0.0.0.0 --port $PORT; exec bash"
    PORT=$((PORT + 1))
done
sleep 5
echo "DEPLOY_DONE"
"""

LAUNCH_SCRIPT = f"""#!/bin/bash
set -uo pipefail
WEBSITES_DIR="{MOUNT_PATH}/websites"
[ -s "$HOME/.nvm/nvm.sh" ] && . "$HOME/.nvm/nvm.sh"
TMUX_SESSION="cua-hub"
BASE_PORT=8000
MOCKS=({' '.join(m + '_mock' for m in MOCKS)})

tmux has-session -t "$TMUX_SESSION" 2>/dev/null && tmux kill-session -t "$TMUX_SESSION"
tmux new-session -d -s "$TMUX_SESSION" -n "_idle" "bash"
PORT=$BASE_PORT
for MOCK in "${{MOCKS[@]}}"; do
    tmux new-window -t "$TMUX_SESSION" -n "$MOCK" \
        "cd '$WEBSITES_DIR/$MOCK' && npm run preview -- --host 0.0.0.0 --port $PORT; exec bash"
    PORT=$((PORT + 1))
done
sleep 5
echo "LAUNCH_DONE"
"""


def main():
    global _volume_id
    print("=== Volume 持久化验证 ===")
    print(f"template  : {TEMPLATE}")
    print(f"repo      : {REPO_URL}")
    print(f"mount_path: {MOUNT_PATH}")

    # ── A. 创建 / 复用 Volume ─────────────────────────────────────────────
    _section("A. Volume.create / 列举已有 volume")
    vol = None
    try:
        existing = Volume.list()
        print(f"  现有 volumes: {[(v.name, v.volume_id) for v in existing]}")
        found = next((v for v in existing if v.name == VOLUME_NAME), None)
        if found:
            _volume_id = found.volume_id
            vol = Volume.connect(_volume_id)
            _ok(f"复用已有 volume  id={_volume_id}")
        else:
            vol = Volume.create(VOLUME_NAME)
            _volume_id = vol.volume_id
            _ok(f"新建 volume  id={_volume_id}  name={vol.name}")
    except Exception as e:
        _fail("Volume 创建/复用失败，无法继续", e)
        return

    # ── B. 建材实例：挂载 volume，clone+install+build ──────────────────────
    _section("B. 建材实例（clone + install + build）")
    sbx = None
    try:
        sbx = Sandbox.create(
            template=TEMPLATE, timeout=BOOTSTRAP_TIMEOUT,
            volume_mounts={MOUNT_PATH: vol},
            metadata={"stage": "bootstrap"},
        )
        _cleanup_sandbox_ids.append(sbx.sandbox_id)
        _ok(f"sandbox_id={sbx.sandbox_id}")
    except Exception as e:
        _fail("建材实例创建失败", e)
        return

    # 检查 volume 挂载点磁盘容量
    try:
        df = _run(sbx, f"df -h {MOUNT_PATH} && echo '---root---' && df -h /", timeout=15)
        print("  磁盘情况:\n  " + df.stdout.replace("\n", "\n  "))
    except Exception as e:
        _fail("df 检查失败", e)

    _install_deps(sbx)

    # clone 到 volume 挂载点
    clone_target = f"{MOUNT_PATH}"
    t0 = time.time()
    try:
        cr = _run(sbx,
            f'[ -d "{MOUNT_PATH}/websites" ] && echo "ALREADY_CLONED" || '
            f'git clone --depth 1 {REPO_URL} /tmp/cua_clone '
            f'&& mv /tmp/cua_clone/* {MOUNT_PATH}/ '
            f'&& mv /tmp/cua_clone/.[^.]* {MOUNT_PATH}/ 2>/dev/null || true '
            f'&& echo "CLONE_DONE"',
            timeout=300)
        print(f"  {cr.stdout.strip()[-200:]}")
        _ok(f"clone/check 耗时 {time.time()-t0:.1f}s")
    except Exception as e:
        _fail("clone 失败", e)
        return

    # 直接 clone 到 MOUNT_PATH 更干净
    try:
        cr2 = _run(sbx,
            f'ls {MOUNT_PATH}/websites | head -5',
            timeout=15)
        print(f"  websites 目录: {cr2.stdout.strip()}")
    except Exception:
        # 上面的 mv 方式可能失败，改用直接 clone 到 MOUNT_PATH
        try:
            _run(sbx, f'rm -rf {MOUNT_PATH}/*', timeout=30, user="root")
            cr3 = _run(sbx,
                f'git clone --depth 1 {REPO_URL} {MOUNT_PATH}',
                timeout=300)
            _ok(f"二次 clone 到 {MOUNT_PATH}")
        except Exception as e:
            _fail("二次 clone 失败", e)
            return

    # 部署脚本
    t0 = time.time()
    try:
        sbx.files.write("/tmp/deploy_31.sh", DEPLOY_SCRIPT)
        _run(sbx, "chmod +x /tmp/deploy_31.sh", timeout=10)
        deploy_res = _run(sbx, "/tmp/deploy_31.sh", timeout=2400)
        elapsed = time.time() - t0
        tail = deploy_res.stdout[-1500:]
        print(f"  --- stdout tail ---\n  " + tail.replace("\n", "\n  "))
        _ok(f"部署脚本耗时 {elapsed:.1f}s")
    except Exception as e:
        _fail("部署脚本失败", e)
        return

    ok_b = _check_ports(sbx, "建材实例")

    # ── C. 冷启动实例：挂载同一 volume，直接 launch ───────────────────────
    _section("C. 冷启动实例（不重新 install/build，直接挂载 launch）")
    sbx2 = None
    t0 = time.time()
    try:
        sbx2 = Sandbox.create(
            template=TEMPLATE, timeout=SANDBOX_TIMEOUT,
            volume_mounts={MOUNT_PATH: vol},
            metadata={"stage": "cold-start"},
        )
        _cleanup_sandbox_ids.append(sbx2.sandbox_id)
        _ok(f"sandbox_id={sbx2.sandbox_id}  创建耗时 {time.time()-t0:.1f}s")
    except Exception as e:
        _fail("冷启动实例创建失败", e)
        sbx2 = None

    if sbx2:
        # 需要 tmux/npm 才能起 vite preview
        _install_deps(sbx2)
        try:
            sbx2.files.write("/tmp/launch_31.sh", LAUNCH_SCRIPT)
            _run(sbx2, "chmod +x /tmp/launch_31.sh", timeout=10)
            t0 = time.time()
            launch_res = _run(sbx2, "/tmp/launch_31.sh", timeout=120)
            print(f"  launch 耗时 {time.time()-t0:.1f}s")
            print(f"  {launch_res.stdout.strip()[-300:]}")
        except Exception as e:
            _fail("launch 脚本失败", e)

        ok_c = _check_ports(sbx2, "冷启动实例")
        print(f"\n  对比: 建材实例={ok_b}/31  冷启动实例={ok_c}/31")

    # ── D. kill 建材实例，确认 volume 内容仍在 ──────────────────────────────
    _section("D. kill 建材实例后，验证 volume 内容持久")
    try:
        sbx.kill()
        _cleanup_sandbox_ids.remove(sbx.sandbox_id)
        sbx = None
        _ok("建材实例已 kill")
    except Exception as e:
        _fail("kill 失败", e)

    if sbx2:
        try:
            ls = _run(sbx2, f"ls {MOUNT_PATH}/websites | wc -l", timeout=15)
            _ok(f"冷启动实例上 volume 仍有 {ls.stdout.strip()} 个 websites 目录")
        except Exception as e:
            _fail("kill 后验证失败", e)

    # ── 总结 ──────────────────────────────────────────────────────────────
    _section("总结")
    print(f"  volume_id = {_volume_id}")
    print(f"  volume_name = {VOLUME_NAME}")
    print(f"  建材实例端口通过: {ok_b}/31")
    if sbx2:
        print(f"  冷启动实例端口通过: {ok_c}/31")
    print()
    print("  若冷启动实例端口全部通过 → Volume 方案可行，可固化为 pool 的 bootstrap 路径")
    print("  若部分通过 → 检查 vite preview 是否绑定了 node_modules 路径问题")

    # ── cleanup ───────────────────────────────────────────────────────────
    _section("cleanup")
    for sid in list(_cleanup_sandbox_ids):
        try:
            Sandbox.connect(sid).kill()
            print(f"  killed  {sid}")
        except Exception:
            print(f"  skip    {sid}")
    print(f"\n  volume {_volume_id} 保留（供下次直接复用测试）")
    print("\n=== done ===")


if __name__ == "__main__":
    main()
