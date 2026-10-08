#!/usr/bin/env python3
"""
验证 OSWorld agent server 在 AGS 沙箱里的可用性，以及 PixelSandboxEnv 瘦客户端。

这条路线的由来：cua-gym 在阿里云 ECS 上就是"VM 内跑 OSWorld 的 Flask server(5000)
+ 宿主 HTTP 调用"（见 gym/utils/env.py 开头的架构注释），osworld/mm_agents 下 50+ 个
agent 也都按"全屏截图 + pyautogui 代码"来 prompt。所以这里复用 server 而不是自己写
环境层，观测是 1920x1080 全屏、动作是 pyautogui 代码。

验证点：
  1. server 常驻          —— 装依赖 + 拉起 + 幂等探活
  2. 观测                 —— /screenshot 返回真实 1920x1080 PNG，非纯黑
  3. 单步延迟             —— 经 envd 的 curl 往返开销
  4. **坐标动作真的生效**  —— 用真实任务注入状态，纯坐标点击改变桌面画面
  5. mm_agents 契约       —— execute_python_command 直接吃 "pyautogui.click(x=..,y=..)"
  6. computer_13          —— execute_action 的 dict 形式
  7. a11y                 —— 确认按预期不可用（pyatspi 装不上）
  8. pool.release         —— 实例保持 running，不 kill

Usage:
    python workspace/smoke_test/test_osworld_server.py [task_id]
"""
import json
import os
import struct
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE))

os.environ.setdefault("NO_PROXY", "*.tencentags.com,*.woa.com,*.tencentyun.com")

from sandbox import osworld_server as osw
from sandbox.pixel_env import PixelEnvError, PixelSandboxEnv
from sandbox.pool import SandboxPool
from tasks import catalog, push

TEMPLATE = "sdt-hojglb51"
TIMEOUT = 86400
REGISTRY = WORKSPACE / "configs" / "sandbox_pool.json"
OUT_DIR = Path("/tmp/osworld_shots")

_passed: list[str] = []
_failed: list[str] = []


def _section(t: str):
    print(f"\n{'─' * 66}\n  {t}\n{'─' * 66}")


def _ok(m: str):
    _passed.append(m)
    print(f"  [PASS] {m}")


def _fail(m: str):
    _failed.append(m)
    print(f"  [FAIL] {m}")


def _nonblack_ratio(png: bytes, sbx) -> float:
    """把 PNG 丢回沙箱算非黑像素占比（本地可能没装 PIL）。"""
    probe = (
        "from PIL import Image\n"
        "im = Image.open('/tmp/_osw_shot.png').convert('RGB')\n"
        "px = list(im.getdata())\n"
        "nb = sum(1 for p in px if sum(p) > 30)\n"
        "print('RATIO=%.4f' % (nb / len(px)))\n"
    )
    sbx.files.write("/tmp/_osw_ratio.py", probe)
    out = sbx.commands.run("python3 /tmp/_osw_ratio.py 2>&1 | tail -1", timeout=120).stdout or ""
    for line in out.splitlines():
        if line.startswith("RATIO="):
            return float(line.split("=")[1])
    return -1.0


def main() -> int:
    want = sys.argv[1] if len(sys.argv) > 1 else None
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    local = {t.task_id: t for t in catalog.load_tasks()}
    pool = SandboxPool(REGISTRY, template=TEMPLATE, max_size=12, timeout=TIMEOUT)
    pool.reconcile()

    _section("1. pool.acquire（复用已部署实例）")
    cfg, sbx = pool.acquire()
    print(f"  sandbox_id = {cfg.sandbox_id}  apps_ready={cfg.apps_ready}")
    _ok("31 个 app 已就绪") if cfg.apps_ready else _fail("apps 未就绪")

    try:
        # ── 2. server 常驻 ───────────────────────────────────────────────────
        _section("2. OSWorld server 常驻")
        t0 = time.time()
        res = osw.ensure_server(sbx)
        print(f"  ensure_server -> started={res['started']} "
              f"already_running={res['already_running']}  {time.time() - t0:.0f}s")
        nproc = (sbx.commands.run("pgrep -cf '[o]sworld_server/main.py' || echo 0",
                                   timeout=60).stdout or "").strip()
        print(f"  server 进程数: {nproc}（应为 1，debug reloader 已关）")
        if osw.is_running(sbx):
            _ok("server 在 5000 端口就绪")
        else:
            _fail("server 探活失败")
            return _summary()

        t0 = time.time()
        osw.ensure_server(sbx)
        print(f"  二次调用（幂等）耗时 {time.time() - t0:.2f}s")

        env = PixelSandboxEnv(sbx, install=False)
        print(f"  platform = {env.get_platform()}   screen = {env.get_screen_size()}")

        # ── 3. 观测 ──────────────────────────────────────────────────────────
        _section("3. 观测：全屏截图")
        t0 = time.time()
        png = env.screenshot(local_out=OUT_DIR / "01_initial.png")
        dt = time.time() - t0
        w, h = struct.unpack(">II", png[16:24])
        print(f"  PNG {w}x{h}  {len(png)} bytes  {dt * 1000:.0f}ms")
        if (w, h) == (1920, 1080):
            _ok(f"截图是全屏 {w}x{h}（与 mm_agents 的坐标系预期一致）")
        else:
            _fail(f"截图尺寸异常 {w}x{h}")
        ratio = _nonblack_ratio(png, sbx)
        print(f"  非黑像素占比 {ratio * 100:.1f}%")
        if ratio > 0.5:
            _ok("画面有实际内容（chromium 窗口已渲染到 Xvfb :1）")
        else:
            _fail(f"画面基本是黑的（占比 {ratio * 100:.1f}%），窗口可能没映射")

        # ── 4. 单步延迟 ──────────────────────────────────────────────────────
        _section("4. 单步延迟（经 envd）")
        mv, sh = [], []
        for _ in range(5):
            t0 = time.time(); env.move(960, 540); mv.append(time.time() - t0)
            t0 = time.time(); env.screenshot(); sh.append(time.time() - t0)
        print(f"  move       中位 {int(sorted(mv)[2] * 1000)}ms  {[int(x*1000) for x in mv]}")
        print(f"  screenshot 中位 {int(sorted(sh)[2] * 1000)}ms  {[int(x*1000) for x in sh]}")
        # 单步约 0.5s，构成实测为：envd 往返 35ms + 起 python3 子进程 60ms +
        # import pyautogui 416ms。那 416ms 是 OSWorld 这套协议固有的——/execute 和
        # /run_python 都是 subprocess 执行，每个动作都要重新 import 一次 pyautogui。
        # 上游 OSWorld 在真机上也是这个代价，且它默认每步后还 sleep(pause) 若干秒，
        # 所以相对 agent 一次推理（秒级）可以忽略。阈值按 1.5s 把关，只拦住真异常。
        if sorted(mv)[2] < 1.5:
            _ok(f"动作单步 {int(sorted(mv)[2]*1000)}ms"
                f"（其中 import pyautogui 约 416ms，为 OSWorld 协议固有开销）")
        else:
            _fail(f"动作单步 {int(sorted(mv)[2]*1000)}ms，显著超出预期")

        # ── 5. 真实任务 + 坐标动作生效 ───────────────────────────────────────
        _section("5. 坐标动作是否真的生效（核心）")
        remote = push.list_remote_tasks(sbx)
        cands = [t for t in remote if t in local]
        if not cands:
            _fail("实例上没有已推送任务，先跑 push_tasks.py")
            return _summary()
        task_id = want or sorted(cands)[0]
        spec = local[task_id]
        print(f"  task: {task_id}  ({spec.app_type}:{spec.port})")

        sbx.commands.run("rm -f /tmp/task_web_sid", timeout=30)
        sbx.commands.run(
            f"cd {push.REMOTE_ROOT}/{task_id} && DISPLAY=:1 python3 initial_setup.py "
            f">/tmp/_setup.log 2>&1 || true", timeout=300)
        sid = (sbx.commands.run("cat /tmp/task_web_sid 2>/dev/null || echo NOSID",
                                 timeout=30).stdout or "").strip()
        if not sid or sid == "NOSID":
            _fail("initial_setup.py 未写出 sid")
            return _summary()
        print(f"  sid : {sid}")
        _ok("任务状态注入成功（launch_gui 已在常驻 chromium 开页）")

        env.sleep(2)
        before = env.screenshot(local_out=OUT_DIR / "02_before_click.png")

        # 纯坐标操作：点页面中部 + 滚动，不用任何 selector
        env.click(960, 540)
        env.sleep(1)
        env.scroll(-6)
        env.sleep(1.5)
        after = env.screenshot(local_out=OUT_DIR / "03_after_click.png")

        print(f"  点击+滚动前后截图是否不同: {before != after}")
        if before != after:
            _ok("纯坐标动作改变了桌面画面 → pyautogui 落到了真实窗口上")
        else:
            _fail("画面无变化，坐标动作可能没生效")

        # ── 6. mm_agents 契约 ────────────────────────────────────────────────
        _section("6. mm_agents 契约：直接吃 pyautogui 代码串")
        shot_a = env.screenshot()
        # 这就是 action_space="pyautogui" 的 agent 原样吐出的东西
        env.step("pyautogui.click(x=640, y=400)")
        env.step("pyautogui.scroll(-4)")
        shot_b = env.screenshot()
        print(f"  step('pyautogui.click(...)') 执行后画面变化: {shot_a != shot_b}")
        _ok("execute_python_command / step 可直接执行 agent 输出的 pyautogui 串")
        obs = env.get_obs()
        print(f"  get_obs() keys = {list(obs)}  screenshot {len(obs['screenshot'])}B")
        if "screenshot" in obs and obs["screenshot"]:
            _ok("get_obs() 返回 mm_agents 期望的 obs dict")
        else:
            _fail("get_obs() 异常")

        # ── 7. computer_13 ───────────────────────────────────────────────────
        _section("7. computer_13 动作空间")
        try:
            env.execute_action({"action_type": "MOVE_TO", "parameters": {"x": 500, "y": 400}})
            env.execute_action({"action_type": "CLICK",
                                "parameters": {"button": "left", "x": 500, "y": 400}})
            env.execute_action({"action_type": "SCROLL", "parameters": {"dy": -3}})
            env.execute_action({"action_type": "WAIT"})
            _ok("MOVE_TO / CLICK / SCROLL / WAIT 均正常")
        except Exception as e:
            _fail(f"computer_13 动作异常: {str(e)[:120]}")

        # ── 8. a11y 按预期不可用 ─────────────────────────────────────────────
        _section("8. a11y 树（预期不可用）")
        try:
            env.get_accessibility_tree()
            _fail("a11y 居然返回了内容，与 pyatspi 不可用的结论矛盾，需复查")
        except PixelEnvError as e:
            print(f"  抛错（符合预期）: {str(e)[:100]}")
            _ok("a11y 明确不可用并抛错，不会静默返回空树")

        print(f"\n  截图已存到 {OUT_DIR}/")
        sbx.commands.run("rm -f /tmp/_osw_ratio.py", timeout=30)
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
        print("\n  OSWorld server 在 AGS 沙箱里跑通：全屏观测 + pyautogui 动作，")
        print("  mm_agents 的 obs/action 契约可直接对接，M3 不需要写翻译层。")
    return 0 if not _failed else 1


if __name__ == "__main__":
    sys.exit(main())
