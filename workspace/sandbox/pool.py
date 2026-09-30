"""
SandboxPool: 基于 e2b pause/resume 的沙箱实例池。

不依赖预制镜像——每个实例首次创建后按需部署 app，之后只在 pause/resume 之间
循环复用，避免为每个任务重复 git clone + npm install。本模块只管沙箱生命周期
（create/pause/resume/kill/registry），不耦合任何 Hub app 部署细节，
部署动作由调用方通过 gym.utils.SandboxEnv.deploy_hub_app 完成后回调
mark_app_deployed() 登记。
"""
import json
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from e2b import Sandbox
from e2b.sandbox.sandbox_api import SandboxQuery

POOL_TAG = {"pool": "cua_gym"}


class SandboxPoolError(Exception):
    pass


@dataclass
class PoolInstanceConfig:
    sandbox_id: str
    template: str
    created_at: str
    status: str = "idle"  # "idle" | "busy"
    current_task_id: Optional[str] = None
    app_type: Optional[str] = None
    deployed_apps: dict = field(default_factory=dict)  # app_name -> port

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PoolInstanceConfig":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in valid})


class SandboxPool:
    def __init__(self, registry_path: Union[str, Path], template: str = "sdt-hojglb51",
                 max_size: int = 12, timeout: int = 86400):
        self._registry_path = Path(registry_path)
        self.template = template
        self.max_size = max_size
        self.timeout = timeout
        self._cond = threading.Condition()
        self._instances: dict[str, PoolInstanceConfig] = {}
        self._pending_handles: dict[str, Sandbox] = {}
        self._load()

    # ---------- 工厂方法 ----------

    @classmethod
    def from_registry(cls, path: Union[str, Path], **kwargs) -> "SandboxPool":
        return cls(path, **kwargs)

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

    def reconcile(self) -> dict:
        """以 Sandbox.list(metadata=POOL_TAG) 为真相源校准本地 registry。"""
        remote = {}
        paginator = Sandbox.list(query=SandboxQuery(metadata=POOL_TAG))
        while True:
            for info in paginator.next_items():
                remote[info.sandbox_id] = info
            if not paginator.has_next:
                break
        removed, added = [], []
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
            self._save()
        return {"removed": removed, "added": added}

    # ---------- 获取 / 归还 ----------

    def acquire(self, app_type: Optional[str] = None, block: bool = True,
                timeout: Optional[float] = None, max_resume_retries: int = 2) -> tuple[PoolInstanceConfig, Sandbox]:
        last_err = None
        for _ in range(max_resume_retries + 1):
            with self._cond:
                cfg = self._select_or_create_locked(app_type, block, timeout)
                handle = self._pending_handles.pop(cfg.sandbox_id, None)

            if handle is not None:
                return cfg, handle
            try:
                sbx = Sandbox.connect(cfg.sandbox_id, timeout=self.timeout, on_resume="restore")
                return cfg, sbx
            except Exception as e:
                last_err = e
                self._drop_dead_locked(cfg.sandbox_id)
        raise SandboxPoolError(f"resume 连续失败 {max_resume_retries + 1} 次，放弃: {last_err}")

    def _drop_dead_locked(self, sandbox_id: str) -> None:
        """resume/connect 失败时的清理：尝试 kill 掉这个已经坏掉的实例，并从 registry 移除，好让下一轮重新创建。"""
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
            app_type=app_type,
        )
        self._instances[cfg.sandbox_id] = cfg
        self._pending_handles[cfg.sandbox_id] = sbx
        self._save()
        return cfg

    def release(self, sandbox_id: str, sbx: Optional[Sandbox] = None, pause: bool = True) -> None:
        if pause:
            live = sbx or Sandbox.connect(sandbox_id, timeout=self.timeout)
            live.pause()

        with self._cond:
            cfg = self._instances.get(sandbox_id)
            if cfg is None:
                return
            cfg.status = "idle"
            cfg.current_task_id = None
            self._save()
            self._cond.notify_all()

    def mark_app_deployed(self, sandbox_id: str, app_type: str, port: int) -> None:
        with self._cond:
            cfg = self._instances.get(sandbox_id)
            if cfg is None:
                return
            cfg.app_type = app_type
            cfg.deployed_apps[app_type] = port
            self._save()

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
