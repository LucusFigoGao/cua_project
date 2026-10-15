"""
Claude 镜头：osworld/mm_agents/anthropic 的 AnthropicAgent。

它已经吐 pyautogui 代码串，动作方言不需要翻译。

base_url 的注入方式与另外两只不同：AnthropicAgent 内部走
anthropic/utils.py::make_anthropic_client，那个 helper 只接 api_key，不接
base_url。好在 Anthropic SDK 认 ANTHROPIC_BASE_URL 环境变量，所以在构造前设上
即可——osworld/ 下的文件仍然不动。

它要两个观测键：screenshot 和 screenshot_original。机身两个都提供（同一份未缩放原图），缩放由镜头自己决定。
"""
import os
from typing import Any

from src.agents.mount import LensSpec, register


class ClaudeLens:
    """
    把 AnthropicAgent 的 tool_use dict 摊平成 pyautogui 串。

    它吐的每个动作长这样（截断）：

        {"name": "computer", "action_type": "tool_use",
         "input": {"action": "left_click", "coordinate": [249, 19]},
         "command": "pyautogui.click(373, 28)\\n", "raw_response": "[THINKING] ..."}

    PixelSandboxEnv.step() 认 dict 里的 command 键，所以原样传也能跑；但整条
    dict 进日志没法看，而且后面做动作归因只需要 command。所以这里取出 command，
    原始 dict 收进 extra 备查。

    注意 coordinate [249,19] 与 command 里的 (373,28) 差 1.5 倍——AnthropicAgent
    内部按 screen_size 做了缩放回算，不需要我们再换算。
    """

    def __init__(self, agent: Any):
        self.agent = agent

    def reset(self, _logger=None, *a, **kw):
        self.agent.reset(_logger)

    def predict(self, instruction: str, obs: dict) -> tuple[str, list, dict]:
        reasonings, raw = self.agent.predict(instruction, obs)

        actions: list = []
        texts: list[str] = []
        for a in raw or []:
            if not isinstance(a, dict):
                actions.append(a)
                continue
            at = str(a.get("action_type", ""))
            if at in ("DONE", "FAIL", "WAIT"):
                actions.append(at)
                continue
            cmd = a.get("command")
            actions.append(cmd if isinstance(cmd, str) and cmd.strip() else a)
            if a.get("raw_response"):
                texts.append(str(a["raw_response"]))

        reply = "\n".join(texts) if texts else str(reasonings or "")
        return reply, actions, {"raw_actions": raw}


def build(*, model: str, base_url: str, api_key: str, **kw):
    # make_anthropic_client 不接 base_url，但 SDK 读这个环境变量。
    os.environ["ANTHROPIC_BASE_URL"] = base_url
    from mm_agents.anthropic.main import AnthropicAgent

    return ClaudeLens(AnthropicAgent(model=model, api_key=api_key, **kw))


register(LensSpec(
    name="claude-cu",
    build=build,
    default_model="claude-sonnet-4-6",
    channel="anthropic",
    obs_keys=("screenshot", "screenshot_original"),
    coordinate_space="absolute",
    defaults={
        "action_space": "claude_computer_use",
        "screen_size": (1920, 1080),
        "only_n_most_recent_images": 10,
        "max_tokens": 4096,
    },
    notes="直接吐 pyautogui 串；base_url 经 ANTHROPIC_BASE_URL 注入",
))
