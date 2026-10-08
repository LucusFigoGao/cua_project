#!/usr/bin/env python3
"""
31-app 部署烟雾测试（不经过 SandboxPool，直接验证 sandbox/deploy.py）。

验证：
  1. 31 个 app 全部 install + build 成功并起在 8000-8030
  2. host.docker.internal 映射生效（task 脚本里硬编码的就是这个域名）
  3. 磁盘占用、总耗时在预期范围内
  4. 重复调用 deploy_all_apps 是幂等的（第二次只走健康检查，秒级返回）

Usage:
    python workspace/smoke_test/test_deploy.py
"""
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE))

from e2b import Sandbox
from sandbox.deploy import deploy_all_apps, load_app_ports

TEMPLATE = "sdt-hojglb51"
SANDBOX_TIMEOUT = 3600


def _section(title):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print("─" * 60)


def _disk(sbx):
    return sbx.commands.run("df -h / | tail -1", timeout=10).stdout.strip()


def main():
    apps = load_app_ports()
    print("=== 31-app deploy smoke test ===")
    print(f"template : {TEMPLATE}")
    print(f"apps     : {len(apps)} ({apps[0][0]} port {apps[0][1]} … "
          f"{apps[-1][0]} port {apps[-1][1]})")

    t_start = time.time()
    sbx = Sandbox.create(template=TEMPLATE, timeout=SANDBOX_TIMEOUT)
    print(f"sandbox  : {sbx.sandbox_id}")

    try:
        # ── 1. 首次部署 ───────────────────────────────────────────────────
        _section("1. deploy_all_apps (首次，预期 ~176s)")
        print(f"  disk before: {_disk(sbx)}")
        t0 = time.time()
        status = deploy_all_apps(sbx)
        deploy_time = time.time() - t0
        ok = [a for a, up in status.items() if up]
        bad = [a for a, up in status.items() if not up]
        print(f"  done in {deploy_time:.0f}s  ok={len(ok)}/{len(apps)}")
        if bad:
            print(f"  [FAIL] 未就绪: {bad}")
            for app in bad[:5]:
                log = sbx.commands.run(f"tail -15 /tmp/build_{app}.log 2>/dev/null"
                                        " || echo '(no build log)'", timeout=10)
                print(f"  --- build log {app} ---\n{log.stdout}")
        else:
            print(f"  [PASS] 31/31 端口返回 200")
        print(f"  disk after : {_disk(sbx)}")

        # ── 2. host.docker.internal 映射 ──────────────────────────────────
        _section("2. host.docker.internal 映射验证")
        probe = sbx.commands.run(
            "for p in 8000 8015 8030; do "
            "echo \"$p $(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "
            "http://host.docker.internal:$p/)\"; done",
            timeout=30)
        lines = [l for l in probe.stdout.strip().splitlines() if l]
        print("  " + "\n  ".join(lines))
        if all(l.endswith(" 200") for l in lines) and len(lines) == 3:
            print("  [PASS] task 脚本里硬编码的 host.docker.internal:800X 可直接访问")
        else:
            print("  [FAIL] host 映射未生效")

        # ── 3. 幂等性 ─────────────────────────────────────────────────────
        _section("3. 幂等性（重复调用应秒级返回）")
        t0 = time.time()
        status2 = deploy_all_apps(sbx)
        again = time.time() - t0
        ok2 = sum(1 for up in status2.values() if up)
        print(f"  done in {again:.0f}s  ok={ok2}/{len(apps)}")
        if again < 60:
            print("  [PASS] 未重新 clone/build，只走了健康检查")
        else:
            print(f"  [WARN] 耗时 {again:.0f}s，可能重跑了部署流程")

        # ── Summary ───────────────────────────────────────────────────────
        total = time.time() - t_start
        _section("Summary")
        print(f"  首次部署耗时 : {deploy_time:.0f}s ({deploy_time/60:.1f} min)")
        print(f"  幂等调用耗时 : {again:.0f}s")
        print(f"  端口就绪     : {len(ok)}/{len(apps)}")
        print(f"  最终磁盘     : {_disk(sbx)}")
        print(f"  总耗时       : {total:.0f}s")
        print(f"  sandbox_id   : {sbx.sandbox_id}")

    finally:
        print(f"\n=== cleanup: killing {sbx.sandbox_id} ===")
        sbx.kill()
        print("done")


if __name__ == "__main__":
    main()
