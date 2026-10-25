"""
在 AGS 沙箱内部署 mock app 并起 vite preview 服务。

部署结构（沙箱内）：
  /opt/apps/
    shared/
      secureMockApiPlugin.mjs   ← 所有 app 共用
    <app_name>/
      dist/                     ← 静态文件，vite preview 服务对象
      package.json
      package-lock.json
      vite.config.js            ← 原始 config（引用 ../../shared/）
      vite.config.allowhosts.mjs ← 包装 config，加 preview.allowedHosts
      node_modules/             ← npm ci 产物（只装 vite 等 devDeps）

host.docker.internal 映射：
  任务脚本硬编码 http://host.docker.internal:80XX，
  迁移后写 /etc/hosts → 127.0.0.1，请求落到沙箱本地的 vite preview。

调用方式（task.py）：
  deploy_task_apps(sbx, spec)   # 一次部署全部所需 app
"""
import time
from pathlib import Path

from e2b import Sandbox

from src.settings import APP_BUNDLES, HOST_ALIAS, app_ports
from src.tasks.catalog import TaskSpec

# 复现仓库目录结构：
#   /tmp/cua_apps/
#     shared/                 ← secureMockApiPlugin.mjs
#     websites/
#       <app_name>/           ← vite.config.js 里 ../../shared/ 能正确解析
REMOTE_APPS_ROOT = "/tmp/cua_apps/websites"
_REMOTE_BASE = "/tmp/cua_apps"  # shared 和 websites 的共同父目录

# 包装原始 vite.config，给 preview server 加 allowedHosts + host 绑定。
# 原始 config 的 preview.port: 0 会被 CLI --port 覆盖，不影响。
_VITE_WRAPPER_NAME = "vite.config.allowhosts.mjs"
# wrapper config 不继承原始 vite.config.js（避免触发 dev-only import），
# 只引入 secureMockApiPlugin 提供 /post /go /state 端点。
# allowedHosts: true 是 vite 5.4 的布尔值，让 host.docker.internal 能访问。
_VITE_WRAPPER = """\
import { secureMockApiPlugin } from '../../shared/secureMockApiPlugin.mjs';
export default {
  plugins: [secureMockApiPlugin()],
  preview: {
    host: '0.0.0.0',
    allowedHosts: true,
  },
}
"""


def set_loopback_host(sbx: Sandbox, timeout: int = 30) -> None:
    """
    把 host.docker.internal 映射到 127.0.0.1。

    任务脚本访问 http://host.docker.internal:80XX，迁移后 app 跑在沙箱本地，
    所以要指向 loopback 而不是开发机 IP。deploy.ensure_host_mapping 是幂等的，
    这里直接传 host_ip="127.0.0.1"。
    """
    from src.sandbox.deploy import ensure_host_mapping
    ensure_host_mapping(sbx, host_ip="127.0.0.1", timeout=timeout)


def ensure_shared(sbx: Sandbox, bundle_dir: Path, timeout: int = 60) -> None:
    """
    把 _shared.tar.gz 解压到 /tmp/cua_apps/shared/（幂等）。
    shared/ 是所有 app vite.config.js 的公共依赖，只需上传一次。
    """
    r = sbx.commands.run(
        f"test -f {_REMOTE_BASE}/shared/secureMockApiPlugin.mjs && echo OK || echo MISSING",
        timeout=10, request_timeout=30)
    if "OK" in (r.stdout or ""):
        return
    bundle_path = bundle_dir / "_shared.tar.gz"
    _upload_and_extract(sbx, bundle_path, _REMOTE_BASE, timeout=timeout)


def deploy_app(sbx: Sandbox, app_name: str, port: int,
               bundle_dir: Path, timeout_npm: int = 300,
               timeout_port: int = 60) -> None:
    """
    部署单个 app 到沙箱并等待 vite preview 就绪。

    前置条件：set_loopback_host() 和 ensure_shared() 已完成。
    """
    app_dir = f"{REMOTE_APPS_ROOT}/{app_name}"
    bundle_path = bundle_dir / f"{app_name}.tar.gz"

    _upload_and_extract(sbx, bundle_path, app_dir, timeout=60)

    sbx.files.write(f"{app_dir}/{_VITE_WRAPPER_NAME}", _VITE_WRAPPER)

    # npm ci 后台跑 + 轮询完成标记。
    # 关键：整个 bash -c 的 stdout/stderr 都重定向到 /dev/null，
    # 让 e2b gRPC 流立即收到 EOF，不会因后台进程长时间运行而被 idle timeout 断掉。
    done_flag = f"/tmp/_npmci_{app_name}.done"
    sbx.commands.run(
        f"bash -c 'rm -f {done_flag}; "
        f"cd {app_dir} && npm ci "
        f">>/tmp/_npmci_{app_name}.log 2>&1 "
        f"&& echo OK > {done_flag} || echo FAIL > {done_flag}' "
        f">/dev/null 2>&1 &",
        timeout=15, request_timeout=30)
    _wait_file(sbx, done_flag, timeout=timeout_npm)

    sbx.commands.run(
        f"bash -c 'cd {app_dir} && setsid "
        f"node_modules/.bin/vite preview "
        f"--config {_VITE_WRAPPER_NAME} --port {port} --strictPort "
        f">/tmp/_vite_{app_name}.log 2>&1 </dev/null &' "
        f">/dev/null 2>&1",
        timeout=15, request_timeout=30)

    _wait_port(sbx, port, timeout=timeout_port)


def deploy_task_apps(sbx: Sandbox, spec: TaskSpec,
                     bundle_dir: Path | None = None) -> None:
    """
    为一个任务完整配置沙箱内的 app 环境：
      1. host.docker.internal → 127.0.0.1
      2. 上传 shared/
      3. 并发上传所有 app bundle + 启动 npm ci
      4. 等所有 npm ci 完成后并发起所有 vite preview
      5. 并发探活所有端口
    """
    bd = Path(bundle_dir or APP_BUNDLES)
    ports = app_ports()

    set_loopback_host(sbx)
    ensure_shared(sbx, bd)

    app_ports_list = [(app, ports[app]) for app in spec.apps]

    # 阶段 1：并发上传 bundle + 写 wrapper config + 启动 npm ci（后台）
    for app_name, _ in app_ports_list:
        app_dir = f"{REMOTE_APPS_ROOT}/{app_name}"
        bundle_path = bd / f"{app_name}.tar.gz"
        _upload_and_extract(sbx, bundle_path, app_dir, timeout=60)
        sbx.files.write(f"{app_dir}/{_VITE_WRAPPER_NAME}", _VITE_WRAPPER)
        done_flag = f"/tmp/_npmci_{app_name}.done"
        sbx.commands.run(
            f"bash -c 'rm -f {done_flag}; "
            f"cd {app_dir} && npm ci "
            f">>/tmp/_npmci_{app_name}.log 2>&1 "
            f"&& echo OK > {done_flag} || echo FAIL > {done_flag}' "
            f">/dev/null 2>&1 &",
            timeout=15, request_timeout=30)

    # 阶段 2：等所有 npm ci 完成，然后起 vite preview
    for app_name, port in app_ports_list:
        app_dir = f"{REMOTE_APPS_ROOT}/{app_name}"
        done_flag = f"/tmp/_npmci_{app_name}.done"
        _wait_file(sbx, done_flag, timeout=300)
        sbx.commands.run(
            f"bash -c 'cd {app_dir} && setsid "
            f"node_modules/.bin/vite preview "
            f"--config {_VITE_WRAPPER_NAME} --port {port} --strictPort "
            f">/tmp/_vite_{app_name}.log 2>&1 </dev/null &' "
            f">/dev/null 2>&1",
            timeout=15, request_timeout=30)

    # 阶段 3：并发探活所有端口
    for app_name, port in app_ports_list:
        _wait_port(sbx, port, timeout=120)


# ---------- 内部工具 ----------

def _upload_and_extract(sbx: Sandbox, bundle_path: Path,
                        dest_dir: str, timeout: int = 60) -> None:
    """上传 tarball 并解压到 dest_dir（目录自动创建）。"""
    data = bundle_path.read_bytes()
    remote_tar = f"/tmp/_cua_{bundle_path.name}"
    sbx.files.write(remote_tar, data)
    sbx.commands.run(
        f"mkdir -p {dest_dir} && tar xzf {remote_tar} -C {dest_dir} && rm -f {remote_tar}",
        timeout=timeout, request_timeout=timeout + 30)


def _wait_file(sbx: Sandbox, path: str, timeout: int = 300) -> None:
    """轮询直到沙箱内 path 文件出现，用于等待后台命令完成。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = sbx.commands.run(
            f"cat {path} 2>/dev/null || true", timeout=10, request_timeout=30)
        content = (r.stdout or "").strip()
        if content == "OK":
            return
        if content == "FAIL":
            log = sbx.commands.run(
                f"tail -20 {path.replace('.done', '.log')} 2>/dev/null || true",
                timeout=10, request_timeout=30).stdout or ""
            raise RuntimeError(f"npm ci 失败。日志：\n{log}")
        time.sleep(2)
    raise RuntimeError(f"等待 {path} 超时（{timeout}s）")


def _wait_port(sbx: Sandbox, port: int, timeout: int = 30) -> None:
    """轮询直到 vite preview 在沙箱内 127.0.0.1:<port> 返回 HTTP 200。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        # || true 防止 curl 非零退出码被 e2b SDK 当异常抛出
        r = sbx.commands.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 2 "
            f"http://127.0.0.1:{port}/ || true",
            timeout=10, request_timeout=30)
        if (r.stdout or "").strip() == "200":
            return
        time.sleep(1)
    # 超时后读日志帮助诊断
    log_out = sbx.commands.run(
        "tail -20 /tmp/_vite_*.log 2>/dev/null || true",
        timeout=10, request_timeout=30).stdout or ""
    raise RuntimeError(
        f"app port {port} 在 {timeout}s 内未就绪。vite 日志：\n{log_out}"
    )
