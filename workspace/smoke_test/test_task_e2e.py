#!/usr/bin/env python3
"""
端到端验证：pool.acquire() 拿到的实例，能否直接跑真实 task 的 initial_setup.py / reward.py。

核心验证点——task 脚本里硬编码的 `http://host.docker.internal:8012` 这类 URL，
在配好 /etc/hosts 映射 + 31 个 app 就绪之后，**不需要任何 sed 占位符替换**就能跑通。
（对比 gym/utils/ags_sandbox_env.py 里 download_task() 的逐任务 sed 方案。）

流程：
  1. pool.acquire()  —— 首次会自动部署 31 个 app（~176s），复用则秒级
  2. 上传本地 tasks_web/<task_id>/ 的 initial_setup.py + reward.py（原样，不改 URL）
  3. 跑 initial_setup.py，确认写出 /tmp/task_web_sid
  4. 跑 reward.py，确认能解析出 REWARD 分数（初始状态下预期为 0）
  5. pool.release(pause=False) 归还实例

Usage:
    python workspace/smoke_test/test_task_e2e.py [task_id]
"""
import re
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE))

from e2b import Sandbox
from sandbox.pool import SandboxPool

TASKS_ROOT = Path("/data/workspace/tasks_web")
DEFAULT_TASK = "3a1d4820-2387-5e6d-b647-43ec6c3d4e52"  # instacart_mock, 单 app, port 8012
TEMPLATE = "sdt-hojglb51"
REGISTRY = Path(__file__).parent / "_e2e_registry.json"
REMOTE_DIR = "/tmp/task_e2e"


def _section(title):
    print(f"\n{'─' * 64}")
    print(f"  {title}")
    print("─" * 64)


def main():
    task_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TASK
    task_dir = TASKS_ROOT / task_id
    if not (task_dir / "initial_setup.py").exists():
        print(f"[FAIL] 找不到 task: {task_dir}")
        return 1

    setup_src = (task_dir / "initial_setup.py").read_text()
    reward_src = (task_dir / "reward.py").read_text()
    urls = sorted(set(re.findall(r"https?://host\.docker\.internal:\d+", setup_src)))

    print("=== 真实 task 端到端验证 ===")
    print(f"task_id : {task_id}")
    print(f"硬编码 URL: {urls}  ← 不做任何替换，直接跑")

    pool = SandboxPool(REGISTRY, template=TEMPLATE, max_size=1, timeout=3600)
    cfg = sbx = None
    try:
        # ── 1. acquire（含自动部署） ──────────────────────────────────────
        _section("1. pool.acquire()（首次会自动部署 31 个 app）")
        t0 = time.time()
        cfg, sbx = pool.acquire(block=False)
        print(f"  {cfg.sandbox_id}  apps_ready={cfg.apps_ready}  耗时 {time.time()-t0:.0f}s")
        if not cfg.apps_ready:
            print("  [FAIL] apps 未就绪，acquire 本应 kill 掉坏实例")
            return 1
        print(f"  [PASS] 31 个 app 已就绪")

        # ── 2. 上传 task 脚本（原样，不改 URL） ───────────────────────────
        _section("2. 上传 initial_setup.py / reward.py（未做 URL 替换）")
        sbx.commands.run(f"mkdir -p {REMOTE_DIR}", timeout=15)
        sbx.files.write(f"{REMOTE_DIR}/initial_setup.py", setup_src)
        sbx.files.write(f"{REMOTE_DIR}/reward.py", reward_src)
        sbx.commands.run("pip install -q requests 2>/dev/null || true", timeout=120)
        print(f"  已上传到 {REMOTE_DIR}")

        # ── 3. 跑 initial_setup.py ────────────────────────────────────────
        _section("3. python3 initial_setup.py")
        t0 = time.time()
        r = sbx.commands.run(
            f"cd {REMOTE_DIR} && python3 initial_setup.py 2>&1 || true", timeout=180)
        out = (r.stdout or "") + (r.stderr or "")
        print("  --- 输出（末尾 15 行） ---")
        for line in out.strip().splitlines()[-15:]:
            print(f"  {line}")

        sid_r = sbx.commands.run("cat /tmp/task_web_sid 2>/dev/null || echo NOSID", timeout=15)
        sid = sid_r.stdout.strip()
        if sid and sid != "NOSID":
            print(f"  [PASS] setup 成功，sid={sid}  ({time.time()-t0:.0f}s)")
        else:
            print(f"  [FAIL] 未生成 /tmp/task_web_sid")
            return 1

        # launch_gui(google-chrome ...) 在无 GUI 的沙箱里会失败，但那是 M1 要解决的
        # 浏览器问题，与"URL 能否解析"无关——只要状态注入成功（sid 已写出）即达成本次验证目标。
        if "GUI_READY" not in out:
            print("  [注] launch_gui 未成功（沙箱无 google-chrome），不影响状态注入，M1 再处理")

        # ── 4. 跑 reward.py ───────────────────────────────────────────────
        _section("4. python3 reward.py")
        r = sbx.commands.run(f"cd {REMOTE_DIR} && python3 reward.py 2>&1 || true", timeout=120)
        rout = (r.stdout or "") + (r.stderr or "")
        print("  --- 输出（末尾 10 行） ---")
        for line in rout.strip().splitlines()[-10:]:
            print(f"  {line}")
        m = re.search(r"REWARD:\s*([\d.]+)", rout)
        if m:
            print(f"  [PASS] 解析到 REWARD={m.group(1)}（初始状态下预期 0.0）")
        else:
            print("  [FAIL] 未能解析 REWARD")
            return 1

        _section("结论")
        print("  task 脚本里硬编码的 host.docker.internal:800X 直接可用，")
        print("  无需 sed 占位符替换 —— /etc/hosts 映射方案成立。")
        return 0

    finally:
        if cfg is not None:
            _section("cleanup")
            try:
                pool.kill(cfg.sandbox_id)
                print(f"  killed {cfg.sandbox_id}")
            except Exception as e:
                print(f"  kill 失败: {e}")
        if REGISTRY.exists():
            REGISTRY.unlink()


if __name__ == "__main__":
    sys.exit(main())
