#!/usr/bin/env python3
"""
沙箱池的运维入口：预热、查看、回收、销毁。

31 个 mock app 跑在开发机上（见 serve_apps.py），沙箱只需写一行 /etc/hosts 把
host.docker.internal 指到开发机，秒级就绪。

所有子命令都先 reconcile —— 以 Sandbox.list(metadata=POOL_TAG) 为真相源校准
configs/sandbox_pool.json，避免对一个已经不存在的实例做操作。

Usage:
    python -m src.cli.manage_pool                   # 同 --warm
    python -m src.cli.manage_pool --warm            # 保证池里有一个就绪实例（有 idle 复用，没有新建）
    python -m src.cli.manage_pool --status          # 列出全部实例及 idle/busy
    python -m src.cli.manage_pool --release-all     # 把卡在 busy 的实例标回 idle
    python -m src.cli.manage_pool --kill <sandbox_id>
    python -m src.cli.manage_pool --kill-all --yes
"""
import argparse
import sys
import time
from typing import Optional

from src import settings
from src.sandbox import apps_host
from src.sandbox.pool import AppsUnreachableError, SandboxPool


def _reconcile(pool: SandboxPool) -> None:
    result = pool.reconcile()
    print(f"reconcile: removed={len(result['removed'])}  added={len(result['added'])}  "
          f"池内 {len(pool.instances())} 个实例，{len(pool.idle_ids())} 个 idle")
    for sid in result["removed"]:
        print(f"  - 远端已不存在，移出 registry: {sid}")
    for sid in result["added"]:
        print(f"  + 捞回远端实例 {sid}")


def warm(host_ip: str) -> int:
    """acquire 再立即 release：保证池里至少有一个 hosts 已配好、app 探活通过的实例。"""
    print("=== 预热沙箱池（24h，用完不销毁）===")
    print(f"template : {settings.SANDBOX_TEMPLATE}")
    print(f"timeout  : {settings.SANDBOX_TIMEOUT}s (24h)")
    print(f"app 主机 : {host_ip}")
    print(f"registry : {settings.REGISTRY}\n")

    print("[ 1/4 ] 检查开发机上的 app ...")
    local = apps_host.check_ports()
    down = [a for a, ok in local.items() if not ok]
    print(f"        {len(local) - len(down)}/{len(local)} 在跑")
    if down:
        print(f"        未就绪: {', '.join(down[:6])}{'...' if len(down) > 6 else ''}")
        print("\n[FAIL] 请先在开发机启动 app：python -m src.cli.serve_apps --start")
        return 1

    pool = SandboxPool(app_host=host_ip)

    print("\n[ 2/4 ] pool.reconcile ...")
    _reconcile(pool)
    idle = pool.idle_ids()

    print(f"\n[ 3/4 ] pool.acquire —— {'复用 idle 实例' if idle else '新建实例'} ...")
    t0 = time.time()
    try:
        cfg, _sbx = pool.acquire()
    except AppsUnreachableError as e:
        print(f"\n[FAIL] {e}")
        return 1
    print(f"        sandbox_id = {cfg.sandbox_id}")
    print(f"        {'复用已有' if cfg.sandbox_id in idle else '新建'}  "
          f"apps_ready={cfg.apps_ready}  app_host={cfg.app_host}  "
          f"耗时 {time.time() - t0:.0f}s")

    print("\n[ 4/4 ] pool.release —— 实例保持 running，回到 idle ...")
    pool.release(cfg.sandbox_id)
    final = pool.get(cfg.sandbox_id)
    print(f"        status = {final.status if final else 'missing'}")

    print(f"\n=== 完成 ===\nsandbox_id : {cfg.sandbox_id}")
    print(f"app 主机   : {cfg.app_host}  （沙箱内 host.docker.internal 指向这里）")
    print(f"registry   : {settings.REGISTRY}\n")
    print("复用示例：")
    print("  from e2b import Sandbox")
    print(f"  sbx = Sandbox.connect('{cfg.sandbox_id}', timeout={settings.SANDBOX_TIMEOUT})")
    return 0


def status(pool: SandboxPool) -> int:
    _reconcile(pool)
    insts = sorted(pool.instances().values(), key=lambda c: c.created_at)
    if not insts:
        print("\n池为空。")
        return 0
    print(f"\n{'sandbox_id':34s} {'status':6s} {'apps_ready':10s} {'app_host':16s} created_at")
    for c in insts:
        print(f"{c.sandbox_id:34s} {c.status:6s} {str(c.apps_ready):10s} "
              f"{c.app_host or '-':16s} {c.created_at}")
    return 0


def release_all(pool: SandboxPool) -> int:
    """
    把所有 busy 标回 idle。

    进程被 timeout / Ctrl-C 杀掉时 finally 里的 release 跑不到，实例会永久卡在 busy，
    下次 acquire 只能新建，配额被慢慢耗光。这是人工兜底。

    registry 没有跨进程锁：另一个进程正在用的实例也会被标回 idle，于是可能被两个任务
    同时拿到。只在确认没有其他 run_task / 批跑在跑时使用。
    """
    _reconcile(pool)
    busy = [sid for sid, c in pool.instances().items() if c.status == "busy"]
    if not busy:
        print("\n没有 busy 实例。")
        return 0
    for sid in busy:
        pool.release(sid)
        print(f"  busy → idle  {sid}")
    print(f"\n已回收 {len(busy)} 个。")
    return 0


def kill(pool: SandboxPool, sandbox_ids: Optional[list[str]], yes: bool) -> int:
    """sandbox_ids 为 None 表示全部 —— 取 reconcile 之后的列表，远端捞回的也算上。"""
    _reconcile(pool)
    known = pool.instances()
    if sandbox_ids is None:
        sandbox_ids = list(known)
    targets = [sid for sid in sandbox_ids if sid in known]
    unknown = [sid for sid in sandbox_ids if sid not in known]
    for sid in unknown:
        print(f"  [跳过] 池里没有 {sid}")
    if not targets:
        return 1 if unknown else 0

    if not yes:
        print(f"\n将销毁 {len(targets)} 个实例（不可恢复）：")
        for sid in targets:
            print(f"  {sid}  status={known[sid].status}")
        print("\n确认请加 --yes")
        return 1

    for sid in targets:
        pool.kill(sid)
        print(f"  已销毁 {sid}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--warm", action="store_true", help="保证池里有一个就绪实例（默认）")
    g.add_argument("--status", action="store_true", help="列出全部实例")
    g.add_argument("--release-all", action="store_true",
                   help="把卡在 busy 的实例标回 idle（确认没有其他任务在跑时才用）")
    g.add_argument("--kill", metavar="SANDBOX_ID", nargs="+", help="销毁指定实例")
    g.add_argument("--kill-all", action="store_true", help="销毁池里全部实例")
    ap.add_argument("--yes", action="store_true", help="销毁类操作的确认")
    args = ap.parse_args()

    if args.status:
        return status(SandboxPool())
    if args.release_all:
        return release_all(SandboxPool())
    if args.kill:
        return kill(SandboxPool(), args.kill, args.yes)
    if args.kill_all:
        return kill(SandboxPool(), None, args.yes)
    return warm(apps_host.detect_host_ip())


if __name__ == "__main__":
    sys.exit(main())
