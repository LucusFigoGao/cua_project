"""
单任务生命周期：acquire → push → setup → episode → reward → save → release/kill。

run_one() 是 cli/run_task.py（单跑）和 runner/batch_runner.py（批跑）的共用核心。
"""
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

from e2b import Sandbox

from src.agents import registry
from src.runner.episode import run_episode
from src.sandbox import osworld_server as osw
from src.sandbox.pixel_env import PixelSandboxEnv
from src.sandbox.pool import SandboxPool
from src.settings import RESULTS
from src.tasks import push
from src.tasks.catalog import TaskSpec

log = logging.getLogger(__name__)


def run_one(pool: SandboxPool, spec: TaskSpec, agent_name: str, *,
            model: Optional[str] = None, max_steps: int = 10,
            pause: float = 1.0, max_tokens: Optional[int] = None,
            verbose: bool = True) -> dict:
    """
    端到端跑一个任务，返回 result dict（同时写入 results/<task_id>/result.json）。

    自行 acquire / release / kill 实例。调用方不需要管理沙箱生命周期。
    """
    cfg, sbx = pool.acquire()
    stop_reason = None
    try:
        result = _run_on_sandbox(
            pool, cfg, sbx, spec, agent_name,
            model=model, max_steps=max_steps, pause=pause,
            max_tokens=max_tokens, verbose=verbose,
        )
        stop_reason = result.get("stop_reason")
        return result
    except Exception as e:
        return {
            "task_id": spec.task_id,
            "app_type": spec.app_type,
            "instruction": spec.instruction,
            "agent": agent_name,
            "model": model or "",
            "stop_reason": "infra_error",
            "error": f"{type(e).__name__}: {e}",
            "steps": 0,
            "actions_executed": 0,
            "trajectory": [],
        }
    finally:
        if stop_reason == "env_error":
            pool.kill(cfg.sandbox_id)
            if verbose:
                log.info("实例 %s env_error，已 kill", cfg.sandbox_id)
        else:
            pool.release(cfg.sandbox_id)


def _run_on_sandbox(pool, cfg, sbx, spec, agent_name, *,
                    model, max_steps, pause, max_tokens, verbose):
    task_id = spec.task_id

    push.ensure_sandbox_deps(sbx)
    if spec.path:
        push.push_single_task(sbx, task_id, spec.path)

    osw.ensure_server(sbx)
    env = PixelSandboxEnv(sbx, install=False)

    knobs = {}
    if max_tokens is not None:
        knobs["max_tokens"] = max_tokens
    agent = registry.load(agent_name, model=model,
                          env_obs_keys=env.OBS_KEYS, **knobs)

    if verbose:
        log.info("task=%s  app=%s  agent=%s  model=%s",
                 task_id, spec.app_type, agent.name, agent.model)

    # 清残留标签
    env.reset_tabs()

    # initial_setup
    sbx.commands.run("rm -f /tmp/task_web_sid", timeout=30)
    sbx.commands.run(
        f"cd {push.REMOTE_ROOT}/{task_id} && DISPLAY=:1 python3 initial_setup.py "
        f">/tmp/_setup.log 2>&1 || true", timeout=300)
    sid = (sbx.commands.run("cat /tmp/task_web_sid 2>/dev/null || echo NOSID",
                            timeout=30).stdout or "").strip()
    if not sid or sid == "NOSID":
        setup_log = sbx.commands.run("tail -15 /tmp/_setup.log", timeout=30).stdout or ""
        raise RuntimeError(f"initial_setup.py 未写出 sid。日志：\n{setup_log}")
    env.sleep(2)

    # baseline reward
    base_score = _reward(sbx, task_id)

    # episode
    out_dir = RESULTS / task_id
    t0 = time.time()
    ep = run_episode(env, spec.instruction, agent, max_steps=max_steps,
                     pause=pause, screenshot_dir=out_dir / "screenshots",
                     verbose=verbose)
    elapsed = time.time() - t0

    # final reward
    final_score = _reward(sbx, task_id)
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
        "max_steps": max_steps,
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

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False))

    if verbose:
        log.info("task=%s  reward=%s→%s  delta=%s  steps=%d  stop=%s",
                 task_id, base_score, final_score, delta,
                 ep["steps"], ep["stop_reason"])
    return result


def _reward(sbx: Sandbox, task_id: str):
    r = sbx.commands.run(
        f"cd {push.REMOTE_ROOT}/{task_id} && python3 reward.py 2>&1 || true", timeout=180)
    out = (r.stdout or "") + (r.stderr or "")
    for pattern in (r"REWARD:\s*([\d.]+)", r"Score:.*?=\s*([\d.]+)"):
        m = re.search(pattern, out)
        if m:
            return float(m.group(1))
    return None
