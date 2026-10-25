"""
Qwen-CUA adapter：osworld/mm_agents/qwen 的 QwenAgent。

那个包是 Qwen-CUA 论文（arXiv 2608.02352）的官方 scaffold，README 示例模型
qwen3.7-plus，与 ichat 上的 qwen3.8-max 同代。它自带几样我们本来要自己写的东西：

    client.py::merge_reasoning_content   把 reasoning_content 包进 <think> 与 content 合并
    images.py::process_image             smart_resize 到 factor=32（1920x1080 -> 1920x1088）
    images.py::adjust_coordinates        relative(0-999) / absolute 坐标反变换
    history.py::update_folding_state     超过 image_max 张时把最老截图折叠成占位文字
    parser.py::looks_infeasible_response 识别「这做不到」类回复 -> FAIL

不用同目录的 qwen3vl_agent.py：它的 _call_llm_openai 不处理 reasoning_content，
走 openai 后端会静默返回空串；且 tool_call 是 JSON 格式，与本包的 XML 格式不通用。
"""
from src.agents.registry import AdapterSpec, register


def _silence_debug_dump() -> None:
    """
    关掉 QwenAgent 每步往 ./draft/message_cache/ 写 JSON 的行为。
    """
    from mm_agents.qwen import main as qwen_main
    qwen_main.dump_debug_messages = lambda *a, **kw: None


def _patch_single_action_prompt() -> None:
    """在 Rules 区追加单动作约束。只 patch 一次。"""
    from mm_agents.qwen import prompts as qwen_prompts
    marker = "Output exactly ONE <tool_call>"
    fn = qwen_prompts.build_internal_system_prompt
    if marker in (fn.__doc__ or ""):
        return
    _orig = fn

    def _patched(*a, **kw):
        text = _orig(*a, **kw)
        return text + (
            "\n- IMPORTANT: Output exactly ONE <tool_call> block per response. "
            "Never output multiple <tool_call> blocks in a single turn."
        )
    _patched.__doc__ = (fn.__doc__ or "") + marker
    qwen_prompts.build_internal_system_prompt = _patched


def build(*, model: str, base_url: str, api_key: str, **kw):
    import openai as _openai
    from mm_agents.qwen import QwenAgent
    from mm_agents.qwen.client import extract_message_field, merge_reasoning_content

    _silence_debug_dump()
    _patch_single_action_prompt()

    retryable = (_openai.APIConnectionError, _openai.APITimeoutError,
                 _openai.RateLimitError, _openai.InternalServerError)

    class _PatchedQwenAgent(QwenAgent):
        """覆写 call_llm 捕获 token usage。"""

        def __init__(self, **init_kw):
            super().__init__(**init_kw)
            self._last_usage: dict = {}
            self._oai_client = _openai.OpenAI(
                base_url=init_kw.get("base_url") or base_url,
                api_key=init_kw.get("api_key") or api_key,
                timeout=180)

        def call_llm(self, payload, model_name):
            last = None
            for attempt in range(1, 4):
                try:
                    resp = self._oai_client.chat.completions.create(
                        model=model_name,
                        messages=payload["messages"],
                        max_tokens=payload.get("max_tokens", self.max_tokens),
                        temperature=payload.get("temperature", self.temperature),
                        top_p=payload.get("top_p", self.top_p),
                    )
                except retryable as e:
                    last = e
                    import time; time.sleep(min(5.0 * attempt, 30.0))
                    continue
                except _openai.APIError:
                    raise
                usage = resp.usage
                self._last_usage = {
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),
                    "completion_tokens": getattr(usage, "completion_tokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None),
                } if usage else {}
                msg = resp.choices[0].message
                content = extract_message_field(msg, "content")
                reasoning = extract_message_field(msg, "reasoning_content")
                return merge_reasoning_content(content, reasoning)
            if last is not None:
                raise last
            return ""

        def predict(self, instruction, obs):
            text, actions = super().predict(instruction, obs)
            return text, actions, {"usage": self._last_usage}

    return _PatchedQwenAgent(model=model, base_url=base_url, api_key=api_key, **kw)


register(AdapterSpec(
    name="qwen-cua",
    build=build,
    default_model="qwen3.8-max",
    channel="openai",
    obs_keys=("screenshot",),
    coordinate_space="relative",
    defaults={
        "temperature": 0.0,
        "top_p": 0.9,
        "max_tokens": 16384,
        "coordinate_type": "relative",
        "observation_type": "screenshot",
        "action_space": "pyautogui",
        "image_max": 20,
        "fold_size": 10,
        "history_n": 100,
    },
    notes="Qwen-CUA 官方 scaffold；coordinate_type 可切 relative/absolute",
))
