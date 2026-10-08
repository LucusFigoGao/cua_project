#!/usr/bin/env python3
"""
【一次性前置】把 gym/bench/artifacts/cua_gym_tasks_v1.tar.zst 解包成 workspace/tasks_data/。

做三件事：
  1. 筛选  —— 只留 app_type 落在 configs/apps.json 那 31 个 mock app 里的任务。
              实测这个条件与 tasks.parquet 的 platform=="web" and setup_kind=="py"
              完全等价（都是 1067 条），而 app_type 就在任务自己的 task.json 里，
              所以这里不读 parquet。
  2. 替换  —— 归档里的 .py 存的是未替换的 __CUA_GYM_<APP>_URL__ 占位符，
              换成沙箱内的 http://host.docker.internal:<port>（见 tasks/urlmap.py）。
  3. 落盘  —— tasks_data/<task_id>/{task.json, initial_setup.py, reward.py}
              + tasks_data/_index.json 供 tasks/catalog.py 快速读取。

跑完之后 tasks_data/ 就是一份自描述的任务库，后续 push_tasks.py 只读它，不再碰归档。

归档遍历有两个坑：zstd 流不可 seek，tar 必须 mode="r|" 单向顺序读完（全量 ~5s）；
归档里混了 macOS 的 ._xxx AppleDouble 伪文件，内容不是 UTF-8，必须按文件名跳过。

Usage:
    python workspace/unpack_tasks.py              # 解全部符合条件的任务
    python workspace/unpack_tasks.py --force       # 已存在的也重新解
    python workspace/unpack_tasks.py --limit 50    # 只解前 50 个（调试用）
"""
import argparse
import json
import os
import re
import shutil
import sys
import tarfile
import time
from pathlib import Path

WORKSPACE = Path(__file__).parent
PROJECT_ROOT = WORKSPACE.parent
sys.path.insert(0, str(WORKSPACE))

from tasks.urlmap import HOST_ALIAS, apply_replacements, build_replacements, load_app_ports

ARCHIVE = PROJECT_ROOT / "gym" / "bench" / "artifacts" / "cua_gym_tasks_v1.tar.zst"
DATA_DIR = WORKSPACE / "tasks_data"

WANTED_FILES = {"task.json", "initial_setup.py", "reward.py"}


def _iter_archive(archive: Path):
    """流式遍历归档，yield (task_id, filename, bytes)，跳过 AppleDouble 伪文件。"""
    import zstandard

    dctx = zstandard.ZstdDecompressor()
    with open(archive, "rb") as fh:
        with dctx.stream_reader(fh) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as tar:
                for member in tar:
                    if not member.isfile():
                        continue
                    name = member.name
                    base = os.path.basename(name)
                    if base.startswith("._") or base not in WANTED_FILES:
                        continue
                    parts = name.split("/")
                    if len(parts) < 2:
                        continue
                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    yield parts[0], base, f.read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="已存在的任务也重新解包")
    ap.add_argument("--limit", type=int, default=0, help="只解前 N 个任务（调试用）")
    ap.add_argument("--archive", type=Path, default=ARCHIVE)
    ap.add_argument("--out", type=Path, default=DATA_DIR)
    args = ap.parse_args()

    if not args.archive.exists():
        print(f"[FAIL] 找不到归档: {args.archive}")
        return 1

    ports = load_app_ports()
    repl = build_replacements(ports)
    print("=== 解包 CUA-Gym web 任务 ===")
    print(f"归档   : {args.archive.relative_to(PROJECT_ROOT)} "
          f"({args.archive.stat().st_size / 1e6:.0f} MB)")
    print(f"输出   : {args.out}")
    print(f"筛选   : app_type ∈ configs/apps.json 的 {len(ports)} 个 mock app")
    print(f"替换表 : {len(repl)} 条占位符")
    print()

    args.out.mkdir(parents=True, exist_ok=True)

    # tar 顺序遍历时同一任务的 task.json / .py 先后顺序不保证，先按 task_id 聚合再判定
    pending: dict[str, dict[str, bytes]] = {}
    written: dict[str, dict] = {}
    skipped_existing = 0
    failed: list[tuple[str, str]] = []
    other_app: dict[str, int] = {}

    t0 = time.time()
    for task_id, base, data in _iter_archive(args.archive):
        bucket = pending.setdefault(task_id, {})
        bucket[base] = data
        if set(bucket) != WANTED_FILES:
            continue

        files = pending.pop(task_id)
        result = _handle_task(task_id, files, ports, repl, args.out, args.force)
        status = result["status"]
        if status == "written":
            written[task_id] = result["meta"]
        elif status == "exists":
            skipped_existing += 1
            written[task_id] = result["meta"]
        elif status == "other_app":
            app = result["app_type"] or "?"
            other_app[app] = other_app.get(app, 0) + 1
        else:
            failed.append((task_id, result["reason"]))

        if args.limit and len(written) >= args.limit:
            break

    elapsed = time.time() - t0

    # 遍历结束仍没齐三个文件的任务。绝大多数是 desktop 任务：它们的 setup 是
    # .sh/.pptx/.docx/.xlsx 而不是 initial_setup.py，所以只有 task.json + reward.py。
    # 这类任务的 app_type 本来就不在 31 个 mock app 里，与 web 评估无关，不值得报警；
    # 只有 app_type 命中 31 个 app 却缺文件才是真问题。
    incomplete = []
    for tid, bucket in pending.items():
        if not bucket or set(bucket) == WANTED_FILES:
            continue
        raw = bucket.get("task.json")
        if raw is None:
            continue
        try:
            if json.loads(raw).get("app_type") in ports:
                incomplete.append((tid, sorted(bucket)))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

    index = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "archive": str(args.archive.relative_to(PROJECT_ROOT)),
        "tasks": written,
    }
    with open(args.out / "_index.json", "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    by_app: dict[str, int] = {}
    for meta in written.values():
        by_app[meta["app_type"]] = by_app.get(meta["app_type"], 0) + 1

    print(f"耗时 {elapsed:.1f}s")
    print(f"已入库 : {len(written)} 个任务，覆盖 {len(by_app)} 个 app")
    if skipped_existing:
        print(f"  其中 {skipped_existing} 个已存在未重解（--force 可强制重解）")
    print(f"非 31-app 的任务（跳过）: {sum(other_app.values())}")
    if failed:
        print(f"[WARN] 剔除 {len(failed)} 个不可用任务（上游数据瑕疵，非本脚本问题）:")
        for tid, reason in failed[:10]:
            print(f"    {tid}  {reason}")
        if len(failed) > 10:
            print(f"    ... 还有 {len(failed) - 10} 个")
    if incomplete:
        print(f"[WARN] 以下 31-app 任务文件残缺 {len(incomplete)} 个: {incomplete[:5]}")

    print()
    print("每个 app 的任务数:")
    for app, n in sorted(by_app.items(), key=lambda kv: -kv[1]):
        print(f"  {app:26s} {n}")
    missing = sorted(set(ports) - set(by_app))
    if missing:
        print(f"\n无 web 任务的 app（已部署但用不上）: {', '.join(missing)}")

    print(f"\n索引: {args.out / '_index.json'}")
    print("下一步: python workspace/push_tasks.py --per-app 3")
    # 被剔除的任务是上游归档的既有瑕疵，不是解包失败，不作为非零退出条件
    return 0


def _handle_task(task_id: str, files: dict[str, bytes], ports: dict[str, int],
                  repl: dict[str, str], out_dir: Path, force: bool) -> dict:
    """处理一个任务：判 app_type → 替换占位符 → 落盘。"""
    try:
        meta = json.loads(files["task.json"])
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return {"status": "failed", "reason": f"task.json 解析失败: {e}"}

    app_type = meta.get("app_type")
    if app_type not in ports:
        return {"status": "other_app", "app_type": app_type}

    tdir = out_dir / task_id
    entry = {
        "app_type": app_type,
        "port": ports[app_type],
        "instruction": meta.get("instruction", ""),
        "difficulty": meta.get("difficulty"),
    }

    if not force and all((tdir / f).exists() for f in WANTED_FILES):
        return {"status": "exists", "meta": entry}

    # 替换两个 .py 里的占位符；残留占位符说明引用了 31 个 app 之外的 mock，
    # 这种任务在当前实例上注定跑不通，不入库。
    rendered: dict[str, str] = {}
    total_repl = 0
    for name in ("initial_setup.py", "reward.py"):
        try:
            src = files[name].decode("utf-8")
        except UnicodeDecodeError as e:
            return {"status": "failed", "reason": f"{name} 非 UTF-8: {e}"}
        text, count, leftover = apply_replacements(src, repl)
        if leftover:
            return {"status": "failed",
                    "reason": f"{name} 残留占位符 {leftover[:3]}"}
        rendered[name] = text
        total_repl += count

    # 上游数据有少量瑕疵任务：归档里直接写死了 172.17.46.46:80xx（另一套部署的 IP 和
    # 端口布局，没留占位符），或者压根不走 HTTP（google_sheets 有个任务是 LibreOffice
    # 本地文件操作）。这些在本实例上跑不通，入库只会让后面的评估拿到假失败，直接剔除。
    expect = f"{HOST_ALIAS}:{ports[app_type]}"
    joined = rendered["initial_setup.py"] + rendered["reward.py"]
    if expect not in joined:
        stray = sorted(set(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}:\d+", joined)))
        reason = f"未引用 {expect}"
        if stray:
            reason += f"，疑似硬编码地址 {stray[:2]}"
        return {"status": "failed", "reason": reason}

    tmp = tdir.with_name(tdir.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    (tmp / "task.json").write_bytes(files["task.json"])
    for name, text in rendered.items():
        (tmp / name).write_text(text)
    if tdir.exists():
        shutil.rmtree(tdir)
    os.replace(tmp, tdir)

    entry["replacements"] = total_repl
    return {"status": "written", "meta": entry}


if __name__ == "__main__":
    sys.exit(main())
