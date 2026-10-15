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
- **实例会卡在 busy**：进程被 `timeout`/Ctrl-C 杀掉时 `finally` 里的 `release`
  跑不到，该实例永久 busy，下次 `acquire` 会新建一个。`reconcile()` 应该回收
  超时未心跳的 busy 实例。批跑前必须修，否则会把配额耗光。
  目前的人工兜底：`python -m src.cli.manage_pool --release-all`（无跨进程锁，确认没有任务在跑再用）。

## 2. episode 健壮性（M4 前置）

### 2.1 执行与观测解耦

harness 没有「每步只发一个动作」的硬约束，各 agent 一步都可能产出多条动作：

| agent | 提示词约束 | 一步产出多条的来源 |
|---|---|---|
| `raw-vlm` | 明确允许多行（`prompts.py:7` "one line or multiple lines"） | 多个代码块 / `;` 拆分 |
| `qwen-cua` / `qwen3vl` | 软约束 "A single <tool_call>"，但解析器照单全收多个 | 带修饰键的点击 → keyDown/click/keyUp；多行 type → typewrite + enter |
| `claude-cu` | 原生允许一条回复多个 tool_use | 多个 tool_use block |
| `gemini-cu` | 无 | 多个 function call；type+press_enter、drag 各拆两条 |

**不在 harness 层强制单动作**：那会改变模型相对官方 baseline 的行为，测到的就不是同一个东西。
要修的是观测侧：`env.step()` 每条动作后都截一张图，而 `episode.py:103` 又重新截一次，
k 条动作截 k+1 张，只用最后一张。改为 runner 循环里只执行不观测，每步结束统一 `get_obs()` 一次。

顺带：最后一步动作后的画面不落盘（`stepNN.png` 都是动作前的），补一张 `final.png`，对照 reward 用。

### 2.2 环境侧异常

现状：agent 异常有兜底（保留已跑的步、记 `agent_error`），环境异常没有——`env.step()` 抛错直接
冲出 `run_episode`，轨迹丢失、`result.json` 不写，`finally` 里还把这个可能已坏的实例 `release`
回 idle，下一个任务接着用。

**先布局骨架，策略留给数据**。现在就要定的是那些不定下来、批跑结果就不可信的东西：

1. **归因**：`stop_reason` 增加 `env_error`；环境挂掉的任务不计入模型成功率，要么重跑要么单列。
   否则沙箱抖一次就记成模型做错一题。
2. **轨迹不丢**：`env.step()` 的异常与 agent 异常一样在 `run_episode` 内捕获，保留前 N 步再返回。
3. **坏实例不回池**：环境异常时实例 `kill` 而不是 `release`（或至少标记、下次 acquire 前做体检）。
4. **动作执行结果不再丢弃**：OSWorld server `/execute` 返回 `status/output/error/returncode`
   （`desktop_env/server/main.py:107`），`step()` 现在全部扔掉。模型生成的代码语法错、
   `pyautogui` 报错都静默变成「执行了 1 个动作」。记进 trajectory 的每条动作里。
   这条要先区分：returncode≠0 多半是**模型**的错（代码写坏了），不是环境错，不该触发 2/3。

可预见的环境故障面（来自代码，未实测频率）：envd 连接断/沙箱被回收（e2b 异常）、
`curl` 到 server 超时（`_post_json` 返回空 → 静默 `{}`）、server 崩溃（`/screenshot` 非 200 →
`PixelEnvError`）、24h 到期、开发机 app 不可达（setup 写不出 sid）。

**留到 rollout 再定**：哪些异常值得原地重试、重试几次、超时阈值多少、整任务重跑上限。
这些依赖真实故障频率，先拍脑袋只会定错。第一轮批跑按上面 1-4 把异常分类落盘，看分布再定。

## 3. 坐标约定标定

`coordinate_type` 取 relative（0-999）还是 absolute，需实测确认，不能照搬默认值。
**由本人确认**。

注意 OSWorld 的 `SYS_PROMPT_IN_SCREENSHOT_OUT_CODE` 全文不声明屏幕分辨率或坐标空间，
而 qwen scaffold 的 `build_description_prompt()` 会明写（relative 时给
`The screen's resolution is 1000x1000`）—— 换 agent 时这项会跟着变。

## 4. M4 批量调度

`src/runner/batch_runner.py`：N 个 worker 线程消费任务队列。
每个 worker 拿实例是秒级的，批跑启动开销基本消失。并发上限 12 个实例（配额所限）。

依赖第 1、2 项先落地，否则每接一个模型都要重做一遍日志与计量。

同时要做的两件结构调整：

- **任务与实例解绑**：现在任务要先 `push_tasks` 到某个实例，`run_task` 要求任务已在拿到的
  实例上（`run_task.py:98`）。多实例时 acquire 拿到的不一定是推过的那台；实例被替换后是空的；
  本地重解包后实例上的副本静默过期。改为 `run_task` 在 setup 前只推当前任务的 3 个文件
  （几十 KB，~100ms）。`google-chrome` shim 与 `requests` 是实例级准备，挪进 `pool.acquire`
  的就绪检查。`cli/push_tasks.py` 之后降为调试工具。
- **单任务生命周期抽出**：`run_task.main()` 里 setup → 基线 → episode → 终值 → 落盘这段
  抽成 `src/runner/task.py::run_one(sbx, spec, agent)`，cli 与 batch_runner 共用。

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
两个字段 `result.json` 都已存，目前没人用这个差值。

建议在批跑前做一次基线扫描：只跑 `initial_setup.py` + `reward.py`，不调模型，
记下每个任务的基线分。不花 token，结果直接决定测试集怎么选。

## 8. 扩展到几百上千个网页

开发机磁盘（build 产物）会先于内存成为瓶颈（31 个 app 的 vite preview 合计才 1.68GB，
磁盘 70GB）。届时考虑按需拉起或反向代理分发。
