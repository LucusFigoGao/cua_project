#!/usr/bin/env python3
"""
批量跑任务：多 worker 并发消费任务队列。

Usage:
    cd workspace && python -m src.cli.batch_run --agent qwen-cua --workers 4 --sample-per-app 3
    cd workspace && python -m src.cli.batch_run --dry-run --sample-per-app 1
"""
import argparse
import json
import logging
import os
import sys
import time

os.environ.setdefault("NO_PROXY", "*.tencentags.com,*.woa.com,*.tencentyun.com")

from pathlib import Path

from src.agents import registry
from src.runner.batch_runner import BatchRunner, summarize
from src.sandbox import apps_host
from src.sandbox.pool import SandboxPool
from src.settings import POOL_MAX_SIZE, RESULTS, SESSIONS
from src.tasks import catalog


def _make_run_name(agent: str, model: str, n_tasks: int) -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    safe_model = model.replace("/", "_").replace(" ", "_")
    return f"{ts}_{agent}_{safe_model}_{n_tasks}tasks"


def main() -> int:
    ap = argparse.ArgumentParser(description="批量跑 CUA 任务")
    ap.add_argument("--agent", default="qwen-cua",
                    help="agent 名；--list-agents 看全部")
    ap.add_argument("--list-agents", action="store_true")
    ap.add_argument("--model", default=None, help="覆盖 agent 默认模型")
    ap.add_argument("--max-steps", type=int, default=10)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--workers", type=int, default=4, help="并发 worker 数")
    ap.add_argument("--max-instances", type=int, default=None,
                    help="沙箱池上限（覆盖 POOL_MAX_SIZE，默认 12）")
    ap.add_argument("--sample-per-app", type=int, default=None,
                    help="每个 app 取 N 个任务；不给则全跑")
    ap.add_argument("--exclude-app", default="",
                    help="排除的 app，逗号分隔（如 monday_mock,discord_mock）")
    ap.add_argument("--tasks", default=None,
                    help="只跑指定的 task_id 列表文件（每行一个 id）")
    ap.add_argument("--resume", action="store_true",
                    help="跳过已有 result.json 的任务（在 run_dir 内检查）")
    ap.add_argument("--run-name", default=None,
                    help="指定 run 目录名（默认自动生成带时间戳的名字）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印任务列表不执行")
    ap.add_argument("--keep-instances", action="store_true",
                    help="批跑结束后保留沙箱实例（默认 kill 所有 idle 实例）")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO if not args.quiet else logging.WARNING,
        format="%(asctime)s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list_agents:
        print(registry.describe())
        return 0

    all_tasks = catalog.load_tasks()
    if not all_tasks:
        print(f"[FAIL] tasks_data 为空，先跑 unpack_tasks.py")
        return 1

    tasks = all_tasks
    if args.exclude_app:
        excluded = {a.strip() for a in args.exclude_app.split(",") if a.strip()}
        tasks = [t for t in tasks if t.app_type not in excluded]

    if args.tasks:
        with open(args.tasks) as f:
            wanted = {l.strip() for l in f if l.strip()}
        tasks = [t for t in tasks if t.task_id in wanted]

    if args.sample_per_app is not None:
        tasks = catalog.sample_per_app(tasks, n=args.sample_per_app)

    resolved_model = args.model or registry.spec_of(args.agent).default_model
    run_name = args.run_name or _make_run_name(args.agent, resolved_model, len(tasks))
    run_dir = RESULTS / run_name
    session_dir = SESSIONS / run_name

    if args.resume:
        tasks = [t for t in tasks
                 if not (run_dir / t.task_id / "result.json").exists()]

    if not tasks:
        print("没有要跑的任务。")
        return 0

    st = catalog.stats(tasks)
    print(f"任务 {st['total']} 个，覆盖 {st['apps']} 个 app")
    for app, cnt in st["by_app"].items():
        print(f"  {app:24s} {cnt}")
    print(f"\n输出目录:")
    print(f"  results:  {run_dir}")
    print(f"  sessions: {session_dir}")

    if args.dry_run:
        print(f"\n[dry-run] 以上 {st['total']} 个任务不执行。")
        return 0

    host_ip = apps_host.detect_host_ip()
    ports = apps_host.check_ports()
    if not all(ports.values()):
        down = [a for a, ok in ports.items() if not ok]
        print(f"[FAIL] 开发机 {host_ip} 上有 {len(down)} 个 app 没在跑: "
              f"{', '.join(down[:5])}")
        return 1

    pool_max = args.max_instances or POOL_MAX_SIZE
    pool = SandboxPool(app_host=host_ip, max_size=pool_max)
    pool.reconcile()

    run_dir.mkdir(parents=True, exist_ok=True)
    session_dir.mkdir(parents=True, exist_ok=True)

    runner = BatchRunner(
        pool, args.agent,
        model=args.model, max_steps=args.max_steps,
        pause=args.pause, max_tokens=args.max_tokens,
        workers=args.workers, run_dir=run_dir,
        session_dir=session_dir, verbose=not args.quiet,
    )

    print(f"\n开始批跑：{len(tasks)} 个任务，{args.workers} workers，"
          f"pool_max={pool_max}\n")
    t0 = time.time()
    results = runner.run(tasks)
    elapsed = time.time() - t0

    summary = summarize(results)
    summary["elapsed_sec"] = round(elapsed, 1)
    summary["agent"] = args.agent
    summary["model"] = resolved_model
    summary["max_steps"] = args.max_steps
    summary["workers"] = args.workers
    summary["max_instances"] = pool_max
    summary["run_name"] = run_name

    summary_path = run_dir / "batch_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"\n{'=' * 60}")
    print(f"  总计 {summary['total']} 个任务，{elapsed:.0f}s")
    print(f"  成功 {summary['ok']}  env_error {summary['env_error']}")
    print()
    for app, info in summary["apps"].items():
        print(f"  {app:24s}  {info['ok']}/{info['count']}  "
              f"avg_delta={info['avg_delta']}  avg_steps={info['avg_steps']}")
    print(f"\n  汇总: {summary_path}")

    if not args.keep_instances:
        idle = pool.idle_ids()
        if idle:
            print(f"\n清理 {len(idle)} 个 idle 沙箱实例...")
            pool.kill_all()
            print("  已全部 kill")
    return 0


if __name__ == "__main__":
    sys.exit(main())
