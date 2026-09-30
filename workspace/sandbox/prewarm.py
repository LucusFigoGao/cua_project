"""
prewarm: 把 CUA-Gym-Hub 的一批网页和任务数据预制到一个实例上。

一个实例上同时运行全部所需网页(跨应用任务一次要用 2 到 5 个网页), 做法参照 gym/hub/deploy-all.sh:
  npm install -> npm run build -> vite preview 各占一个端口(端口由 catalog.port_map 按名字排序固定分配)
任务数据: 上传(或从 HF 下载)压缩包, 一次扫描提取全部任务并把地址占位符换成 localhost:端口。

整个过程幂等: 仓库、node_modules、dist、已在跑的服务、已提取的数据都会跳过, 中断后重跑即可续上。
每个网页装完都检查剩余磁盘, 不够就停止安装并在报告里说明(沙箱系统盘实测只有约 8G)。
"""
from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Tuple

log = logging.getLogger("prewarm")
HERE = Path(__file__).resolve().parent

HUB_REPO_URL = "https://github.com/xlang-ai/CUA-Gym-Hub.git"  # 与 SandboxEnv.deploy_hub_app 一致
REWARD_RE = re.compile(r"REWARD:\s*([\d.]+)")

_PROBE_SCRIPT = """\
import json, sys, urllib.error, urllib.request
out = {}
for p in json.loads(sys.argv[1]):
    try:
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            f"http://localhost:{p}/go?sid=__healthcheck__", timeout=3)
        out[str(p)] = True
    except urllib.error.HTTPError:
        out[str(p)] = True  # 服务有响应(哪怕是 4xx)就算活着
    except Exception:
        out[str(p)] = False
print(json.dumps(out))
"""

_HF_DOWNLOAD_SCRIPT = """\
import os, sys
os.environ.setdefault("HF_ENDPOINT", sys.argv[1])
from huggingface_hub import hf_hub_download
print(hf_hub_download(repo_id="xlangai/CUA-Gym", repo_type="dataset",
      filename="artifacts/cua_gym_tasks_v1.tar.zst", local_dir=sys.argv[2]))
"""


class Shell(Protocol):
    def run(self, cmd: str, timeout: int = 60) -> Tuple[int, str]: ...
    def write(self, path: str, data) -> None: ...
    def put_file(self, local: str, remote: str) -> None: ...
    def spawn(self, cmd: str) -> None: ...


@dataclass
class Paths:
    repo_dir: str = "/mnt/workspace/CUA-Gym-Hub"
    data_dir: str = "/mnt/workspace/CUA-Gym-data"
    tasks_dir: str = "/mnt/workspace/cua_gym_tasks"
    tmp_dir: str = "/tmp"

    @property
    def archive(self) -> str:
        return f"{self.data_dir}/artifacts/cua_gym_tasks_v1.tar.zst"

    def app_dir(self, app: str) -> str:
        return f"{self.repo_dir}/websites/{app}"


@dataclass
class Plan:
    apps: List[str]
    ports: Dict[str, int]
    task_ids: List[str]
    replacements: Dict[str, str]
    repo_url: str = HUB_REPO_URL
    repo_copy_from: Optional[str] = None  # 仅测试用: 直接拷贝本地目录而不是 git clone
    archive_local: Optional[str] = None  # 本地压缩包路径, 有就上传, 没有走 HF
    hf_endpoint: str = "https://hf-mirror.com"
    pip_index: str = "https://mirrors.cloud.tencent.com/pypi/simple"
    min_free_mb: int = 1500
    install_workers: int = 3
    install_timeout: int = 900
    build_timeout: int = 900
    skip_data: bool = False


# ---------------------------------------------------------------- 小工具


def free_mb(shell: Shell, path: str) -> int:
    code, out = shell.run(f"mkdir -p {path} && df --output=avail -B1M {path} | tail -1", timeout=30)
    try:
        return int(out.strip().split()[-1])
    except (ValueError, IndexError):
        return -1


def dir_mb(shell: Shell, path: str) -> int:
    code, out = shell.run(f"du -sm {path} 2>/dev/null | cut -f1", timeout=120)
    try:
        return int(out.strip())
    except ValueError:
        return -1


def probe_ports(shell: Shell, paths: Paths, ports: List[int]) -> Dict[int, bool]:
    script = f"{paths.tmp_dir}/probe_ports.py"
    shell.write(script, _PROBE_SCRIPT)
    code, out = shell.run(f"python3 {script} '{json.dumps(ports)}'", timeout=30 + 4 * len(ports))
    try:
        return {int(k): v for k, v in json.loads(out.strip().splitlines()[-1]).items()}
    except (ValueError, IndexError):
        return {p: False for p in ports}


def _tail(text: str, n: int = 400) -> str:
    return text.strip()[-n:]


# ---------------------------------------------------------------- 各步骤


def ensure_repo(shell: Shell, plan: Plan, paths: Paths) -> dict:
    t0 = time.time()
    code, _ = shell.run(f"test -d {paths.repo_dir}/websites", timeout=15)
    if code == 0:
        return {"ok": True, "skipped": True}
    if plan.repo_copy_from:
        code, out = shell.run(f"mkdir -p {paths.repo_dir} && cp -r {plan.repo_copy_from}/. {paths.repo_dir}/", timeout=300)
        return {"ok": code == 0, "seconds": round(time.time() - t0, 1), **({} if code == 0 else {"error": _tail(out)})}
    err = ""
    for _ in range(3):
        shell.run(f"rm -rf {paths.repo_dir}", timeout=60)
        code, out = shell.run(f"git clone --depth 1 {plan.repo_url} {paths.repo_dir}", timeout=600)
        if code == 0:
            return {"ok": True, "seconds": round(time.time() - t0, 1)}
        err = _tail(out)
        time.sleep(3)
    return {"ok": False, "error": err}


def build_app(shell: Shell, plan: Plan, paths: Paths, app: str) -> dict:
    d = paths.app_dir(app)
    rec: dict = {"app": app, "port": plan.ports[app]}
    free = free_mb(shell, paths.repo_dir)
    if 0 <= free < plan.min_free_mb:
        return {**rec, "ok": False, "skipped": "disk", "free_mb": free}
    t0 = time.time()
    code, out = shell.run(
        f"cd {d} && (test -x node_modules/.bin/vite || npm install --no-audit --no-fund --loglevel=error)",
        timeout=plan.install_timeout,
    )
    rec["install_s"] = round(time.time() - t0, 1)
    if code != 0:
        return {**rec, "ok": False, "error": "npm install: " + _tail(out)}
    t0 = time.time()
    code, out = shell.run(f"cd {d} && (test -f dist/index.html || npm run build)", timeout=plan.build_timeout)
    rec["build_s"] = round(time.time() - t0, 1)
    if code != 0:
        return {**rec, "ok": False, "error": "npm run build: " + _tail(out)}
    rec["node_modules_mb"] = dir_mb(shell, f"{d}/node_modules")
    return {**rec, "ok": True}


def build_apps(shell: Shell, plan: Plan, paths: Paths) -> List[dict]:
    with ThreadPoolExecutor(max_workers=max(1, plan.install_workers)) as ex:
        return list(ex.map(lambda a: build_app(shell, plan, paths, a), plan.apps))


def start_servers(shell: Shell, plan: Plan, paths: Paths, apps: List[str], wait: int = 90) -> Dict[str, bool]:
    ports = [plan.ports[a] for a in apps]
    alive = probe_ports(shell, paths, ports)
    for a in apps:
        p = plan.ports[a]
        if alive.get(p):
            continue
        # --strictPort: 端口被占就直接失败, 不要悄悄换端口, 否则和占位符替换的地址对不上
        shell.spawn(
            f"cd {paths.app_dir(a)} && exec npm run preview -- --host 0.0.0.0 --port {p} --strictPort "
            f"> {paths.tmp_dir}/hub_{a}.log 2>&1"
        )
    deadline = time.time() + wait
    while time.time() < deadline:
        alive = probe_ports(shell, paths, ports)
        if all(alive.values()):
            break
        time.sleep(3)
    return {a: bool(alive.get(plan.ports[a])) for a in apps}


def prepare_data(shell: Shell, plan: Plan, paths: Paths) -> dict:
    t0 = time.time()
    shell.run(f"mkdir -p {paths.data_dir}/artifacts {paths.tasks_dir}", timeout=30)
    code, _ = shell.run(f"test -s {paths.archive}", timeout=15)
    if code != 0:
        if plan.archive_local and Path(plan.archive_local).exists():
            shell.put_file(plan.archive_local, paths.archive)
        else:
            shell.run(f"python3 -c 'import huggingface_hub' || pip install -q huggingface_hub -i {plan.pip_index}", timeout=300)
            script = f"{paths.tmp_dir}/hf_download.py"
            shell.write(script, _HF_DOWNLOAD_SCRIPT)
            code, out = shell.run(f"python3 {script} {plan.hf_endpoint} {paths.data_dir}", timeout=900)
            if code != 0:
                return {"ok": False, "error": "下载压缩包失败: " + _tail(out)}
    # 提取脚本依赖 zstandard, 任务脚本(initial_setup/reward)依赖 requests
    for mod in ("zstandard", "requests"):
        shell.run(f"python3 -c 'import {mod}' || pip install -q {mod} -i {plan.pip_index}", timeout=300)
    shell.write(f"{paths.tmp_dir}/task_extract.py", (HERE / "task_extract.py").read_text())
    shell.write(f"{paths.tmp_dir}/extract_ids.json", json.dumps(plan.task_ids))
    shell.write(f"{paths.tmp_dir}/extract_repl.json", json.dumps(plan.replacements))
    code, out = shell.run(
        f"python3 {paths.tmp_dir}/task_extract.py --archive {paths.archive} --out {paths.tasks_dir} "
        f"--ids {paths.tmp_dir}/extract_ids.json --repl {paths.tmp_dir}/extract_repl.json "
        f"--report {paths.tmp_dir}/extract_report.json",
        timeout=900,
    )
    if code != 0:
        return {"ok": False, "error": "提取失败: " + _tail(out)}
    _, raw = shell.run(f"cat {paths.tmp_dir}/extract_report.json", timeout=30)
    rep = json.loads(raw)
    rep.update(ok=not rep["missing"], total_seconds=round(time.time() - t0, 1))
    return rep


# ---------------------------------------------------------------- 总入口


def prewarm_instance(shell: Shell, plan: Plan, paths: Optional[Paths] = None) -> dict:
    paths = paths or Paths()
    t0 = time.time()
    report: dict = {"disk_free_mb_start": free_mb(shell, paths.repo_dir)}
    report["repo"] = ensure_repo(shell, plan, paths)
    if not report["repo"]["ok"]:
        report["ok"] = False
        return report
    if not plan.skip_data:
        report["data"] = prepare_data(shell, plan, paths)
    report["apps"] = build_apps(shell, plan, paths)
    built = [r["app"] for r in report["apps"] if r["ok"]]
    report["servers"] = start_servers(shell, plan, paths, built) if built else {}
    report["ports_ok"] = sorted(a for a, up in report["servers"].items() if up)
    report["ports_failed"] = sorted(set(plan.apps) - set(report["ports_ok"]))
    report["disk_free_mb_end"] = free_mb(shell, paths.repo_dir)
    report["seconds"] = round(time.time() - t0, 1)
    report["ok"] = not report["ports_failed"] and (plan.skip_data or report.get("data", {}).get("ok", False))
    return report


def verify_task(shell: Shell, paths: Paths, task_id: str, timeout: int = 120) -> dict:
    """在实例上把一个任务的 initial_setup 和 reward 各跑一遍, 检查预制的网页和数据能配合工作。
    不做任何操作时 reward 通常是 0, 这里只检查两个脚本能跑通、REWARD 能解析。"""
    d = f"{paths.tasks_dir}/{task_id}"
    rec: dict = {"task_id": task_id}
    code, _ = shell.run(f"test -f {d}/initial_setup.py", timeout=15)
    if code != 0:
        return {**rec, "ok": False, "error": "任务目录不存在, 数据没提取"}
    code, out = shell.run(f"rm -f /tmp/task_web_sid; cd {d} && python3 initial_setup.py", timeout=timeout)
    rec["setup_exit"] = code
    if code != 0:
        return {**rec, "ok": False, "error": "initial_setup: " + _tail(out)}
    _, sid = shell.run("cat /tmp/task_web_sid 2>/dev/null", timeout=15)
    rec["sid"] = sid.strip()
    code, out = shell.run(f"cd {d} && python3 reward.py", timeout=timeout)
    m = REWARD_RE.search(out)
    rec["reward_exit"] = code
    if not m:
        return {**rec, "ok": False, "error": "reward: 解析不到 REWARD: " + _tail(out)}
    rec["reward"] = float(m.group(1))
    return {**rec, "ok": True}
