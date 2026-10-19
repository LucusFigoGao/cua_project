"""
通用 VLM adapter：不挑模型，任何能读图的 chat 模型都能装。

提示词和动作解析从 osworld/mm_agents 原样 import（SYS_PROMPT_IN_SCREENSHOT_OUT_CODE、
parse_code_from_string），行为对齐 PromptAgent 的 observation_type="screenshot" /
action_space="pyautogui" 组合。

不直接用 mm_agents.PromptAgent，因为它的 HTTP 层与 ichat 不兼容：
    agent.py:620  elif self.model.startswith("gpt"):   只有 gpt* 走 OPENAI_BASE_URL
    agent.py:624  两种 URL 拼法都带 /v1
而 ichat 的真实路径是 {base}/chat/completions，带 /v1 一律 404；model="qwen*" 还会在
agent.py:1028 走 dashscope SDK。两条路都堵，所以这里自己发请求。

坐标空间：告诉模型屏幕是 1000x1000，模型输出 0-999 相对坐标，adapter 把 pyautogui
代码里的坐标换算成真实的 1920x1080 像素。与 qwen-cua / qwen3vl 的相对坐标机制一致。
"""
import base64
import json
import re
import time
import urllib.error
import urllib.request

from src.agents.registry import AdapterSpec, register  # 先导入它，osworld path 在那里加

from mm_agents.agent import parse_code_from_string          # noqa: E402
from mm_agents.prompts import SYS_PROMPT_IN_SCREENSHOT_OUT_CODE  # noqa: E402

_SCREEN_W, _SCREEN_H = 1920, 1080

_COORD_FUNCS = (
    "click", "moveTo", "moveRel", "dragTo", "dragRel",
    "doubleClick", "rightClick", "tripleClick", "middleClick",
)
_COORD_RE = re.compile(
    r"(pyautogui\.(?:" + "|".join(_COORD_FUNCS) + r")\s*\()"
    r"\s*(?:x\s*=\s*)?(\d+(?:\.\d+)?)"
    r"\s*,\s*(?:y\s*=\s*)?(\d+(?:\.\d+)?)"
    r"(.*)",
)


def _scale_relative_coords(code: str,
                           w: int = _SCREEN_W, h: int = _SCREEN_H) -> str:
    """把 pyautogui 代码里的 0-999 相对坐标换算成实际像素。"""
    def _sub(m):
        prefix = m.group(1)
        x = int(float(m.group(2)) / 999 * w)
        y = int(float(m.group(3)) / 999 * h)
        return f"{prefix}{x}, {y}{m.group(4)}"
    return _COORD_RE.sub(_sub, code)


class AgentError(Exception):
    pass


def _extract_usage(usage) -> dict:
    """从 OpenAI 兼容 API 的 usage 对象提取标准化 token 计数。"""
    if not usage:
        return {}
    if isinstance(usage, dict):
        return {k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                if k in usage}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


class ScreenshotAgent:
    """screenshot 观测 + pyautogui 动作空间，走 OpenAI 兼容 chat 接口。"""

    def __init__(self, model: str, base_url: str, api_key: str,
                 max_tokens: int = 16384, temperature: float = 0.0,
                 top_p: float = 0.9, max_trajectory_length: int = 3,
                 client_password: str = "password", timeout: int = 180,
                 retries: int = 3, max_token_ceiling: int = 32768):
        self.model = model
        self.chat_url = f"{base_url.rstrip('/')}/chat/completions"
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.max_token_ceiling = max_token_ceiling
        self.temperature = temperature
        self.top_p = top_p
        self.max_trajectory_length = max_trajectory_length
        self.timeout = timeout
        self.retries = retries
        self.system_message = SYS_PROMPT_IN_SCREENSHOT_OUT_CODE.format(
            CLIENT_PASSWORD=client_password) + (
            "\nThe screen's resolution is 1000x1000."
            "\nIMPORTANT: Return exactly ONE action per step. "
            "Do not output multiple code blocks or multiple actions in a single response."
        )
        self.observations: list[dict] = []
        self.thoughts: list[str] = []
        self.actions: list[list] = []
        self._last_usage: dict = {}

    def reset(self, _logger=None, *args, **kwargs) -> None:
        self.observations.clear()
        self.thoughts.clear()
        self.actions.clear()
        self._last_usage = {}

    def predict(self, instruction: str, obs: dict) -> tuple[str, list]:
        """
        历史组装照 PromptAgent.predict：system 带任务指令，然后交替
        user(截图) / assistant(上一步回复)，只保留最近 max_trajectory_length 轮。
        """
        self.observations.append({"screenshot": obs["screenshot"]})

        messages = [{
            "role": "system",
            "content": [{"type": "text",
                         "text": f"{self.system_message}\n"
                                 f"You are asked to complete the following task: "
                                 f"{instruction}"}],
        }]

        start = max(0, len(self.observations) - self.max_trajectory_length)
        for i in range(start, len(self.observations)):
            shot = self.observations[i]["screenshot"]
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Given the screenshot as below. "
                                             "What's the next step that you will do "
                                             "to help with the task?"},
                    {"type": "image_url",
                     "image_url": {
                         "url": "data:image/png;base64,"
                                + base64.b64encode(shot).decode(),
                         "detail": "high"}},
                ],
            })
            if i < len(self.thoughts):
                messages.append({"role": "assistant",
                                 "content": [{"type": "text", "text": self.thoughts[i]}]})

        reply = self._call(messages)
        self.thoughts.append(reply)
        try:
            actions = parse_code_from_string(reply)
        except Exception as e:
            raise AgentError(f"解析模型回复失败: {e}\n原始回复: {reply[:300]}") from e
        actions = [_scale_relative_coords(a) if isinstance(a, str) else a
                   for a in actions]
        self.actions.append(actions)
        return reply, actions, {"usage": self._last_usage}

    def _call(self, messages: list) -> str:
        payload = {"model": self.model, "messages": messages,
                   "temperature": self.temperature, "top_p": self.top_p}
        last = None
        budget = self.max_tokens
        for attempt in range(self.retries):
            payload["max_tokens"] = budget
            req = urllib.request.Request(
                self.chat_url, data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.loads(r.read())
                self._last_usage = _extract_usage(data.get("usage"))
                msg = data["choices"][0]["message"]
                content = (msg.get("content") or "").strip()
                if content:
                    return content
                det = (data.get("usage") or {}).get("completion_tokens_details") or {}
                last = (f"模型返回空 content（reasoning_tokens="
                        f"{det.get('reasoning_tokens')}，max_tokens={budget}）")
                budget = min(budget * 2, self.max_token_ceiling)
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
            except Exception as e:
                last = f"{type(e).__name__}: {str(e)[:200]}"
            if attempt < self.retries - 1:
                time.sleep(2 * (attempt + 1))
        raise AgentError(f"调用模型失败（重试 {self.retries} 次）: {last}")


def build(*, model: str, base_url: str, api_key: str, **kw):
    return ScreenshotAgent(model=model, base_url=base_url, api_key=api_key, **kw)


register(AdapterSpec(
    name="raw-vlm",
    build=build,
    default_model="qwen3.8-max",
    channel="openai",
    obs_keys=("screenshot",),
    coordinate_space="relative",
    defaults={"temperature": 0.0, "max_tokens": 16384},
    notes="OSWorld 提示词 + 1000x1000 相对坐标（adapter 做反变换到 1920x1080）",
))
