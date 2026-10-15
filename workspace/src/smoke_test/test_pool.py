#!/usr/bin/env python3
"""
SandboxPool smoke test — hits real AGS API.

Tests:
  1. Sandbox.create     — 新建实例是否正常
  2. pool.acquire       — 池为空时建实例并接通开发机上的 app（写 hosts，秒级）
  3. pool.release       — release 后实例保持 running，回到 idle
  4. pool.acquire       — 复用已 idle 实例（秒级返回）
  5. pool.reconcile     — 远端校准是否正常

前置：31 个 app 要先在开发机上跑起来（python -m src.cli.serve_apps --start）。
整个脚本约 1-2 分钟。

Usage:
    python -m src.smoke_test.test_pool
"""
import time
import traceback
from pathlib import Path

from e2b import Sandbox
from src.sandbox.pool import AppsUnreachableError, SandboxPool

from src.settings import SANDBOX_TEMPLATE

# 用独立 registry，不污染生产池的 configs/sandbox_pool.json
REGISTRY = Path(__file__).parent / "_smoke_registry.json"
SANDBOX_TIMEOUT = 300

_cleanup_ids: list[str] = []


def _section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


def _ok(msg: str = ""):
    print(f"  [PASS]" + (f"  {msg}" if msg else ""))


def _fail(msg: str, exc: Exception | None = None):
    print(f"  [FAIL]  {msg}")
    if exc:
        traceback.print_exc()


def _cleanup():
    print("\n=== cleanup ===")
    for sid in _cleanup_ids:
        try:
            Sandbox.kill(sid)
            print(f"  killed  {sid}")
        except Exception as e:
            print(f"  could not kill {sid}: {e}")
    if REGISTRY.exists():
        REGISTRY.unlink()
        print(f"  removed {REGISTRY.name}")


def main():
    print("=== SandboxPool smoke test ===")
    print(f"template : {SANDBOX_TEMPLATE}")
    print(f"registry : {REGISTRY}")

    try:
        # ── 1. Sandbox.create ────────────────────────────────────────────────
        _section("1. Sandbox.create")
        try:
            sbx = Sandbox.create(
                template=SANDBOX_TEMPLATE,
                timeout=SANDBOX_TIMEOUT,
                metadata={"pool": "smoke_test"},
            )
            _cleanup_ids.append(sbx.sandbox_id)
            _ok(f"sandbox_id={sbx.sandbox_id}")
            sbx.kill()
            _cleanup_ids.remove(sbx.sandbox_id)
            _ok("kill() succeeded")
        except Exception as e:
            _fail("Sandbox.create/kill failed — cannot continue", e)
            return

        # ── 2. pool.acquire (新建 + 配好 hosts 映射) ─────────────────────────
        _section("2. pool.acquire — 池为空，新建实例并接通开发机上的 app")
        pool = SandboxPool(REGISTRY, template=SANDBOX_TEMPLATE, max_size=2,
                       timeout=SANDBOX_TIMEOUT)
        try:
            t0 = time.time()
            pool_cfg, pool_sbx = pool.acquire(block=False)
            first_elapsed = time.time() - t0
            _cleanup_ids.append(pool_cfg.sandbox_id)
            pool_sid = pool_cfg.sandbox_id
            _ok(f"acquired {pool_sid}  status={pool_cfg.status}  "
                f"apps_ready={pool_cfg.apps_ready}  app_host={pool_cfg.app_host}  "
                f"耗时 {first_elapsed:.0f}s")
            # app 装在开发机上，新实例只需写一行 hosts，不该再出现分钟级的部署耗时
            if first_elapsed > 90:
                _fail(f"新建耗时 {first_elapsed:.0f}s，疑似仍在沙箱内部署 app")
            else:
                _ok(f"新建实例 {first_elapsed:.0f}s（app 在开发机上，无需沙箱内部署）")
        except AppsUnreachableError as e:
            _fail(f"开发机上的 app 不可达，先跑 serve_apps.py --start: {e}")
            return
        except Exception as e:
            _fail("pool.acquire (create) failed — skipping pool tests", e)
            return

        # ── 3. pool.release (pause=False，保持 running) ──────────────────────
        _section("3. pool.release (pause=False — 沙箱保持 running)")
        try:
            pool.release(pool_sid)
            cfg = pool.get(pool_sid)
            _ok(f"sandbox {pool_sid}  status={cfg.status if cfg else 'missing'}")
        except Exception as e:
            _fail("pool.release failed — skipping reacquire test", e)
            return

        # ── 4. pool.acquire (复用 running 实例，不应重新部署) ────────────────
        _section("4. pool.acquire — 复用已 idle 的 running 实例")
        try:
            t0 = time.time()
            cfg2, sbx2 = pool.acquire(block=False)
            reuse_elapsed = time.time() - t0
            same = cfg2.sandbox_id == pool_sid
            _ok(f"acquired {cfg2.sandbox_id}  same_instance={same}  "
                f"apps_ready={cfg2.apps_ready}  耗时 {reuse_elapsed:.0f}s")
            if reuse_elapsed < 30:
                _ok(f"复用未重新部署（首次 {first_elapsed:.0f}s → 复用 {reuse_elapsed:.0f}s）")
            else:
                _fail(f"复用耗时 {reuse_elapsed:.0f}s，疑似重跑了部署流程")
            pool.release(cfg2.sandbox_id)
        except Exception as e:
            _fail(f"pool.acquire (reuse) failed: {e}", e)

        # ── 5. pool.reconcile ────────────────────────────────────────────────
        _section("5. pool.reconcile")
        try:
            result = pool.reconcile()
            _ok(f"removed={result['removed']}  added={result['added']}")
            print(f"  pool now tracks {len(pool.instances())} instance(s)")
        except Exception as e:
            _fail(f"reconcile failed: {e}", e)

    finally:
        _cleanup()

    print("\n=== done ===")


if __name__ == "__main__":
    main()
