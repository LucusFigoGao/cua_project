"""
把 osworld/mm_agents 的 agent 接到 PixelSandboxEnv 上。

能直接复用的部分（从 osworld/ 原样 import，不改动那边代码）：
  - mm_agents.prompts.SYS_PROMPT_IN_SCREENSHOT_OUT_CODE  系统提示词
  - mm_agents.agent.parse_code_from_string               从模型回复里抠出 ```python``` 代码块
  - mm_agents.agent.encode_image                         图片转 base64

唯一不能直接用 PromptAgent 的原因是**它的 HTTP 调用层和 ichat 不兼容**：

    agent.py:620  elif self.model.startswith("gpt"):          ← 只有 gpt* 走 OPENAI_BASE_URL
    agent.py:624  api_url = base_url.endswith('/v1')
                      and f"{base_url}/chat/completions"
                      or  f"{base_url}/v1/chat/completions"    ← 两种拼法都带 /v1

而 ichat 的真实路径是 `{ICHAT_BASE_URL}/chat/completions`（**不带 /v1**，实测带 /v1
一律 404）。另外 model="qwen*" 在 agent.py:1028 会走 dashscope SDK（阿里云原生 API），
不走 ichat 的 OpenAI 兼容端点。两条路都堵，所以这里自己发请求，但**提示词和动作解析
仍然复用 mm_agents 的**——保证 agent 行为与 OSWorld 一致。

如果以后 ichat 支持了 /v1 前缀，或者换成原生 OpenAI/Anthropic endpoint，直接改用
mm_agents.agent.PromptAgent 即可，本文件的 ScreenshotAgent 可以整个删掉。

观测/动作的契约（已在 smoke_test/test_osworld_server.py 验证）：
    obs    = {"screenshot": bytes}            PixelSandboxEnv.get_obs()
    action = "pyautogui.click(x=.., y=..)"    PixelSandboxEnv.step() 直接吃
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Union

PROJECT_ROOT = Path(__file__).parent.parent.parent
OSWORLD_DIR = PROJECT_ROOT / "osworld"
if str(OSWORLD_DIR) not in sys.path:
    sys.path.insert(0, str(OSWORLD_DIR))

from mm_agents.agent import parse_code_from_string  # noqa: E402
from mm_agents.prompts import SYS_PROMPT_IN_SCREENSHOT_OUT_CODE  # noqa: E402

SPECIAL = ("WAIT", "DONE", "FAIL")


class AgentError(Exception):
    pass


def _chat_url() -> str:
    base = os.environ.get("ICHAT_BASE_URL", "").rstrip("/")
    if not base:
        raise AgentError(
            "ICHAT_BASE_URL 未设置。注意它定义在 ~/.bashrc 里，非交互 shell 不会自动加载，"
            "需要先 `source ~/.bashrc`（或用 bash -lc 跑）。")
    return f"{base}/chat/completions"


def _api_key() -> str:
    key = os.environ.get("ICHAT_API_KEY", "")
    if not key:
        raise AgentError("ICHAT_API_KEY 未设置（同样来自 ~/.bashrc）。")
    return key


class ScreenshotAgent:
    """
    screenshot 观测 + pyautogui 动作空间的 agent。

    行为对齐 mm_agents.PromptAgent 的 observation_type="screenshot" /
    action_space="pyautogui" 组合：同一套系统提示词、同样保留最近
    max_trajectory_length 轮的图文历史、同一个代码解析函数。
    """

    def __init__(self, model: str = "qwen3.8-max", max_tokens: int = 1500,
                 temperature: float = 0.5, top_p: float = 0.9,
                 max_trajectory_length: int = 3, client_password: str = "password",
                 timeout: int = 180, retries: int = 3):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.max_trajectory_length = max_trajectory_length
        self.timeout = timeout
        self.retries = retries
        # 复用 OSWorld 的提示词，保证与官方 baseline 行为一致
        self.system_message = SYS_PROMPT_IN_SCREENSHOT_OUT_CODE.format(
            CLIENT_PASSWORD=client_password)
        self.observations: list[dict] = []
        self.thoughts: list[str] = []
        self.actions: list[list] = []

    def reset(self) -> None:
        self.observations.clear()
        self.thoughts.clear()
        self.actions.clear()

    # ---------- 核心 ----------

    def predict(self, instruction: str, obs: dict) -> tuple[str, list]:
        """
        返回 (模型原始回复, 动作列表)。动作是 pyautogui 代码串或 WAIT/DONE/FAIL。

        历史组装方式照 PromptAgent.predict：system 里带任务指令，然后交替
        user(截图) / assistant(上一步回复)，只保留最近 max_trajectory_length 轮。
        """
        shot = obs["screenshot"]
        self.observations.append({"screenshot": shot})

        messages = [{
            "role": "system",
            "content": [{"type": "text",
                         "text": f"{self.system_message}\n"
                                 f"You are asked to complete the following task: {instruction}"}],
        }]

        start = max(0, len(self.observations) - self.max_trajectory_length)
        for i in range(start, len(self.observations)):
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Given the screenshot as below. "
                                             "What's the next step that you will do "
                                             "to help with the task?"},
                    {"type": "image_url",
                     "image_url": {
                         "url": "data:image/png;base64,"
                                + base64.b64encode(self.observations[i]["screenshot"]).decode(),
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
        self.actions.append(actions)
        return reply, actions

    def _call(self, messages: list) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        req_body = json.dumps(payload).encode()
        last = None
        for attempt in range(self.retries):
            req = urllib.request.Request(
                _chat_url(), data=req_body,
                headers={"Authorization": f"Bearer {_api_key()}",
                         "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = json.loads(r.read())
                msg = data["choices"][0]["message"]
                content = (msg.get("content") or "").strip()
                if content:
                    return content
                # 部分模型（qwen3.x 系列）把预算花在 reasoning_content 上，
                # max_tokens 给太小会导致 content 为空。这不是"没视觉"，是被截断了。
                det = (data.get("usage") or {}).get("completion_tokens_details") or {}
                last = (f"模型返回空 content（reasoning_tokens="
                        f"{det.get('reasoning_tokens')}，max_tokens={self.max_tokens}）。"
                        f"该模型会先输出思维链，请调大 max_tokens。")
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
            except Exception as e:
                last = f"{type(e).__name__}: {str(e)[:200]}"
            if attempt < self.retries - 1:
                time.sleep(2 * (attempt + 1))
        raise AgentError(f"调用模型失败（重试 {self.retries} 次）: {last}")


def run_episode(env, instruction: str, agent: ScreenshotAgent, max_steps: int = 10,
                pause: float = 1.0, screenshot_dir: Union[str, Path, None] = None,
                verbose: bool = True) -> dict:
    """
    跑一个 episode：reset → [predict → step] * max_steps → 汇总。

    时序照 osworld/lib_run_single.py 的 run_single_example：每步先拿观测给 agent，
    再把 agent 吐出的动作逐条执行，遇到 DONE/FAIL 提前结束。
    """
    agent.reset()
    traj = []
    done = False
    verdict = None

    obs = env.get_obs()
    for step in range(1, max_steps + 1):
        if screenshot_dir:
            Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
            (Path(screenshot_dir) / f"step{step:02d}.png").write_bytes(obs["screenshot"])

        reply, actions = agent.predict(instruction, obs)
        if verbose:
            first = reply.strip().splitlines()[0] if reply.strip() else ""
            print(f"  [step {step}] 模型: {first[:88]}")
            print(f"            动作: {actions}")

        for action in actions:
            if action in SPECIAL:
                if action in ("DONE", "FAIL"):
                    done, verdict = True, action
                    break
                env.sleep(pause)
                continue
            obs = env.step(action, pause=pause)

        traj.append({"step": step, "reply": reply, "actions": actions})
        if done:
            break
        obs = env.get_obs()

    return {"steps": len(traj), "done": done, "verdict": verdict, "trajectory": traj}
