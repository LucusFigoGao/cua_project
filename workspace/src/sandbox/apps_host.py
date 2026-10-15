"""
开发机侧的 31-app 服务管理：clone → npm install → npm run build → tmux 起 vite preview。

31 个 app 跑在开发机上供所有沙箱共享，沙箱内不装 app。app 是无状态静态服务，一份够用；
沙箱只负责跑浏览器和 agent 动作，新实例秒级可用。

任务脚本硬编码的 `http://host.docker.internal:<port>` 靠沙箱内 /etc/hosts 把
host.docker.internal 指向开发机落到这里（见 deploy.ensure_host_mapping）。

并发安全：mock app 用随机 UUID 作 sid 做状态隔离（`/post?sid=x` 写、`/go?sid=x` 读），
不同沙箱 sid 不同，共享一份 app 实例不会互相污染。

实测：31 个 vite preview 合计 RSS 约 1.68GB（单个均值 18MB），沙箱访问延迟约 4ms。
再扩展主要吃磁盘（build 产物）而非内存。
"""
import os
import shlex
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional

from src.settings import app_ports

REPO_URL = "https://github.com/xlang-ai/CUA-Gym-Hub"
# 不放 /tmp（可能被系统清理，build 产物重建要几分钟），也不放 workspace/
# （build 产物有数 GB，不该和代码混在一起）。
REPO_DIR = Path(os.environ.get("CUA_HUB_DIR", "/data/workspace/cua_hub"))
TMUX_SESSION = "cua-gym-apps"
#: 早期版本用过的会话名。stop_all 一并清理，否则它们继续占着 8000-8030，
#: 新起的 vite 会顺延到 8031+，而探活看到的其实是老进程。
LEGACY_SESSIONS = ("cua-hub",)

# npm install 串行跑（31 个并发会把内存打爆）；build 用 xargs -P 批量并发。
BUILD_PARALLELISM = 8


class AppsHostError(Exception):
    pass


# ---------- 基础 ----------

def load_app_ports() -> list[tuple[str, int]]:
    """返回 [(app_name, port), ...]，按端口升序。"""
    return sorted(app_ports().items(), key=lambda ap: ap[1])


def detect_host_ip() -> str:
    """
    探测开发机上对沙箱可见的 IP。

    沙箱在 AGS 内网，走的是开发机的默认路由网卡（实测 eth1 / 21.6.127.153），
    所以用"连一个外部地址看本地端取哪个 IP"这个惯用法即可，不会误取 docker0
    的 172.17.0.1（那个沙箱访问不到）。

    可用环境变量 CUA_APP_HOST 覆盖。
    """
    override = os.environ.get("CUA_APP_HOST")
    if override:
        return override.strip()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("1.1.1.1", 80))  # 不会真的发包，只为让内核选出源地址
        return s.getsockname()[0]
    finally:
        s.close()


def _run(cmd: str, timeout: int = 300, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          timeout=timeout, check=check)


def _npm_env() -> str:
    """
    npm/node 可能装在 nvm 下，非交互 shell 的 PATH 里没有。
    这里把探测到的 node bin 目录前置到 PATH。
    """
    node = shutil.which("node")
    if node:
        return f'export PATH="{Path(node).parent}:$PATH"; '
    # nvm 默认布局兜底
    candidates = sorted(Path.home().glob(".nvm/versions/node/*/bin"), reverse=True)
    if candidates:
        return f'export PATH="{candidates[0]}:$PATH"; '
    return ""


# ---------- 探活 ----------

def check_ports(apps: Optional[list[tuple[str, int]]] = None,
                timeout: float = 3.0) -> dict[str, bool]:
    """逐个 TCP 连 127.0.0.1:<port>，返回 {app_name: is_up}。比 curl 快得多。"""
    apps = apps or load_app_ports()
    status = {}
    for app, port in apps:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            status[app] = s.connect_ex(("127.0.0.1", port)) == 0
        except OSError:
            status[app] = False
        finally:
            s.close()
    return status


def all_up(apps: Optional[list[tuple[str, int]]] = None) -> bool:
    st = check_ports(apps)
    return bool(st) and all(st.values())


# ---------- 部署 ----------

def ensure_repo(repo_dir: Path = REPO_DIR, repo_url: str = REPO_URL,
                clone_timeout: int = 600) -> bool:
    """clone CUA-Gym-Hub（已存在则跳过）。返回是否执行了 clone。"""
    repo_dir = Path(repo_dir)
    if (repo_dir / "websites").is_dir():
        return False
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    r = _run(f"git clone --depth 1 {repo_url} {repo_dir}", timeout=clone_timeout)
    if not (repo_dir / "websites").is_dir():
        raise AppsHostError(f"clone 失败: {(r.stderr or r.stdout)[-400:]}")
    return True


def build_apps(apps: Optional[list[tuple[str, int]]] = None,
               repo_dir: Path = REPO_DIR, force: bool = False,
               install_timeout: int = 3600, build_timeout: int = 2400) -> dict:
    """
    npm install + npm run build。幂等：已有 dist/ 的 app 默认跳过。

    install 串行（并发会把内存打爆），build 用 xargs -P 8 并发。
    单个 app 失败不中断其余，最后用 dist/ 是否存在来判定。
    """
    apps = apps or load_app_ports()
    repo_dir = Path(repo_dir)
    env = _npm_env()

    todo = []
    for app, _ in apps:
        d = repo_dir / "websites" / app
        if not d.is_dir():
            continue
        if force or not (d / "dist").is_dir():
            todo.append(app)

    if not todo:
        return {"installed": 0, "built": 0, "skipped": len(apps), "failed": []}

    names = " ".join(todo)
    # npm install：串行
    _run(f'{env}for app in {names}; do '
         f'  cd {repo_dir}/websites/$app && npm install --silent >/dev/null 2>&1 '
         f'  || echo "INSTALL_FAIL $app"; '
         f'done', timeout=install_timeout)
    # npm run build：并发
    _run(f'{env}for app in {names}; do echo $app; done | '
         f'xargs -I{{}} -P {BUILD_PARALLELISM} bash -c '
         f"'cd {repo_dir}/websites/{{}} && npm run build --silent "
         f"> /tmp/cua_build_{{}}.log 2>&1 || echo BUILD_FAIL_{{}}'",
         timeout=build_timeout)

    failed = [a for a in todo if not (repo_dir / "websites" / a / "dist").is_dir()]
    return {"installed": len(todo), "built": len(todo) - len(failed),
            "skipped": len(apps) - len(todo), "failed": failed}


#: 包装 config 的文件名。放在 app 自己目录下，与原 vite.config 同级。
ALLOWHOSTS_CONFIG = "vite.config.allowhosts.mjs"

#: 包装 config 的内容模板。`{orig}` 替换为原配置文件名（含扩展名）。
#
# vite 5 的 preview server 带 Host 白名单，默认只放行 localhost 和裸 IP。沙箱统一用
# http://host.docker.internal:<port> 访问，这是个主机名，没显式配 allowedHosts 的 app
# 会返回 403（本机 curl 127.0.0.1 却是 200）。`vite preview` 没有 --allowedHosts 开关，
# 只能从配置走。
#
# 合并而非替换原配置：原 vite.config 的 plugins 提供 /post /state /go 三个 mock API，
# 任务的 initial_setup.py / reward.py 全靠它们读写状态。
_ALLOWHOSTS_TEMPLATE = """\
// 由 workspace/src/sandbox/apps_host.py 自动生成，请勿手改。
// 作用：在原 vite 配置之上追加 preview.allowedHosts，放行 host.docker.internal。
// 原配置的 plugins（/post /state /go 等 mock API）通过展开原对象保留。
import base from './{orig}'

const cfg = typeof base === 'function'
  ? base({{ command: 'serve', mode: 'production' }})
  : base

export default {{
  ...cfg,
  preview: {{ ...(cfg.preview || {{}}), allowedHosts: true }},
}}
"""


def ensure_allowed_hosts(apps: Optional[list[tuple[str, int]]] = None,
                         repo_dir: Path = REPO_DIR) -> list[str]:
    """
    给缺 allowedHosts 的 app 生成包装 config，返回被处理的 app 名列表。

    幂等：内容不变则不重写。每次 start_all 前调用，所以仓库重新 clone 后也会自动补上。
    """
    apps = apps or load_app_ports()
    repo_dir = Path(repo_dir)
    patched: list[str] = []

    for app, _ in apps:
        app_dir = repo_dir / "websites" / app
        if not app_dir.is_dir():
            continue

        origs = [p for p in sorted(app_dir.glob("vite.config.*"))
                 if p.name != ALLOWHOSTS_CONFIG]
        if not origs:
            continue

        # 原配置已经自己声明了 allowedHosts，不用管。
        if any("allowedHosts" in p.read_text(errors="ignore") for p in origs):
            continue

        content = _ALLOWHOSTS_TEMPLATE.format(orig=origs[0].name)
        target = app_dir / ALLOWHOSTS_CONFIG
        if not target.exists() or target.read_text(errors="ignore") != content:
            target.write_text(content)
        patched.append(app)

    return patched


def start_all(apps: Optional[list[tuple[str, int]]] = None,
              repo_dir: Path = REPO_DIR, restart: bool = False,
              wait: float = 90.0) -> dict[str, bool]:
    """
    用 tmux 起 31 个 vite preview，每个 app 一个 window。

    必须 --host 0.0.0.0：默认只听 localhost，沙箱就访问不到了。
    """
    apps = apps or load_app_ports()
    repo_dir = Path(repo_dir)
    env = _npm_env()
    patched = set(ensure_allowed_hosts(apps, repo_dir))

    if all_up(apps) and not restart:
        return check_ports(apps)

    # 走到这里说明要重起或当前没全起来。两种情况都先清干净再建会话，
    # 否则残留进程占着端口会让 --strictPort 直接失败。
    stop_all(apps)

    # PATH 的 export 必须放进 tmux 窗口内部执行的命令里，不能只加在 tmux 自己的命令行
    # 前面：tmux 窗口继承的是 tmux server 的环境，而 server 可能更早、在没有 nvm PATH
    # 的情况下启动，那样 npx 会找不到。
    def _win_cmd(app: str, port: int) -> str:
        # 缺 allowedHosts 的 app 走包装 config，否则沙箱用 host.docker.internal 访问会 403。
        cfg = f" --config {ALLOWHOSTS_CONFIG}" if app in patched else ""
        # --strictPort：端口被占时直接报错退出。默认行为是顺延到下一个空闲端口，
        # 那样 app 会跑在非约定端口上，而任务脚本硬编码了端口号，等于静默错配。
        return (f"cd {repo_dir}/websites/{app} && {env}"
                f"exec npx vite preview{cfg} --strictPort "
                f"--host 0.0.0.0 --port {port}")

    first_app, first_port = apps[0]
    _run(f"tmux new-session -d -s {TMUX_SESSION} -n {first_app} "
         f"{shlex.quote(_win_cmd(first_app, first_port))}", timeout=60)
    for idx, (app, port) in enumerate(apps[1:], start=1):
        _run(f"tmux new-window -t {TMUX_SESSION}:{idx} -n {app} "
             f"{shlex.quote(_win_cmd(app, port))}", timeout=60)

    deadline = time.time() + wait
    status = check_ports(apps)
    while time.time() < deadline and not all(status.values()):
        time.sleep(3)
        status = check_ports(apps)
    return status


def stop_all(apps: Optional[list[tuple[str, int]]] = None) -> None:
    """
    停掉所有 mock app：当前会话 + 历史会话名 + 占着目标端口的游离进程。

    后两类必须一并清理。残留进程占着 8000-8030 时，新进程起来会顺延到 8031+，
    于是「31/31 在跑」其实是老进程在应答，新配置从未生效。
    """
    for name in (TMUX_SESSION, *LEGACY_SESSIONS):
        _run(f"tmux kill-session -t {name} 2>/dev/null; true", timeout=30)

    # 兜底：杀掉仍监听目标端口的 vite preview（可能由已消失的会话留下）。
    for _, port in (apps or load_app_ports()):
        _run(
            f"pids=$(ss -ltnp 2>/dev/null | grep ':{port} ' "
            f"| grep -oP 'pid=\\K[0-9]+' | sort -u); "
            f'for p in $pids; do '
            f'  if ps -o cmd= -p "$p" | grep -q "vite preview"; then kill "$p"; fi; '
            f"done; true",
            timeout=20,
        )
    time.sleep(2)


def serve(apps: Optional[list[tuple[str, int]]] = None, repo_dir: Path = REPO_DIR,
          force_build: bool = False, restart: bool = False) -> dict:
    """一条龙：clone → build → 起服务。返回 {status, cloned, build, host_ip}。"""
    apps = apps or load_app_ports()
    cloned = ensure_repo(repo_dir)
    build = build_apps(apps, repo_dir, force=force_build)
    status = start_all(apps, repo_dir, restart=restart)
    return {"status": status, "cloned": cloned, "build": build,
            "host_ip": detect_host_ip(),
            "up": sum(1 for v in status.values() if v), "total": len(apps)}


def status_report(apps: Optional[list[tuple[str, int]]] = None) -> dict:
    apps = apps or load_app_ports()
    st = check_ports(apps)
    ports = dict(apps)
    return {
        "host_ip": detect_host_ip(),
        "up": sum(1 for v in st.values() if v),
        "total": len(apps),
        "down": [a for a, ok in st.items() if not ok],
        "ports": ports,
        "status": st,
    }
