"""
episode 循环：跑一个 episode。

时序照 osworld/lib_run_single.py 的 run_single_example：每步先拿观测给 agent，
再把吐出的动作执行，遇到 DONE/FAIL 提前结束。

这里不认识任何具体模型，只跟 src.agents.registry.Adapter 打交道。分步日志、
动作计数、提前结束的原因记录都在这里做一次，所有 agent 共享。

约定：提示词已约束 agent 每步只产出一个可执行动作。runner 层做截断兜底。
"""
import time
from pathlib import Path
from typing import Union

from src.agents.registry import SPECIAL, Adapter, AdapterError


def _looks_like_parse_miss(reply: str, actions: list) -> bool:
    """
    判断这一步的 DONE 是不是「解析不出动作」伪装的。

    qwen/actions.py:317 在一个 tool_call 都没解析到时会 fallback 成 DONE——
    于是解析失败长得跟任务完成一模一样，episode 当场结束且记为成功退出。
    这两件事必须分开记，否则一个输出格式不稳的模型会被误判成「很快做完了」。
    """
    if actions != ["DONE"]:
        return False
    low = reply.lower()
    return "<tool_call>" not in low and "```" not in low


def _truncate_to_single_action(actions: list) -> tuple[list, bool]:
    """
    如果 agent 返回多个可执行动作，只保留第一个，其余丢弃。
    返回 (truncated_actions, was_truncated)。
    """
    executable = [a for a in actions if a not in SPECIAL]
    if len(executable) <= 1:
        return actions, False
    first = executable[0]
    tail = [a for a in actions if a in SPECIAL]
    return [first] + tail, True


def _fmt(actions: list) -> str:
    """动作摘要。dict 动作（claude 的 tool_use）整条打出来没法看，只取要点。"""
    out = []
    for a in actions:
        if isinstance(a, str):
            out.append(a.strip().replace("\n", "; ")[:72])
        elif isinstance(a, dict):
            out.append(str(a.get("command") or a.get("action_type") or "dict")
                       .strip().replace("\n", "; ")[:72])
        else:
            out.append(type(a).__name__)
    return " | ".join(out) or "(无)"


def run_episode(env, instruction: str, agent: Adapter, max_steps: int = 10,
                pause: float = 1.0, screenshot_dir: Union[str, Path, None] = None,
                verbose: bool = True) -> dict:
    agent.reset()
    traj: list[dict] = []
    done = False
    verdict = None
    error = None
    stop_reason = "max_steps"
    env_broken = False

    try:
        obs = env.get_obs(agent.obs_keys)
    except Exception as e:
        error = f"env_error: {type(e).__name__}: {e}"
        stop_reason = "env_error"
        if verbose:
            print(f"  [init] 首次截图就失败: {error[:160]}")
        return _build_result(agent, traj, done, verdict, stop_reason, error)

    for step in range(1, max_steps + 1):
        if screenshot_dir:
            Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
            (Path(screenshot_dir) / f"step{step:02d}.png").write_bytes(obs["screenshot"])

        t0 = time.time()
        try:
            reply, actions, extra = agent.predict(instruction, obs)
        except (AdapterError, Exception) as e:
            error = f"{type(e).__name__}: {e}"
            stop_reason = "agent_error"
            if verbose:
                print(f"  [step {step}] agent 异常，保留前 {len(traj)} 步: {error[:160]}")
            break
        latency = time.time() - t0

        parse_miss = _looks_like_parse_miss(reply, actions)
        actions, truncated = _truncate_to_single_action(actions)

        if verbose:
            first = reply.strip().splitlines()[0] if reply.strip() else "(空回复)"
            print(f"  [step {step}] {latency:5.1f}s  {first[:80]}")
            suffix = ""
            if parse_miss:
                suffix += "   ← 疑似解析失败伪装成 DONE"
            if truncated:
                suffix += "   ← 多动作已截断"
            print(f"            动作: {_fmt(actions)}{suffix}")

        executed = 0
        exec_result: dict = {}
        for action in actions:
            if action in SPECIAL:
                if action in ("DONE", "FAIL"):
                    done, verdict = True, action
                    stop_reason = "parse_miss" if parse_miss else action.lower()
                    break
                env.sleep(pause)
                continue
            try:
                obs = env.step(action, pause=pause)
                exec_result = obs.pop("_exec", {})
            except Exception as e:
                error = f"env_error: {type(e).__name__}: {e}"
                stop_reason = "env_error"
                env_broken = True
                if verbose:
                    print(f"  [step {step}] env 异常: {error[:160]}")
                break
            executed += 1

        traj.append({
            "step": step,
            "latency_sec": round(latency, 2),
            "reply": reply,
            "actions": actions,
            "executed": executed,
            "parse_miss": parse_miss,
            "truncated": truncated,
            "exec_result": exec_result,
            "extra": extra or None,
        })

        if done or env_broken:
            break

        if executed == 0:
            try:
                obs = env.get_obs(agent.obs_keys)
            except Exception as e:
                error = f"env_error: {type(e).__name__}: {e}"
                stop_reason = "env_error"
                if verbose:
                    print(f"  [step {step}] get_obs 异常: {error[:160]}")
                break

    if screenshot_dir:
        try:
            shot = env.get_obs(("screenshot",))
            Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
            (Path(screenshot_dir) / "final.png").write_bytes(shot["screenshot"])
        except Exception:
            pass

    return _build_result(agent, traj, done, verdict, stop_reason, error)


def _build_result(agent, traj, done, verdict, stop_reason, error):
    return {
        "agent": agent.name,
        "model": agent.model,
        "steps": len(traj),
        "done": done,
        "verdict": verdict,
        "stop_reason": stop_reason,
        "parse_miss_steps": sum(1 for t in traj if t["parse_miss"]),
        "actions_executed": sum(t["executed"] for t in traj),
        "error": error,
        "trajectory": traj,
    }
