"""
SandboxPool: 基于 e2b 长运行沙箱的实例池。

31 个 mock app 跑在开发机上（见 apps_host.py），沙箱内不装 app。acquire 拿到新实例时
只需写一行 /etc/hosts 把 host.docker.internal 指到开发机再探活，秒级完成。

实例常驻复用：release 只把状态标回 idle，不 pause 也不 kill，acquire 直接 connect
运行中的实例。pause/resume 在模板 sdt-hojglb51 上 resume 必 500，不可用。
"""
import json
import os
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from e2b import Sandbox
from e2b.sandbox.sandbox_api import SandboxQuery

from src.sandbox import deploy
from src.settings import (POOL_MAX_SIZE, POOL_TAG, REGISTRY, SANDBOX_TEMPLATE,
                          SANDBOX_TIMEOUT)


class SandboxPoolError(Exception):
    pass


class AppsUnreachableError(SandboxPoolError):
    """开发机上的 mock app 不可达。是开发机侧的问题，不代表沙箱实例坏了。"""


@dataclass
class PoolInstanceConfig:
    sandbox_id: str
    template: str
    created_at: str
    status: str = "idle"  # "idle" | "busy"
    app_type: Optional[str] = None
    #: hosts 映射已配好且开发机上的 app 探活通过。
    apps_ready: bool = False
    app_host: Optional[str] = None  # app 实际跑在哪台机器上
    busy_since: Optional[str] = None  # ISO 时间戳，acquire 设 busy 时写入

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PoolInstanceConfig":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in valid})


class SandboxPool:
    def __init__(self, registry_path: Union[str, Path] = REGISTRY,
                 template: str = SANDBOX_TEMPLATE,
                 max_size: int = POOL_MAX_SIZE, timeout: int = SANDBOX_TIMEOUT,
                 app_host: Optional[str] = None):
        self._registry_path = Path(registry_path)
        self.template = template
        self.max_size = max_size
        self.timeout = timeout
        # mock app 跑在哪台机器上。None = 自动探测本机对沙箱可见的 IP。
        self.app_host = app_host
        self._cond = threading.Condition()
        self._instances: dict[str, PoolInstanceConfig] = {}
        self._pending_handles: dict[str, Sandbox] = {}
        self._load()

    # ---------- registry 落盘 ----------

    def _load(self) -> None:
        if not self._registry_path.exists():
            self._instances = {}
            return
        with open(self._registry_path) as f:
            data = json.load(f)
        self._instances = {
            sid: PoolInstanceConfig.from_dict(cfg) for sid, cfg in data.get("instances", {}).items()
        }

    def _save(self) -> None:
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"instances": {sid: cfg.to_dict() for sid, cfg in self._instances.items()}}
        tmp_path = self._registry_path.with_suffix(self._registry_path.suffix + ".tmp")
        with open(tmp_path, "w") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, self._registry_path)

    # ---------- 校准 ----------

    BUSY_TIMEOUT = 1800  # 30 分钟

    def reconcile(self) -> dict:
        """以 Sandbox.list(metadata=POOL_TAG) 为真相源校准本地 registry。"""
        remote = {}
        paginator = Sandbox.list(query=SandboxQuery(metadata=POOL_TAG))
        while True:
            for info in paginator.next_items():
                remote[info.sandbox_id] = info
            if not paginator.has_next:
                break
        removed, added, recovered = [], [], []
        with self._cond:
            for sid in list(self._instances):
                if sid not in remote:
                    del self._instances[sid]
                    removed.append(sid)
            for sid, info in remote.items():
                if sid not in self._instances:
                    self._instances[sid] = PoolInstanceConfig(
                        sandbox_id=sid,
                        template=info.template_id,
                        created_at=info.started_at.isoformat() if info.started_at else "",
                        status="idle",
                        app_type=(info.metadata or {}).get("app_type") or None,
                    )
                    added.append(sid)
            now = datetime.now().timestamp()
            for cfg in self._instances.values():
                if cfg.status == "busy" and cfg.busy_since:
                    try:
                        busy_ts = datetime.fromisoformat(cfg.busy_since).timestamp()
                    except (ValueError, TypeError):
                        busy_ts = 0
                    if now - busy_ts > self.BUSY_TIMEOUT:
                        cfg.status = "idle"
                        cfg.busy_since = None
                        recovered.append(cfg.sandbox_id)
            self._save()
        return {"removed": removed, "added": added, "recovered": recovered}

    # ---------- 获取 / 归还 ----------

    def acquire(self, app_type: Optional[str] = None, block: bool = True,
                timeout: Optional[float] = None, max_retries: int = 2,
                ensure_apps: bool = True) -> tuple[PoolInstanceConfig, Sandbox]:
        """
        取一个可用实例，并保证它能访问到开发机上的 31 个 app（写 hosts + 探活，秒级）。

        app 不可达说明开发机那边没起服务或网络不通，不是实例的问题，所以不 kill 实例，
        直接抛 AppsUnreachableError 让调用方去跑 serve_apps.py。

        ensure_apps=False 跳过这一步，用于只需要裸沙箱的场景（如烟雾测试）。
        """
        last_err = None
        for _ in range(max_retries + 1):
            with self._cond:
                cfg = self._select_or_create_locked(app_type, block, timeout)
                handle = self._pending_handles.pop(cfg.sandbox_id, None)

            sbx = handle
            if sbx is None:
                try:
                    sbx = Sandbox.connect(cfg.sandbox_id, timeout=self.timeout)
                except Exception as e:
                    last_err = e
                    self._drop_dead_locked(cfg.sandbox_id)
                    continue

            if not ensure_apps:
                return cfg, sbx

            try:
                self._ensure_apps_ready(cfg, sbx)
            except AppsUnreachableError:
                # 实例本身没问题，归还而不是 kill，把问题抛给调用方
                self.release(cfg.sandbox_id)
                raise
            except Exception as e:
                last_err = e
                self._drop_dead_locked(cfg.sandbox_id)
                continue

            return cfg, sbx
        raise SandboxPoolError(f"acquire 连续失败 {max_retries + 1} 次，放弃: {last_err}")

    def _ensure_apps_ready(self, cfg: PoolInstanceConfig, sbx: Sandbox) -> None:
        """
        保证实例能访问开发机上的 31 个 app：写一行 /etc/hosts 再探活，秒级。

        每次 acquire 都重写 hosts 而不是靠 cfg.apps_ready 跳过：开发机 IP 可能变了，
        或实例是从远端 reconcile 回来的（registry 里没有它的 app_host）。写入幂等，
        成本可忽略。
        """
        result = deploy.ensure_apps_reachable(sbx, host_ip=self.app_host)
        ready = result["ready"]

        with self._cond:
            current = self._instances.get(cfg.sandbox_id)
            for target in (current, cfg):
                if target is None:
                    continue
                target.apps_ready = ready
                target.app_host = result["host_ip"]
            self._save()

        if not ready:
            raise AppsUnreachableError(
                f"开发机 {result['host_ip']} 上有 {len(result['down'])} 个 app 不可达"
                f"（{', '.join(result['down'][:5])}{'...' if len(result['down']) > 5 else ''}）。"
                f"请先在开发机执行: python -m workspace.src.serve_apps --start")

    def _drop_dead_locked(self, sandbox_id: str) -> None:
        """connect 失败等实例级故障的清理：kill 掉坏实例并从 registry 移除，好让下一轮重新创建。"""
        try:
            Sandbox.kill(sandbox_id)
        except Exception:
            pass
        with self._cond:
            self._instances.pop(sandbox_id, None)
            self._pending_handles.pop(sandbox_id, None)
            self._save()
            self._cond.notify_all()

    def _select_or_create_locked(self, app_type: Optional[str], block: bool,
                                  timeout: Optional[float]) -> PoolInstanceConfig:
        deadline = None if timeout is None else (datetime.now().timestamp() + timeout)
        while True:
            idle = [c for c in self._instances.values() if c.status == "idle"]
            cand = next((c for c in idle if c.app_type == app_type and app_type is not None), None)
            cand = cand or next((c for c in idle if c.app_type is None), None)
            cand = cand or (idle[0] if idle else None)

            if cand is not None:
                cand.status = "busy"
                cand.busy_since = datetime.now().isoformat()
                self._save()
                return cand

            if len(self._instances) < self.max_size:
                return self._create_new_locked(app_type)

            if not block:
                raise SandboxPoolError("pool 已满且无空闲实例（max_size=%d）" % self.max_size)

            wait_for = None if deadline is None else max(0.0, deadline - datetime.now().timestamp())
            if wait_for == 0.0:
                raise SandboxPoolError("等待空闲实例超时")
            if not self._cond.wait(timeout=wait_for):
                raise SandboxPoolError("等待空闲实例超时")

    def _create_new_locked(self, app_type: Optional[str]) -> PoolInstanceConfig:
        metadata = dict(POOL_TAG)
        if app_type:
            metadata["app_type"] = app_type
        sbx = Sandbox.create(template=self.template, timeout=self.timeout, metadata=metadata)
        cfg = PoolInstanceConfig(
            sandbox_id=sbx.sandbox_id,
            template=self.template,
            created_at=datetime.now().isoformat(),
            status="busy",
            busy_since=datetime.now().isoformat(),
            app_type=app_type,
        )
        self._instances[cfg.sandbox_id] = cfg
        self._pending_handles[cfg.sandbox_id] = sbx
        self._save()
        return cfg

    def release(self, sandbox_id: str) -> None:
        """标记为 idle。实例保持 running 等待复用，不 pause 也不 kill。"""
        with self._cond:
            cfg = self._instances.get(sandbox_id)
            if cfg is None:
                return
            cfg.status = "idle"
            cfg.busy_since = None
            self._save()
            self._cond.notify_all()

    # ---------- 查询 ----------

    def instances(self) -> dict[str, PoolInstanceConfig]:
        with self._cond:
            return dict(self._instances)

    def get(self, sandbox_id: str) -> Optional[PoolInstanceConfig]:
        with self._cond:
            return self._instances.get(sandbox_id)

    def idle_ids(self) -> list[str]:
        with self._cond:
            return [sid for sid, c in self._instances.items() if c.status == "idle"]

    # ---------- 销毁 ----------

    def kill(self, sandbox_id: str) -> None:
        Sandbox.kill(sandbox_id)
        with self._cond:
            self._instances.pop(sandbox_id, None)
            self._pending_handles.pop(sandbox_id, None)
            self._save()
            self._cond.notify_all()

    def kill_all(self) -> None:
        for sid in list(self._instances):
            self.kill(sid)
