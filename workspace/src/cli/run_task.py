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

from src.agents import registry
from src.runner.episode import run_episode
from src.sandbox import apps_host
from src.sandbox import osworld_server as osw
from src.sandbox.pixel_env import PixelSandboxEnv
from src.sandbox.pool import AppsUnreachableError, SandboxPool
from src.settings import RESULTS
from src.tasks import catalog, push


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", help="task_id，默认取实例上已推送的第一个")
    ap.add_argument("--agent", default="qwen-cua",
                    help="用哪个 agent；--list-agents 看全部")
    ap.add_argument("--list-agents", action="store_true", help="列出已注册 agent 后退出")
    ap.add_argument("--model", default=None, help="覆盖该 agent 的默认模型")
    ap.add_argument("--max-steps", type=int, default=10)
    ap.add_argument("--max-tokens", type=int, default=None,
                    help="覆盖 agent 默认值；不给则用 agent 自己的默认")
    ap.add_argument("--pause", type=float, default=1.0, help="每个动作后等待秒数")
    ap.add_argument("--list", action="store_true", help="列出实例上可跑的任务后退出")
    args = ap.parse_args()

    if args.list_agents:
        print(registry.describe())
        return 0

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

    ep = None
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

        # ── 1. server + 装载 agent + 初始状态 ──────────────────────────────
        osw.ensure_server(sbx)
        env = PixelSandboxEnv(sbx, install=False)

        # 装载时就做能力比对：agent 要的观测环境给不了，当场报错，
        # 不要等 rollout 跑到第 5 步才炸。
        try:
            # 只传显式给出的旋钮。各 agent 接受的参数不一样（GeminiFCAgent
            # 就没有 max_tokens），无条件塞会直接 TypeError。
            knobs = {}
            if args.max_tokens is not None:
                knobs["max_tokens"] = args.max_tokens
            agent = registry.load(args.agent, model=args.model,
                                  env_obs_keys=env.OBS_KEYS, **knobs)
        except registry.AdapterError as e:
            print(f"[FAIL] 装载 agent 失败: {e}")
            return 1

        print(f"task    : {task_id}")
        print(f"app     : {spec.app_type}  port {spec.port}")
        print(f"agent   : {agent.name}  model={agent.model}  "
              f"coord={agent.spec.coordinate_space}  max_steps={args.max_steps}")
        print(f"\n指令    : {spec.instruction}\n")

        print("[ 1/4 ] 注入初始状态（initial_setup.py）...")
        # 实例是复用的，之前任务 launch_gui 开的标签页还留着（没人关）。截图里标签栏
        # 是画面的一部分，残留标签既改变版面又是干扰项，必须先归零。
        tabs = env.reset_tabs()
        if tabs["closed"]:
            print(f"        清理残留标签 {tabs['closed']} 个"
                  f"（{tabs['before']} → {tabs['after']}）")
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

        # ── 3. rollout ──────────────────────────────────────────────────────
        print(f"[ 3/4 ] {agent.name} 开始操作（最多 {args.max_steps} 步）...")
        out_dir = RESULTS / task_id
        t0 = time.time()
        ep = run_episode(env, spec.instruction, agent, max_steps=args.max_steps,
                         pause=args.pause, screenshot_dir=out_dir / "screenshots")
        elapsed = time.time() - t0
        print(f"        {ep['steps']} 步 / 执行 {ep['actions_executed']} 个动作，"
              f"{elapsed:.0f}s，结束于 {ep['stop_reason']}")
        if ep["parse_miss_steps"]:
            print(f"        [注意] {ep['parse_miss_steps']} 步疑似解析失败伪装成 DONE")
        if ep.get("error"):
            print(f"        [提前结束] {ep['error'][:200]}")

        # ── 4. 评分 ─────────────────────────────────────────────────────────
        print("[ 4/4 ] 跑 reward.py 评分 ...")
        final_score = _reward(sbx, task_id)
        print(f"        动作后 REWARD = {final_score}")

        out_dir.mkdir(parents=True, exist_ok=True)
        # 真正该看的是增量而不是终值：部分 reward.py 含反向检查项，
        # 什么都不做反而先得分（NO-OP 任务基线直接就是 1.0）。
        delta = None
        if base_score is not None and final_score is not None:
            delta = round(final_score - base_score, 4)

        result = {
            "task_id": task_id,
            "app_type": spec.app_type,
            "instruction": spec.instruction,
            "agent": ep["agent"],
            "model": ep["model"],
            "coordinate_space": agent.spec.coordinate_space,
            "sid": sid,
            "steps": ep["steps"],
            "max_steps": args.max_steps,
            "actions_executed": ep["actions_executed"],
            "verdict": ep.get("verdict"),
            "stop_reason": ep["stop_reason"],
            "parse_miss_steps": ep["parse_miss_steps"],
            "baseline_reward": base_score,
            "final_reward": final_score,
            "reward_delta": delta,
            "elapsed_sec": round(elapsed, 1),
            "error": ep.get("error"),
            "trajectory": ep["trajectory"],
        }
        (out_dir / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False))

        print(f"\n=== 结果 ===")
        print(f"  REWARD {base_score} → {final_score}   delta={delta}")
        print(f"  轨迹与截图: {out_dir}")
        return 0

    finally:
        if ep and ep.get("stop_reason") == "env_error":
            pool.kill(cfg.sandbox_id)
            print(f"\n实例 env_error，已 kill（不回池）")
        else:
            pool.release(cfg.sandbox_id)
            print(f"\n已 release，实例保持 running（未 kill）")


def _reward(sbx, task_id: str):
    """
    跑 reward.py 并解析分数。解析不到返回 None。

    两种输出格式都要认：1048 个任务打印 `REWARD: 0.5`，另有 14 个只打印
    `Score: 3/6 = 0.5`。只匹配前者会把那 14 个静默记成「无分数」。
    """
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
