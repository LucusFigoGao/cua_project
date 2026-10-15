"""导入即注册。新增 adapter 在这里加一行 import。"""
from src.agents.adapters import claude_cu  # noqa: F401
from src.agents.adapters import gemini_cu  # noqa: F401
from src.agents.adapters import qwen_cua   # noqa: F401
from src.agents.adapters import qwen3vl    # noqa: F401
from src.agents.adapters import raw_vlm    # noqa: F401
