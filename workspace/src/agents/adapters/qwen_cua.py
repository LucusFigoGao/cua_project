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
    from mm_agents.qwen import QwenAgent

    _silence_debug_dump()
    _patch_single_action_prompt()
    return QwenAgent(model=model, base_url=base_url, api_key=api_key, **kw)


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
