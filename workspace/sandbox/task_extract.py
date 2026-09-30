"""
一次顺序扫描任务压缩包, 把指定任务提取到目录, 同时把地址占位符替换成沙箱内地址。

为什么要这样做: gym.utils.SandboxEnv.download_task 每处理一个任务都要把整个压缩包(8.7万个成员)从头扫一遍,
本机实测扫一遍约 7 秒, 1417 个任务累计要几个小时; 这里一次扫描全部提取, 之后每个任务零等待。

本文件只依赖标准库和 zstandard, 既在本机被 import 使用, 也会被上传到沙箱里当脚本运行:
    python3 task_extract.py --archive A.tar.zst --out DIR --ids ids.json --repl repl.json --report report.json
"""
from __future__ import annotations

import argparse
import json
import re
import tarfile
import time
from pathlib import Path
from typing import Dict, Iterable

PLACEHOLDER = re.compile(r"__CUA_GYM_[A-Z0-9_]+__")
# 沙箱里没有 google-chrome 桌面窗口, 注释掉启动它的那一行(与 SandboxEnv.download_task 里的 sed 等价)
LAUNCH_GUI = re.compile(r"^(?P<line>.*launch_gui\(f'google-chrome.*)$", re.M)
TEXT_SUFFIXES = (".py", ".json", ".sh", ".txt", ".md")


def transform_text(name: str, text: str, replacements: Dict[str, str]) -> str:
    for k, v in replacements.items():
        text = text.replace(k, v)
    if name == "initial_setup.py":
        text = LAUNCH_GUI.sub(r"#\g<line>", text)
    return text


def extract_tasks(archive: str, out_dir: str, task_ids: Iterable[str], replacements: Dict[str, str]) -> dict:
    import zstandard

    wanted = set(task_ids)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seen, files = set(), 0
    unresolved: Dict[str, set] = {}
    t0 = time.time()
    with open(archive, "rb") as f, zstandard.ZstdDecompressor().stream_reader(f) as reader:
        with tarfile.open(fileobj=reader, mode="r|") as tar:
            for m in tar:
                parts = m.name.split("/")
                if len(parts) < 2 or parts[0] not in wanted or not m.isfile():
                    continue
                base = parts[-1]
                if base.startswith("._"):  # macOS 打包带进来的资源叉文件, 不是任务内容
                    continue
                data = tar.extractfile(m).read()
                if base.endswith(TEXT_SUFFIXES):
                    try:
                        text = transform_text(base, data.decode("utf-8"), replacements)
                    except UnicodeDecodeError:
                        text = None
                    if text is not None:
                        left = set(PLACEHOLDER.findall(text))
                        if left:
                            unresolved.setdefault(parts[0], set()).update(left)
                        data = text.encode("utf-8")
                dest = out / m.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                seen.add(parts[0])
                files += 1
    return {
        "requested": len(wanted),
        "extracted": len(seen),
        "files": files,
        "missing": sorted(wanted - seen),
        # 替换后仍残留占位符的任务(比如依赖 URL 模板或没部署的网页), 这些任务在该实例上跑不了
        "unresolved": {k: sorted(v) for k, v in sorted(unresolved.items())},
        "seconds": round(time.time() - t0, 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ids", required=True, help="JSON 文件, 任务 id 列表")
    ap.add_argument("--repl", required=True, help="JSON 文件, 占位符到地址的映射")
    ap.add_argument("--report", required=True)
    a = ap.parse_args()
    report = extract_tasks(a.archive, a.out, json.load(open(a.ids)), json.load(open(a.repl)))
    Path(a.report).write_text(json.dumps(report, ensure_ascii=False))
    print(json.dumps({k: v for k, v in report.items() if k not in ("missing", "unresolved")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
