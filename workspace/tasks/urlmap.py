"""
占位符替换表：把任务脚本里的 __CUA_GYM_<APP>_URL__ / __CUA_GYM_<APP>_HOST__
换成沙箱内的 host.docker.internal:<port>。

归档 cua_gym_tasks_v1.tar.zst 里的 initial_setup.py / reward.py 保留的是**未替换的
占位符**（`BASE_URL = '__CUA_GYM_INSTACART_URL__'`），不是 /data/workspace/tasks_web
下那份已经替换好的产物。所以解包时必须做这一步替换，否则 setup 会去连
`__CUA_GYM_INSTACART_URL__` 这种非法地址。

两种形式（实测扫 4000 个 .py 共 38 种占位符）：
  __CUA_GYM_<APP>_URL__   -> http://host.docker.internal:<port>   带 scheme
  __CUA_GYM_<APP>_HOST__  -> host.docker.internal:<port>          不带 scheme

APP 段由 app 名去掉 _mock 后缀再大写得到，已验证对 configs/apps.json 里 31 个 app
31/31 全部命中 tasks_web/url_variables.json 记录的 env 名。
"""
import json
import re
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path(__file__).parent.parent / "configs" / "apps.json"
HOST_ALIAS = "host.docker.internal"

PLACEHOLDER_RE = re.compile(r"__CUA_GYM_[A-Z0-9_]+__")

# 少数任务用的非规范占位符 -> 规范 app 名。
# __CUA_GYM_NOTION_MOCK_URL__ 多了 _MOCK 段（4 个任务用到），推导规则覆盖不到，单列。
ALIASES = {
    "__CUA_GYM_NOTION_MOCK_URL__": ("notion_mock", "url"),
}


def load_app_ports(path: Optional[Path] = None) -> dict[str, int]:
    """读 configs/apps.json，返回 {app_name: port}。"""
    with open(path or CONFIG_PATH) as f:
        data = json.load(f)
    return {a["app"]: a["port"] for a in data["apps"]}


def app_stem(app: str) -> str:
    """instacart_mock -> INSTACART，用于拼占位符名。"""
    return re.sub(r"_mock$", "", app).upper()


def build_replacements(apps: Optional[dict[str, int]] = None) -> dict[str, str]:
    """生成 {占位符: 替换值}。每个 app 两条（_URL__ / _HOST__），外加 ALIASES。"""
    apps = apps or load_app_ports()
    repl: dict[str, str] = {}
    for app, port in apps.items():
        stem = app_stem(app)
        repl[f"__CUA_GYM_{stem}_URL__"] = f"http://{HOST_ALIAS}:{port}"
        repl[f"__CUA_GYM_{stem}_HOST__"] = f"{HOST_ALIAS}:{port}"
    for token, (app, kind) in ALIASES.items():
        port = apps.get(app)
        if port is None:
            continue
        repl[token] = f"http://{HOST_ALIAS}:{port}" if kind == "url" else f"{HOST_ALIAS}:{port}"
    return repl


def apply_replacements(src: str, repl: Optional[dict[str, str]] = None) -> tuple[str, int, list[str]]:
    """
    替换 src 里的占位符，返回 (结果文本, 替换次数, 替换后仍残留的占位符)。

    残留非空说明脚本引用了 31 个 app 之外的 mock app——这种任务在当前实例上跑不通，
    调用方应当丢弃它而不是推上去。
    """
    repl = repl if repl is not None else build_replacements()
    count = 0
    for token, value in repl.items():
        if token in src:
            count += src.count(token)
            src = src.replace(token, value)
    leftover = sorted(set(PLACEHOLDER_RE.findall(src)))
    return src, count, leftover
