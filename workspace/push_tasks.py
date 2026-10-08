#!/usr/bin/env python3
"""
从 tasks_data/ 选一批任务推送到池里的沙箱实例。

走 SandboxPool 的正常复用路径（reconcile → acquire → release），**不 kill 实例**：
实例上 31 个 app 的部署成本是一次性的（~176s），push 完还要继续用。

前置：先跑一次 python workspace/unpack_tasks.py 生成 tasks_data/。

Usage:
    python workspace/push_tasks.py                      # 每个 app 取 3 个
    python workspace/push_tasks.py --per-app 10
    python workspace/push_tasks.py --all                # 全部 1062 个
    python workspace/push_tasks.py --app instacart_mock --app slack_mock --per-app 5
    python workspace/push_tasks.py --dry-run            # 只打印选中的任务，不碰实例
"""
import argparse
import os
import sys
from pathlib import Path

WORKSPACE = Path(__file__).parent
sys.path.insert(0, str(WORKSPACE))

os.environ.setdefault("NO_PROXY", "*.tencentags.com,*.woa.com,*.tencentyun.com")

from sandbox.pool import SandboxPool
from tasks import catalog, push

TEMPLATE = "sdt-hojglb51"
TIMEOUT = 86400  # 24 小时
MAX_SIZE = 12
REGISTRY = WORKSPACE / "configs" / "sandbox_pool.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-app", type=int, default=3, help="每个 app 取几个任务（默认 3）")
    ap.add_argument("--all", action="store_true", help="推送全部任务，忽略 --per-app")
    ap.add_argument("--app", action="append", default=[], help="只推指定 app（可重复）")
    ap.add_argument("--seed", type=int, default=0, help="取样随机种子，固定可复现")
    ap.add_argument("--dry-run", action="store_true", help="只打印选中任务，不连实例")
    ap.add_argument("--remote-root", default=push.REMOTE_ROOT)
    args = ap.parse_args()

    all_tasks = catalog.load_tasks()
    if not all_tasks:
        print(f"[FAIL] {catalog.DATA_DIR} 下没有任务。")
        print("       先跑: python workspace/unpack_tasks.py")
        return 1

    s = catalog.stats(all_tasks)
    print("=== 推送任务到沙箱实例 ===")
    print(f"任务库 : {catalog.DATA_DIR}  共 {s['total']} 个任务 / {s['apps']} 个 app")

    tasks = all_tasks
    if args.app:
        tasks = catalog.filter_apps(tasks, args.app)
        if not tasks:
            print(f"[FAIL] 没有匹配 {args.app} 的任务")
            return 1
    if not args.all:
        tasks = catalog.sample_per_app(tasks, n=args.per_app, seed=args.seed)

    sel = catalog.stats(tasks)
    mode = "全部" if args.all else f"每 app {args.per_app} 个"
    print(f"选中   : {sel['total']} 个任务 / {sel['apps']} 个 app（{mode}）")
    print()
    for app, n in sorted(sel["by_app"].items()):
        print(f"  {app:26s} {n}")

    if args.dry_run:
        print("\n--dry-run：未连接实例。")
        return 0

    # ── 取实例（复用，不新建）────────────────────────────────────────────────
    print()
    pool = SandboxPool(REGISTRY, template=TEMPLATE, max_size=MAX_SIZE, timeout=TIMEOUT)
    print("[ 1/3 ] pool.reconcile ...")
    result = pool.reconcile()
    idle = [c.sandbox_id for c in pool._instances.values() if c.status == "idle"]
    print(f"        池内 {len(pool._instances)} 个实例，{len(idle)} 个 idle "
          f"(removed={len(result['removed'])} added={len(result['added'])})")

    print("[ 2/3 ] pool.acquire ...")
    cfg, sbx = pool.acquire()
    reused = cfg.sandbox_id in idle
    print(f"        {cfg.sandbox_id}  {'复用' if reused else '新建'}  "
          f"apps_ready={cfg.apps_ready}")

    try:
        print(f"[ 3/3 ] 上传 {sel['total']} 个任务到 {args.remote_root} ...")
        info = push.push_tasks(sbx, tasks, remote_root=args.remote_root)
        print(f"        {info['files']} 个文件 / {info['bytes'] / 1e6:.1f} MB，"
              f"耗时 {info['elapsed']:.0f}s")
        print(f"        远端任务目录数: {info['remote_dirs']}")
        print(f"        google-chrome shim: {'已就绪' if info['shim'] else '未就绪'}")
        if info["remote_dirs"] < info["uploaded"]:
            print(f"        [WARN] 远端目录数 {info['remote_dirs']} "
                  f"少于上传数 {info['uploaded']}")
        if not info["shim"]:
            print("        [WARN] shim 未就绪，任务脚本里的 launch_gui 会失败")
    finally:
        # 保持 running 回到 idle，不 kill
        pool.release(cfg.sandbox_id, sbx=sbx, pause=False)
        final = pool._instances.get(cfg.sandbox_id)
        print(f"\n已 release，实例 status={final.status if final else '?'}（未销毁）")

    print("\n=== 完成 ===")
    print(f"sandbox_id : {cfg.sandbox_id}")
    print(f"任务位置   : {args.remote_root}/<task_id>/")
    print("\n验证: python workspace/smoke_test/test_task_from_archive.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
