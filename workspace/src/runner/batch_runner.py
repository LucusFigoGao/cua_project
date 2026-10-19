"""
多线程批跑引擎：N 个 worker 消费任务队列，每个 worker 调用 run_one()。

并发上限受 pool.max_size 约束。worker 通过 pool.acquire 自动排队，
所以 workers > pool.max_size 也能工作（多余的 worker 会阻塞在 acquire 上）。
"""
import logging
import queue
import threading
from pathlib import Path
from typing import Optional

from src.runner.task import run_one
from src.sandbox.pool import SandboxPool
from src.tasks.catalog import TaskSpec

log = logging.getLogger(__name__)


class BatchRunner:
    def __init__(self, pool: SandboxPool, agent_name: str, *,
                 model: Optional[str] = None, max_steps: int = 10,
                 pause: float = 1.0, max_tokens: Optional[int] = None,
                 workers: int = 4, run_dir: Optional[Path] = None,
                 session_dir: Optional[Path] = None, verbose: bool = True):
        self.pool = pool
        self.agent_name = agent_name
        self.model = model
        self.max_steps = max_steps
        self.pause = pause
        self.max_tokens = max_tokens
        self.workers = workers
        self.run_dir = run_dir
        self.session_dir = session_dir
        self.verbose = verbose
        self._queue: queue.Queue[Optional[TaskSpec]] = queue.Queue()
        self._results: list[dict] = []
        self._lock = threading.Lock()
        self._progress = {"done": 0, "total": 0}

    def run(self, specs: list[TaskSpec]) -> list[dict]:
        self._progress["total"] = len(specs)
        self._progress["done"] = 0
        self._results = []

        for s in specs:
            self._queue.put(s)
        for _ in range(self.workers):
            self._queue.put(None)

        threads = []
        for i in range(self.workers):
            t = threading.Thread(target=self._worker, name=f"worker-{i}",
                                 daemon=True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        return list(self._results)

    def _worker(self):
        while True:
            spec = self._queue.get()
            if spec is None:
                break
            try:
                result = run_one(
                    self.pool, spec, self.agent_name,
                    model=self.model, max_steps=self.max_steps,
                    pause=self.pause, max_tokens=self.max_tokens,
                    run_dir=self.run_dir, session_dir=self.session_dir,
                    verbose=self.verbose,
                )
            except Exception as e:
                result = {
                    "task_id": spec.task_id,
                    "app_type": spec.app_type,
                    "stop_reason": "infra_error",
                    "error": f"{type(e).__name__}: {e}",
                    "steps": 0,
                }
                log.error("worker 异常: task=%s  %s", spec.task_id, e)

            with self._lock:
                self._results.append(result)
                self._progress["done"] += 1
                n = self._progress["done"]
                total = self._progress["total"]
                sr = result.get("stop_reason", "?")
                delta = result.get("reward_delta")
                log.info("[%d/%d] %s  stop=%s  delta=%s",
                         n, total, spec.task_id, sr, delta)


def summarize(results: list[dict]) -> dict:
    """按 app 分组汇总。"""
    by_app: dict[str, list] = {}
    for r in results:
        app = r.get("app_type", "unknown")
        by_app.setdefault(app, []).append(r)

    summary = {"total": len(results), "apps": {}}
    total_ok, total_err = 0, 0
    for app, rs in sorted(by_app.items()):
        ok = [r for r in rs if r.get("stop_reason") not in ("env_error", "infra_error")]
        err = len(rs) - len(ok)
        deltas = [r["reward_delta"] for r in ok
                  if r.get("reward_delta") is not None]
        summary["apps"][app] = {
            "count": len(rs),
            "ok": len(ok),
            "env_error": err,
            "avg_delta": round(sum(deltas) / len(deltas), 4) if deltas else None,
            "avg_steps": round(sum(r.get("steps", 0) for r in ok) / max(len(ok), 1), 1),
        }
        total_ok += len(ok)
        total_err += err

    summary["ok"] = total_ok
    summary["env_error"] = total_err
    return summary
