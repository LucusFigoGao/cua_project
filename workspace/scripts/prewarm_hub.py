"""
在 AGS 沙箱上预制 CUA-Gym-Hub 网页和任务数据, 每个实例同时运行全部所需网页。

默认部署 catalog 算出的 31 个网页(覆盖 1417 个 web 与纯网页跨应用任务), 端口 8000 起按名字排序固定分配。

用法(仓库根目录, 已设置 E2B_API_KEY / E2B_DOMAIN):
    python workspace/scripts/prewarm_hub.py --dry-run                        # 只看计划, 不连 AGS
    python workspace/scripts/prewarm_hub.py --n 1 --verify \\
        --apps notion_mock,gmail_mock,slack_mock                             # 先小规模试, 看磁盘和耗时
    python workspace/scripts/prewarm_hub.py --n 5 --verify                   # 全部 31 个网页, 5 个实例

预制完的实例保持运行(不暂停), 因为 AGS 的 resume 目前有 500 问题。重跑是幂等的, 会复用池里已有的空闲实例。
报告写入 workspace/configs/prewarm_report.json(configs/ 已在 .gitignore 里)。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from workspace.sandbox.prewarm import Paths, Plan, prewarm_instance, verify_task  # noqa: E402
from workspace.tasks import catalog  # noqa: E402

REGISTRY = REPO_ROOT / "workspace" / "configs" / "pool_registry.json"
REPORT = REPO_ROOT / "workspace" / "configs" / "prewarm_report.json"
APPROX_MB_PER_APP = 130  # 实测 node_modules 83 到 167MB


def build_plan(args):
    tasks = catalog.select_tasks(catalog.load_index())
    all_apps = catalog.required_apps(tasks)
    apps = [a.strip() for a in args.apps.split(",") if a.strip()] if args.apps else all_apps
    unknown = sorted(set(apps) - set(all_apps))
    if unknown:
        sys.exit(f"未知网页: {unknown}\n可选: {all_apps}")
    ports = catalog.port_map(all_apps)  # 端口始终按全部 31 个分配, 子集试跑和全量部署用同一套
    picked = tasks if set(apps) == set(all_apps) else catalog.tasks_within(tasks, apps)
    archive = catalog.ARCHIVE_PATH if catalog.ARCHIVE_PATH.exists() and args.archive == "local" else None
    plan = Plan(
        apps=apps,
        ports=ports,
        task_ids=[t.id for t in picked],
        replacements=catalog.replacements(all_apps, ports),
        archive_local=str(archive) if archive else None,
        min_free_mb=args.min_free_mb,
        install_workers=args.install_workers,
        skip_data=args.skip_data,
    )
    return plan, picked


def print_plan(plan, picked, n):
    print(f"计划: {len(plan.apps)} 个网页, {len(plan.task_ids)} 个任务, {n} 个实例")
    print(f"端口: {min(plan.ports[a] for a in plan.apps)} 到 {max(plan.ports[a] for a in plan.apps)} (按名字排序固定分配)")
    print(f"任务数据: {'上传本地压缩包' if plan.archive_local else '从 HF 下载压缩包'}, 一次扫描提取全部任务")
    est = len(plan.apps) * APPROX_MB_PER_APP
    print(f"每个实例 node_modules 约需 {est / 1024:.1f}GB 磁盘(沙箱系统盘约 8GB, 剩余不足 {plan.min_free_mb}MB 时会停止安装并报告)")


def run_one(cfg, sbx, plan, picked, verify):
    from workspace.sandbox.shells import SandboxShell

    shell = SandboxShell(sbx)
    paths = Paths()
    try:
        rep = prewarm_instance(shell, plan, paths)
    except Exception as e:  # noqa: BLE001
        return {"sandbox_id": cfg.sandbox_id, "ok": False, "error": f"{type(e).__name__}: {e}"}
    rep["sandbox_id"] = cfg.sandbox_id
    if verify and rep.get("data", {}).get("ok", plan.skip_data):
        bad = set(rep.get("data", {}).get("unresolved", {}))
        ok_ports = set(rep.get("ports_ok", []))
        samples = [t for t in catalog.sample_tasks(picked, plan.apps) if t.id not in bad and set(t.apps) <= ok_ports]
        rep["verify"] = [verify_task(shell, paths, t.id) for t in samples]  # 脚本共用 /tmp/task_web_sid, 必须串行
    return rep


def summarize(reports):
    print("\n" + "=" * 60)
    for r in reports:
        sid = r.get("sandbox_id", "?")[:16]
        if "error" in r and "apps" not in r:
            print(f"[{sid}] 失败: {r['error']}")
            continue
        apps = r.get("apps", [])
        failed = [a for a in apps if not a["ok"]]
        data = r.get("data", {})
        print(
            f"[{sid}] {'OK' if r['ok'] else '有问题'}  端口 {len(r.get('ports_ok', []))}/{len(apps)}  "
            f"数据 {data.get('extracted', '-')}/{data.get('requested', '-')}  "
            f"磁盘剩余 {r.get('disk_free_mb_start')}MB -> {r.get('disk_free_mb_end')}MB  用时 {r.get('seconds')}s"
        )
        for a in failed:
            print(f"    - {a['app']}: {a.get('skipped') or a.get('error', '')[:160]}")
        if data.get("unresolved"):
            print(f"    - 有 {len(data['unresolved'])} 个任务替换后仍有占位符, 在该实例上跑不了(用 unresolved 字段查看)")
        v = r.get("verify")
        if v is not None:
            good = [x for x in v if x["ok"]]
            print(f"    验证任务 {len(good)}/{len(v)} 通过")
            for x in v:
                if not x["ok"]:
                    print(f"    - {x['task_id']}: {x.get('error', '')[:160]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=1, help="实例数")
    ap.add_argument("--apps", default="", help="逗号分隔的网页, 默认全部 31 个")
    ap.add_argument("--verify", action="store_true", help="预制后抽样跑任务的 initial_setup 和 reward")
    ap.add_argument("--skip-data", action="store_true", help="只部署网页, 不处理任务数据")
    ap.add_argument("--archive", choices=["local", "hf"], default="local", help="压缩包来源: 上传本地文件, 或让实例从 HF 下载")
    ap.add_argument("--min-free-mb", type=int, default=1500)
    ap.add_argument("--install-workers", type=int, default=3, help="单个实例内同时安装的网页数")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    plan, picked = build_plan(args)
    print_plan(plan, picked, args.n)
    if args.dry_run:
        return

    from workspace.sandbox.shells import configure_e2b

    configure_e2b()
    from workspace.sandbox.pool import SandboxPool

    pool = SandboxPool(REGISTRY, max_size=max(12, args.n))
    pool.reconcile()
    acquired, reports = [], []
    t0 = time.time()
    try:
        for i in range(args.n):
            cfg, sbx = pool.acquire(app_type=None)  # 优先复用池里的空闲实例
            acquired.append((cfg, sbx))
            print(f"实例 {i + 1}/{args.n}: {cfg.sandbox_id}")
        with ThreadPoolExecutor(max_workers=len(acquired)) as ex:
            reports = list(ex.map(lambda it: run_one(it[0], it[1], plan, picked, args.verify), acquired))
        for (cfg, _), rep in zip(acquired, reports):
            for a in rep.get("ports_ok", []):
                pool.mark_app_deployed(cfg.sandbox_id, a, plan.ports[a])
    finally:
        for cfg, sbx in acquired:
            pool.release(cfg.sandbox_id, sbx, pause=False)  # 保持运行
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(reports, ensure_ascii=False, indent=1, default=str))
    summarize(reports)
    print(f"\n总用时 {time.time() - t0:.0f}s, 详细报告: {REPORT}")


if __name__ == "__main__":
    main()
