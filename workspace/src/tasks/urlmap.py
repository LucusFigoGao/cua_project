"""
占位符替换表：把任务脚本里的 __CUA_GYM_<APP>_URL__ / __CUA_GYM_<APP>_HOST__
换成 host.docker.internal:<port>。

归档里的 initial_setup.py / reward.py 存的是未替换的占位符
（`BASE_URL = '__CUA_GYM_INSTACART_URL__'`），解包时必须做这一步替换。

两种形式：
  __CUA_GYM_<APP>_URL__   -> http://host.docker.internal:<port>   带 scheme
  __CUA_GYM_<APP>_HOST__  -> host.docker.internal:<port>          不带 scheme

APP 段由 app 名去掉 _mock 后缀再大写得到，对 configs/apps.json 的 31 个 app 全部命中。
"""
import re
from typing import Optional

from src.settings import HOST_ALIAS, app_ports

PLACEHOLDER_RE = re.compile(r"__CUA_GYM_[A-Z0-9_]+__")

# 非规范占位符 -> 规范 app 名。__CUA_GYM_NOTION_MOCK_URL__ 多了 _MOCK 段，推导规则覆盖不到。
ALIASES = {
    "__CUA_GYM_NOTION_MOCK_URL__": ("notion_mock", "url"),
}


def app_stem(app: str) -> str:
    """instacart_mock -> INSTACART，用于拼占位符名。"""
    return re.sub(r"_mock$", "", app).upper()


def build_replacements(apps: Optional[dict[str, int]] = None) -> dict[str, str]:
    """生成 {占位符: 替换值}。每个 app 两条（_URL__ / _HOST__），外加 ALIASES。"""
    apps = apps or app_ports()
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

    残留非空说明脚本引用了 31 个 app 之外的 mock app，这种任务跑不通，调用方应当丢弃。
    """
    repl = repl if repl is not None else build_replacements()
    count = 0
    for token, value in repl.items():
        if token in src:
            count += src.count(token)
            src = src.replace(token, value)
    leftover = sorted(set(PLACEHOLDER_RE.findall(src)))
    return src, count, leftover
