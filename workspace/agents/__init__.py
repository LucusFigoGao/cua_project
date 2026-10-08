"""
Agent 侧：把 osworld/mm_agents 的 agent 接到 PixelSandboxEnv。

bridge.py 复用 mm_agents 的系统提示词和动作解析，只替换掉与 ichat 不兼容的
HTTP 调用层（ichat 的路径是 /chat/completions 不带 /v1，且 qwen* 在 mm_agents
里会走 dashscope SDK）。详见 bridge.py 顶部说明。
"""
