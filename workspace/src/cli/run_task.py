#!/usr/bin/env python3
"""
单任务端到端调试工具：申请沙箱 → 部署 app → 推任务 → episode → reward → kill。

Usage:
    cd workspace && python -m src.cli.run_task --task <task_id> --max-steps 15
    cd workspace && python -m src.cli.run_task --list-tasks
"""
import argparse
import json
import os
import re
import sys
import time

os.environ.setdefault("NO_PROXY", "*.tencentags.com,*.woa.com,*.tencentyun.com")

from src.agents import registry
from src.runner.episode import run_episode
from src.sandbox import osworld_server as osw
from src.sandbox.app_deploy import deploy_task_apps
from src.sandbox.pixel_env import PixelSandboxEnv
from src.sandbox.pool import SandboxPool
from src.settings import APP_BUNDLES, RESULTS
from src.tasks import catalog, push


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", help="task_id")
    ap.add_argument("--agent", default="qwen-cua")
    ap.add_argument("--list-agents", action="store_true")
    ap.add_argument("--list-tasks", action="store_true", help="列出本地任务后退出")
    ap.add_argument("--model", default=None)
    ap.add_argument("--max-steps", type=int, default=10)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--app-bundles", type=str, default=None,
                    help="app bundle 目录（默认 workspace/app_bundles）")
    args = ap.parse_args()

    if args.list_agents:
        print(registry.describe())
        return 0

    local = {t.task_id: t for t in catalog.load_tasks()}
    if not local:
        print(f"[FAIL] {catalog.DATA_DIR} 为空，先跑 unpack_tasks.py")
        return 1

    if args.list_tasks:
        for t in sorted(local.values(), key=lambda s: (s.app_type, s.task_id)):
            print(f"  {t.task_id}  {t.app_type:24s}  {t.instruction[:60]}")
        return 0

    if not args.task:
        print("[FAIL] 请用 --task <task_id> 指定任务，或 --list-tasks 查看可用任务")
        return 1

    if args.task not in local:
        print(f"[FAIL] 本地任务库里没有 {args.task}")
        return 1
    spec = local[args.task]
    bundle_dir = args.app_bundles or APP_BUNDLES

    pool = SandboxPool(max_size=1)
    pool.reconcile()
    cfg, sbx = pool.acquire()
    print(f"sandbox : {cfg.sandbox_id}")

    ep = None
    try:
        # ── 0. 基础依赖 + 推任务文件 ──────────────────────────────────────
        print("[ 0/5 ] 推任务文件 + 基础依赖...")
        push.ensure_sandbox_deps(sbx)
        if spec.path:
            push.push_single_task(sbx, spec.task_id, spec.path)

        # ── 1. 部署 app ────────────────────────────────────────────────────
        print(f"[ 1/5 ] 部署 app：{spec.apps}...")
        deploy_task_apps(sbx, spec, bundle_dir=bundle_dir)
        print(f"        app 就绪")

        # ── 2. OSWorld server + agent ──────────────────────────────────────
        print("[ 2/5 ] 启动 OSWorld server + 装载 agent...")
        osw.ensure_server(sbx)
        env = PixelSandboxEnv(sbx, install=False)
        knobs = {}
        if args.max_tokens is not None:
            knobs["max_tokens"] = args.max_tokens
        try:
            agent = registry.load(args.agent, model=args.model,
                                  env_obs_keys=env.OBS_KEYS, **knobs)
        except registry.AdapterError as e:
            print(f"[FAIL] 装载 agent 失败: {e}")
            return 1
        print(f"        agent={agent.name}  model={agent.model}  "
              f"coord={agent.spec.coordinate_space}")

        # ── 3. 初始状态 ───────────────────────────────────────────────────
        print("[ 3/5 ] 注入初始状态（initial_setup.py）...")
        env.reset_tabs()
        # initial_setup.py 里的 launch_gui 硬编码 DISPLAY=:0，而沙箱 Xvfb 跑在 :1。
        sbx.commands.run("ln -sf /tmp/.X11-unix/X1 /tmp/.X11-unix/X0", timeout=10)
        sbx.commands.run("rm -f /tmp/task_web_sid", timeout=30)
        sbx.commands.run(
            f"cd {push.REMOTE_ROOT}/{spec.task_id} && DISPLAY=:1 python3 initial_setup.py "
            f">/tmp/_setup.log 2>&1 || true", timeout=300)
        sid = (sbx.commands.run("cat /tmp/task_web_sid 2>/dev/null || echo NOSID",
                                timeout=30).stdout or "").strip()
        if not sid or sid == "NOSID":
            setup_log = sbx.commands.run("tail -15 /tmp/_setup.log", timeout=30).stdout or ""
            print(f"[FAIL] initial_setup.py 未写出 sid。日志：\n{setup_log}")
            return 1
        print(f"        sid={sid}")
        env.sleep(2)

        # ── 4. 基线分 → rollout → 终分 ───────────────────────────────────
        print("[ 4/5 ] 基线 reward...")
        base_score = _reward(sbx, spec.task_id)
        print(f"        baseline={base_score}")

        print(f"[ 4/5 ] {agent.name} 开始操作（最多 {args.max_steps} 步）...")
        print(f"        指令: {spec.instruction}\n")
        out_dir = RESULTS / spec.task_id
        t0 = time.time()
        ep = run_episode(env, spec.instruction, agent, max_steps=args.max_steps,
                         pause=args.pause, screenshot_dir=out_dir / "screenshots")
        elapsed = time.time() - t0
        print(f"        {ep['steps']} 步 / {ep['actions_executed']} 个动作 / "
              f"{elapsed:.0f}s / stop={ep['stop_reason']}")
        if ep["parse_miss_steps"]:
            print(f"        [注意] {ep['parse_miss_steps']} 步疑似解析失败")

        print("[ 5/5 ] 最终 reward...")
        final_score = _reward(sbx, spec.task_id)
        delta = None
        if base_score is not None and final_score is not None:
            delta = round(final_score - base_score, 4)
        print(f"        {base_score} → {final_score}  delta={delta}")

        result = {
            "task_id": spec.task_id,
            "app_type": spec.app_type,
            "apps": spec.apps,
            "instruction": spec.instruction,
            "agent": ep["agent"],
            "model": ep["model"],
            "coordinate_space": agent.spec.coordinate_space,
            "sid": sid,
            "steps": ep["steps"],
            "max_steps": args.max_steps,
            "actions_executed": ep["actions_executed"],
            "stop_reason": ep["stop_reason"],
            "parse_miss_steps": ep["parse_miss_steps"],
            "baseline_reward": base_score,
            "final_reward": final_score,
            "reward_delta": delta,
            "elapsed_sec": round(elapsed, 1),
            "error": ep.get("error"),
            "trajectory": ep["trajectory"],
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\n  结果: {out_dir / 'result.json'}")
        return 0

    finally:
        pool.kill(cfg.sandbox_id)
        print(f"sandbox {cfg.sandbox_id} 已 kill")


def _reward(sbx, task_id: str):
    r = sbx.commands.run(
        f"cd {push.REMOTE_ROOT}/{task_id} && python3 reward.py 2>&1 || true", timeout=180)
    out = (r.stdout or "") + (r.stderr or "")
    for pattern in (r"REWARD:\s*([\d.]+)", r"Score:.*?=\s*([\d.]+)"):
        m = re.search(pattern, out)
        if m:
            return float(m.group(1))
    return None


if __name__ == "__main__":
    sys.exit(main())
