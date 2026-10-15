"""
agent 注册表与装载：把 osworld/mm_agents 下的各式 agent 接到 PixelSandboxEnv 上。

环境（PixelSandboxEnv）与 episode 循环（src/runner/episode.py）不认识任何具体模型，
只认这里定义的统一接口。换模型 = 换一个 adapter（src/agents/adapters/），其余不动。

统一接口不是这里发明的，是 osworld/mm_agents 下 36 个 agent 的既有约定：

    predict(instruction: str, obs: dict) -> (response_text, actions: list)
    reset(_logger=None, ...)

动作两种格式，PixelSandboxEnv.step() 都接受：
    str  -> pyautogui 代码，走 execute_python_command
    dict -> computer_13，走 execute_action

观测只强制 screenshot。多模态模型只要动作空间是坐标，单截图就能 rollout；a11y 树
是补充。mm_agents 里那些 obs["accessibility_tree"] 的引用全部挂在 observation_type
分支之后，设成 "screenshot" 就不会去读。唯一的真依赖是 observation_type="som"
——它的动作空间定义在标注节点上，画框要 a11y，沙箱里用不了。
"""

import sys
import logging

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

from src.settings import ICHAT_CHANNELS, PROJECT_ROOT, ichat_key

# mm_agents 在 osworld/ 下，不是本包的一部分。在注册表这里统一加 path，所有 adapter 都能直接 import；放在某个 adapter 里会让其他 adapter 依赖导入顺序。
_OSWORLD = str(PROJECT_ROOT / "osworld")
if _OSWORLD not in sys.path:
    sys.path.insert(0, _OSWORLD)

SPECIAL = ("WAIT", "DONE", "FAIL")


class AdapterError(Exception):
    pass


@dataclass(frozen=True)
class AdapterSpec:
    """一个 adapter 的装载说明。"""
    name: str
    build: Callable[..., Any]          # (model, base_url, api_key, **kw) -> agent 实例
    default_model: str
    channel: str = "openai"            # ICHAT_CHANNELS 的键
    obs_keys: tuple[str, ...] = ("screenshot",)
    coordinate_space: str = "unknown"  # "relative" | "absolute" | "unknown"
    defaults: dict = field(default_factory=dict)
    notes: str = ""


_REGISTRY: dict[str, AdapterSpec] = {}
_LOADED = False


def register(spec: AdapterSpec) -> AdapterSpec:
    _REGISTRY[spec.name] = spec
    return spec


def _ensure_adapters() -> None:
    """惰性导入 adapters 包触发注册。惰性是为了避开循环导入：adapters 要 import 本模块。"""
    global _LOADED
    if not _LOADED:
        _LOADED = True
        import src.agents.adapters  # noqa: F401


def available() -> list[str]:
    _ensure_adapters()
    return sorted(_REGISTRY)


def spec_of(name: str) -> AdapterSpec:
    _ensure_adapters()
    try:
        return _REGISTRY[name]
    except KeyError:
        raise AdapterError(
            f"未知 agent {name!r}。已注册: {', '.join(available()) or '(空)'}") from None


class Adapter:
    """
    装载好的 agent。把各 agent 的返回差异抹平，对 runner 只暴露一种形状。

    predict() 统一返回 (reply_text, actions, meta)：
      - 二元组 (text, actions)                —— 多数 agent
      - 三元组 (text, actions, extra)         —— opencua 多一个 CoT dict
      - list  [text, actions]                 —— m3 返回的是 list 不是 tuple
    """

    def __init__(self, spec: AdapterSpec, agent: Any, model: str):
        self.spec = spec
        self.agent = agent
        self.model = model
        self.name = spec.name

    @property
    def obs_keys(self) -> tuple[str, ...]:
        return self.spec.obs_keys

    def reset(self, logger: Optional[logging.Logger] = None) -> None:
        # mm_agents 普遍把 logger 存成模块级全局，初值 None；个别 agent
        # （qwen3vl_agent.py:336）调用时不做 if 保护，不先 reset 就 predict 会
        # AttributeError。所以这里总是传一个真 logger。
        self.agent.reset(logger or logging.getLogger(f"agent.{self.name}"))

    def predict(self, instruction: str, obs: dict) -> tuple[str, list, dict]:
        out = self.agent.predict(instruction, obs)
        if not isinstance(out, (tuple, list)):
            raise AdapterError(f"{self.name}.predict 返回了 {type(out).__name__}，"
                               f"期望 (text, actions)")
        if len(out) < 2:
            raise AdapterError(f"{self.name}.predict 返回元素数 {len(out)} < 2")
        text, actions = out[0], out[1]
        extra = out[2] if len(out) > 2 and isinstance(out[2], dict) else {}
        if actions is None:
            actions = []
        if not isinstance(actions, (list, tuple)):
            actions = [actions]
        return str(text or ""), list(actions), extra


def load(name: str, *, model: Optional[str] = None,
         env_obs_keys: Optional[Sequence[str]] = None,
         logger: Optional[logging.Logger] = None,
         **overrides) -> Adapter:
    """
    装载一个 agent，并在**装载时**就把能力不匹配暴露出来。

    env_obs_keys 传环境能提供的观测键（PixelSandboxEnv.OBS_KEYS）。agent 要的键
    环境给不了就当场报错——不要等 rollout 跑到第 5 步才炸。
    """
    spec = spec_of(name)

    if env_obs_keys is not None:
        missing = [k for k in spec.obs_keys if k not in set(env_obs_keys)]
        if missing:
            raise AdapterError(
                f"agent {name!r} 需要观测 {missing}，当前环境只提供 "
                f"{sorted(env_obs_keys)}。")

    base_url = ICHAT_CHANNELS.get(spec.channel)
    if not base_url:
        raise AdapterError(f"agent {name!r} 要求通道 {spec.channel!r}，"
                           f"但 ICHAT_CHANNELS 里没有它。")
    api_key = ichat_key()
    if not api_key:
        raise AdapterError("ICHAT_API_KEY 未设置。它定义在 ~/.bashrc，非交互 shell "
                           "不会自动加载，需要先 source（或用 bash -lc 跑）。")

    kwargs = dict(spec.defaults)
    kwargs.update(overrides)
    agent = spec.build(model=model or spec.default_model,
                       base_url=base_url, api_key=api_key, **kwargs)

    adapter = Adapter(spec, agent, model or spec.default_model)
    adapter.reset(logger)
    return adapter


def describe() -> str:
    rows = ["已注册 agent："]
    for n in available():
        s = _REGISTRY[n]
        rows.append(f"  {n:12s} model={s.default_model:26s} "
                    f"channel={s.channel:12s} coord={s.coordinate_space}")
        if s.notes:
            rows.append(f"  {'':12s} {s.notes}")
    return "\n".join(rows)
