"""
SandboxEnv: AGS All-In-One 沙箱的统一操作接口。
接口设计参考 gym/utils/env.py 的 Env/EnvConfig（该文件面向阿里云 VM + Flask server），
这里换成 e2b SDK 背后的 AGS 沙箱作为底层实现。
"""
import os
import json
import time
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

os.environ.setdefault("NO_PROXY", "*.tencentags.com,*.woa.com,*.tencentyun.com")

import e2b.envd.rpc as _rpc
_rpc.default_username = "root"

from e2b import Sandbox


class SandboxEnvError(Exception):
    pass


@dataclass
class SandboxConfig:
    """可序列化的沙箱连接配置，供多次运行 / 多个脚本复用同一个实例。"""
    sandbox_id: str
    template: str = "sdt-hojglb51"
    hub_base_url: str = "http://localhost:5173"
    task_id: Optional[str] = None
    sid: Optional[str] = None
    task_dir: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "SandboxConfig":
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in valid})

    def save(self, path: Union[str, Path]) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "SandboxConfig":
        with open(path) as f:
            return cls.from_dict(json.load(f))


class SandboxEnv:
    """
    - SandboxEnv.create()      → 新建一个沙箱实例
    - SandboxEnv.connect(id)   → 连接到已有实例（不会 kill）
    - SandboxEnv.from_config() → 从配置文件重连
    """

    def __init__(self, sbx: Sandbox, config: SandboxConfig):
        self.sbx = sbx
        self.config = config

    # ---------- 工厂方法 ----------

    @classmethod
    def create(cls, template: str = "sdt-hojglb51", timeout: int = 86400,
               task_id: Optional[str] = None) -> "SandboxEnv":
        sbx = Sandbox.create(template=template, timeout=timeout)
        config = SandboxConfig(
            sandbox_id=sbx.sandbox_id,
            template=template,
            task_id=task_id,
            created_at=datetime.now().isoformat(),
        )
        return cls(sbx=sbx, config=config)

    @classmethod
    def connect(cls, sandbox_id: str, hub_base_url: str = "http://localhost:5173",
                timeout: int = 86400) -> "SandboxEnv":
        sbx = Sandbox.connect(sandbox_id)
        sbx.set_timeout(timeout)
        config = SandboxConfig(sandbox_id=sandbox_id, hub_base_url=hub_base_url)
        return cls(sbx=sbx, config=config)

    @classmethod
    def from_config(cls, config_path: Union[str, Path], timeout: int = 86400) -> "SandboxEnv":
        config = SandboxConfig.load(config_path)
        sbx = Sandbox.connect(config.sandbox_id)
        sbx.set_timeout(timeout)
        return cls(sbx=sbx, config=config)

    def save_config(self, path: Union[str, Path]) -> None:
        self.config.save(path)

    # ---------- 命令执行 helper ----------

    def run(self, cmd: str, user: str = "root", timeout: int = 60, envs: Optional[dict] = None):
        return self.sbx.commands.run(cmd, user=user, timeout=timeout, envs=envs or {})

    def write_and_run(self, script: str, filename: str, user: str = "root",
                       timeout: int = 60, envs: Optional[dict] = None):
        path = f"/mnt/workspace/{filename}"
        self.sbx.files.write(path, script)
        return self.run(f"python3 {path}", user=user, timeout=timeout, envs=envs)

    # ---------- Hub 环境部署 ----------

    def deploy_hub_app(self, app_name: str, port: int = 5173,
                        repo_url: str = "https://github.com/xlang-ai/CUA-Gym-Hub.git",
                        repo_dir: str = "/mnt/workspace/CUA-Gym-Hub") -> None:
        """克隆（如未克隆）CUA-Gym-Hub 并把指定 mock app 起成后台服务。幂等：已在跑则直接返回。"""
        check = self.run(f"curl -s -m 2 http://localhost:{port}/go?sid=__healthcheck__ || echo NOT_RUNNING")
        if "NOT_RUNNING" not in check.stdout:
            return

        exists = self.run(f"test -d {repo_dir} && echo EXISTS || echo MISSING")
        if "MISSING" in exists.stdout:
            self.run(f"git clone {repo_url} {repo_dir}", timeout=120)

        app_dir = f"{repo_dir}/websites/{app_name}"
        self.run(f"cd {app_dir} && npm install", timeout=180)
        self.sbx.commands.run(f"cd {app_dir} && npm run dev", user="root", background=True)

        for _ in range(20):
            time.sleep(1)
            r = self.run(f"curl -s -m 2 http://localhost:{port}/go?sid=__healthcheck__ || echo NOT_RUNNING")
            if "NOT_RUNNING" not in r.stdout:
                return
        raise SandboxEnvError(f"{app_name} 在端口 {port} 启动超时")

    # ---------- State API ----------

    def get_state(self, sid: str) -> dict:
        r = self.run(f"curl -s '{self.config.hub_base_url}/go?sid={sid}'")
        return json.loads(r.stdout)

    def set_state(self, sid: str, state: dict, action: str = "set") -> dict:
        payload = json.dumps({"action": action, "state": state})
        script = f'''
import requests
resp = requests.post("{self.config.hub_base_url}/post?sid={sid}", json={payload}, timeout=30)
print(resp.status_code, resp.text[:200])
'''
        r = self.write_and_run(script, "_set_state.py")
        return {"stdout": r.stdout}

    # ---------- 浏览器 / CDP ----------

    def screenshot(self, sid: str, local_out: Optional[str] = None) -> bytes:
        remote_path = "/mnt/workspace/_screenshot.png"
        script = f'''
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()
    page.goto("{self.config.hub_base_url}/?sid={sid}", timeout=15000)
    page.wait_for_timeout(800)
    page.screenshot(path="{remote_path}", full_page=True)
    browser.close()
'''
        self.write_and_run(script, "_screenshot.py", timeout=30)
        data = self.sbx.files.read(remote_path, format="bytes")
        if local_out:
            with open(local_out, "wb") as f:
                f.write(data)
        return data

    def act(self, sid: str, action: dict) -> None:
        """
        执行一个动作，action 格式先支持最基础的几种，后续按你们的 action space 扩展：
        {"type": "click", "selector": "..."}
        {"type": "fill", "selector": "...", "text": "..."}
        {"type": "press", "key": "Enter"}
        """
        act_type = action.get("type")
        if act_type == "click":
            body = f'page.click({action["selector"]!r}, timeout=10000)'
        elif act_type == "fill":
            body = f'page.fill({action["selector"]!r}, {action["text"]!r}, timeout=10000)'
        elif act_type == "press":
            body = f'page.keyboard.press({action["key"]!r})'
        else:
            raise SandboxEnvError(f"未知的 action type: {act_type}")

        script = f'''
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    if context.pages:
        page = context.pages[0]
    else:
        page = context.new_page()
        page.goto("{self.config.hub_base_url}/?sid={sid}", timeout=15000)
    {body}
    browser.close()
'''
        self.write_and_run(script, "_act.py", timeout=20)

    # ---------- Task 下载 / 执行 / 评分 ----------

    def find_task(self, app_type: str, hf_endpoint: str = "https://hf-mirror.com") -> dict:
        script = f'''
import os, json
os.environ.setdefault("HF_ENDPOINT", "{hf_endpoint}")
from datasets import load_dataset

tasks = load_dataset("xlangai/CUA-Gym", "tasks", split="train")
matched = tasks.filter(lambda row: row["app_type"] == "{app_type}")
t = matched[0]
print(json.dumps({{
    "task_id": t["id"],
    "instruction": t["instruction"],
    "archive_member": t["archive_member"],
}}))
'''
        r = self.write_and_run(script, "_find_task.py", timeout=300)
        for line in r.stdout.strip().splitlines()[::-1]:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        raise SandboxEnvError(f"未能解析 find_task 输出:\n{r.stdout}")

    def download_task(self, task_id: str, url_placeholder: str, url_value: str,
                       hf_endpoint: str = "https://hf-mirror.com") -> str:
        """下载并解压单个 task，替换 URL 占位符，返回 task 目录路径。幂等：已存在则跳过下载。"""
        task_dir = f"/mnt/workspace/cua_gym_tasks/{task_id}"
        exists = self.run(f"test -f {task_dir}/task.json && echo EXISTS || echo MISSING")
        if "MISSING" in exists.stdout:
            self.run("pip install -U datasets huggingface_hub zstandard "
                      "-i https://mirrors.cloud.tencent.com/pypi/simple", timeout=180)

            download_script = f'''
import os
os.environ.setdefault("HF_ENDPOINT", "{hf_endpoint}")
from huggingface_hub import hf_hub_download
path = hf_hub_download(
    repo_id="xlangai/CUA-Gym", repo_type="dataset",
    filename="artifacts/cua_gym_tasks_v1.tar.zst",
    local_dir="/mnt/workspace/CUA-Gym-data",
)
print(path)
'''
            self.write_and_run(download_script, "_download_task.py", timeout=600)

            extract_script = f'''
import zstandard, tarfile
dctx = zstandard.ZstdDecompressor()
with open("/mnt/workspace/CUA-Gym-data/artifacts/cua_gym_tasks_v1.tar.zst", "rb") as f:
    with dctx.stream_reader(f) as reader:
        with tarfile.open(fileobj=reader, mode="r|") as tar:
            for member in tar:
                if member.name.startswith("{task_id}/"):
                    tar.extract(member, path="/mnt/workspace/cua_gym_tasks")
'''
            self.write_and_run(extract_script, "_extract_task.py", timeout=300)

        self.run(f"sed -i 's|{url_placeholder}|{url_value}|g' {task_dir}/initial_setup.py {task_dir}/reward.py")
        # 注释掉尝试拉起 google-chrome 桌面窗口的那一行（沙箱里没有这个命令，不影响状态注入）
        self.run(f"sed -i \"/launch_gui(f'google-chrome/s/^/#/\" {task_dir}/initial_setup.py")

        self.config.task_id = task_id
        self.config.task_dir = task_dir
        return task_dir

    def run_initial_setup(self, task_dir: Optional[str] = None) -> str:
        """跑 initial_setup.py，返回生成的 sid。"""
        task_dir = task_dir or self.config.task_dir
        self.run("pip install requests -i https://mirrors.cloud.tencent.com/pypi/simple", timeout=60)
        self.run(f"cd {task_dir} && python3 initial_setup.py", timeout=60)
        r = self.run("cat /tmp/task_web_sid")
        sid = r.stdout.strip()
        self.config.sid = sid
        return sid

    def run_reward(self, task_dir: Optional[str] = None) -> float:
        """跑 reward.py，解析并返回最终分数。"""
        task_dir = task_dir or self.config.task_dir
        r = self.run(f"cd {task_dir} && python3 reward.py", timeout=60)
        match = re.search(r"REWARD:\s*([\d.]+)", r.stdout)
        if not match:
            raise SandboxEnvError(f"未能从 reward.py 输出中解析分数:\n{r.stdout}")
        return float(match.group(1))

    # ---------- 生命周期 ----------

    def set_timeout(self, seconds: int) -> None:
        self.sbx.set_timeout(seconds)

    def kill(self) -> None:
        self.sbx.kill()