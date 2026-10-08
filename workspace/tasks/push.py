"""
把本地 tasks_data/ 里选中的任务推送到沙箱实例。

两件事：
  1. 打成单个 tar.gz 一次上传。逐文件 sbx.files.write 不现实——单个 initial_setup.py
     可达 85KB，上千任务是两千多次往返。
  2. 装 google-chrome shim。任务脚本末尾都有一行
     `launch_gui(f'google-chrome "{BASE_URL}/?sid={sid}"')`，而 all-in-one 模板里
     浏览器叫 /usr/bin/chromium，没有 google-chrome 这个名字。实例里 chromium 由 s6
     托管常驻运行（DISPLAY=:1，CDP 9222 已监听），shim 转发过去会让它在**已有浏览器
     会话**里开 tab（输出 "Opening in existing browser session."），页面随即出现在
     CDP target 列表里。

     注意 shim 必须以默认用户（user）被调用：chromium 拒绝以 root 运行而不加
     --no-sandbox。写 /usr/local/bin 本身需要 root，所以只有建 shim 这一步用 root，
     跟 deploy.ensure_host_mapping 写 /etc/hosts 的处理方式一致。
"""
import json
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Iterable

from e2b import Sandbox

REMOTE_ROOT = "/tmp/cua_tasks"
CHROME_SHIM = "/usr/local/bin/google-chrome"
CHROMIUM_BIN = "/usr/bin/chromium"
UPLOAD_TMP = "/tmp/_cua_tasks_upload.tar.gz"


def ensure_chrome_shim(sbx: Sandbox, timeout: int = 30) -> bool:
    """幂等建立 google-chrome -> chromium 的 shim。返回 shim 是否可用。"""
    script = (
        f"if [ ! -x {CHROME_SHIM} ]; then "
        f"  printf '%s\\n' '#!/bin/sh' 'exec {CHROMIUM_BIN} \"$@\"' > {CHROME_SHIM} && "
        f"  chmod 755 {CHROME_SHIM}; "
        f"fi; "
        f"command -v google-chrome >/dev/null && echo SHIM_OK || echo SHIM_MISSING"
    )
    r = sbx.commands.run(script, user="root", timeout=timeout)
    return "SHIM_OK" in (r.stdout or "")


def ensure_requests(sbx: Sandbox, timeout: int = 180) -> None:
    """任务脚本依赖 requests。幂等：已装则秒返回。"""
    sbx.commands.run(
        "python3 -c 'import requests' 2>/dev/null || "
        "pip install -q requests 2>/dev/null || true",
        timeout=timeout,
    )


def _build_tarball(specs: Iterable, dest: Path) -> int:
    """把选中任务打进 tar.gz，返回文件数。arcname 用 task_id，解压后即 <root>/<task_id>/。"""
    count = 0
    with tarfile.open(dest, "w:gz") as tar:
        for spec in specs:
            if spec.path is None or not spec.path.is_dir():
                continue
            for f in sorted(spec.path.iterdir()):
                if f.is_file():
                    tar.add(f, arcname=f"{spec.task_id}/{f.name}")
                    count += 1
    return count


def push_tasks(sbx: Sandbox, specs: list, remote_root: str = REMOTE_ROOT,
               upload_timeout: int = 600) -> dict:
    """
    上传 specs 对应的任务目录到实例的 remote_root/<task_id>/，并准备好运行环境。

    返回 {'uploaded': n, 'files': n, 'remote_dirs': n, 'shim': bool, 'bytes': n, 'elapsed': s}
    """
    specs = [s for s in specs if s.path is not None and s.path.is_dir()]
    if not specs:
        return {"uploaded": 0, "files": 0, "remote_dirs": 0, "shim": False,
                "bytes": 0, "elapsed": 0.0}

    t0 = time.time()
    with tempfile.TemporaryDirectory() as td:
        tarball = Path(td) / "tasks.tar.gz"
        n_files = _build_tarball(specs, tarball)
        payload = tarball.read_bytes()

        sbx.commands.run(f"mkdir -p {remote_root}", timeout=30)
        # e2b 的 files.write 接受 bytes，走 envd 上传，不经 shell
        sbx.files.write(UPLOAD_TMP, payload)
        sbx.commands.run(
            f"tar -xzf {UPLOAD_TMP} -C {remote_root} && rm -f {UPLOAD_TMP}",
            timeout=upload_timeout,
        )

    shim = ensure_chrome_shim(sbx)
    ensure_requests(sbx)

    r = sbx.commands.run(
        f"find {remote_root} -mindepth 1 -maxdepth 1 -type d | wc -l", timeout=60)
    remote_dirs = int((r.stdout or "0").strip() or 0)

    # 写一份清单到实例上，方便在沙箱里直接查有哪些任务
    manifest = {
        "pushed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(specs),
        "tasks": {s.task_id: {"app_type": s.app_type, "port": s.port} for s in specs},
    }
    sbx.files.write(f"{remote_root}/_manifest.json",
                    json.dumps(manifest, indent=2, ensure_ascii=False))

    return {
        "uploaded": len(specs),
        "files": n_files,
        "remote_dirs": remote_dirs,
        "shim": shim,
        "bytes": len(payload),
        "elapsed": time.time() - t0,
    }


def list_remote_tasks(sbx: Sandbox, remote_root: str = REMOTE_ROOT) -> list[str]:
    r = sbx.commands.run(
        f"find {remote_root} -mindepth 1 -maxdepth 1 -type d -printf '%f\\n' 2>/dev/null || true",
        timeout=60)
    return [l for l in (r.stdout or "").splitlines() if l.strip()]
