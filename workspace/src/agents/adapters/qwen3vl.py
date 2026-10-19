"""
Qwen3-VL adapter：osworld/mm_agents/qwen3vl_agent.py 的 Qwen3VLAgent。

与 qwen-cua 是同一家的两代 scaffold，不能共用一个 adapter：
    tool_call 格式    这里是 JSON（{"name":..,"arguments":..}），qwen/ 是 XML（<function=..>）
    构造参数          不接 base_url / api_key / image_max / fold_size
    历史              history_n=4 硬截断，没有截图折叠
    解析不出动作      返回 []（继续下一步），qwen/ 是 fallback 成 DONE

提示词、历史组装、动作解析、坐标反变换全部沿用上游；adapter 只替换 HTTP 层，修四处
会污染测量的缺陷（行号指 qwen3vl_agent.py）：

    :636  base_url / api_key 只从环境变量读          → 构造时直接传给 client，不碰进程环境
    :650  openai 分支丢掉 reasoning_content           → 包进 <think> 与 content 合并，
                                                        与它自己 dashscope 分支 :605 的做法一致
    :647  temperature / top_p 被注释掉，实际不生效   → 补上，否则 temperature=0 只是名义上的
    :657  重试耗尽静默返回 ""                        → 抛 AdapterError，runner 记为 agent_error
    :609  外层 backoff（5 次 × 30s）套内层 5 次重试   → 整个 call_llm 覆盖掉，400 不重试

另外 content 为空时（思维链把 max_tokens 吃光）翻倍预算重试，同 raw-vlm。

没修的：predict 内联往 ./draft/message_cache/ 写完整 base64 的消息 JSON（:314），
打不了补丁。文件名只带步号，跨 episode 互相覆盖，不会无限增长，先接受。
predict 每步还会 print 两行分辨率，同理。
"""
import time

from src.agents.registry import AdapterError, AdapterSpec, register

_AGENT_CLS = None


def _agent_cls():
    """
    惰性定义子类。qwen3vl_agent 模块级就 import dashscope / google.api_core，
    放到模块顶层会让 --list-agents 之类与它无关的调用也背上这些依赖。
    """
    global _AGENT_CLS
    if _AGENT_CLS is not None:
        return _AGENT_CLS

    import openai
    from mm_agents.qwen.client import extract_message_field, merge_reasoning_content
    from mm_agents.qwen3vl_agent import Qwen3VLAgent

    # 只有这几类值得重试；400 之类重试多少次结果都一样。
    retryable = (openai.APIConnectionError, openai.APITimeoutError,
                 openai.RateLimitError, openai.InternalServerError)

    _SINGLE_ACTION_SUFFIX = (
        "\n- IMPORTANT: Output exactly ONE <tool_call> block per response. "
        "Never output multiple <tool_call> blocks in a single turn."
    )

    class _PatchedQwen3VLAgent(Qwen3VLAgent):
        def __init__(self, *, base_url: str, api_key: str, timeout: float = 180,
                     retries: int = 3, max_token_ceiling: int = 32768, **kw):
            super().__init__(**kw)
            self._client = openai.OpenAI(base_url=base_url, api_key=api_key,
                                         timeout=timeout)
            self._retries = retries
            self._max_token_ceiling = max_token_ceiling

        def call_llm(self, payload, model):
            msgs = payload["messages"]
            if msgs and msgs[0].get("role") == "system":
                content = msgs[0].get("content", "")
                if isinstance(content, str) and _SINGLE_ACTION_SUFFIX.strip() not in content:
                    msgs[0]["content"] = content + _SINGLE_ACTION_SUFFIX
            return self._call_llm_openai(msgs, model)

        def _call_llm_openai(self, messages, model):
            last = None
            budget = self.max_tokens
            for attempt in range(1, self._retries + 1):
                try:
                    resp = self._client.chat.completions.create(
                        model=model, messages=messages, max_tokens=budget,
                        temperature=self.temperature, top_p=self.top_p)
                except retryable as e:
                    last = f"{type(e).__name__}: {str(e)[:200]}"
                except openai.APIError as e:
                    raise AdapterError(f"调用模型失败: {type(e).__name__}: {str(e)[:200]}") from e
                else:
                    msg = resp.choices[0].message
                    content = extract_message_field(msg, "content")
                    if (content or "").strip():
                        return merge_reasoning_content(
                            content, extract_message_field(msg, "reasoning_content"))
                    # 思维链把预算花光，content 为空。同样的 max_tokens 重试还是空，翻倍。
                    last = f"模型返回空 content（max_tokens={budget}）"
                    budget = min(budget * 2, self._max_token_ceiling)
                if attempt < self._retries:
                    time.sleep(2 * attempt)
            raise AdapterError(f"调用模型失败（重试 {self._retries} 次）: {last}")

    _AGENT_CLS = _PatchedQwen3VLAgent
    return _AGENT_CLS


def build(*, model: str, base_url: str, api_key: str, **kw):
    return _agent_cls()(model=model, base_url=base_url, api_key=api_key, **kw)


register(AdapterSpec(
    name="qwen3vl",
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
        "history_n": 4,
        "api_backend": "openai",
    },
    notes="Qwen3-VL baseline；JSON tool_call，与 qwen-cua 的 XML 格式不通用",
))
