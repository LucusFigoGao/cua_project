"""
沙箱侧的 app 接入：把沙箱内的 host.docker.internal 指到开发机，并探活。

31 个 app 跑在开发机上（见 sandbox/apps_host.py），沙箱内不装 app。任务脚本硬编码了
`http://host.docker.internal:8000`~`8030`，这里把该主机名解析到开发机 IP，请求自然落
到那边。实测沙箱→开发机 HTTP 200、延迟约 4ms。

并发安全：mock app 用随机 UUID 作 sid 隔离状态（`/post?sid=x` 写、`/go?sid=x` 读），
多个沙箱共享同一份 app 不会互相污染。
"""
from typing import Optional

from e2b import Sandbox

from src.sandbox import apps_host
from src.settings import HOST_ALIAS, app_ports


def load_app_ports() -> list[tuple[str, int]]:
    """返回 [(app_name, port), ...]，按端口升序。"""
    return sorted(app_ports().items(), key=lambda ap: ap[1])


def ensure_host_mapping(sbx: Sandbox, host_ip: Optional[str] = None,
                        timeout: int = 30) -> str:
    """
    幂等：让沙箱内 host.docker.internal 解析到 host_ip（默认 = 开发机 IP）。

    两个坑：
      1. 写 /etc/hosts 要 root（沙箱默认命令用户是 uid 1000 的 `user`）。
      2. /etc/hosts 在沙箱里是 bind mount，`sed -i` 会报 "Device or resource busy"
         （它要 rename 临时文件），必须原地覆写内容。
    """
    host_ip = host_ip or apps_host.detect_host_ip()
    script = (
        f"grep -v '[[:space:]]{HOST_ALIAS}$' /etc/hosts > /tmp/_hosts.new || true; "
        f"echo '{host_ip} {HOST_ALIAS}' >> /tmp/_hosts.new; "
        f"cat /tmp/_hosts.new > /etc/hosts; "
        f"rm -f /tmp/_hosts.new; "
        f"grep '{HOST_ALIAS}' /etc/hosts"
    )
    sbx.commands.run(script, user="root", timeout=timeout)
    return host_ip


def check_ports(sbx: Sandbox, apps: Optional[list[tuple[str, int]]] = None,
                timeout: int = 120) -> dict[str, bool]:
    """
    从沙箱内部逐个 curl host.docker.internal:<port>，返回 {app_name: is_up}。

    走 host.docker.internal 而非 127.0.0.1，验证的就是沙箱真正会用的那条链路
    （hosts 映射 + 开发机可达 + app 在跑），和任务脚本的访问方式一致。
    """
    apps = apps or load_app_ports()
    probe = "; ".join(
        f"echo \"{app} $(curl -s -o /dev/null -w '%{{http_code}}' --max-time 3 "
        f"http://{HOST_ALIAS}:{port}/)\""
        for app, port in apps
    )
    r = sbx.commands.run(probe, timeout=timeout)
    status = {app: False for app, _ in apps}
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in status:
            status[parts[0]] = parts[1] == "200"
    return status


def ensure_apps_reachable(sbx: Sandbox, apps: Optional[list[tuple[str, int]]] = None,
                          host_ip: Optional[str] = None) -> dict:
    """
    让一个沙箱能访问到开发机上的 31 个 app：写一行 hosts 再探活，秒级以内。

    返回 {"host_ip", "status", "ready", "down"}。
    """
    apps = apps or load_app_ports()
    ip = ensure_host_mapping(sbx, host_ip)
    status = check_ports(sbx, apps)
    down = [a for a, ok in status.items() if not ok]
    return {"host_ip": ip, "status": status, "ready": not down, "down": down}
