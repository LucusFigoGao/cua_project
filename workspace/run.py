#!/usr/bin/env python3
"""
取一个带 31 个 mock app 的沙箱实例（24 小时过期），用完归还但**不销毁**。

走 SandboxPool.acquire 的正常复用路径：
  1. reconcile  —— 以远端 Sandbox.list(metadata={"pool": "cua_gym"}) 为真相源校准本地 registry，
                   把已经在跑的实例捞回池里（本地 registry 丢了也能恢复）
  2. acquire    —— 池里有 idle 实例就直接复用（秒级，只做一遍健康检查）；
                   没有才新建 + 部署 31 个 app（首次约 3-5 分钟）
  3. release    —— pause=False，实例保持 running 回到 idle，下次 run.py 可以直接复用

registry 落在 workspace/configs/sandbox_pool.json，后续脚本可直接
Sandbox.connect(sandbox_id) 复用。

Usage:
    python workspace/run.py
"""
import json
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).parent
sys.path.insert(0, str(WORKSPACE))

from sandbox.pool import SandboxPool

TEMPLATE = "sdt-hojglb51"
TIMEOUT = 86400  # 24 小时
MAX_SIZE = 12
REGISTRY = WORKSPACE / "configs" / "sandbox_pool.json"


def main():
    print("=== 取一个沙箱实例（24h，用完不销毁）===")
    print(f"template : {TEMPLATE}")
    print(f"timeout  : {TIMEOUT}s (24h)")
    print(f"registry : {REGISTRY}")
    print()

    pool = SandboxPool(REGISTRY, template=TEMPLATE, max_size=MAX_SIZE, timeout=TIMEOUT)

    # ── 1. 校准 registry：把远端还在跑的实例捞回池里 ──────────────────────────
    print("[ 1/3 ] pool.reconcile —— 以远端为真相源校准 registry ...")
    result = pool.reconcile()
    idle = [c.sandbox_id for c in pool._instances.values() if c.status == "idle"]
    print(f"        removed={len(result['removed'])}  added={len(result['added'])}  "
          f"池内 {len(pool._instances)} 个实例，其中 {len(idle)} 个 idle")
    for sid in result["added"]:
        print(f"        + 捞回远端实例 {sid}")

    # ── 2. acquire：有 idle 就复用，没有才新建 + 部署 ─────────────────────────
    print()
    if idle:
        print("[ 2/3 ] pool.acquire —— 池内有 idle 实例，预期复用（秒级）...")
    else:
        print("[ 2/3 ] pool.acquire —— 池内无 idle 实例，将新建并部署 31 个 app（约 3-5 分钟）...")
    t0 = time.time()
    cfg, sbx = pool.acquire()
    elapsed = time.time() - t0
    reused = cfg.sandbox_id in idle
    print(f"        sandbox_id = {cfg.sandbox_id}")
    print(f"        {'复用已有实例' if reused else '新建实例'}  "
          f"apps_ready={cfg.apps_ready}  耗时 {elapsed:.0f}s")

    # ── 3. release：保持 running 回到 idle，不 kill ───────────────────────────
    print()
    print("[ 3/3 ] pool.release(pause=False) —— 实例保持 running，回到 idle ...")
    pool.release(cfg.sandbox_id, sbx=sbx, pause=False)
    final = pool._instances.get(cfg.sandbox_id)
    print(f"        status = {final.status if final else 'missing'}（实例未销毁）")

    print()
    print("=== 完成 ===")
    print(f"sandbox_id : {cfg.sandbox_id}")
    print(f"apps       : {len(cfg.deployed_apps)}/31 已登记  apps_ready={cfg.apps_ready}")
    print(f"registry   : {REGISTRY}")
    print()
    print("复用示例：")
    print("  from e2b import Sandbox")
    print(f"  sbx = Sandbox.connect('{cfg.sandbox_id}', timeout={TIMEOUT})")
    print()
    print("再次运行 run.py 会直接复用这个实例，不会重新部署。")


if __name__ == "__main__":
    main()
