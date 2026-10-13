#!/usr/bin/env python3
"""
单任务端到端：注入初始状态 → agent 看截图点鼠标 → 跑 reward.py 打分。

时序照 osworld/lib_run_single.py 的 run_single_example：
    reset(task) → [ agent.predict(obs) → env.step(action) ] * max_steps → evaluate()

任务脚本必须在沙箱内执行：initial_setup.py 把 sid 写到 /tmp/task_web_sid、
reward.py 从那里读，两者必须同机；launch_gui 也要在沙箱的 chromium 里开页面。
它们访问的 app 跑在开发机上。

ICHAT_API_KEY / ICHAT_BASE_URL 定义在 ~/.bashrc，非交互 shell 不会自动加载。

Usage:
    bash -lc 'source ~/.bashrc && python -m src.cli.run_task --list'
    bash -lc 'source ~/.bashrc && python -m src.cli.run_task --task <id> --max-steps 15'
"""
import argparse
import json
import os
import re
import sys
import time

os.environ.setdefault("NO_PROXY", "*.tencentags.com,*.woa.com,*.tencentyun.com")

from src.agents.bridge import ScreenshotAgent, run_episode
from src.sandbox import apps_host
from src.sandbox import osworld_server as osw
from src.sandbox.pixel_env import PixelSandboxEnv
from src.sandbox.pool import AppsUnreachableError, SandboxPool
from src.settings import DEFAULT_MAX_TOKENS, RESULTS
from src.tasks import catalog, push


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", help="task_id，默认取实例上已推送的第一个")
    ap.add_argument("--model", default="qwen3.8-max", help="ichat 上的模型名")
    ap.add_argument("--max-steps", type=int, default=10)
    ap.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    ap.add_argument("--pause", type=float, default=1.0, help="每个动作后等待秒数")
    ap.add_argument("--list", action="store_true", help="列出实例上可跑的任务后退出")
    args = ap.parse_args()

    local = {t.task_id: t for t in catalog.load_tasks()}
    if not local:
        print(f"[FAIL] {catalog.DATA_DIR} 为空，先跑 unpack_tasks.py")
        return 1

    # app 在开发机上，先确认它们在跑——否则任务脚本注入状态必然失败
    host_ip = apps_host.detect_host_ip()
    ports = apps_host.check_ports()
    if not all(ports.values()):
        down = [a for a, ok in ports.items() if not ok]
        print(f"[FAIL] 开发机 {host_ip} 上有 {len(down)} 个 app 没在跑: "
              f"{', '.join(down[:5])}{'...' if len(down) > 5 else ''}")
        print("       先执行: python -m src.cli.serve_apps --start")
        return 1

    pool = SandboxPool(app_host=host_ip)
    pool.reconcile()
    try:
        cfg, sbx = pool.acquire()
    except AppsUnreachableError as e:
        print(f"[FAIL] {e}")
        return 1
    print(f"sandbox : {cfg.sandbox_id}  apps_ready={cfg.apps_ready}  "
          f"app_host={cfg.app_host}")

    try:
        remote = push.list_remote_tasks(sbx)
        cands = sorted(t for t in remote if t in local)
        if not cands:
            print(f"[FAIL] 实例上没有已推送任务，先跑 push_tasks.py")
            return 1

        if args.list:
            print(f"\n实例上可跑的任务 {len(cands)} 个：")
            for tid in cands:
                s = local[tid]
                print(f"  {tid}  {s.app_type:24s} {s.instruction[:60]}")
            return 0

        task_id = args.task or cands[0]
        if task_id not in local:
            print(f"[FAIL] 本地任务库里没有 {task_id}")
            return 1
        if task_id not in remote:
            print(f"[FAIL] {task_id} 还没推到实例上")
            return 1
        spec = local[task_id]

        print(f"task    : {task_id}")
        print(f"app     : {spec.app_type}  port {spec.port}")
        print(f"model   : {args.model}   max_steps={args.max_steps}")
        print(f"\n指令    : {spec.instruction}\n")

        # ── 1. server + 初始状态 ─────────────────────────────────────────────
        osw.ensure_server(sbx)
        env = PixelSandboxEnv(sbx, install=False)

        print("[ 1/4 ] 注入初始状态（initial_setup.py）...")
        sbx.commands.run("rm -f /tmp/task_web_sid", timeout=30)
        sbx.commands.run(
            f"cd {push.REMOTE_ROOT}/{task_id} && DISPLAY=:1 python3 initial_setup.py "
            f">/tmp/_setup.log 2>&1 || true", timeout=300)
        sid = (sbx.commands.run("cat /tmp/task_web_sid 2>/dev/null || echo NOSID",
                                 timeout=30).stdout or "").strip()
        if not sid or sid == "NOSID":
            log = sbx.commands.run("tail -15 /tmp/_setup.log", timeout=30).stdout or ""
            print(f"[FAIL] initial_setup.py 未写出 sid。日志：\n{log}")
            return 1
        print(f"        sid = {sid}")

        # initial_setup 里的 launch_gui 已经在常驻 chromium 开好了页面；
        # 等一下让页面渲染完，再把浏览器窗口置前（agent 只能看到屏幕上的东西）。
        env.sleep(2)

        # ── 2. 初始分（基线）────────────────────────────────────────────────
        print("[ 2/4 ] 跑一次 reward.py 拿基线分 ...")
        base_score = _reward(sbx, task_id)
        print(f"        动作前 REWARD = {base_score}")

        # ── 3. agent loop ───────────────────────────────────────────────────
        print(f"[ 3/4 ] agent 开始操作（最多 {args.max_steps} 步）...")
        out_dir = RESULTS / task_id
        agent = ScreenshotAgent(model=args.model, max_tokens=args.max_tokens)
        t0 = time.time()
        try:
            ep = run_episode(env, spec.instruction, agent, max_steps=args.max_steps,
                             pause=args.pause, screenshot_dir=out_dir / "screenshots")
        except Exception as e:
            print(f"        [agent 异常] {type(e).__name__}: {str(e)[:300]}")
            ep = {"steps": 0, "done": False, "verdict": None, "trajectory": [],
                  "error": f"{type(e).__name__}: {e}"}
        elapsed = time.time() - t0
        print(f"        跑了 {ep['steps']} 步，{elapsed:.0f}s，"
              f"verdict={ep.get('verdict')}")
        if ep.get("error"):
            print(f"        [提前结束] {ep['error'][:200]}")

        # ── 4. 评分 ─────────────────────────────────────────────────────────
        print("[ 4/4 ] 跑 reward.py 评分 ...")
        final_score = _reward(sbx, task_id)
        print(f"        动作后 REWARD = {final_score}")

        out_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "task_id": task_id,
            "app_type": spec.app_type,
            "instruction": spec.instruction,
            "model": args.model,
            "sid": sid,
            "steps": ep["steps"],
            "max_steps": args.max_steps,
            "verdict": ep.get("verdict"),
            "baseline_reward": base_score,
            "final_reward": final_score,
            "elapsed_sec": round(elapsed, 1),
            "error": ep.get("error"),
            "trajectory": ep["trajectory"],
        }
        (out_dir / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False))

        print(f"\n=== 结果 ===")
        print(f"  {base_score} → {final_score}"
              f"{'  (分数提升)' if (final_score or 0) > (base_score or 0) else ''}")
        print(f"  轨迹与截图: {out_dir}")
        return 0

    finally:
        pool.release(cfg.sandbox_id)
        print(f"\n已 release，实例保持 running（未 kill）")


def _reward(sbx, task_id: str):
    """跑 reward.py 并解析 REWARD: 分数。解析不到返回 None。"""
    r = sbx.commands.run(
        f"cd {push.REMOTE_ROOT}/{task_id} && python3 reward.py 2>&1 || true", timeout=180)
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"REWARD:\s*([\d.]+)", out)
    return float(m.group(1)) if m else None


if __name__ == "__main__":
    sys.exit(main())
