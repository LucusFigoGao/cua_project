# TODO

## 1. agent 接入层（已落地）

`bridge.py` 已拆成「注册表 + adapter + episode 循环」三层，`run_episode` 搬到 `src/runner/episode.py`。

```
src/agents/registry.py       注册表：AdapterSpec + 装载校验 + 工厂；osworld path 也在这里统一加
src/agents/adapters/         qwen_cua / qwen3vl / claude_cu / gemini_cu / raw_vlm
src/runner/episode.py        episode 循环：交互时序、分步日志、动作计数、提前结束原因
```

用法：`--agent qwen-cua`，`--list-agents` 列全部，`--model` 覆盖默认模型。

### 已验证

| agent | 通道 | 结果 |
|---|---|---|
| `qwen-cua` | openai | 跑通，`<think>` 合并与 0-999 反变换均生效 |
| `claude-cu` | anthropic | 跑通，3-4s/步 |
| `raw-vlm` + `gemini-3.5-flash` | openai | 跑通 |
| `gemini-cu` | google_genai | 通道通，但上游 scaffold 崩（见下） |

**所有模型都能走 OpenAI 协议**，原生 SDK 通道不是必需的。`raw-vlm` 不挑模型，`--model` 换任何模型即可。

### gemini-cu 的已知问题

`gemini_agent.py:639` 遇到 `text='' function_call=None` 的 part 直接
`raise ValueError("Cannot handle part")`，而 gemini-3.5-flash 会吐这种空 part，
于是第二步必定 parsing_error → FAIL。这是上游 scaffold 的健壮性问题，不是通道问题。

另外 `gemini-2.5-computer-use-preview-*` 配 `action_space="pyautogui"` 会被上游
Vertex 回 400 —— computer-use 模型只接受原生 computer_use tool，不接受自定义
FunctionDeclaration。要用它得把翻译表改成 Google 预定义函数名。

想跑 gemini 现在直接用 `--agent raw-vlm --model gemini-3.5-flash`。

### 顺带修掉的

- `GeminiFCAgent` 的 `API_RETRY_TIMES=500` 在 adapter 里压到 4。对 400 这类永不恢复的
  错误，500 次重试表现为"卡住"而不是报错，批跑时致命。
- `--max-tokens` 改成显式覆盖。各 agent 接受的参数不同（`GeminiFCAgent` 没有
  `max_tokens`），无条件塞会 TypeError。
- `reward` 解析兼容 `Score: 3/6 = 0.5` 格式（原先漏 14 个任务）。
- `result.json` 增加 `reward_delta` / `stop_reason` / `parse_miss_steps` /
  `actions_executed` / `agent` / `coordinate_space`，分步记录 `latency_sec`。

### 还没做

- `parse_miss` 检测只认 `<tool_call>` 和 ``` 两种标记（`src/runner/episode.py`）。
  `qwen/actions.py:317` 在解析不出任何 tool_call 时 fallback 成 `DONE`，解析失败
  长得跟任务完成一样。接新 agent 时这个判据要跟着扩。
  **首轮批跑已触发 3 次 parse_miss**（google_docs / pinterest / salesforce），
  其中 google_docs 的 parse_miss 导致 delta=0，任务实际没做就结束了。

## 2. episode 健壮性（已落地）

已实现：

- **环境异常兜底**：`env.step()` / `env.get_obs()` 异常在 `run_episode` 内捕获，
  `stop_reason="env_error"`，保留已跑步数 + error 信息，`result.json` 正常写入。
- **坏实例不回池**：`env_error` 时 `pool.kill()` 而不是 `release()`。
- **动作执行结果记录**：`pixel_env.step()` 返回 `_exec` 字段（`/execute` 端点原始
  `{status, output, error, returncode}`），记入 trajectory 的 `exec_result`。
- **单动作约束**：5 个 adapter 全部在提示词中约束每步只出一个动作（不改 osworld/ 原始文件），
  runner 层做截断兜底。去掉了 `episode.py:103` 的冗余 `get_obs()`。
- **final.png**：循环结束后额外截一张 `screenshots/final.png`，对照 reward 用。
- **busy-stuck 回收**：`PoolInstanceConfig` 加 `busy_since` 时间戳，`reconcile()` 自动
  回收超时 30 分钟的 busy 实例。

**首轮批跑验证**：27 个任务 env_error = 0，环境全程稳定。

### 留到后续再定

哪些异常值得原地重试、重试几次、超时阈值多少、整任务重跑上限。
首轮数据显示环境侧稳定，暂不需要重试机制。

## 3. 坐标约定标定（已落地）

统一使用 **relative（0-999）** 坐标空间。各 adapter 状态：

| adapter | coordinate_space | 机制 |
|---|---|---|
| qwen-cua | relative | 提示词 1000x1000 + `adjust_coordinates()` 反变换 |
| qwen3vl | relative | 同上 |
| gemini-cu | relative | schema 0-999 + adapter `_xy()` 反变换 |
| raw-vlm | relative | 提示词 1000x1000 + adapter `_scale_relative_coords()` 反变换 |
| claude-cu | absolute | Anthropic 原生 `computer_20241022` 工具自带缩放，不走 0-999 体系 |

## 4. M4 批量调度（已落地）

```
src/runner/task.py           run_one()：单任务完整生命周期，自动 acquire/push/episode/reward/release
src/runner/batch_runner.py   BatchRunner：多线程批跑引擎
src/cli/batch_run.py         CLI 入口
src/tasks/push.py            push_single_task()：轻量单任务推送（~30KB，~100ms）
```

用法：
```bash
cd workspace && python -m src.cli.batch_run \
    --agent qwen-cua --workers 4 --sample-per-app 3 \
    --exclude-app monday_mock --resume
```

**任务与实例已解绑**：`run_one()` 在 setup 前只推当前任务的 3 个文件，不需要提前 push_tasks。
`cli/push_tasks.py` 降为调试工具。

### 首轮批跑结果（qwen-cua / qwen3.8-max / max_steps=50）

27 个 app 各 1 个任务，排除 monday_mock 等 4 个，总耗时 78 分钟。

| 指标 | 值 |
|---|---|
| env_error | 0 |
| 平均 reward_delta | 0.406 |
| delta > 0（有进展） | 17/27 = 63% |
| delta = 1.0（满分） | 5 个：facebook, github, jira, postman, shopify_admin |
| delta = 0（没做对） | 9 个 |
| stop=done（主动结束） | 11 |
| stop=max_steps（跑满 50 步） | 13 |
| stop=parse_miss | 3（google_docs, pinterest, salesforce） |

**发现的问题**：

- **twitter_mock reward=None**：`reward.py` 输出格式不在已识别的两种模式
  （`REWARD: 0.5` / `Score: .../... = 0.5`）内，需要补第三种解析模式。
- **基线非零已确认 2 个**：pinterest（1.0，NO-OP）、gitlab（0.2）。
  `reward_delta` 作为主指标是对的。
- **13/27 跑满 50 步**：模型没有在合理步数内完成。要看是任务难还是模型在循环。

## 5. 系统性迁移（待启动）

**需求**：把单个任务的完整链路做成"每任务独占沙箱、用完即销毁"：申请沙箱、上传网页和任务、npm install、build 并起服务、跑 agent、跑 reward、release 并 kill。要求支持 20 台并发，空置率低于 X（X 待定），不依赖目前内网那台托管 31 个 app 的开发机。

**任务分布**：共 1062 个任务，28 个 app。931 个只用 1 个 app，131 个（12%）跨多个 app（106个用2个，21个用3个，4个用4到5个）。常见组合：google_sheets+slack、google_sheets+gmail、google_drive+gmail、gitlab+slack。

### 之前已完成的探测结论（4C/8G 的 sdt-hojglb51 上实测）

**单沙箱完整冷启动，均值 21.8s（16.8到25.6s）**

| 阶段 | 耗时 |
|---|---|
| Sandbox.create | 0.4s |
| OSWorld 依赖（apt 7.8s，pip 3.4s，probe 0.6s） | 约 11.8s（首次真装） |
| OSWorld server 起来 | 2.2到2.5s |
| chrome shim、hosts、上传单 app 包（0.2MB） | 不到 1s |
| npm install（冷） | 4.1s（2.5到6.2s） |
| vite preview 起到端口 200 | 1.1到1.3s |

- 12并发完整冷启动：12/12 就绪，wall 27.4s，apt/pip/npm 源均未被压垮。
- 单 app 部署资源：磁盘 65到188MB（共 8.0G），内存约 1.0GB（共 7.8G），2C4G 放得下。
- 任务实测时长：mean 815s，median 849s，p25 370s。
- 依赖安装发生在跑任务时而非建实例时：`task.py:81` 的 `osw.ensure_server(sbx)` 默认 install=True；`ensure_server` 有探活早退，所以现有复用池里每个实例只有第一个任务付这笔钱。改成 kill-per-task 后每个任务都要付。

**策略对比**

| 策略 | 每任务额外开销 | 实例利用率 |
|---|---|---|
| 每任务 kill 重建 | 21.8s | 97.3%（空置率约 2.7%） |
| 复用且换 app | 5.0s | 99.4% |
| 复用且同 app | 0.12s | 约 100% |

**已确认的代码现状**

- `pool.acquire(ensure_apps=False)`（pool.py:138,162）已能绕过"31 个 app 全部可达"的检查。
- `pool.kill()`（pool.py:289-295）已含 Sandbox.kill、注册表 pop、_save、notify_all。
- `pool._create_new_locked()`（pool.py:244-260）只有 Sandbox.create 加写注册表。
- `apps_host.build_apps(apps=[one])` 已按 app 参数化。
- `push.push_single_task()` 推 3 个文件约 30KB，已有。
- `run_episode()`、`PixelSandboxEnv`、`_reward()`、`reward_delta` 已有。
- `task.py:39` 的 `pool.acquire()` 没传 `spec.app_type`；`batch_runner.py` 是纯 FIFO 的 `queue.Queue` 加 N 个 daemon worker，已能跑 20并发。
- 依赖定义在 `src/sandbox/osworld_server.py:29-31`（`gnome-screenshot xdotool` 加 `flask pyautogui python-xlib pillow lxml numpy requests`）。
- 你在 `/tmp/bench_deploy/` 里已实测跑通部署命令，包括 `setsid nohup` 三流重定向、`--strictPort`、`vite.config.allowhosts.mjs` 包装、`pkill -f '[v]ite'`。

**关键判断**：npm install 只占冷启动 19%，Python 通用 mock server 省不了多少且有保真度风险，本轮不做。kill-per-task 下每个 worker 独占实例，不存在实例空等派发，空置率由冷启动占比结构性决定（约 2.6%），affinity 调度本轮可以不做。

# TODO List

> 以下各项均面向「系统性迁移」目标：每任务独占沙箱、app 在沙箱内部署、用完即 kill。
> 执行顺序：T7 → T1 → T2 → T3 → T4 → T5/T6 → T8。
>
> ✅ T7（2026-10-22）：`settings.py` 新增 `APP_BUNDLES` 路径常量和 `port_to_app()` 反向映射函数。
> ✅ T1（2026-10-22）：`TaskSpec` 新增 `apps: list[str]` 字段，`catalog.py` 扫 `initial_setup.py` 端口自动填充；131 个 multi-app 任务识别正确。
> ✅ T2（2026-10-22）：`src/cli/pack_app_bundles.py` 新增；31 个 app bundle + `_shared.tar.gz` 打包完成，存于 `app_bundles/`，合计 5MB。
> ✅ T3（2026-10-22）：`src/sandbox/app_deploy.py` 新增；`set_loopback_host` / `ensure_shared` / `deploy_app` / `deploy_task_apps` 四个函数，实现沙箱内 app 完整部署链路。
> ✅ T4（2026-10-22）：`task.py` 新增 `kill_after` / `bundle_dir` 参数；`pool.acquire(ensure_apps=False)`；插入 `deploy_task_apps(sbx, spec)`；finally 块改为 kill_after 时无条件 kill。
> ✅ T5（2026-10-22）：`batch_run.py` 移除开发机检查，新增 `--no-kill-per-task` / `--app-bundles` flag；`BatchRunner` 透传 `kill_after` / `bundle_dir`。
> ✅ T6（2026-10-22）：`pool.py` `acquire()` 默认改为 `ensure_apps=False`，旧路径保留可显式传 `True` 回退。

---

### T1 扩展 TaskSpec：记录任务所需的全部 app 端口

**问题**：`TaskSpec.app_type` 只有主 app，131 个 multi-app 任务还依赖其他端口的 app，但目前没有字段存储。

**做法**：
- `src/tasks/catalog.py`：解析 `initial_setup.py` 文本，提取所有 `host.docker.internal:80XX` 端口，经 `PORT_TO_APP` 反向映射成 app 名列表，写入新字段 `TaskSpec.apps: list[str]`（默认 `[app_type]`）
- `src/settings.py`：由 `apps.json` 生成 `PORT_TO_APP: dict[int, str]` 常量

**验证**：`load_tasks()` 后统计 `len(spec.apps) > 1` 的条数应等于 131。

---

### T2 预打包 app dist bundle

**问题**：沙箱内部署 app 需要上传 build 产物，目前没有独立于开发机的可传输格式。

**做法**：
- `src/cli/pack_app_bundles.py`：遍历 `configs/apps.json` 的 31 个 app，从 `CUA_HUB_DIR/websites/<app>/` 打出 `app_bundles/<app>.tar.gz`（内含 `dist/`、`package.json`、`vite.config*`），已有 dist 则跳过（`--force` 重打）
- `workspace/.gitignore` / `workspace/configs/` 的忽略规则加上 `app_bundles/`
- 单个 app 约 65~188 MB，31 个合计约 4 GB，需确认磁盘空间

**验证**：`tar tzf app_bundles/gitlab_mock.tar.gz | grep dist/` 能列出文件。

---

### T3 新模块 `src/sandbox/app_deploy.py`

**问题**：目前没有在沙箱内部起 app 的代码；`deploy.py` 写的是外部 IP，迁移后要写 loopback。

**做法**（基于 `/tmp/bench_deploy/` 已验证的命令）：

```python
set_loopback_host(sbx)
    写 /etc/hosts: "127.0.0.1  host.docker.internal"（root）

deploy_app(sbx, app_name, bundle_dir, port)
    上传 app_bundles/<app_name>.tar.gz → 沙箱 /tmp/
    解压到 /opt/apps/<app_name>/
    写 vite.config.allowhosts.mjs（允许 host.docker.internal 访问）
    setsid nohup vite preview --port <port> --strictPort >/dev/null 2>&1 &
    wait_for_port(sbx, port, timeout=30s)：curl 200 为止

deploy_task_apps(sbx, spec)
    set_loopback_host(sbx)
    for app in spec.apps: deploy_app(sbx, app, ...)
```

**关键细节**：
- `pkill -f '[v]ite.*<port>'` 清理残留进程（env_error 后 kill 整个沙箱，但 wait_for_port 超时时需要）
- multi-app 任务各 app 并发上传、串行 vite preview（端口间不干扰，可并发起）
- `vite.config.allowhosts.mjs` 内容已在 `/tmp/bench_deploy/` 测试过

---

### T4 修改 `src/runner/task.py` 走 kill-per-task 路径

**问题**：`_run_on_sandbox()` 依赖 `deploy.ensure_apps_reachable()`（外部开发机），`finally` 块只有 `env_error` 时才 kill。

**做法**：
- `run_one()` 新增参数 `kill_after: bool = True`
- `pool.acquire(ensure_apps=False)`（已支持，改为传参而非默认）
- 替换：`deploy.ensure_apps_reachable(sbx)` → `app_deploy.deploy_task_apps(sbx, spec)`
- `finally` 块：`kill_after=True` 时无论成功/失败均 `pool.kill(cfg.sandbox_id)`；`False` 时保持原复用逻辑（不删旧路径，保留回退能力）

**影响文件**：`src/runner/task.py`（约 10 行改动）

---

### T5 修改 `src/cli/batch_run.py`

**问题**：无 kill-per-task 开关，无 app-bundles 路径参数，默认仍走开发机。

**做法**：
- 新增 `--kill-per-task / --no-kill-per-task`（默认 True）
- 新增 `--app-bundles <dir>`（默认 `workspace/app_bundles/`，传给 `app_deploy`）
- `--workers` 上限说明：T8 实测后写进 help 文字

---

### T6 修改 `src/sandbox/pool.py`

**问题**：`acquire()` 默认 `ensure_apps=True`，kill-per-task 模式下每次 acquire 还是会尝试检查开发机。

**做法**：
- `acquire()` 默认改为 `ensure_apps=False`（调用方显式传 `True` 才走旧路径）
- 现有 `_ensure_apps_ready()` 保留但标记 `# deprecated: reuse-pool only`
- `kill_per_task` 不需要在 pool 层感知，T4 的 `kill_after` 已处理

---

### T7 `src/settings.py` 新增常量

**做法**：
```python
APP_BUNDLES = WORKSPACE / "app_bundles"

def port_to_app() -> dict[int, str]:
    """端口 → app_name 反向映射，由 apps.json 推导。"""
    return {v: k for k, v in app_ports().items()}
```

这是 T1 和 T3 的共同依赖，应最先合入。

---

### T8 端到端烟雾测试

依次验证：

1. **单 app 任务**：选一个简单任务（如 `github_mock`），`--kill-per-task --workers 1`，确认 app 在沙箱内可达、episode 跑通、reward 写入、沙箱 kill 成功
2. **Multi-app 任务**：选 `ad7989c7`（需要 `google_sheets_mock` + `slack_mock` + 另一 app），确认多 app 均在沙箱内可达
3. **20 并发压测**：`--workers 20 --sample-per-app 1`，观察冷启动时间分布、空置率、OOM 是否触发

**成功指标**：env_error = 0，reward_delta 分布与首轮批跑（开发机模式）接近，p95 冷启动 < 35s。
