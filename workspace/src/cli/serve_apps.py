#!/usr/bin/env python3
"""
在开发机上起 31 个 mock app，供所有沙箱共享访问。

app 是无状态静态服务，一份就够所有沙箱用。沙箱内任务脚本硬编码的
http://host.docker.internal:<port> 会被沙箱 /etc/hosts 的映射指到开发机
（见 src/sandbox/deploy.ensure_host_mapping）。

Usage:
    python -m src.cli.serve_apps --start        # clone + build + 起服务（首次较慢）
    python -m src.cli.serve_apps --status       # 看哪些在跑
    python -m src.cli.serve_apps --restart      # 重启全部
    python -m src.cli.serve_apps --stop
    python -m src.cli.serve_apps --start --force-build   # 强制重新 build
"""
import argparse
import sys
import time

from src.sandbox import apps_host


def _print_status(rep: dict, show_all: bool = False) -> None:
    print(f"开发机 IP : {rep['host_ip']}  ← 沙箱通过这个地址访问")
    print(f"服务状态  : {rep['up']}/{rep['total']} 在跑")
    if rep["down"]:
        print(f"未就绪    : {', '.join(rep['down'])}")
    if show_all:
        print()
        for app, port in sorted(rep["ports"].items(), key=lambda kv: kv[1]):
            mark = "✓" if rep["status"].get(app) else "✗"
            print(f"  {mark} {app:26s} :{port}")


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--start", action="store_true", help="clone + build + 起服务")
    g.add_argument("--stop", action="store_true")
    g.add_argument("--restart", action="store_true", help="重启全部 app")
    g.add_argument("--status", action="store_true", help="只看状态")
    ap.add_argument("--force-build", action="store_true", help="强制重新 npm build")
    ap.add_argument("--verbose", "-v", action="store_true", help="列出每个 app")
    args = ap.parse_args()

    if not any([args.start, args.stop, args.restart, args.status]):
        args.status = True

    if args.stop:
        apps_host.stop_all()
        print("已停止全部 app")
        return 0

    if args.status:
        _print_status(apps_host.status_report(), show_all=args.verbose)
        return 0

    # --start / --restart
    print("=== 在开发机上起 31 个 mock app ===")
    print(f"仓库目录 : {apps_host.REPO_DIR}")
    print(f"开发机 IP: {apps_host.detect_host_ip()}")
    print()

    t0 = time.time()
    print("[ 1/3 ] clone CUA-Gym-Hub（已存在则跳过）...")
    cloned = apps_host.ensure_repo()
    print(f"        {'已 clone' if cloned else '已存在，跳过'}  ({time.time() - t0:.0f}s)")

    print("[ 2/3 ] npm install + build（已有 dist/ 的跳过，首次约 3-5 分钟）...")
    t1 = time.time()
    build = apps_host.build_apps(force=args.force_build)
    print(f"        build={build['built']}  skipped={build['skipped']}  "
          f"({time.time() - t1:.0f}s)")
    if build["failed"]:
        print(f"        [WARN] build 失败: {', '.join(build['failed'])}")

    print("[ 3/3 ] tmux 起 vite preview ...")
    t2 = time.time()
    status = apps_host.start_all(restart=args.restart)
    up = sum(1 for v in status.values() if v)
    print(f"        {up}/{len(status)} 就绪  ({time.time() - t2:.0f}s)")

    print()
    rep = apps_host.status_report()
    _print_status(rep, show_all=args.verbose)

    if rep["up"] < rep["total"]:
        print(f"\n[WARN] 有 {rep['total'] - rep['up']} 个 app 未就绪，"
              f"查看日志: tmux attach -t {apps_host.TMUX_SESSION}")
        return 1

    print(f"\n总耗时 {time.time() - t0:.0f}s")
    print("\n下一步: python -m src.cli.manage_pool   （实例会自动把 hosts 指向本机）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
