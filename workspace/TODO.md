# TODO

## 1. 镜头卡口（已落地）

`bridge.py` 已拆成卡口 + 镜头 + 机身三层，`run_episode` 搬到 `src/runner/episode.py`。

```
src/agents/mount.py          卡口：LensSpec + 装载校验 + 工厂；osworld path 也在这里统一加
src/agents/lenses/           qwen_cua / claude_cu / gemini_cu / raw_vlm
src/runner/episode.py        机身：快门时序、分步日志、动作计数、提前结束原因
```

用法：`--lens qwen-cua`，`--lenses` 列全部，`--model` 覆盖默认模型。

### 已验证

| 镜头 | 通道 | 结果 |
|---|---|---|
| `qwen-cua` | openai | 跑通，`<think>` 合并与 0-999 反变换均生效 |
| `claude-cu` | anthropic | 跑通，3-4s/步 |
| `raw-vlm` + `gemini-3.5-flash` | openai | 跑通 |
| `gemini-cu` | google_genai | 通道通，但上游 scaffold 崩（见下） |

**所有模型都能走 OpenAI 协议**（`http://ichat.woa.com/api/external`），原生 SDK
通道不是必需的。`raw-vlm` 不挑模型，`--model` 换任何模型即可。

### gemini-cu 的已知问题

`gemini_agent.py:639` 遇到 `text='' function_call=None` 的 part 直接
`raise ValueError("Cannot handle part")`，而 gemini-3.5-flash 会吐这种空 part，
于是第二步必定 parsing_error → FAIL。这是上游 scaffold 的健壮性问题，不是通道问题。

另外 `gemini-2.5-computer-use-preview-*` 配 `action_space="pyautogui"` 会被上游
Vertex 回 400 —— computer-use 模型只接受原生 computer_use tool，不接受自定义
FunctionDeclaration。要用它得把翻译表改成 Google 预定义函数名。

想跑 gemini 现在直接用 `--lens raw-vlm --model gemini-3.5-flash`。

### 顺带修掉的

- `GeminiFCAgent` 的 `API_RETRY_TIMES=500` 在镜头里压到 4。对 400 这类永不恢复的
  错误，500 次重试表现为"卡住"而不是报错，批跑时致命。
- `--max-tokens` 改成显式覆盖。各镜头接受的参数不同（`GeminiFCAgent` 没有
  `max_tokens`），无条件塞会 TypeError。
- `reward` 解析兼容 `Score: 3/6 = 0.5` 格式（原先漏 14 个任务）。
- `result.json` 增加 `reward_delta` / `stop_reason` / `parse_miss_steps` /
  `actions_executed` / `lens` / `coordinate_space`，分步记录 `latency_sec`。

### 还没做

- `parse_miss` 检测只认 `<tool_call>` 和 ``` 两种标记（`src/runner/episode.py`）。
  `qwen/actions.py:317` 在解析不出任何 tool_call 时 fallback 成 `DONE`，解析失败
  长得跟任务完成一样。换新镜头时这个判据要跟着扩。
- **实例会卡在 busy**：进程被 `timeout`/Ctrl-C 杀掉时 `finally` 里的 `release`
  跑不到，该实例永久 busy，下次 `acquire` 会新建一个。`reconcile()` 应该回收
  超时未心跳的 busy 实例。批跑前必须修，否则会把配额耗光。

## 2. 坐标约定标定

`coordinate_type` 取 relative（0-999）还是 absolute，需实测确认，不能照搬默认值。
**由本人确认**。

注意 OSWorld 的 `SYS_PROMPT_IN_SCREENSHOT_OUT_CODE` 全文不声明屏幕分辨率或坐标空间，
而 qwen scaffold 的 `build_description_prompt()` 会明写（relative 时给
`The screen's resolution is 1000x1000`）—— 换镜头时这项会跟着变。

## 3. M4 批量调度

`src/runner/batch_runner.py`：N 个 worker 线程消费任务队列。
每个 worker 拿实例是秒级的，批跑启动开销基本消失。并发上限 12 个实例（配额所限）。

依赖第 1 项先落地，否则每接一个模型都要重做一遍日志与计量。

## 4. 补 `src/smoke_test/test_apps_host.py`

开发机 app 的验证目前没有脚本覆盖，需要测三件事：
31 个 app 在开发机上起得来、沙箱经 `host.docker.internal` 能访问到、
不同 sid 之间状态互不污染。

## 5. monday_mock（8017）整个 app 白屏

`App.jsx` 只挂了 `AppProvider`，但 `Sidebar` / `Board` / `AutomationsPanel` 等 7 个活跃
组件用的是另一套 `useStore()`（来自 `StoreContext`），而 `StoreProvider` 从未挂载；
`createContext()` 又没给默认值，hook 返回 undefined，解构 `state` 直接抛错。

43 个任务因此全部不可做。修复要改 `/data/workspace/cua_hub`（另一个仓库，有未提交改动），
在那之前测试集应排除该 app。

同目录下 `discord_mock`(8001) 的 `useStore` 是 zustand（不需要 provider，仅同名）、
`microsoft_teams_mock`(8016) 那两个文件没人 import（死代码），两者实测渲染正常。

## 6. 基线 reward 扫描

`e872dfd6`（pinterest）实测基线 REWARD 就是 1.0 —— 这是故意设计的 NO-OP 任务，
`reward.py` 明写 "the correct agent behavior is to recognize the follow already exists
and do nothing"。显式标注 NO-OP 的只有 1 个，但「基线非零」范围更大：
部分 `reward.py` 含反向检查项（「不该动的东西没被动过」），什么都不做反而先得分。

所以该记的指标是 **`final_reward - baseline_reward`**，不是 `final_reward`。
两个字段 `result.json` 都已存，目前没人用这个差值。

建议在批跑前做一次基线扫描：只跑 `initial_setup.py` + `reward.py`，不调模型，
记下每个任务的基线分。不花 token，结果直接决定测试集怎么选。

## 7. 扩展到几百上千个网页

开发机磁盘（build 产物）会先于内存成为瓶颈（31 个 app 的 vite preview 合计才 1.68GB，
磁盘 70GB）。届时考虑按需拉起或反向代理分发。
