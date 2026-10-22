"""
把开发机上已构建好的 app dist 产物打成 tarball，供 T3 上传进沙箱。

每个 app 打出 app_bundles/<app_name>.tar.gz，内含：
  dist/           vite preview 服务的静态文件
  package.json    scripts.preview 入口 + 依赖声明
  package-lock.json  供沙箱内 npm ci 快速安装 vite
  vite.config.*   vite 配置（可能有多个变体）

沙箱内部署流程（T3）：
  1. 上传 tarball，解压到 /opt/apps/<app_name>/
  2. npm ci --omit=optional（有 lock，跳过解析，只装 vite 等；实测约 2-3s）
  3. setsid nohup vite preview --port <port> --strictPort ...

用法：
  python -m src.cli.pack_app_bundles              # 打全部（已有则跳过）
  python -m src.cli.pack_app_bundles --force       # 强制重打全部
  python -m src.cli.pack_app_bundles --app gitlab_mock github_mock
  python -m src.cli.pack_app_bundles --websites /path/to/your/repo/websites
"""
import argparse
import sys
import tarfile
from pathlib import Path

from src.sandbox.apps_host import REPO_DIR
from src.settings import APP_BUNDLES, app_ports

# tarball 内包含哪些文件/目录（相对 app 目录）
_INCLUDE = ("dist", "package.json", "package-lock.json")
_VITE_GLOB = "vite.config.*"


def _vite_configs(app_dir: Path) -> list[Path]:
    return list(app_dir.glob(_VITE_GLOB))


def pack_one(app_name: str, websites_dir: Path, out_dir: Path,
             force: bool = False) -> str:
    """
    打包单个 app，返回状态字符串：'packed' | 'skipped' | 'missing_dist' | 'missing_app'
    """
    app_dir = websites_dir / app_name
    if not app_dir.is_dir():
        return "missing_app"
    if not (app_dir / "dist").is_dir():
        return "missing_dist"

    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = out_dir / f"{app_name}.tar.gz"
    if bundle.exists() and not force:
        return "skipped"

    with tarfile.open(bundle, "w:gz") as tar:
        for name in _INCLUDE:
            p = app_dir / name
            if p.exists():
                tar.add(p, arcname=name, recursive=True)
        for vcfg in _vite_configs(app_dir):
            tar.add(vcfg, arcname=vcfg.name)

    return "packed"


def main() -> None:
    parser = argparse.ArgumentParser(description="打包 app dist bundle")
    parser.add_argument("--app", nargs="+", metavar="APP",
                        help="只打指定的 app（默认全部）")
    parser.add_argument("--websites", type=Path, default=REPO_DIR / "websites",
                        help="app 源码目录（默认 CUA_HUB_DIR/websites）")
    parser.add_argument("--out", type=Path, default=APP_BUNDLES,
                        help="bundle 输出目录（默认 workspace/app_bundles）")
    parser.add_argument("--force", action="store_true",
                        help="已有 bundle 也强制重打")
    args = parser.parse_args()

    all_apps = list(app_ports().keys())
    targets = args.app if args.app else all_apps

    unknown = [a for a in targets if a not in set(all_apps)]
    if unknown:
        print(f"未知 app（不在 apps.json 里）：{unknown}", file=sys.stderr)
        sys.exit(1)

    results: dict[str, list[str]] = {"packed": [], "skipped": [], "missing_dist": [], "missing_app": []}
    for app in targets:
        status = pack_one(app, args.websites, args.out, force=args.force)
        results[status].append(app)
        icon = {"packed": "✓", "skipped": "·", "missing_dist": "✗", "missing_app": "✗"}[status]
        print(f"  {icon} {app:<30} {status}")

    print()
    print(f"packed={len(results['packed'])}  skipped={len(results['skipped'])}"
          f"  missing_dist={len(results['missing_dist'])}  missing_app={len(results['missing_app'])}")

    if results["missing_dist"] or results["missing_app"]:
        print("\n有 app 缺少 dist/，先在开发机运行：")
        print("  python -m src.sandbox.apps_host build")
        sys.exit(1)


if __name__ == "__main__":
    main()
