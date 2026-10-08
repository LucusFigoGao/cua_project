#!/usr/bin/env python3
"""
SandboxPool smoke test — hits real AGS API.

Tests:
  1. Sandbox.create          — 新建实例是否正常
  2. pool.acquire (新建)     — 池为空时建实例并自动部署 31 个 app（~3-5 min）
  3. pool.release (pause=False) — release 后实例保持 running，回到 idle
  4. pool.acquire (复用)     — 复用已 idle 实例，且不重新部署（秒级返回）
  5. pool.reconcile          — 远端校准是否正常

注意：第 2 步会触发一次完整的 31-app 部署，整个脚本跑完约需 5-6 分钟。

Usage:
    python workspace/smoke_test/test_pool.py
"""
import sys
import time
import traceback
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE))

from e2b import Sandbox
from sandbox.pool import SandboxPool

TEMPLATE = "sdt-hojglb51"
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
    print(f"template : {TEMPLATE}")
    print(f"registry : {REGISTRY}")

    try:
        # ── 1. Sandbox.create ────────────────────────────────────────────────
        _section("1. Sandbox.create")
        try:
            sbx = Sandbox.create(
                template=TEMPLATE,
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

        # ── 2. pool.acquire (新建 + 自动部署 31 个 app) ──────────────────────
        _section("2. pool.acquire — 池为空，新建实例并自动部署 31 个 app")
        pool = SandboxPool(REGISTRY, template=TEMPLATE, max_size=2, timeout=SANDBOX_TIMEOUT)
        try:
            t0 = time.time()
            pool_cfg, pool_sbx = pool.acquire(block=False)
            first_elapsed = time.time() - t0
            _cleanup_ids.append(pool_cfg.sandbox_id)
            pool_sid = pool_cfg.sandbox_id
            _ok(f"acquired {pool_sid}  status={pool_cfg.status}  "
                f"apps_ready={pool_cfg.apps_ready}  耗时 {first_elapsed:.0f}s")
            if not pool_cfg.apps_ready:
                _fail("apps_ready=False —— acquire 本应 kill 坏实例后重建")
        except Exception as e:
            _fail("pool.acquire (create) failed — skipping pool tests", e)
            return

        # ── 3. pool.release (pause=False，保持 running) ──────────────────────
        _section("3. pool.release (pause=False — 沙箱保持 running)")
        try:
            pool.release(pool_sid, sbx=pool_sbx, pause=False)
            cfg = pool._instances.get(pool_sid)
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
            pool.release(cfg2.sandbox_id, sbx=sbx2, pause=False)
        except Exception as e:
            _fail(f"pool.acquire (reuse) failed: {e}", e)

        # ── 5. pool.reconcile ────────────────────────────────────────────────
        _section("5. pool.reconcile")
        try:
            result = pool.reconcile()
            _ok(f"removed={result['removed']}  added={result['added']}")
            print(f"  pool now tracks {len(pool._instances)} instance(s)")
        except Exception as e:
            _fail(f"reconcile failed: {e}", e)

    finally:
        _cleanup()

    print("\n=== done ===")


if __name__ == "__main__":
    main()
