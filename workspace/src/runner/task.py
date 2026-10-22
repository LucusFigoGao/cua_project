"""
单任务生命周期：acquire → deploy_apps → push → setup → episode → reward → save → kill/release。

run_one() 是 cli/run_task.py（单跑）和 runner/batch_runner.py（批跑）的共用核心。
kill_after=True（默认）：任务结束后无论成功/失败都 kill 沙箱（kill-per-task 模式）。
kill_after=False：保持旧的复用逻辑（env_error kill，其余 release）。
"""
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from e2b import Sandbox

from src.agents import registry
from src.runner.episode import run_episode
from src.sandbox import osworld_server as osw
from src.sandbox.app_deploy import deploy_task_apps
from src.sandbox.pixel_env import PixelSandboxEnv
from src.sandbox.pool import SandboxPool
from src.settings import RESULTS, SESSIONS
from src.tasks import push
from src.tasks.catalog import TaskSpec

log = logging.getLogger(__name__)


def run_one(pool: SandboxPool, spec: TaskSpec, agent_name: str, *,
            model: Optional[str] = None, max_steps: int = 10,
            pause: float = 1.0, max_tokens: Optional[int] = None,
            run_dir: Optional[Path] = None, session_dir: Optional[Path] = None,
            kill_after: bool = True, verbose: bool = True) -> dict:
    """
    端到端跑一个任务，返回 result dict（同时写入 result.json 和 session JSONL）。

    run_dir:     result.json 和 screenshots 的输出目录，默认 RESULTS/<task_id>
    session_dir: session JSONL 的输出目录，默认 SESSIONS/<task_id>.jsonl
    kill_after:  True = 任务结束后 kill 沙箱（kill-per-task 模式，默认）
                 False = 旧复用逻辑（env_error kill，其余 release）
    """
    cfg, sbx = pool.acquire(ensure_apps=False)
    stop_reason = None
    try:
        result = _run_on_sandbox(
            pool, cfg, sbx, spec, agent_name,
            model=model, max_steps=max_steps, pause=pause,
            max_tokens=max_tokens, run_dir=run_dir,
            session_dir=session_dir, verbose=verbose,
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
        if kill_after:
            pool.kill(cfg.sandbox_id)
            if verbose:
                log.info("实例 %s 任务结束，已 kill", cfg.sandbox_id)
        elif stop_reason == "env_error":
            pool.kill(cfg.sandbox_id)
            if verbose:
                log.info("实例 %s env_error，已 kill", cfg.sandbox_id)
        else:
            pool.release(cfg.sandbox_id)


def _run_on_sandbox(pool, cfg, sbx, spec, agent_name, *,
                    model, max_steps, pause, max_tokens,
                    run_dir, session_dir, verbose):
    task_id = spec.task_id

    push.ensure_sandbox_deps(sbx)
    if spec.path:
        push.push_single_task(sbx, task_id, spec.path)

    deploy_task_apps(sbx, spec)

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

    env.reset_tabs()

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

    base_score = _reward(sbx, task_id)

    out_dir = (run_dir / task_id) if run_dir else (RESULTS / task_id)
    t0 = time.time()
    ep = run_episode(env, spec.instruction, agent, max_steps=max_steps,
                     pause=pause, screenshot_dir=out_dir / "screenshots",
                     verbose=verbose)
    elapsed = time.time() - t0

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

    _write_session_jsonl(ep["trajectory"], task_id, session_dir)

    if verbose:
        log.info("task=%s  reward=%s→%s  delta=%s  steps=%d  stop=%s",
                 task_id, base_score, final_score, delta,
                 ep["steps"], ep["stop_reason"])
    return result


def _write_session_jsonl(trajectory: list, task_id: str,
                         session_dir: Optional[Path]):
    """从 trajectory 生成 session JSONL，每行一步。"""
    if not session_dir:
        return
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / f"{task_id}.jsonl"
    with open(path, "w") as f:
        for entry in trajectory:
            extra = entry.get("extra") or {}
            line = {
                "step": entry["step"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "raw_response": entry.get("reply", ""),
                "actions": entry.get("actions", []),
                "parse_miss": entry.get("parse_miss", False),
                "truncated": entry.get("truncated", False),
                "latency_sec": entry.get("latency_sec", 0),
                "exec_result": entry.get("exec_result", {}),
                "usage": extra.get("usage"),
            }
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def _reward(sbx: Sandbox, task_id: str):
    r = sbx.commands.run(
        f"cd {push.REMOTE_ROOT}/{task_id} && python3 reward.py 2>&1 || true", timeout=180)
    out = (r.stdout or "") + (r.stderr or "")
    for pattern in (r"REWARD:\s*([\d.]+)", r"Score:.*?=\s*([\d.]+)"):
        m = re.search(pattern, out)
        if m:
            return float(m.group(1))
    return None
