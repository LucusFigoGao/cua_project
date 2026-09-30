"""
手动验证脚本：只跑通 SandboxPool 的生命周期机制（create/pause/resume/reconcile/kill），
不部署任何 Hub app。会产生真实的 e2b 实例创建和计费，运行前请确认。

用法: python3 workspace/sandbox/_manual_check.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandbox import SandboxPool

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "..", "configs", "pool_registry.json")


def main():
    pool = SandboxPool(REGISTRY_PATH, max_size=2)

    print("[1] acquire -> 应触发真实 Sandbox.create")
    cfg, sbx = pool.acquire()
    print("    sandbox_id:", cfg.sandbox_id, "status:", cfg.status)
    assert sbx.is_running() is True
    print("    is_running() == True  OK")

    print("[2] release(pause=True) -> 应触发 sbx.pause()")
    pool.release(cfg.sandbox_id, sbx)
    print("    registry status:", pool._instances[cfg.sandbox_id].status)

    print("[3] reconcile -> 用 Sandbox.list() 校准，确认远端状态一致")
    diff = pool.reconcile()
    print("    reconcile diff:", diff)

    print("[4] 再次 acquire -> 应复用同一个 sandbox_id（走 resume 路径）")
    cfg2, sbx2 = pool.acquire()
    print("    sandbox_id:", cfg2.sandbox_id)
    assert cfg2.sandbox_id == cfg.sandbox_id, "期望复用同一个实例，但拿到了新的"
    print("    复用成功 OK")

    print("[5] kill -> 清理")
    pool.kill(cfg2.sandbox_id)
    print("    已清理:", cfg2.sandbox_id)


if __name__ == "__main__":
    main()
