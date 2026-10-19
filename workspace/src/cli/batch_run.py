#!/usr/bin/env python3
"""
批量跑任务：多 worker 并发消费任务队列。

Usage:
    bash -lc 'source ~/.bashrc && python -m src.cli.batch_run --agent qwen-cua --workers 4 --sample-per-app 3'
    bash -lc 'source ~/.bashrc && python -m src.cli.batch_run --agent qwen-cua --workers 2 --dry-run'
"""
import argparse
import json
import logging
import os
import sys
import time

os.environ.setdefault("NO_PROXY", "*.tencentags.com,*.woa.com,*.tencentyun.com")

from src.agents import registry
from src.runner.batch_runner import BatchRunner, summarize
from src.sandbox import apps_host
from src.sandbox.pool import AppsUnreachableError, SandboxPool
from src.settings import RESULTS
from src.tasks import catalog


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
    ap.add_argument("--sample-per-app", type=int, default=None,
                    help="每个 app 取 N 个任务；不给则全跑")
    ap.add_argument("--exclude-app", action="append", default=[],
                    help="排除某个 app（可多次指定）")
    ap.add_argument("--tasks", default=None,
                    help="只跑指定的 task_id 列表文件（每行一个 id）")
    ap.add_argument("--resume", action="store_true",
                    help="跳过 results/ 下已有 result.json 的任务")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印任务列表不执行")
    ap.add_argument("-v", "--verbose", action="store_true", default=True)
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

    # 加载任务
    all_tasks = catalog.load_tasks()
    if not all_tasks:
        print(f"[FAIL] tasks_data 为空，先跑 unpack_tasks.py")
        return 1

    # 过滤
    tasks = all_tasks
    if args.exclude_app:
        excluded = set(args.exclude_app)
        tasks = [t for t in tasks if t.app_type not in excluded]

    if args.tasks:
        with open(args.tasks) as f:
            wanted = {l.strip() for l in f if l.strip()}
        tasks = [t for t in tasks if t.task_id in wanted]

    if args.sample_per_app is not None:
        tasks = catalog.sample_per_app(tasks, n=args.sample_per_app)

    if args.resume:
        tasks = [t for t in tasks
                 if not (RESULTS / t.task_id / "result.json").exists()]

    if not tasks:
        print("没有要跑的任务。")
        return 0

    # 统计
    st = catalog.stats(tasks)
    print(f"任务 {st['total']} 个，覆盖 {st['apps']} 个 app")
    for app, cnt in st["by_app"].items():
        print(f"  {app:24s} {cnt}")

    if args.dry_run:
        print(f"\n[dry-run] 以上 {st['total']} 个任务不执行。")
        return 0

    # 检查 app 服务
    host_ip = apps_host.detect_host_ip()
    ports = apps_host.check_ports()
    if not all(ports.values()):
        down = [a for a, ok in ports.items() if not ok]
        print(f"[FAIL] 开发机 {host_ip} 上有 {len(down)} 个 app 没在跑: "
              f"{', '.join(down[:5])}")
        return 1

    pool = SandboxPool(app_host=host_ip)
    pool.reconcile()

    runner = BatchRunner(
        pool, args.agent,
        model=args.model, max_steps=args.max_steps,
        pause=args.pause, max_tokens=args.max_tokens,
        workers=args.workers,
        verbose=not args.quiet,
    )

    print(f"\n开始批跑：{len(tasks)} 个任务，{args.workers} workers\n")
    t0 = time.time()
    results = runner.run(tasks)
    elapsed = time.time() - t0

    # 汇总
    summary = summarize(results)
    summary["elapsed_sec"] = round(elapsed, 1)
    summary["agent"] = args.agent
    summary["model"] = args.model or registry.spec_of(args.agent).default_model
    summary["max_steps"] = args.max_steps

    summary_path = RESULTS / "batch_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"\n{'=' * 60}")
    print(f"  总计 {summary['total']} 个任务，{elapsed:.0f}s")
    print(f"  成功 {summary['ok']}  env_error {summary['env_error']}")
    print()
    for app, info in summary["apps"].items():
        print(f"  {app:24s}  {info['ok']}/{info['count']}  "
              f"avg_delta={info['avg_delta']}  avg_steps={info['avg_steps']}")
    print(f"\n  汇总: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
