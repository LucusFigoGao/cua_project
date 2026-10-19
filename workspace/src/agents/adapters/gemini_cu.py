"""
Gemini adapter：osworld/mm_agents/gemini_agent.py 的 GeminiFCAgent。

它接收一个构造好的 genai.Client，所以 ichat 的 google-genai 通道直接注入即可，
不需要改 osworld/ 里的任何东西。

这个 adapter 要做一层格式翻译，因为 GeminiFCAgent 吐的是第三种动作格式：

    {"action_type": "computer_agent_api:click", "parameters": {"x": .., "y": ..}}

既不是 pyautogui 代码串，也不是 computer_13 dict。而且 **x/y 是 0-999 归一化**
（FunctionDeclaration 的 schema 里明写 "0 (left) to 999 (right) of the screen"），
必须按实际分辨率换算成像素。osworld 仓库里没有现成的转换器，所以在这里写。
"""
import io
from typing import Any

from src.agents.registry import AdapterSpec, register

_P = "computer_agent_api:"


def _xy(params: dict, w: int, h: int, kx: str = "x", ky: str = "y"):
    """0-999 归一化 → 像素。"""
    return (int(float(params[kx]) / 999 * w), int(float(params[ky]) / 999 * h))


def _to_pyautogui(action: dict, w: int, h: int) -> list[str]:
    """把一个 gemini function call 翻成 pyautogui 代码串（或特殊动作）。"""
    at = str(action.get("action_type", ""))
    p = action.get("parameters") or {}

    if at == "done":
        return ["DONE"]
    if at == "thought":
        return []
    if at in ("safety_error", "parsing_error"):
        return ["FAIL"]
    if not at.startswith(_P):
        return []

    op = at[len(_P):]
    simple = {"click": "click", "double_click": "doubleClick",
              "triple_click": "tripleClick", "middle_click": "middleClick",
              "right_click": "rightClick", "move": "moveTo"}
    if op in simple:
        x, y = _xy(p, w, h)
        return [f"pyautogui.{simple[op]}({x}, {y})"]
    if op in ("mouse_down", "mouse_up"):
        x, y = _xy(p, w, h)
        fn = "mouseDown" if op == "mouse_down" else "mouseUp"
        return [f"pyautogui.moveTo({x}, {y})", f"pyautogui.{fn}()"]
    if op == "drag_and_drop":
        sx, sy = _xy(p, w, h, "start_x", "start_y")
        ex, ey = _xy(p, w, h, "end_x", "end_y")
        return [f"pyautogui.moveTo({sx}, {sy})",
                f"pyautogui.dragTo({ex}, {ey}, duration=0.5)"]
    if op == "type":
        out = [f"pyautogui.typewrite({str(p.get('text', ''))!r}, interval=0.02)"]
        if p.get("press_enter"):
            out.append("pyautogui.press('enter')")
        return out
    if op == "press_key":
        return [f"pyautogui.press({str(p.get('key', ''))!r})"]
    if op == "key_down":
        return [f"pyautogui.keyDown({str(p.get('key', ''))!r})"]
    if op == "key_up":
        return [f"pyautogui.keyUp({str(p.get('key', ''))!r})"]
    if op == "hotkey":
        keys = p.get("keys") or []
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.replace("+", ",").split(",") if k.strip()]
        return [f"pyautogui.hotkey({', '.join(repr(str(k)) for k in keys)})"] if keys else []
    if op == "scroll":
        mag = int(float(p.get("magnitude_in_wheel_clicks", 3) or 3))
        down = str(p.get("direction", "down")).lower() in ("down", "bottom")
        out = []
        if "x" in p and "y" in p:
            x, y = _xy(p, w, h)
            out.append(f"pyautogui.moveTo({x}, {y})")
        out.append(f"pyautogui.scroll({-mag if down else mag})")
        return out
    if op == "wait":
        return ["WAIT"]
    if op == "take_screenshot":
        # 下一轮本来就会重新抓屏，这里不必产生动作。
        return []
    if op == "infeasible":
        return ["FAIL"]
    return []


class GeminiPyAutoGUIAdapter:
    """包住 GeminiFCAgent，把它的 function call 翻成 pyautogui 串。"""

    def __init__(self, agent: Any):
        self.agent = agent

    def reset(self, _logger=None, *a, **kw):
        self.agent.reset(_logger)

    def predict(self, instruction: str, obs: dict) -> tuple[str, list]:
        from PIL import Image
        w, h = Image.open(io.BytesIO(obs["screenshot"])).size

        _text, raw_actions = self.agent.predict(instruction, obs)

        actions: list[str] = []
        thoughts: list[str] = []
        for a in raw_actions or []:
            if isinstance(a, dict) and a.get("action_type") == "thought":
                thoughts.append(str(a.get("parameters", "")))
            if isinstance(a, dict):
                actions.extend(_to_pyautogui(a, w, h))
        reply = "\n".join(thoughts) if thoughts else str(_text or "")
        return reply, actions


def build(*, model: str, base_url: str, api_key: str, **kw):
    from google import genai
    from mm_agents import gemini_agent as ga

    # GeminiFCAgent 没有 max_tokens（生成长度由 thinking_level 间接控制）。
    # 通用旋钮在这里消化掉，不要让它冒到调用方去。
    kw.pop("max_tokens", None)
    retries = int(kw.pop("api_retry_times", 4))

    # 上游写死 API_RETRY_TIMES=500（gemini_agent.py:12）。对 400 这类永不恢复的
    # 错误，它会一直重试到墙上时间耗尽——表现为"卡住"而不是报错，批跑时致命。
    # 第 574 行是运行时读模块全局，所以改属性即可，osworld/ 下的文件不动。
    ga.API_RETRY_TIMES = retries
    ga.GEMINI_DI = ga.GEMINI_DI + (
        "\n* IMPORTANT: Output exactly ONE function call per response. "
        "Do not combine multiple actions in a single turn."
    )
    GeminiFCAgent = ga.GeminiFCAgent

    client = genai.Client(api_key=api_key, http_options={"base_url": base_url})
    return GeminiPyAutoGUIAdapter(
        GeminiFCAgent(client=client, model_id=model, **kw))


register(AdapterSpec(
    name="gemini-cu",
    build=build,
    default_model="gemini-3.5-flash",
    channel="google_genai",
    obs_keys=("screenshot",),
    coordinate_space="relative",
    # action_space="pyautogui" 用 COMPLETE_OSWORLD_ACTIONS 那 18 个
    # FunctionDeclaration；"gemini_computer_use" 走原生 Computer Use tool，
    # 函数名与参数不同，本 adapter 的翻译表对不上。
    defaults={"action_space": "pyautogui", "thinking_level": "medium"},
    notes="function call 0-999 归一化，本 adapter 负责换算成像素",
))
