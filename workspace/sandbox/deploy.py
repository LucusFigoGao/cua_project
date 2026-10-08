"""
31-app 固定端口部署：把 CUA-Gym-Hub 的 31 个 mock app 部署到一个沙箱实例上。

端口不可改动——task 的 initial_setup.py / reward.py 里硬编码了
`http://host.docker.internal:8000` ~ `8030`。配合 ensure_host_mapping() 把
host.docker.internal 指到 127.0.0.1，这些脚本在沙箱内可以原样执行，不需要做
任何 URL 占位符替换。

实测（模板 sdt-hojglb51，8GB 盘 / 4C / 7.8GB 内存）：首次部署 170-290s
（clone + 31×install + 31×build + 起 31 个 vite preview），磁盘占用 4.5G/8G；
已部署过的实例重复调用只走健康检查，1s 返回。
"""
import json
from pathlib import Path
from typing import Optional

from e2b import Sandbox

CONFIG_PATH = Path(__file__).parent.parent / "configs" / "apps.json"
REPO_URL = "https://github.com/xlang-ai/CUA-Gym-Hub"
REPO_DIR = "/tmp/hub"
TMUX_SESSION = "cua-gym"
HOST_ALIAS = "host.docker.internal"

# npm install 串行跑（31 个并发会把 7.8GB 内存打爆）；build 用 xargs -P 8 批量并发。
BUILD_PARALLELISM = 8


def load_app_ports(path: Optional[Path] = None) -> list[tuple[str, int]]:
    """读 configs/apps.json，返回 [(app_name, port), ...]，按端口升序。"""
    with open(path or CONFIG_PATH) as f:
        data = json.load(f)
    apps = [(a["app"], a["port"]) for a in data["apps"]]
    return sorted(apps, key=lambda ap: ap[1])


def ensure_host_mapping(sbx: Sandbox, timeout: int = 20) -> None:
    """
    幂等：确保沙箱内 host.docker.internal 解析到 127.0.0.1。

    沙箱默认命令用户是 `user`(uid 1000)，写 /etc/hosts 需要 root，
    因此这一条特意用 user="root" 执行（其余部署步骤都跑在默认用户下）。
    """
    sbx.commands.run(
        f"grep -q '{HOST_ALIAS}' /etc/hosts || echo '127.0.0.1 {HOST_ALIAS}' >> /etc/hosts",
        user="root",
        timeout=timeout,
    )


def check_ports(sbx: Sandbox, apps: Optional[list[tuple[str, int]]] = None,
                timeout: int = 90) -> dict[str, bool]:
    """逐个 curl localhost:<port>，返回 {app_name: is_up}。"""
    apps = apps or load_app_ports()
    probe = "; ".join(
        f"echo \"{app} $(curl -s -o /dev/null -w '%{{http_code}}' --max-time 3 "
        f"http://127.0.0.1:{port}/)\""
        for app, port in apps
    )
    r = sbx.commands.run(probe, timeout=timeout)
    status = {app: False for app, _ in apps}
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in status:
            status[parts[0]] = parts[1] == "200"
    return status


def deploy_all_apps(sbx: Sandbox, apps: Optional[list[tuple[str, int]]] = None,
                     repo_url: str = REPO_URL, repo_dir: str = REPO_DIR,
                     clone_timeout: int = 180, install_timeout: int = 1800,
                     build_timeout: int = 1200) -> dict[str, bool]:
    """
    幂等地把 31 个 app 部署到 sbx 并起 vite preview，返回 {app_name: is_up}。

    已经部署好的实例（比如池里复用的）只会走一遍健康检查，耗时数秒。
    单个 app 起不来不抛异常——由调用方（见 SandboxPool.acquire）决定如何处置。
    """
    apps = apps or load_app_ports()
    ensure_host_mapping(sbx)

    status = check_ports(sbx, apps)
    if all(status.values()):
        return status

    names = " ".join(app for app, _ in apps)

    # clone（已存在则跳过）
    sbx.commands.run(
        f"test -d {repo_dir}/websites || git clone --depth 1 {repo_url} {repo_dir}",
        timeout=clone_timeout,
    )

    # npm install：串行，避免 OOM。单个 app 失败不中断其余。
    sbx.commands.run(
        f"for app in {names}; do "
        f"  cd {repo_dir}/websites/$app && npm install --silent >/dev/null 2>&1 "
        f"  || echo \"INSTALL_FAIL $app\"; "
        f"done",
        timeout=install_timeout,
    )

    # npm run build：xargs 控制并发数
    sbx.commands.run(
        f"for app in {names}; do echo $app; done | "
        f"xargs -I{{}} -P {BUILD_PARALLELISM} bash -c "
        f"'cd {repo_dir}/websites/{{}} && npm run build --silent "
        f"> /tmp/build_{{}}.log 2>&1 || echo BUILD_FAIL_{{}}'",
        timeout=build_timeout,
    )

    # tmux：每个 app 一个 window 跑 vite preview
    sbx.commands.run(f"tmux kill-session -t {TMUX_SESSION} 2>/dev/null; true", timeout=15)
    first_app, first_port = apps[0]
    sbx.commands.run(
        f"tmux new-session -d -s {TMUX_SESSION} -n {first_app} "
        f"\"cd {repo_dir}/websites/{first_app} && "
        f"npx vite preview --host 0.0.0.0 --port {first_port}\"",
        timeout=20,
    )
    for idx, (app, port) in enumerate(apps[1:], start=1):
        sbx.commands.run(
            f"tmux new-window -t {TMUX_SESSION}:{idx} -n {app} "
            f"\"cd {repo_dir}/websites/{app} && "
            f"npx vite preview --host 0.0.0.0 --port {port}\"",
            timeout=15,
        )

    # 等服务起来：轮询直到全部 200 或超时
    for _ in range(12):
        sbx.commands.run("sleep 3", timeout=10)
        status = check_ports(sbx, apps)
        if all(status.values()):
            break
    return status
