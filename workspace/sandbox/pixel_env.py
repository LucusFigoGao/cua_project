"""
PixelSandboxEnv：OSWorld agent server 的瘦客户端。

形状照搬 gym/utils/env.py 的 Env（cua-gym 在阿里云 ECS 上就是这么用的，方法名
screenshot / execute / execute_python_command / get_screen_size 与 server 路由一一
对应），只换了传输层：

    cua-gym (阿里云)：  编排进程 --HTTP--> ECS VM 私网 IP:5000
    这里   (AGS 沙箱)： 编排进程 --envd--> 沙箱内 curl 127.0.0.1:5000

为什么不直连：模板 sdt-hojglb51 **没有对外暴露任何沙箱端口**（实测 5000/9222/8000/
8018/5900/6080 全部返回 310508 "sandbox endpoint is not configured"，只有 envd 自己
的端口可达；Sandbox.create(network=SandboxNetworkOpts(allow_public_traffic=True,
https_ports=[...])) 也改不了，端口暴露是模板级固定的）。所以所有请求都要经 envd 的
commands.run 用 curl 发到 localhost。

实测延迟（活跃实例）：
    动作（move/click 等）  约 540ms
      = envd 往返 35ms + 起 python3 子进程 60ms + import pyautogui 416ms
    screenshot            约 240ms（1920x1080 PNG 约 550KB）

那 416ms 是 OSWorld 这套协议固有的：/execute 和 /run_python 都用 subprocess 执行，
每个动作都要重新 import 一次 pyautogui，上游在真机上也是这个代价。相对 agent 一次
推理（秒级）可以忽略，而且 OSWorld 默认每步后还会 sleep 若干秒。如果将来要压这个
开销，正确做法是给 server 加一个常驻 exec 路由（在 Flask 进程内 exec，pyautogui 已
import），但那是改 OSWorld server 的事，当前不做。

坐标系：**全屏 1920x1080**，不是浏览器 viewport。这是刻意的——osworld/mm_agents 下
50+ 个 agent 全部按"全屏截图 + pyautogui 代码"来 prompt，给浏览器 viewport 截图会
让模型的坐标判断系统性偏移。

a11y 树不可用：沙箱内 pyatspi 无法 import（见 osworld_server.py 顶部说明），所以
get_accessibility_tree() 会抛错，observation_type 只用 "screenshot"。
"""
import json
import shlex
from pathlib import Path
from typing import Any, Optional, Union

from e2b import Sandbox

from . import osworld_server

SCREEN_SIZE = (1920, 1080)

# 照抄 osworld/desktop_env/controllers/python.py 的 PYAUTOGUI_PKGS_PREFIX。
# 它做三件事：import pyautogui、关掉 FAILSAFE（否则鼠标移到角落会抛异常中断任务）、
# 以及修 pyautogui 对 shift 字符的判断（Linux 下 '<' 不需要 shift，上游 pyautogui
# 判错会导致 typewrite 打出错字）。这段不能省——agent 的 typewrite 输出依赖它。
PYAUTOGUI_PKGS_PREFIX = (
    "import pyautogui; import time; import platform; "
    "pyautogui.FAILSAFE = False; "
    "_osworld_shift_chars = '~!@#$%^&*()_+' + chr(123) + chr(125) + '|:\"<>?'; "
    "_osworld_linux_shift_chars = '~!@#$%^&*()_+' + chr(123) + chr(125) + '|:\">?'; "
    "pyautogui.isShiftCharacter = lambda character: character.isupper() or "
    "character in (_osworld_linux_shift_chars if platform.system() == 'Linux' else _osworld_shift_chars); "
    "{command}"
)


class PixelEnvError(Exception):
    pass


class PixelSandboxEnv:
    """
    用法：
        env = PixelSandboxEnv(sbx)                  # 自动确保 server 在跑
        png = env.screenshot()                       # 1920x1080 全屏 PNG
        env.execute_python_command("pyautogui.click(x=500, y=300)")   # mm_agents 原样输出
        env.execute_action({"action_type": "CLICK", "parameters": {...}})  # computer_13
        obs = env.get_obs()                          # {"screenshot": bytes}
    """

    def __init__(self, sbx: Sandbox, port: int = osworld_server.SERVER_PORT,
                 autostart: bool = True, install: bool = True):
        self.sbx = sbx
        self.port = port
        self.base = f"http://127.0.0.1:{port}"
        if autostart:
            osworld_server.ensure_server(sbx, port=port, install=install)

    # ---------- 传输层：经 envd 用 curl 打本地 server ----------

    def _curl(self, args: str, timeout: int = 120, binary_out: Optional[str] = None) -> str:
        cmd = f"curl -s -m {max(10, timeout - 10)} {args}"
        if binary_out:
            cmd = f"{cmd} -o {binary_out} -w '%{{http_code}}'"
        r = self.sbx.commands.run(cmd, timeout=timeout)
        return (r.stdout or "").strip()

    def _get_json(self, route: str, timeout: int = 60) -> Any:
        out = self._curl(f"{self.base}{route}", timeout=timeout)
        return self._parse_json(route, out)

    def _post_json(self, route: str, payload: dict, timeout: int = 120) -> Any:
        body = json.dumps(payload, ensure_ascii=False)
        out = self._curl(
            f"-X POST -H 'Content-Type: application/json' "
            f"--data-binary {shlex.quote(body)} {self.base}{route}",
            timeout=timeout)
        return self._parse_json(route, out)

    def _post_form(self, route: str, fields: dict, timeout: int = 120) -> Any:
        parts = " ".join(f"--data-urlencode {shlex.quote(f'{k}={v}')}" for k, v in fields.items())
        out = self._curl(f"-X POST {parts} {self.base}{route}", timeout=timeout)
        return self._parse_json(route, out)

    @staticmethod
    def _parse_json(route: str, out: str) -> Any:
        if not out:
            return None
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return out  # /platform 之类返回纯文本

    # ---------- 观测 ----------

    def screenshot(self, local_out: Union[str, Path, None] = None) -> bytes:
        """
        抓一张全屏 PNG（1920x1080）。

        走沙箱内临时文件再 files.read，而不是把 PNG 塞进 stdout——envd 的 stdout 是
        文本通道，直接传二进制会被破坏。
        """
        remote = "/tmp/_osw_shot.png"
        code = self._curl(f"{self.base}/screenshot", timeout=120, binary_out=remote)
        if not code.endswith("200"):
            raise PixelEnvError(f"/screenshot 返回 {code}；server 日志：\n"
                                f"{osworld_server.server_log(self.sbx, 15)}")
        data = self.sbx.files.read(remote, format="bytes")
        if local_out:
            Path(local_out).write_bytes(data)
        return data

    def get_obs(self) -> dict:
        """
        组装 mm_agents 期望的 obs dict。

        只给 screenshot：a11y_tree 在本沙箱不可用（pyatspi 装不上），所以 agent 侧
        observation_type 要设成 "screenshot"。
        """
        return {"screenshot": self.screenshot()}

    def get_screen_size(self) -> dict:
        return self._post_json("/screen_size", {}, timeout=60) or {}

    def get_platform(self) -> str:
        return str(self._get_json("/platform", timeout=60) or "")

    def get_accessibility_tree(self) -> str:
        """
        不可用。沙箱内 python3 是 3.12 而 python3-pyatspi 依赖的 _gi 是为 3.13 编译的
        C 扩展，import 必失败；要修得重做模板。此处直接抛错而不是静默返回空串，避免
        上层以为拿到了空树。
        """
        raise PixelEnvError(
            "a11y 树在本沙箱不可用（pyatspi 无法 import，详见 sandbox/osworld_server.py）。"
            "请用 observation_type='screenshot'。")

    # ---------- 动作 ----------

    def execute_python_command(self, command: str, timeout: int = 180) -> dict:
        """
        执行一段 python 代码（通常是 pyautogui 动作）。

        这是 mm_agents 的 action_space="pyautogui" 的直接落点：模型吐出的
        `pyautogui.click(x=500, y=300)` 原样传进来即可，不需要翻译。

        实现照 osworld 的 PythonController.execute_python_command：/execute 路由其实是
        跑 **子进程**（subprocess.run），不是 exec 一段 python，所以必须把代码包成
        ["python3", "-c", PREFIX.format(command=...)] 这样的 argv 列表传过去，并且
        shell=False。之前直接传代码字符串会被 server 端 shlex.split 切碎然后卡住。

        argv 用列表传、不经 shell，所以代码里的引号/分号都不需要再转义。
        """
        payload = {
            "command": ["python3", "-c", PYAUTOGUI_PKGS_PREFIX.format(command=command)],
            "shell": False,
        }
        return self._post_json("/execute", payload, timeout=timeout) or {}

    def run_python_script(self, script: str, timeout: int = 180) -> dict:
        """跑一整段 python 脚本（server 的 /run_python，内部 exec）。"""
        return self._post_json("/run_python", {"code": script}, timeout=timeout) or {}

    def execute(self, command: str, timeout: int = 120) -> dict:
        """执行 shell 命令。对应 server 的 /setup/execute（shell=True）。"""
        return self._post_json("/setup/execute", {"command": command, "shell": True},
                                timeout=timeout) or {}

    def launch(self, command: str, timeout: int = 60) -> dict:
        """非阻塞拉起一个应用。command 按空格切成 argv（与 cua-gym Env.launch 一致）。"""
        return self._post_json("/setup/launch",
                                {"command": command.split(), "shell": False},
                                timeout=timeout) or {}

    def step(self, action, pause: float = 0.5) -> dict:
        """
        执行一个动作并返回新观测，语义对齐 osworld 的 DesktopEnv.step：
          - 字符串           -> 当 pyautogui 代码执行
          - {"command": ...} -> 取 command 执行
          - WAIT/FAIL/DONE   -> 不产生动作
        返回 {"screenshot": bytes}。
        """
        special = ("WAIT", "FAIL", "DONE")
        if action in special or (isinstance(action, dict)
                                 and action.get("action_type") in special):
            pass
        elif isinstance(action, str):
            self.execute_python_command(action)
        elif isinstance(action, dict) and "command" in action:
            self.execute_python_command(action["command"])
        elif isinstance(action, dict):
            self.execute_action(action)
        else:
            raise PixelEnvError(f"无法识别的 action: {type(action)}")

        if pause:
            self.sleep(pause)
        return self.get_obs()

    def sleep(self, seconds: float) -> None:
        """等待。直接用 envd 的 sleep，不绕 server 起一个 python 子进程。"""
        self.sbx.commands.run(f"sleep {seconds}", timeout=int(seconds) + 30)

    def execute_action(self, action: dict) -> None:
        """
        computer_13 风格的 dict 动作。翻译规则照 osworld 的
        PythonController.execute_action（desktop_env/controllers/python.py），
        只实现浏览器任务用得到的那些。
        """
        at = action.get("action_type")
        p = action.get("parameters") or {k: v for k, v in action.items() if k != "action_type"}

        if at in ("WAIT", "FAIL", "DONE"):
            return
        if at == "MOVE_TO":
            self.execute_python_command(f"pyautogui.moveTo({p['x']}, {p['y']})")
        elif at == "CLICK":
            btn = p.get("button", "left")
            n = p.get("num_clicks", 1)
            if "x" in p and "y" in p:
                self.execute_python_command(
                    f"pyautogui.click(button='{btn}', x={p['x']}, y={p['y']}, clicks={n})")
            else:
                self.execute_python_command(f"pyautogui.click(button='{btn}', clicks={n})")
        elif at == "RIGHT_CLICK":
            self.execute_python_command(
                f"pyautogui.click(button='right', x={p['x']}, y={p['y']})"
                if "x" in p else "pyautogui.click(button='right')")
        elif at == "DOUBLE_CLICK":
            self.execute_python_command(
                f"pyautogui.doubleClick(x={p['x']}, y={p['y']})"
                if "x" in p else "pyautogui.doubleClick()")
        elif at == "DRAG_TO":
            self.execute_python_command(
                f"pyautogui.dragTo({p['x']}, {p['y']}, button='left')")
        elif at == "SCROLL":
            self.execute_python_command(f"pyautogui.scroll({p.get('dy', 0)})")
        elif at == "TYPING":
            text = p.get("text", "")
            self.execute_python_command(f"pyautogui.typewrite({text!r})")
        elif at in ("PRESS", "KEY_DOWN", "KEY_UP", "HOTKEY"):
            keys = p.get("keys") or ([p["key"]] if "key" in p else [])
            if at == "HOTKEY" or len(keys) > 1:
                args = ", ".join(repr(k) for k in keys)
                self.execute_python_command(f"pyautogui.hotkey({args})")
            elif keys:
                fn = {"PRESS": "press", "KEY_DOWN": "keyDown", "KEY_UP": "keyUp"}[at]
                self.execute_python_command(f"pyautogui.{fn}({keys[0]!r})")
        else:
            raise PixelEnvError(f"未实现的 computer_13 动作: {at}")

    # ---------- 便捷包装（给冒烟测试和手工调试用）----------

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> None:
        self.execute_python_command(
            f"pyautogui.click(button='{button}', x={x}, y={y}, clicks={clicks})")

    def move(self, x: int, y: int) -> None:
        self.execute_python_command(f"pyautogui.moveTo({x}, {y})")

    def type(self, text: str) -> None:
        self.execute_python_command(f"pyautogui.typewrite({text!r})")

    def key(self, *keys: str) -> None:
        if len(keys) == 1:
            self.execute_python_command(f"pyautogui.press({keys[0]!r})")
        else:
            self.execute_python_command(
                f"pyautogui.hotkey({', '.join(repr(k) for k in keys)})")

    def scroll(self, dy: int) -> None:
        self.execute_python_command(f"pyautogui.scroll({dy})")

    # ---------- 文件 ----------

    def upload(self, local_path: Union[str, Path], remote_path: str) -> None:
        """直接用 envd 的 files.write，不绕 server 的 /setup/upload（multipart 不好用 curl 拼）。"""
        self.sbx.files.write(remote_path, Path(local_path).read_bytes())

    def download(self, remote_path: str) -> bytes:
        return self.sbx.files.read(remote_path, format="bytes")

    # ---------- 浏览器便捷入口 ----------

    def open_url(self, url: str) -> dict:
        """
        在沙箱的常驻 chromium 里打开一个 URL。

        用 CDP 的 PUT /json/new 而不是起新进程：实例里 chromium 由 s6 托管常驻
        （DISPLAY=:1，CDP 9222 在听），新起进程只会把 URL 转交给它。
        """
        quoted = url.replace("'", "%27")
        return self.execute(
            f"curl -s -m 10 -X PUT 'http://127.0.0.1:9222/json/new?{quoted}'")
