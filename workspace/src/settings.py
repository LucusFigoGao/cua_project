"""全局常量与路径。所有模块从这里取配置，不各自硬编码。"""
import os
from pathlib import Path

# src/settings.py → src/ → workspace/ → cua_project/
WORKSPACE = Path(__file__).resolve().parent.parent
PROJECT_ROOT = WORKSPACE.parent

CONFIGS = WORKSPACE / "configs"
APPS_JSON = CONFIGS / "apps.json"
REGISTRY = CONFIGS / "sandbox_pool.json"
TASKS_DATA = WORKSPACE / "tasks_data"
RESULTS = WORKSPACE / "results"
TASK_ARCHIVE = PROJECT_ROOT / "gym" / "bench" / "artifacts" / "cua_gym_tasks_v1.tar.zst"

# 沙箱
SANDBOX_TEMPLATE = "sdt-0ld6f9gj"
SANDBOX_TIMEOUT = 900  # 24h
POOL_MAX_SIZE = 12       # AGS 配额：50C / 4C每实例 = 12
POOL_TAG = {"pool": "cua_gym"}

# 任务脚本里硬编码的主机名，由沙箱 /etc/hosts 映射到开发机
HOST_ALIAS = "host.docker.internal"
REMOTE_TASK_ROOT = "/tmp/cua_tasks"

# OSWorld agent server：从 osworld/ 取源码，装到沙箱的 OSWORLD_SERVER_DIR 下常驻
SERVER_SRC = PROJECT_ROOT / "osworld" / "desktop_env" / "server" / "main.py"
PYXCURSOR_SRC = PROJECT_ROOT / "osworld" / "desktop_env" / "server" / "pyxcursor.py"
OSWORLD_SERVER_DIR = "/opt/osworld_server"
SERVER_PORT = 5000
SERVER_LOG = "/tmp/osworld_server.log"
DISPLAY = ":1"          # 沙箱的 Xvfb 跑在 :1
SCREEN_W, SCREEN_H = 1920, 1080

# 模型：qwen3.x 先输出思维链再给 content，max_tokens 给小了 content 会为空。
# 实测 3000 不够一步的思维链，截断后 content 为空，所以给到 8000。
DEFAULT_MODEL = "qwen3.8-max"
DEFAULT_MAX_TOKENS = 16384

# ichat 的三条 SDK 兼容通道直接从环境变量中读取
ICHAT_CHANNELS = {
    "openai": os.environ.get("ICHAT_BASE_URL"),
    "anthropic": os.environ.get("ICHAT_ANTHROPIC_BASE_URL"),
    "google_genai": os.environ.get("ICHAT_DASHSCOPE_BASE_URL")
}


def ichat_key() -> str:
    """ICHAT_API_KEY。定义在 ~/.zshrc，非交互 shell 不会自动加载。"""
    return os.environ.get("ICHAT_API_KEY", "")

# AGS 域名不走代理
os.environ.setdefault("NO_PROXY", "*.tencentags.com,*.woa.com,*.tencentyun.com")

_PORTS_CACHE: dict[str, int] | None = None


def app_ports() -> dict[str, int]:
    """读 configs/apps.json，返回 {app_type: port}。这是 app 与端口的唯一事实来源。"""
    global _PORTS_CACHE
    if _PORTS_CACHE is None:
        import json
        data = json.loads(APPS_JSON.read_text())
        _PORTS_CACHE = {a["app"]: a["port"] for a in data["apps"]}
    return dict(_PORTS_CACHE)
