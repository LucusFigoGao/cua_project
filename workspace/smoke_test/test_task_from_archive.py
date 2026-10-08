#!/usr/bin/env python3
"""
端到端验证：从归档解包出来的任务（占位符已替换）能否在实例上真正跑通。

与旧的 test_task_e2e.py 的区别：
  - 任务来自 workspace/tasks_data/（unpack_tasks.py 从 gym/bench 的归档解出），
    不再读 /data/workspace/tasks_web
  - **不 kill 实例**，结束 release(pause=False) 让它回到 idle 继续复用
  - 额外验证 launch_gui 经 google-chrome shim 真的在常驻 chromium 里开了页面
    （查 CDP 9222 的 target 列表里有没有对应的 ?sid=）

验证链路：
  1. pool.acquire        —— 复用已部署好 31 个 app 的实例
  2. 挑一个已推送的任务   —— 默认从 /tmp/cua_tasks 的清单里取
  3. initial_setup.py    —— 应写出 /tmp/task_web_sid
  4. CDP target 检查      —— 页面 URL 带该 sid，证明 shim + launch_gui 生效
  5. reward.py           —— 应解析出 REWARD（初始状态预期 0.0）
  6. pool.release        —— 实例保持 running

Usage:
    python workspace/smoke_test/test_task_from_archive.py [task_id]
"""
import json
import os
import re
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE))

os.environ.setdefault("NO_PROXY", "*.tencentags.com,*.woa.com,*.tencentyun.com")

from sandbox.pool import SandboxPool
from tasks import catalog, push

TEMPLATE = "sdt-hojglb51"
TIMEOUT = 86400
REGISTRY = WORKSPACE / "configs" / "sandbox_pool.json"
REMOTE_ROOT = push.REMOTE_ROOT

_passed: list[str] = []
_failed: list[str] = []


def _section(title: str):
    print(f"\n{'─' * 66}")
    print(f"  {title}")
    print("─" * 66)


def _ok(msg: str):
    _passed.append(msg)
    print(f"  [PASS] {msg}")


def _fail(msg: str):
    _failed.append(msg)
    print(f"  [FAIL] {msg}")


def main() -> int:
    want = sys.argv[1] if len(sys.argv) > 1 else None

    local = {t.task_id: t for t in catalog.load_tasks()}
    if not local:
        print(f"[FAIL] {catalog.DATA_DIR} 下没有任务，先跑 unpack_tasks.py")
        return 1

    print("=== 归档任务端到端验证 ===")
    print(f"本地任务库 : {catalog.DATA_DIR}（{len(local)} 个任务）")

    pool = SandboxPool(REGISTRY, template=TEMPLATE, max_size=12, timeout=TIMEOUT)
    pool.reconcile()

    _section("1. pool.acquire（复用已部署实例）")
    t0 = time.time()
    cfg, sbx = pool.acquire()
    print(f"  sandbox_id = {cfg.sandbox_id}")
    print(f"  apps_ready = {cfg.apps_ready}   耗时 {time.time() - t0:.0f}s")
    if cfg.apps_ready:
        _ok("31 个 app 已就绪")
    else:
        _fail("apps 未就绪")

    try:
        # ── 2. 选一个实例上已有的任务 ────────────────────────────────────────
        _section("2. 选取任务")
        remote_ids = push.list_remote_tasks(sbx, REMOTE_ROOT)
        if not remote_ids:
            _fail(f"{REMOTE_ROOT} 下没有任务，先跑 push_tasks.py")
            return 1
        print(f"  实例上有 {len(remote_ids)} 个任务")

        candidates = [tid for tid in remote_ids if tid in local]
        if want:
            if want not in remote_ids:
                _fail(f"指定的 {want} 不在实例上")
                return 1
            task_id = want
        else:
            task_id = sorted(candidates)[0]
        spec = local.get(task_id)
        print(f"  task_id  = {task_id}")
        print(f"  app_type = {spec.app_type}  port = {spec.port}")
        print(f"  指令     : {spec.instruction[:90]}")

        remote_dir = f"{REMOTE_ROOT}/{task_id}"
        # 确认推上去的脚本里 URL 已替换（不是占位符、也不是别的 app 的端口）。
        # 不能只认 BASE_URL：跨 app 任务用的是 TRELLO_URL / SLACK_URL / GITHUB_URL
        # 这类分别命名的变量，所以直接查脚本里引用了哪些 host.docker.internal 端口。
        r = sbx.commands.run(
            f"grep -ohE 'host\\.docker\\.internal:[0-9]+' "
            f"{remote_dir}/initial_setup.py {remote_dir}/reward.py | sort -u || true",
            timeout=30)
        refs = sorted({l.strip() for l in (r.stdout or "").splitlines() if l.strip()})
        print(f"  远端引用的地址: {refs}")
        r2 = sbx.commands.run(
            f"grep -c '__CUA_GYM_' {remote_dir}/initial_setup.py {remote_dir}/reward.py "
            f"2>/dev/null | grep -v ':0' || true", timeout=30)
        leftover = (r2.stdout or "").strip()

        if f"{'host.docker.internal'}:{spec.port}" in refs:
            extra = [x for x in refs if not x.endswith(f":{spec.port}")]
            note = f"，另引用 {len(extra)} 个其它 app（跨 app 任务）" if extra else ""
            _ok(f"URL 已替换为本实例端口 {spec.port}{note}")
        else:
            _fail(f"脚本未引用 host.docker.internal:{spec.port}，实际 {refs}")
        if leftover:
            _fail(f"脚本里仍有未替换的占位符: {leftover}")
        else:
            _ok("无残留 __CUA_GYM_* 占位符")

        # ── 3. initial_setup.py ─────────────────────────────────────────────
        _section("3. python3 initial_setup.py")
        sbx.commands.run("rm -f /tmp/task_web_sid", timeout=30)
        t0 = time.time()
        r = sbx.commands.run(
            f"cd {remote_dir} && DISPLAY=:1 python3 initial_setup.py 2>&1 || true",
            timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        print("  --- 输出（末尾 12 行）---")
        for line in out.strip().splitlines()[-12:]:
            print(f"  {line}")

        sid_r = sbx.commands.run(
            "cat /tmp/task_web_sid 2>/dev/null || echo NOSID", timeout=30)
        sid = (sid_r.stdout or "").strip()
        if sid and sid != "NOSID":
            _ok(f"状态注入成功，sid={sid}  ({time.time() - t0:.0f}s)")
        else:
            _fail("未生成 /tmp/task_web_sid")
            return _summary()

        # ── 4. launch_gui 是否真的开了页面（shim 验证）────────────────────────
        _section("4. launch_gui → CDP target 检查")
        if "GUI_READY" in out:
            _ok("initial_setup.py 打印了 GUI_READY")
        else:
            print("  [注] 输出里没有 GUI_READY")

        target_url = None
        for _ in range(6):
            tr = sbx.commands.run(
                "curl -s -m 3 http://127.0.0.1:9222/json/list || true", timeout=30)
            urls = re.findall(r'"url":\s*"([^"]+)"', tr.stdout or "")
            target_url = next((u for u in urls if sid in u), None)
            if target_url:
                break
            sbx.commands.run("sleep 2", timeout=10)

        if target_url:
            _ok(f"CDP 里找到该任务页面: {target_url}")
            print("       → google-chrome shim + 常驻 chromium 工作正常")
        else:
            _fail("CDP target 列表里没有带该 sid 的页面")

        # ── 5. reward.py ────────────────────────────────────────────────────
        _section("5. python3 reward.py")
        r = sbx.commands.run(
            f"cd {remote_dir} && python3 reward.py 2>&1 || true", timeout=180)
        rout = (r.stdout or "") + (r.stderr or "")
        print("  --- 输出（末尾 10 行）---")
        for line in rout.strip().splitlines()[-10:]:
            print(f"  {line}")
        m = re.search(r"REWARD:\s*([\d.]+)", rout)
        if m:
            # 多数任务未操作就是 0.0，但有些 reward.py 含"不该动的东西没被动过"这类
            # 反向检查项（例如某 slack 任务的 Component 3 占 0.20 分），什么都不做
            # 反而先拿到分。所以这里只断言能解析出分数，不断言一定等于 0。
            _ok(f"解析到 REWARD={m.group(1)}（未操作，通常为 0.0；含反向检查项的任务会非 0）")
        else:
            _fail("未能解析 REWARD")

        # ── 6. 清理本次开的 tab，保持实例干净 ─────────────────────────────────
        if target_url:
            tr = sbx.commands.run(
                "curl -s -m 3 http://127.0.0.1:9222/json/list || true", timeout=30)
            blocks = (tr.stdout or "").split("{")
            for b in blocks:
                if sid in b:
                    tid_m = re.search(r'"id":\s*"(\w+)"', b)
                    if tid_m:
                        sbx.commands.run(
                            f"curl -s -m 3 http://127.0.0.1:9222/json/close/{tid_m.group(1)}",
                            timeout=20)

        return _summary()

    finally:
        _section("release（不 kill）")
        pool.release(cfg.sandbox_id, sbx=sbx, pause=False)
        final = pool._instances.get(cfg.sandbox_id)
        print(f"  {cfg.sandbox_id}  status={final.status if final else '?'}  实例保持 running")


def _summary() -> int:
    _section("结论")
    print(f"  通过 {len(_passed)} 项，失败 {len(_failed)} 项")
    for f in _failed:
        print(f"    [FAIL] {f}")
    if not _failed:
        print("\n  归档 → 解包替换 → 推送 → setup → reward 全链路打通。")
    return 0 if not _failed else 1


if __name__ == "__main__":
    sys.exit(main())
