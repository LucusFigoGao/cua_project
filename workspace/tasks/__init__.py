"""
任务侧模块：从 tasks_data/（已解包、已替换占位符的任务库）选任务并推送到沙箱实例。

分工：
  urlmap.py  —— 占位符替换表，从 configs/apps.json 推导。被 unpack_tasks.py 复用。
  catalog.py —— 读 tasks_data/，筛选 + 分层取样。纯文件系统，不读 tasks.parquet。
  push.py    —— 选中任务打 tar 上传实例，并装 google-chrome shim。

数据源是 workspace/tasks_data/，由顶层 unpack_tasks.py 从
gym/bench/artifacts/cua_gym_tasks_v1.tar.zst 一次性解包生成。
"""
