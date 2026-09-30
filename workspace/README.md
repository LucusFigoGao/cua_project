# CUA-Gym Web 任务评估 — 启动报告

> 本文档规划如何在**不修改** `gym/` 与 `osworld/` 的前提下，在 `workspace/` 下新建一套跑 CUA-Gym web 任务的 pipeline，复用 OSWorld 的 agent loop 思路 + `mm_agents/*` 模型侧代码 + `gym/utils` 里已有的沙箱封装。所有新代码只 `import` 引用两个目录，不改动其中任何文件。

## 0. 关键前置事实（本次调研确认）

- 本环境已有 `E2B_API_KEY` / `E2B_DOMAIN=ap-guangzhou.tencentags.com` 环境变量，说明 AGS 沙箱走的是 **e2b SDK 直连**，不经过 SSH。
- `e2b.Sandbox` 原生提供 `create / connect / list / get_host / kill / set_timeout / pause / fork`，沙箱的创建、查询、销毁全部通过 API 调用完成，**不需要**任何类似 `gym/utils/env.py` 里 `SSHGateway`（走跳板机 SSH 隧道）或 `LocalExecutor`（本地起子进程跑阿里云 SDK 脚本）的中间层——那两者是专门为"阿里云裸 VM 只能通过 SSH 触达"这个场景设计的，AGS/e2b 场景下没有对应问题。
- `Sandbox.get_host(port)` 会返回一个可从**编排进程所在机器**直接访问的公网 host:port。这意味着我们不必像现有 `ags_sandbox_env.py` 那样，把每一次截图/点击都写成一个 Python 脚本、上传、再 `commands.run` 执行（每次动作都有进程拉起开销，量级在 1-2 秒）；而是可以对沙箱内运行的 Chrome CDP 端口（默认 9222）调用一次 `get_host(9222)`，编排进程直接用 Playwright `connect_over_cdp` **保持一条常驻连接**，后续每步动作只是一次网络往返。这是本次调研中对第 2 点最重要的一个优化点。
- `gym/hub/websites/` 下有 **99 个** mock app（`gmail_mock`、`notion_mock`、`slack_mock`……），每个 app 通过 `/go /post /state /upload` 这套统一 HTTP State API 支持状态注入、读取、diff、reset。CUA-Gym 的 web 任务本质上就是"选一个 mock app + 注入一份 initial_state + 跑 reward.py 读 diff"，不需要 OSWorld 那种带类型分发的 `config/evaluator` schema。
- 本地 `gym/bench/data/tasks.parquet` + `gym/bench/stats.json` 已经是筛选后的任务索引：`num_web_tasks: 1075`（另有 430 个 `cross_app`）。你说的 1505 大概率是 web + cross_app 的合集，或来自更新版本数据集，实际数字以你们跑 loader 筛选时的真实结果为准，不影响下面的架构设计。

---

## 1. 目录规划

```
workspace/
├── README.md                  # 本文件
├── requirements.txt            # 新增依赖（pandas/pyarrow、e2b、playwright 等，均已在根 requirements 或需要补充 pyarrow）
├── configs/
│   └── pool_config.json        # 沙箱池配置：模板 id、并发数、每实例超时、app→port 映射
├── sandbox/
│   ├── __init__.py
│   ├── pool.py                 # SandboxPool：批量创建/连接/回收 AGS 沙箱实例（对应问题 1 & 5）
│   └── pixel_env.py            # PixelSandboxEnv：继承/组合 gym.utils.SandboxEnv，加坐标动作 + a11y 快照（对应问题 2）
├── tasks/
│   ├── __init__.py
│   ├── catalog.py               # 从 tasks.parquet 筛 web 任务、生成任务队列（对应问题 3）
│   └── loader.py                 # 单任务下载/URL 占位符替换/初始化/评分，薄封装 SandboxEnv 已有方法
├── agents/
│   ├── __init__.py
│   └── bridge.py                  # 把 mm_agents.* 的 obs/action 格式对接到 PixelSandboxEnv（对应问题 4）
├── runner/
│   ├── single_task.py              # 单实例单任务：reset → agent loop → reward，仿 osworld/lib_run_single.py 的结构
│   └── batch_runner.py              # 多实例并行调度，消费 tasks/catalog 产出的队列
└── results/
    └── <task_id>/...                 # 轨迹、截图、reward 日志
```

---

## 2. 逐项落地方案

### 问题 1 + 5：沙箱/实例管理与并行调度（合并为一个组件 `sandbox/pool.py`）

**结论：不使用 SSHGateway，也不使用 LocalExecutor 的模式，直接基于 e2b SDK 写一个新的 `SandboxPool`。**

`gym/utils/env.py` 里 `SSHGateway` / `LocalExecutor` 解决的是"如何在没有直连能力的阿里云 ECS 上执行 VM 生命周期脚本"这个问题；AGS 沙箱创建/连接/销毁本身就是一次 API 调用（`Sandbox.create/connect/list/kill`），不存在"要不要 SSH 跳板"的选择——两个都不需要，两者的问题在这里都不存在。

参照 `EnvConfig` + `Env` 的**形状**（可序列化配置 + 工厂方法 + save/load），已实现于 `workspace/sandbox/pool.py`：

```python
@dataclass
class PoolInstanceConfig:
    sandbox_id: str
    template: str
    created_at: str
    status: str  # "idle" | "busy"
    current_task_id: Optional[str] = None
    app_type: Optional[str] = None
    deployed_apps: dict[str, int] = field(default_factory=dict)  # app_name -> port

class SandboxPool:
    @classmethod
    def from_registry(cls, path, **kwargs) -> "SandboxPool": ...
    def acquire(self, app_type=None, block=True, timeout=None) -> tuple[PoolInstanceConfig, Sandbox]: ...
    def release(self, sandbox_id: str, sbx=None, pause=True) -> None: ...
    def mark_app_deployed(self, sandbox_id: str, app_type: str, port: int) -> None: ...
    def reconcile(self) -> dict:      # 调 Sandbox.list(query=SandboxQuery(metadata=POOL_TAG)) 校准 registry
    def kill(self, sandbox_id: str) -> None: ...
    def kill_all(self) -> None: ...
```

- `acquire()` 池满且无空闲实例时用 `threading.Condition` 阻塞等待 `release()` 唤醒（`block=False` 则直接抛 `SandboxPoolError`），不需要 `ThreadPoolExecutor` 额外并发层——沙箱创建本身就是一次网络 IO，多个 worker 线程各自调用 `acquire()` 天然并发。
- registry 落盘为 JSON（`configs/pool_registry.json`，已加入 `.gitignore`），每次批跑前 `reconcile()` 用 `Sandbox.list()` 核对，避免"本地记录活着、实际已过期销毁"的脏状态；新建实例时写入 `metadata={"pool": "cua_gym", "app_type": ...}`，reconcile 靠这个 metadata 而不是纯本地文件作为真相源。
- pool 本身不知道 Hub app 部署细节：调用方用 `SandboxEnv.deploy_hub_app` 部署完成后调 `pool.mark_app_deployed()` 登记，后续 `acquire(app_type=...)` 优先复用已部署对应 app 的空闲实例。
- `batch_runner.py` 就是这个 pool 的消费者：N 个 worker 线程，每个从任务队列取一个 task，`pool.acquire(app_type=...)` 拿一个空闲沙箱，跑完 `release()`（默认 `pause=True`）。

### 问题 2：像素级动作优先，兼容 a11y 树（`sandbox/pixel_env.py`）

不改 `gym/utils/ags_sandbox_env.py`，而是新写一个类，**优先复用**已有的 `SandboxEnv` 做沙箱管理相关的部分（`deploy_hub_app` / `run_initial_setup` / `run_reward` 直接调用），只重做"观测 + 动作"这两个方法：

```python
class PixelSandboxEnv:
    def __init__(self, sandbox_env: SandboxEnv, viewport=(1280, 800)):
        self._env = sandbox_env
        self._cdp_url = f"https://{sandbox_env.sbx.get_host(9222)}"
        # 用 playwright 建立一条常驻 CDP 连接，而不是每次动作都 write_and_run
        ...

    def screenshot(self) -> bytes:            # 固定 viewport，不用 full_page，保证坐标系对齐
    def step(self, action: dict) -> None:      # {"type": "click", "x":.., "y":..} / "type" / "key" / "scroll" / "move"
    def get_a11y_tree(self) -> str:             # P1：page.accessibility.snapshot() 或 aria_snapshot()，返回给 agent 当文本观测
```

- P0：`click(x,y) / double_click / type_text / key_press / scroll / mouse_move`，全部走 CDP `page.mouse.*` / `page.keyboard.*`，坐标系和 `screenshot()` 的 viewport 严格一致。
- P1：`get_a11y_tree()` 作为可选观测，配合 `mm_agents` 里 `observation_type in {"a11y_tree","screenshot_a11y_tree"}` 的 agent 变体。
- 用 `get_host(9222)` 常驻连接代替"写脚本→上传→跑→解析 stdout"，单步延迟从秒级降到百毫秒级，这对 1505 个任务规模的评估吞吐很关键。

### 问题 3：任务 loader，借鉴 OSWorld 的是"编排循环形状"而不是"schema"

OSWorld 的 `config`/`evaluator` 分发机制（type 映射到 controller 方法、`evaluator.func` 映射到注册的 Python 函数）**不需要照搬**——CUA-Gym 的 web 任务本来就是自包含脚本（`initial_setup.py` 直接跑、`reward.py` 直接跑读 REWARD 输出），复杂度低很多。真正值得借鉴的是 OSWorld `lib_run_single.py` 的**单任务执行时序**：

```
reset(task) → [ agent.predict(obs) → env.step(action) ] * max_steps → evaluate() → log
```

`tasks/loader.py` 直接薄封装 `SandboxEnv` 已有的：
- `find_task` / `download_task`（HF 下载 + tar.zst 解压 + URL 占位符替换，已实现，直接调用）
- `run_initial_setup`（跑 `initial_setup.py`，拿到 `sid`）
- `run_reward`（跑 `reward.py`，解析 `REWARD:` 分数）

`tasks/catalog.py` 新增的是**批量筛选 + app 路由**：
1. 读本地 `gym/bench/data/tasks.parquet`，过滤 `platform == "web"`（以及需要的话 `app_family == "mock_web"` / `cross_app`），产出任务队列。
2. 每个任务的 `app_type` 需要映射到 `gym/hub/websites/<app_type>_mock` 这个目录名（99 个 mock app 命名基本规整，个别需要做别名表，例如大小写不一致的 `Canvas-LMS_mock` / `canvas_mock`、`Expensify_mock` 等）。
3. **待确认的开放问题**：一个沙箱实例上，`deploy_hub_app` 目前默认把 app 起在固定端口 5173。如果同一批次里有多个不同 `app_type` 的任务落在同一个沙箱实例上，要么（a）每个 app 用不同端口全部预启动（"all-in-one" 沙箱如果镜像里已经装好全部 99 个 app，这是最优方案），要么（b）单实例同一时间只服务一个 app，换任务前先 kill 旧进程再重新 `npm run dev`（简单但有启动开销）。这个需要先确认 `sdt-2nn0tz4x` 这个模板镜像里到底预置了什么（是否已经 clone 好 `CUA-Gym-Hub` 仓库、是否所有 99 个 app 的 `npm install` 已经提前跑过）。

### 问题 4：复用 `mm_agents`

```python
import sys
sys.path.insert(0, str(OSWORLD_DIR))  # osworld/ 作为纯引用路径，不改动其中代码
from mm_agents.agent import PromptAgent
```

`agents/bridge.py` 只做一件事：把 `PixelSandboxEnv.screenshot()` / `get_a11y_tree()` 包成 `mm_agents` 期望的 `obs = {"screenshot": bytes, "a11y_tree": str}` 格式，再把 agent 吐出的 pyautogui/`computer_13` 动作解析成 `PixelSandboxEnv.step()` 能吃的 `{"type":...}` dict。这一层是唯一需要"翻译"的地方，`mm_agents` 内部代码零改动。

---

## 3. 阶段计划

| 阶段 | 内容 | 产出 | 依赖 |
|---|---|---|---|
| M0 | `sandbox/pool.py`：批量创建/连接/回收 + registry 落盘 | 能并发拉起 N 个沙箱并稳定回收 | E2B_API_KEY（已具备） |
| M1 | `sandbox/pixel_env.py`：CDP 常驻连接 + 坐标动作 + 固定 viewport 截图 | 单实例可用坐标点击跑通一个 mock app | M0 |
| M2 | `tasks/catalog.py` + `loader.py`：筛选 web 任务、app 路由表、跑通 setup→reward 单任务闭环 | 单任务端到端跑通（不接 agent，先用固定脚本模拟点击验证 reward 能拿到分） | M1，需先确认镜像预置内容 |
| M3 | `agents/bridge.py` + `runner/single_task.py`：接入 `mm_agents.PromptAgent`，单实例单任务全链路（reset→agent loop→reward） | 一条完整轨迹 + 分数 | M1, M2 |
| M4 | `runner/batch_runner.py`：多实例并行跑全量 web 任务集 | 全量评估报告（成功率/分数分布） | M0-M3 全部完成 |

建议先做 M0+M1 的最小验证（一个沙箱 + 一个 mock app + 手写固定坐标点几下），确认 CDP 常驻连接和坐标系对齐没问题，再往上叠 M2-M4。

---

## 4. 开放问题（已确认 2 条，待定 2 条）

### ✅ 已确认

**镜像内容（原问题 1）**：`sdt-2nn0tz4x` 没有预制镜像，每次新建实例都需要从 git/HuggingFace clone CUA-Gym-Hub 并跑 `npm install`。单实例资源约 4C/8Gi。

这个约束对架构有决定性影响，见下文"Pause 策略"一节。

**并发配额（原问题 2）**：AGS 账号单地域限制如下：

| 配额项 | 限制 | 对本项目的含义 |
|---|---|---|
| 沙箱实例数（运行中+空闲） | 50 | 池中实例总数上限 |
| CPU 总和（运行中） | 50C | 50C / 4C/实例 = **最多 12 个并发运行** |
| 内存总和（运行中） | 100Gi | 100Gi / 8Gi/实例 = **最多 12 个并发运行** |
| 暂停实例数 | 20 | 可保留 20 个预热实例不销毁 |

有效并发上限：**12 个实例**（CPU 和内存约束同时压住，取 min(12, 12) = 12）。

### Pause 策略（由"无预制镜像"推导出）

无法预制镜像意味着每个新实例都要执行：

1. `git clone CUA-Gym-Hub`（网络耗时，约 30-60s）
2. `npm install`（每个 app，约 60-120s）
3. `npm run dev`（启动服务，约 5-15s）

如果每个任务跑完就 kill 实例，再新建时重复以上三步，cost 远超任务本身执行时间，跑 1500 个任务基本不可行。

**正确做法**：利用 e2b 的 pause/resume（实例方法 `sbx.pause(keep_memory=...)` + `Sandbox.connect(sandbox_id, on_resume='restore')`，已用 `inspect` 核实真实签名）在任务间保留实例状态：

- 每个实例首次创建时部署好需要的 mock app（一次性 clone + npm install），然后 pause。
- 调度器需要实例时 resume，任务完成后再次 pause，而不是 kill。
- 20 个 pause slot 对应 20 个预热实例（每个可以部署不同的 app，也可以同一 app 多副本）。
- 真正需要 kill 的场景：实例异常、pool 需要缩减、app 类型需要切换但 pause 槽满了。

这个策略让实际的 clone+install 只发生一次（per 实例 lifetime），大幅提升吞吐。`SandboxPool`（`workspace/sandbox/pool.py`，已实现）的 `acquire/release` 就是 **pause/resume** 语义，而不是 create/kill；`Sandbox.create(metadata=...)` + `Sandbox.list(query=SandboxQuery(metadata=...))` 被用作 registry 的校准真相源（`reconcile()`）。

### ❓ 待确认

**a11y 树 API**：CDP `page.accessibility.snapshot()`（旧，Playwright 标记为 deprecated）还是 `locator.aria_snapshot()`（新，纯文本树，格式不同）？建议 M1 阶段做一个小 spike：对同一个 mock app 页面同时调两个 API，对比输出格式，再决定 `mm_agents` 里对应的 `observation_type` 配置方式。

**1505 vs 1075 的口径**：跑 `tasks/catalog.py` 时打印一次实际筛出的任务数和 app_type 分布，看是否要包含 `cross_app` 才能凑到 1505。

---

## 5. 新增依赖

`workspace/requirements.txt`（待创建，草案）：
```
pandas
pyarrow          # 读 tasks.parquet，当前环境缺失
e2b==2.51.0       # 已装
playwright==1.63.0 # 已装，但需要 playwright install chromium（若从编排进程直连 CDP 需要本地也有 playwright python 包，不需要本地装 chromium 二进制，因为是 connect_over_cdp 到远端）
```

环境变量沿用现有的 `E2B_API_KEY` / `E2B_DOMAIN`，无需新增。
