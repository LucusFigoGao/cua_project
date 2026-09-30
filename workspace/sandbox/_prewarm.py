"""
预热脚本：创建 N 个沙箱实例，每个部署同一个 mock app，完成后保持运行（不 pause）。

resume 目前在 AGS 侧还有已知的 500 问题（见项目记忆 ags_resume_blocked），
所以这里先不 pause，部署完直接留着跑，等 AGS 修复后再切换成 pause。
会产生真实的 e2b 实例创建 + clone/npm install 开销，运行前请确认。

用法: python3 workspace/sandbox/_prewarm.py [--n 5] [--app notion_mock]
"""
import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(WORKSPACE_DIR)
sys.path.insert(0, WORKSPACE_DIR)
sys.path.insert(0, ROOT_DIR)

from sandbox import SandboxPool
from gym.utils import SandboxEnv, SandboxConfig

REGISTRY_PATH = os.path.join(WORKSPACE_DIR, "configs", "pool_registry.json")
PORT = 5173


def deploy_one(pool: SandboxPool, cfg, sbx, app_type: str) -> str:
    env = SandboxEnv(sbx=sbx, config=SandboxConfig(sandbox_id=cfg.sandbox_id))
    env.deploy_hub_app(app_type, port=PORT)
    pool.mark_app_deployed(cfg.sandbox_id, app_type, PORT)
    return cfg.sandbox_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--app", type=str, default="notion_mock")
    args = parser.parse_args()

    pool = SandboxPool(REGISTRY_PATH, max_size=max(12, args.n))

    print(f"[1] 创建 {args.n} 个实例 ...")
    acquired = []
    for i in range(args.n):
        cfg, sbx = pool.acquire(app_type=args.app)
        print(f"    ({i + 1}/{args.n}) {cfg.sandbox_id}")
        acquired.append((cfg, sbx))

    print(f"[2] 并发部署 {args.app} ...")
    ready, failed = [], []
    with ThreadPoolExecutor(max_workers=args.n) as pool_exec:
        futures = {pool_exec.submit(deploy_one, pool, cfg, sbx, args.app): cfg for cfg, sbx in acquired}
        for fut in as_completed(futures):
            cfg = futures[fut]
            try:
                sid = fut.result()
                print(f"    ready: {sid}")
                ready.append(sid)
            except Exception as e:
                print(f"    FAILED: {cfg.sandbox_id} -> {e}")
                failed.append(cfg.sandbox_id)

    print("[3] release(pause=False) -> 标记 idle，但保持运行")
    for cfg, sbx in acquired:
        pool.release(cfg.sandbox_id, sbx, pause=False)

    print()
    print(f"完成：{len(ready)}/{args.n} 部署成功，保持运行状态。")
    for sid in ready:
        print(" -", sid)
    if failed:
        print(f"失败 {len(failed)} 个：", failed)


if __name__ == "__main__":
    main()
