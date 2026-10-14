"""
Qwen-CUA 镜头：osworld/mm_agents/qwen 的 QwenAgent。

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
from src.agents.mount import LensSpec, register


def _silence_debug_dump() -> None:
    """
    关掉 QwenAgent 每步往 ./draft/message_cache/ 写 JSON 的行为。

    那是个 cwd 相对路径的硬编码（qwen/history.py:119），批跑会产生上万个文件。
    main.py 是 `from .history import dump_debug_messages` 直接取进自己命名空间的，
    所以要打在 main 上，打在 history 上不生效。osworld/ 下的文件不动。
    """
    from mm_agents.qwen import main as qwen_main
    qwen_main.dump_debug_messages = lambda *a, **kw: None


def build(*, model: str, base_url: str, api_key: str, **kw):
    from mm_agents.qwen import QwenAgent

    _silence_debug_dump()
    return QwenAgent(model=model, base_url=base_url, api_key=api_key, **kw)


register(LensSpec(
    name="qwen-cua",
    build=build,
    default_model="qwen3.8-max",
    channel="openai",
    obs_keys=("screenshot",),
    coordinate_space="relative",
    defaults={
        # temperature=0 是复现性要求：同输入必须同输出，否则任何差异都分不清
        # 是真实变化还是采样噪声。
        "temperature": 0.0,
        "top_p": 0.9,
        "max_tokens": 16384,
        "coordinate_type": "relative",
        "observation_type": "screenshot",
        "action_space": "pyautogui",
        # 老截图折叠而不是整个丢弃：保留 20 张，更早的压成一行占位文字。
        "image_max": 20,
        "fold_size": 10,
        "history_n": 100,
    },
    notes="Qwen-CUA 官方 scaffold；coordinate_type 可切 relative/absolute",
))
