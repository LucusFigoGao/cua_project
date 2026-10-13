#!/usr/bin/env python3
"""
取一个沙箱实例（24h 过期），用完归还但不销毁。

31 个 mock app 跑在开发机上（见 serve_apps.py），沙箱只需写一行 /etc/hosts 把
host.docker.internal 指到开发机，秒级就绪。

流程：探活开发机 app → reconcile 校准 registry → acquire（有 idle 就复用）→
release 回到 idle。registry 落在 configs/sandbox_pool.json，后续脚本可直接
Sandbox.connect(sandbox_id) 复用。

Usage:
    python -m src.cli.run
"""
import sys
import time

from src import settings
from src.sandbox import apps_host
from src.sandbox.pool import AppsUnreachableError, SandboxPool


def main() -> int:
    host_ip = apps_host.detect_host_ip()
    print("=== 取一个沙箱实例（24h，用完不销毁）===")
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

    print("\n[ 2/4 ] pool.reconcile —— 以远端为真相源校准 registry ...")
    result = pool.reconcile()
    idle = pool.idle_ids()
    print(f"        removed={len(result['removed'])}  added={len(result['added'])}  "
          f"池内 {len(pool.instances())} 个实例，{len(idle)} 个 idle")
    for sid in result["added"]:
        print(f"        + 捞回远端实例 {sid}")

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


if __name__ == "__main__":
    sys.exit(main())
