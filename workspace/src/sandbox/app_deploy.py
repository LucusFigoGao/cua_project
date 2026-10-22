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

REMOTE_APPS_ROOT = "/opt/apps"

# 包装原始 vite.config，给 preview server 加 allowedHosts + host 绑定。
# 原始 config 的 preview.port: 0 会被 CLI --port 覆盖，不影响。
_VITE_WRAPPER_NAME = "vite.config.allowhosts.mjs"
_VITE_WRAPPER = """\
import base from './vite.config.js'
export default {
  ...base,
  preview: {
    ...(base.preview ?? {}),
    host: '0.0.0.0',
    allowedHosts: 'all',
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
    把 _shared.tar.gz 解压到 /opt/apps/shared/（幂等）。
    shared/ 是所有 app vite.config.js 的公共依赖，只需上传一次。
    """
    r = sbx.commands.run(
        f"test -f {REMOTE_APPS_ROOT}/shared/secureMockApiPlugin.mjs && echo OK || echo MISSING",
        timeout=10)
    if "OK" in (r.stdout or ""):
        return
    bundle_path = bundle_dir / "_shared.tar.gz"
    _upload_and_extract(sbx, bundle_path, REMOTE_APPS_ROOT, timeout=timeout)


def deploy_app(sbx: Sandbox, app_name: str, port: int,
               bundle_dir: Path, timeout_npm: int = 120,
               timeout_port: int = 30) -> None:
    """
    部署单个 app 到沙箱并等待 vite preview 就绪。

    前置条件：set_loopback_host() 和 ensure_shared() 已完成。
    """
    app_dir = f"{REMOTE_APPS_ROOT}/{app_name}"
    bundle_path = bundle_dir / f"{app_name}.tar.gz"

    _upload_and_extract(sbx, bundle_path, app_dir, timeout=60)

    sbx.files.write(f"{app_dir}/{_VITE_WRAPPER_NAME}", _VITE_WRAPPER)

    sbx.commands.run(
        f"cd {app_dir} && npm ci --omit=optional --silent 2>/dev/null || true",
        timeout=timeout_npm)

    sbx.commands.run(
        f"cd {app_dir} && setsid nohup "
        f"node_modules/.bin/vite preview "
        f"--config {_VITE_WRAPPER_NAME} --port {port} --strictPort "
        f">/tmp/_vite_{app_name}.log 2>&1 </dev/null &",
        timeout=15)

    _wait_port(sbx, port, timeout=timeout_port)


def deploy_task_apps(sbx: Sandbox, spec: TaskSpec,
                     bundle_dir: Path | None = None) -> None:
    """
    为一个任务完整配置沙箱内的 app 环境：
      1. host.docker.internal → 127.0.0.1
      2. 上传 shared/
      3. 逐个部署 spec.apps 里的每个 app
    """
    bd = Path(bundle_dir or APP_BUNDLES)
    ports = app_ports()

    set_loopback_host(sbx)
    ensure_shared(sbx, bd)

    for app_name in spec.apps:
        port = ports[app_name]
        deploy_app(sbx, app_name, port, bd)


# ---------- 内部工具 ----------

def _upload_and_extract(sbx: Sandbox, bundle_path: Path,
                        dest_dir: str, timeout: int = 60) -> None:
    """上传 tarball 并解压到 dest_dir（目录自动创建）。"""
    data = bundle_path.read_bytes()
    remote_tar = f"/tmp/_cua_{bundle_path.stem}.tar.gz"
    sbx.files.write(remote_tar, data)
    sbx.commands.run(
        f"mkdir -p {dest_dir} && tar xzf {remote_tar} -C {dest_dir} && rm -f {remote_tar}",
        timeout=timeout)


def _wait_port(sbx: Sandbox, port: int, timeout: int = 30) -> None:
    """轮询直到 vite preview 在沙箱内 127.0.0.1:<port> 返回 HTTP 200。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = sbx.commands.run(
            f"curl -s -o /dev/null -w '%{{http_code}}' --max-time 2 http://127.0.0.1:{port}/",
            timeout=10)
        if (r.stdout or "").strip() == "200":
            return
        time.sleep(1)
    raise RuntimeError(
        f"app port {port} 在 {timeout}s 内未就绪，"
        f"日志：{sbx.commands.run(f'tail -5 /tmp/_vite_*.log 2>/dev/null || true', timeout=10).stdout or ''}"
    )
