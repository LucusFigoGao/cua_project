"""
任务目录读取与取样。

数据源是 workspace/tasks_data/（由 cli/unpack_tasks.py 生成），不读
gym/bench/data/tasks.parquet：`app_type ∈ configs/apps.json 的 31 个 app` 与 parquet 里
`platform=="web" and setup_kind=="py"` 等价（都是 1067 条），而 app_type 就写在每个任务
自己的 task.json 里。任务目录自描述，新增任务不必同步维护索引。
"""
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from src.settings import TASKS_DATA, app_ports, port_to_app

DATA_DIR = TASKS_DATA
INDEX_NAME = "_index.json"
REQUIRED_FILES = ("task.json", "initial_setup.py", "reward.py")


@dataclass
class TaskSpec:
    task_id: str
    app_type: str
    port: int
    instruction: str = ""
    difficulty: Optional[str] = None
    path: Optional[Path] = None
    # 任务需要的全部 app（含主 app），multi-app 任务会有 2 个以上
    apps: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.apps:
            self.apps = [self.app_type]


_PORT_RE = re.compile(r"host\.docker\.internal:(80\d\d)")


def _extract_apps(setup_path: Path, p2a: dict[int, str], primary: str) -> list[str]:
    """
    扫 initial_setup.py，提取所有出现的 host.docker.internal:80XX 端口，
    映射成 app 名列表。primary app 排在第一位，其余按端口升序追加。
    """
    try:
        text = setup_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [primary]
    ports = {int(p) for p in _PORT_RE.findall(text)}
    apps = [primary]
    for port in sorted(ports):
        name = p2a.get(port)
        if name and name != primary:
            apps.append(name)
    return apps


def load_tasks(data_dir: Union[str, Path, None] = None) -> list[TaskSpec]:
    """
    读出 tasks_data/ 里的全部任务。

    优先走 _index.json（快）；索引缺失或与目录不一致时回退到逐目录读 task.json，
    这样手工往 tasks_data/ 里丢一个任务目录也能被认出来。
    """
    root = Path(data_dir or DATA_DIR)
    if not root.exists():
        return []

    ports = app_ports()
    p2a = port_to_app()
    index_path = root / INDEX_NAME
    specs: list[TaskSpec] = []
    seen: set[str] = set()

    if index_path.exists():
        with open(index_path) as f:
            index = json.load(f)
        for task_id, meta in index.get("tasks", {}).items():
            tdir = root / task_id
            if not _is_complete(tdir):
                continue
            app_type = meta["app_type"]
            specs.append(TaskSpec(
                task_id=task_id,
                app_type=app_type,
                port=meta.get("port") or ports.get(app_type, 0),
                instruction=meta.get("instruction", ""),
                difficulty=meta.get("difficulty"),
                path=tdir,
                apps=_extract_apps(tdir / "initial_setup.py", p2a, app_type),
            ))
            seen.add(task_id)

    # 索引里没有但目录里存在的任务：直接读它自己的 task.json
    for tdir in sorted(root.iterdir()):
        if not tdir.is_dir() or tdir.name in seen or not _is_complete(tdir):
            continue
        spec = _spec_from_dir(tdir, ports, p2a)
        if spec is not None:
            specs.append(spec)

    specs.sort(key=lambda s: (s.app_type, s.task_id))
    return specs


def _is_complete(tdir: Path) -> bool:
    return tdir.is_dir() and all((tdir / f).exists() for f in REQUIRED_FILES)


def _spec_from_dir(tdir: Path, ports: dict[str, int],
                   p2a: dict[int, str]) -> Optional["TaskSpec"]:
    try:
        with open(tdir / "task.json") as f:
            meta = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    app_type = meta.get("app_type")
    if app_type not in ports:
        return None
    return TaskSpec(
        task_id=meta.get("id", tdir.name),
        app_type=app_type,
        port=ports[app_type],
        instruction=meta.get("instruction", ""),
        difficulty=meta.get("difficulty"),
        path=tdir,
        apps=_extract_apps(tdir / "initial_setup.py", p2a, app_type),
    )


def filter_apps(tasks: list[TaskSpec], apps: list[str]) -> list[TaskSpec]:
    wanted = set(apps)
    return [t for t in tasks if t.app_type in wanted]


def sample_per_app(tasks: list[TaskSpec], n: int = 3, seed: int = 0) -> list[TaskSpec]:
    """
    每个 app_type 取 n 个任务。固定 seed，同样输入必得同样输出，便于复现。
    某个 app 的任务数少于 n 时就全取。
    """
    grouped: dict[str, list[TaskSpec]] = {}
    for t in tasks:
        grouped.setdefault(t.app_type, []).append(t)

    picked: list[TaskSpec] = []
    for app in sorted(grouped):
        pool = sorted(grouped[app], key=lambda s: s.task_id)
        if len(pool) <= n:
            picked.extend(pool)
        else:
            rng = random.Random(f"{seed}:{app}")
            picked.extend(rng.sample(pool, n))
    picked.sort(key=lambda s: (s.app_type, s.task_id))
    return picked


def stats(tasks: list[TaskSpec]) -> dict:
    by_app: dict[str, int] = {}
    for t in tasks:
        by_app[t.app_type] = by_app.get(t.app_type, 0) + 1
    return {"total": len(tasks), "apps": len(by_app), "by_app": dict(sorted(by_app.items()))}
