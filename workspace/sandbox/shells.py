"""
Shell: prewarm 只依赖的一个极小接口, 有两个实现:
- SandboxShell: 在 AGS 沙箱里执行(生产用)
- LocalShell:   在本机的一个目录里执行(不连 AGS 就能完整演练预制流程, 用于开发机自测)

run() 对"命令非零退出"不抛异常, 返回 (退出码, 输出); 超时和网络错误才抛异常。
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import List, Tuple, Union


class LocalShell:
    def __init__(self) -> None:
        self._procs: List[subprocess.Popen] = []

    def run(self, cmd: str, timeout: int = 60) -> Tuple[int, str]:
        try:
            p = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise TimeoutError(f"命令超时({timeout}s): {cmd[:120]}") from e
        return p.returncode, p.stdout if p.returncode == 0 else (p.stdout + p.stderr)

    def write(self, path: str, data: Union[str, bytes]) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(data.encode("utf-8") if isinstance(data, str) else data)

    def put_file(self, local: str, remote: str) -> None:
        Path(remote).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local, remote)

    def spawn(self, cmd: str) -> None:
        self._procs.append(
            subprocess.Popen(
                ["bash", "-c", cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        )

    def close(self) -> None:
        for p in self._procs:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        self._procs.clear()


def configure_e2b() -> None:
    """与 gym/utils/ags_sandbox_env.py 保持一致: 直连内网域名, 默认用户 root(文件接口也要用 root)。"""
    os.environ.setdefault("NO_PROXY", "*.tencentags.com,*.woa.com,*.tencentyun.com")
    import e2b.envd.rpc as _rpc

    _rpc.default_username = "root"


class SandboxShell:
    """包装一个 e2b Sandbox。"""

    def __init__(self, sbx) -> None:
        configure_e2b()
        self.sbx = sbx

    def run(self, cmd: str, timeout: int = 60) -> Tuple[int, str]:
        try:
            r = self.sbx.commands.run(cmd, user="root", timeout=timeout)
            return 0, r.stdout
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "exit_code", None)
            if code is None:  # 超时或网络错误, 不是命令自己失败
                raise
            return int(code), (getattr(e, "stdout", "") or "") + (getattr(e, "stderr", "") or "")

    def write(self, path: str, data: Union[str, bytes]) -> None:
        self.sbx.files.write(path, data)

    def put_file(self, local: str, remote: str) -> None:
        with open(local, "rb") as f:
            self.sbx.files.write(remote, f)

    def spawn(self, cmd: str) -> None:
        self.sbx.commands.run(cmd, user="root", background=True)

    def close(self) -> None:
        pass
