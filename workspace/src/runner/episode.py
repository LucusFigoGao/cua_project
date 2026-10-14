"""
机身快门：跑一个 episode。

时序照 osworld/lib_run_single.py 的 run_single_example：每步先拿观测给镜头，
再把吐出的动作逐条执行，遇到 DONE/FAIL 提前结束。

机身不认识任何具体模型，只跟 src.agents.mount.Lens 打交道。分步日志、
动作计数、提前结束的原因记录都在这里做一次，所有镜头共享。
"""
import time
from pathlib import Path
from typing import Optional, Union

from src.agents.mount import SPECIAL, Lens, LensError


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


def run_episode(env, instruction: str, lens: Lens, max_steps: int = 10,
                pause: float = 1.0, screenshot_dir: Union[str, Path, None] = None,
                verbose: bool = True) -> dict:
    lens.reset()
    traj: list[dict] = []
    done = False
    verdict = None
    error = None
    stop_reason = "max_steps"

    obs = env.get_obs(lens.obs_keys)
    for step in range(1, max_steps + 1):
        if screenshot_dir:
            Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
            (Path(screenshot_dir) / f"step{step:02d}.png").write_bytes(obs["screenshot"])

        t0 = time.time()
        try:
            reply, actions, extra = lens.predict(instruction, obs)
        except (LensError, Exception) as e:
            # 这一步挂了，但前面几步是真跑过的，保留它们再退出。
            error = f"{type(e).__name__}: {e}"
            stop_reason = "lens_error"
            if verbose:
                print(f"  [step {step}] 镜头异常，保留前 {len(traj)} 步: {error[:160]}")
            break
        latency = time.time() - t0

        parse_miss = _looks_like_parse_miss(reply, actions)
        if verbose:
            first = reply.strip().splitlines()[0] if reply.strip() else "(空回复)"
            print(f"  [step {step}] {latency:5.1f}s  {first[:80]}")
            print(f"            动作: {_fmt(actions)}"
                  f"{'   ← 疑似解析失败伪装成 DONE' if parse_miss else ''}")

        executed = 0
        for action in actions:
            if action in SPECIAL:
                if action in ("DONE", "FAIL"):
                    done, verdict = True, action
                    stop_reason = "parse_miss" if parse_miss else action.lower()
                    break
                env.sleep(pause)
                continue
            obs = env.step(action, pause=pause)
            executed += 1

        traj.append({
            "step": step,
            "latency_sec": round(latency, 2),
            "reply": reply,
            "actions": actions,
            "executed": executed,
            "parse_miss": parse_miss,
            "extra": extra or None,
        })
        if done:
            break
        obs = env.get_obs(lens.obs_keys)

    return {
        "lens": lens.name,
        "model": lens.model,
        "steps": len(traj),
        "done": done,
        "verdict": verdict,
        "stop_reason": stop_reason,
        "parse_miss_steps": sum(1 for t in traj if t["parse_miss"]),
        "actions_executed": sum(t["executed"] for t in traj),
        "error": error,
        "trajectory": traj,
    }
