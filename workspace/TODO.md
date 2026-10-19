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

## 5. 补 `src/smoke_test/test_apps_host.py`

开发机 app 的验证目前没有脚本覆盖，需要测三件事：
31 个 app 在开发机上起得来、沙箱经 `host.docker.internal` 能访问到、
不同 sid 之间状态互不污染。

## 6. monday_mock（8017）整个 app 白屏

`App.jsx` 只挂了 `AppProvider`，但 `Sidebar` / `Board` / `AutomationsPanel` 等 7 个活跃
组件用的是另一套 `useStore()`（来自 `StoreContext`），而 `StoreProvider` 从未挂载；
`createContext()` 又没给默认值，hook 返回 undefined，解构 `state` 直接抛错。

43 个任务因此全部不可做。修复要改 `/data/workspace/cua_hub`（另一个仓库，有未提交改动），
在那之前测试集应排除该 app。

同目录下 `discord_mock`(8001) 的 `useStore` 是 zustand（不需要 provider，仅同名）、
`microsoft_teams_mock`(8016) 那两个文件没人 import（死代码），两者实测渲染正常。

## 7. 基线 reward 扫描

`e872dfd6`（pinterest）实测基线 REWARD 就是 1.0 —— 这是故意设计的 NO-OP 任务，
`reward.py` 明写 "the correct agent behavior is to recognize the follow already exists
and do nothing"。显式标注 NO-OP 的只有 1 个，但「基线非零」范围更大：
部分 `reward.py` 含反向检查项（「不该动的东西没被动过」），什么都不做反而先得分。

所以该记的指标是 **`final_reward - baseline_reward`**，不是 `final_reward`。
两个字段 `result.json` 都已存，批跑汇总用 `reward_delta`。

**首轮批跑已确认基线非零 2 个**：pinterest(1.0)、gitlab(0.2)。
全量基线扫描（只跑 initial_setup + reward，不调模型）仍建议做一次，
用于确认测试集里有多少 NO-OP 任务和反向检查项。

## 8. 扩展到几百上千个网页

开发机磁盘（build 产物）会先于内存成为瓶颈（31 个 app 的 vite preview 合计才 1.68GB，
磁盘 70GB）。届时考虑按需拉起或反向代理分发。

## 9. mock app 迁到独立 CVM

31 个 mock app 部署到一台固定的 CVM，当前开发机只负责编排（pool / agent / run_task）。

```
┌─ App CVM（固定）──────┐     ┌─ 编排机（当前开发机）─┐       ┌─ AGS 沙箱 ×N ─────────────┐
│ 31 个 vite preview     │     │ pool / agent / run_task│─envd─→│ OSWorld server + chromium │
│ :8000-8030             │←────┼──────── HTTP ──────────┼───────│ hosts: <CVM IP> h.d.i     │
└────────────────────────┘ 探活└────────────────────────┘       └───────────────────────────┘
```

### 9.1 网络连通性验证（先于代码改动）

- 沙箱 → CVM：先测同地域私网 IP；不通再用 CVM 公网 IP。
- 编排机 → CVM：8000-8030 可达，用于探活。
- 走公网时，安全组只对沙箱出口 IP 放行 8000-8030（沙箱内 `curl ifconfig.me` 取出口 IP，
  并确认是否固定）。

### 9.2 代码

- app 主机地址改为显式配置（`CUA_APP_HOST` 或 `settings`），未配置直接报错；
  去掉 `apps_host.detect_host_ip()` 取本机 IP 的默认行为。
- `run_task.py` / `manage_pool.py` 的 app 探活从 `127.0.0.1` 改为探测 CVM 地址。
- `apps_host.py` 按运行位置拆分：clone / build / tmux 启停留给 CVM 上的 `serve_apps.py`；
  编排机侧只保留远程探活函数。拆分后挪出 `src/sandbox/`（如 `src/host/`）。
- `deploy.load_app_ports()` 与 `apps_host.load_app_ports()` 合并为一份。
- `deploy.py` 写 hosts、vite `allowedHosts` 补丁保持不变，IP 换成 CVM 的。

### 9.3 CVM 部署

- 装 node 22 / npm / tmux / git，放一份本仓库（`serve_apps` 依赖 `configs/apps.json` 与 `apps_host`）。
- 磁盘按 build 产物数 GB 并为扩展网页留余量。
- 开机自动拉起 31 个 app（systemd 或 crontab `@reboot`）。

### 9.4 文档

- README 第 1 节架构图改为三角色，「单点」由开发机改为 App CVM。
- README 第 5 节出向连通性实测数据在新环境重测后更新。
- 第 5 项 `test_apps_host.py` 的验证对象由开发机改为 CVM。
