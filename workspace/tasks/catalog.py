"""
任务目录: 从 gym/bench 的任务索引里挑出能在浏览器沙箱里跑的任务, 算出要部署哪些网页、每个网页用哪个端口、
以及任务文件里的地址占位符该替换成什么。

选择规则(2026-09 对 tasks.parquet 实测):
- web 任务 1075 个, 全部保留(其中 8 个 app_type 是泛标签 mock_websites, 具体用哪个网页要看任务文件里的占位符)
- cross_app 任务 430 个, 只保留涉及的应用全是 *_mock 网页的 342 个, 其余 88 个混有 LibreOffice / vscode / os 等桌面软件
- 合计 1417 个任务, 用到 31 个网页

命令行:  python -m workspace.tasks.catalog
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = REPO_ROOT / "gym" / "bench" / "data" / "tasks.parquet"
URL_VARIABLES_PATH = REPO_ROOT / "gym" / "bench" / "url_variables.json"
ARCHIVE_PATH = REPO_ROOT / "gym" / "bench" / "artifacts" / "cua_gym_tasks_v1.tar.zst"

BASE_PORT = 8000
# 不是具体网页的泛标签, 具体网页要看任务文件里的占位符
GENERIC_TAGS = {"mock_websites"}
# 占位符里给同一个网页起的别名(url_variables.json 里除了 NOTION 还有 NOTION_MOCK)
ALIASES: Dict[str, List[str]] = {"notion_mock": ["NOTION_MOCK"]}


@dataclass(frozen=True)
class Task:
    id: str
    instruction: str
    platform: str  # "web" | "cross_app"
    apps: Tuple[str, ...]  # 涉及的网页; 泛标签任务为空元组
    generic: bool = False


def split_apps(app_type) -> List[str]:
    if not isinstance(app_type, str):
        return []
    return [a.strip() for a in app_type.split(",") if a.strip()]


def is_web_app(name: str) -> bool:
    return name.endswith("_mock") and name not in GENERIC_TAGS


def load_index(path: Path = INDEX_PATH):
    """读任务索引, 需要 pandas + pyarrow。"""
    import pandas as pd

    return pd.read_parquet(path)


def select_tasks(df) -> List[Task]:
    tasks: List[Task] = []
    for r in df[df.platform.isin(["web", "cross_app"])].itertuples(index=False):
        apps = split_apps(r.app_type)
        generic = any(a in GENERIC_TAGS for a in apps)
        if r.platform == "cross_app" and not all(is_web_app(a) for a in apps):
            continue
        real = tuple(a for a in apps if is_web_app(a))
        tasks.append(Task(r.id, r.instruction, r.platform, real, generic))
    return tasks


def skipped_summary(df) -> Dict[str, int]:
    """被排除的任务, 用于核对口径。"""
    cross = df[df.platform == "cross_app"]
    mixed = sum(1 for s in cross.app_type if not all(is_web_app(a) for a in split_apps(s)))
    return {"cross_app_with_desktop_apps": mixed, "desktop": int((df.platform == "desktop").sum())}


def required_apps(tasks: Iterable[Task]) -> List[str]:
    return sorted({a for t in tasks for a in t.apps})


def tasks_per_app(tasks: Iterable[Task]) -> Counter:
    c: Counter = Counter()
    for t in tasks:
        c.update(t.apps)
    return c


def tasks_within(tasks: Iterable[Task], apps: Iterable[str]) -> List[Task]:
    """只用到给定网页的任务。泛标签任务的网页不确定, 子集模式下不纳入。"""
    allowed = set(apps)
    return [t for t in tasks if t.apps and not t.generic and set(t.apps) <= allowed]


def port_map(apps: Iterable[str], base: int = BASE_PORT) -> Dict[str, int]:
    """按名字排序依次分配端口, 同一批网页在所有实例上端口一致。"""
    return {a: base + i for i, a in enumerate(sorted(set(apps)))}


def replacements(apps: Iterable[str], ports: Dict[str, int]) -> Dict[str, str]:
    """任务文件里的占位符 -> 沙箱内地址。_URL__ 换成完整地址, _HOST__ 换成 主机:端口。"""
    out: Dict[str, str] = {}
    for a in apps:
        name = a[: -len("_mock")].upper()
        url = f"http://localhost:{ports[a]}"
        host = f"localhost:{ports[a]}"
        for n in [name] + ALIASES.get(a, []):
            out[f"__CUA_GYM_{n}_URL__"] = url
            out[f"__CUA_GYM_{n}_HOST__"] = host
    return out


def sample_tasks(tasks: List[Task], apps: Iterable[str], cross: int = 3) -> List[Task]:
    """验证用: 每个网页至少覆盖一个任务, 再额外取几个跨应用任务。

    优先用只涉及该网页的 web 任务; asana / discord / docusign 这类网页没有单网页任务,
    退而取涉及网页最少的跨应用任务。"""
    allowed = set(apps)
    usable = [t for t in tasks if t.apps and not t.generic and set(t.apps) <= allowed]
    picked: List[Task] = []
    seen = set()
    for a in sorted(allowed):
        cands = [t for t in usable if a in t.apps]
        if not cands:
            continue
        best = min(cands, key=lambda t: (t.platform != "web", len(t.apps), t.id))
        if best.id not in seen:
            picked.append(best)
            seen.add(best.id)
    extra = [t for t in usable if t.platform == "cross_app" and t.id not in seen]
    return picked + extra[:cross]


def unknown_placeholders(apps: Iterable[str]) -> List[str]:
    """url_variables.json 里属于给定网页、却没被 replacements() 覆盖的占位符, 用于自检。"""
    ports = port_map(apps)
    covered = set(replacements(ports, ports))
    known = json.loads(URL_VARIABLES_PATH.read_text())["variables"]
    names = {a[: -len("_mock")].upper() for a in apps} | {n for a in apps for n in ALIASES.get(a, [])}
    missing = []
    for ph in known:
        for suffix in ("_URL__", "_HOST__"):
            if ph.startswith("__CUA_GYM_") and ph.endswith(suffix):
                if ph[len("__CUA_GYM_") : -len(suffix)] in names and ph not in covered:
                    missing.append(ph)
    return sorted(missing)


def main() -> None:
    df = load_index()
    tasks = select_tasks(df)
    apps = required_apps(tasks)
    ports = port_map(apps)
    per_app = tasks_per_app(tasks)
    web = [t for t in tasks if t.platform == "web"]
    cross = [t for t in tasks if t.platform == "cross_app"]
    print(f"任务总数 {len(df)}; 纳入 {len(tasks)} (web {len(web)}, 跨应用纯网页 {len(cross)}), 用到 {len(apps)} 个网页")
    print("排除:", skipped_summary(df))
    print(f"泛标签(mock_websites)任务: {sum(t.generic for t in tasks)}")
    print(f"\n{'端口':<6}{'网页':<26}任务数")
    for a in sorted(apps, key=lambda x: -per_app[x]):
        print(f"{ports[a]:<6}{a:<26}{per_app[a]}")
    miss = unknown_placeholders(apps)
    print("\n未覆盖的占位符:", miss or "无")


if __name__ == "__main__":
    main()
