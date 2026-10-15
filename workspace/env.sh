# 用法: cd workspace && source env.sh
#
# 把 cua_project/ 和 osworld/ 放进 PYTHONPATH，这样所有模块都能用绝对导入
# （from src.xxx import / from mm_agents.xxx import），不需要在代码里改 sys.path。
# osworld/ 本身也要在路径上，因为 mm_agents/agent.py 内部是 `from mm_agents...` 导入的。
#
# 同时加载 ~/.bashrc 里的 ICHAT_API_KEY / ICHAT_BASE_URL（跑 agent 必需）。

_WS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_ROOT="$(dirname "$_WS")"

export PYTHONPATH="$_ROOT:$_ROOT/osworld${PYTHONPATH:+:$PYTHONPATH}"
[ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"

echo "PYTHONPATH=$PYTHONPATH"
echo "ICHAT_BASE_URL=${ICHAT_BASE_URL:-<未设置>}"
echo "ICHAT_API_KEY=${ICHAT_API_KEY:+<已设置>}${ICHAT_API_KEY:-<未设置>}"
