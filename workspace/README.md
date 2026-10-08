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
├── requirements.txt            # 新增依赖（zstandard、e2b、playwright 等）
├── run.py                       # ✅ 取一个部署好 31 app 的实例（24h，复用不 kill）
├── unpack_tasks.py               # ✅ 【一次性】归档 → 筛选+占位符替换 → tasks_data/
├── push_tasks.py                  # ✅ 选一批任务打 tar 推到实例
├── configs/
│   ├── apps.json                   # ✅ 31 个 mock app 及固定端口（占位符替换表的事实来源）
│   └── sandbox_pool.json            # ✅ 池 registry（reconcile 以远端 metadata 为真相源）
├── tasks_data/                       # ✅ 解包产物（.gitignore）：1062 个任务 + _index.json
├── sandbox/
│   ├── pool.py                        # ✅ SandboxPool：no-pause 常驻复用
│   ├── deploy.py                       # ✅ 31-app 固定端口部署（~176s，幂等）
│   └── pixel_env.py                     # M1：坐标动作 + a11y 快照（对应问题 2）
├── tasks/
│   ├── urlmap.py                         # ✅ 占位符替换表（从 apps.json 推导）
│   ├── catalog.py                         # ✅ 读 tasks_data/，筛选 + 分层取样
│   └── push.py                             # ✅ tar 上传 + google-chrome shim
├── agents/
│   └── bridge.py                            # M3：mm_agents 的 obs/action 适配（对应问题 4）
├── runner/
│   ├── single_task.py                        # M3：单实例单任务
│   └── batch_runner.py                        # M4：多实例并行调度
└── results/
    └── <task_id>/...                           # 轨迹、截图、reward 日志
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

#### ✅ 已实现（M2 任务侧落地）

实际落地的分工与最初设想有调整：**不复用** `SandboxEnv.find_task` / `download_task`（它们走 HF 在线下载 + 逐任务 `sed` 替换），改成"一次性解包出本地任务库 + 按需推送"两段式。理由是任务会持续扩展和修订，本地任务库是可重复生成的中间产物，比每次在沙箱内联网下载更快也更可控。

```
workspace/
├── unpack_tasks.py     # 【一次性】归档 → 筛选 + 占位符替换 → tasks_data/
├── push_tasks.py       # CLI：取样 → 打 tar → 推实例
├── tasks_data/         # 解包产物（.gitignore），1062 个任务 + _index.json
└── tasks/
    ├── urlmap.py       # 占位符替换表（从 configs/apps.json 推导）
    ├── catalog.py      # 读 tasks_data/，筛选 + 分层取样
    └── push.py         # tar 上传 + google-chrome shim
```

**数据源是 `gym/bench/artifacts/cua_gym_tasks_v1.tar.zst`（52MB，本地已有），不读 `tasks.parquet`。** 实测 `app_type ∈ configs/apps.json 的 31 个 app` 与 parquet 里 `platform=="web" and setup_kind=="py"` **完全等价（都是 1067 条）**，而 `app_type` 就写在每个任务的 `task.json` 里（`id`/`app_type`/`instruction` 覆盖率 100%，`difficulty` 78%）。所以筛选条件可以从任务目录自身读出，不需要外部索引——新增任务只要目录结构对就能被认出来，不必同步维护 parquet。

**关键坑：归档里的脚本是「未替换」的占位符。** 这与 `/data/workspace/tasks_web/` 那份手工预处理产物不同：

| 来源 | `BASE_URL` |
|---|---|
| `tasks_web/<id>/initial_setup.py` | `'http://host.docker.internal:8012'`（已替换） |
| 归档 `<id>/initial_setup.py` | `'__CUA_GYM_INSTACART_URL__'`（**占位符**） |

两种占位符形式都要处理（实测 38 种）：`__CUA_GYM_<APP>_URL__` → `http://host.docker.internal:<port>`，`__CUA_GYM_<APP>_HOST__` → `host.docker.internal:<port>`（**无 scheme**）。替换表由 `tasks/urlmap.py` 从 `configs/apps.json` 自包含推导（`app` 去掉 `_mock` 后缀再大写），已验证 31/31 全命中；另有 `__CUA_GYM_NOTION_MOCK_URL__` 一个非规范命名走别名表。

解包时的两道质量门禁：替换后仍残留 `__CUA_GYM_*__` 的任务、以及脚本未引用本实例对应端口的任务，都**不入库**。后者筛掉了 5 个上游数据瑕疵任务——4 个在归档里就写死了 `172.17.46.46:80xx`（另一套部署的 IP 和端口布局，压根没留占位符），1 个 `google_sheets` 任务是 LibreOffice 本地文件操作、不走 HTTP。最终 **1062 个可用任务，覆盖 28 个 app**。

归档遍历两个实现细节：zstd 流不可 seek，`tarfile` 必须 `mode="r|"` 单向顺序读完（全量 ~5s，所以要一次遍历提取所有任务）；归档里混了 macOS 的 `._xxx` AppleDouble 伪文件，内容非 UTF-8，必须按文件名跳过否则 `.decode()` 抛异常。

另外 `asana_mock` / `discord_mock` / `docusign_mock` 这 3 个 app **没有任何 web 任务**——部署了但用不上，31 个 app 里实际只有 28 个会被任务引用。

#### 端口与部署（原结论，仍成立）

任务 setup 文件把 mock app URL 硬编码为 `http://host.docker.internal:8000`~`8030`，不是任意端口路由问题，而是**同一个沙箱实例必须同时跑满这 31 个固定 app**（不是全部 99 个，是 `tasks_web` metadata 里筛出的 31 个子集，字母序对应端口 8000→8030）。已用 `smoke_test/test_deploy.py` 在模板 `sdt-hojglb51`（8GB 盘/4C/7.8GB 内存）上验证：git clone 8s + npm install（31 个串行）97s + npm run build（8 并发批量）58s + tmux 起 31 个 `vite preview` 12s = **总耗时 176s**，31/31 端口返回 200，磁盘占用 60%（4.5G/8G）。单实例装满 31 个 app 完全可行。

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
| M0 | `sandbox/pool.py`：批量创建/连接/回收 + registry 落盘 | ✅ 已完成。`run.py` 走 reconcile → acquire → release(pause=False) 复用路径 | E2B_API_KEY（已具备） |
| M1 | `sandbox/pixel_env.py`：CDP 常驻连接 + 坐标动作 + 固定 viewport 截图 | 单实例可用坐标点击跑通一个 mock app | M0。浏览器侧前置已清：chromium 常驻 + CDP 9222 在听（见 §4） |
| M2 | `tasks/`：筛选 web 任务、占位符替换、推送实例、跑通 setup→reward 闭环 | ✅ 任务侧已完成：1062 个任务入库，84 个（每 app 3 个）已推实例，setup→launch_gui→reward 全链路验证通过（`smoke_test/test_task_from_archive.py`）。待接 agent | M0 |
| M3 | `agents/bridge.py` + `runner/single_task.py`：接入 `mm_agents.PromptAgent`，单实例单任务全链路（reset→agent loop→reward） | 一条完整轨迹 + 分数 | M1, M2 |
| M4 | `runner/batch_runner.py`：多实例并行跑全量 web 任务集 | 全量评估报告（成功率/分数分布） | M0-M3 全部完成 |

建议先做 M0+M1 的最小验证（一个沙箱 + 一个 mock app + 手写固定坐标点几下），确认 CDP 常驻连接和坐标系对齐没问题，再往上叠 M2-M4。

---

## 4. 开放问题（已确认 2 条，待定 2 条）

### ✅ 已确认

**镜像内容（原问题 1）**：最终选定模板 `sdt-hojglb51`（all-in-one，8GB 盘/4C/7.8GB 内存），没有预制镜像，每次新建实例都要从 git clone CUA-Gym-Hub 并跑 31 个 app 的 `npm install` + `npm run build`。实测总耗时 176s（见上文问题 3）。

这个约束对架构有决定性影响，见下文"实例复用策略"一节。

**并发配额（原问题 2）**：AGS 账号单地域限制如下：

| 配额项 | 限制 | 对本项目的含义 |
|---|---|---|
| 沙箱实例数（运行中+空闲） | 50 | 池中实例总数上限 |
| CPU 总和（运行中） | 50C | 50C / 4C/实例 = **最多 12 个并发运行** |
| 内存总和（运行中） | 100Gi | 100Gi / 8Gi/实例 = **最多 12 个并发运行** |
| 暂停实例数 | 20 | 可保留 20 个预热实例不销毁 |

有效并发上限：**12 个实例**（CPU 和内存约束同时压住，取 min(12, 12) = 12）。

### 实例复用策略（由"无预制镜像 + 固定 31-app 部署"推导出，no-pause 常驻复用）

无法预制镜像意味着每个新实例首次使用都要执行一次性的部署（clone + 31 个 app 的 install/build + tmux 起 31 个 `vite preview`，实测 176s）。如果每个任务跑完就 kill 实例，再新建时重复这一整套，cost 远超任务本身执行时间，跑 1500 个任务基本不可行。

**曾经考虑过的方案**：e2b 的 pause/resume（`sbx.pause()` + `Sandbox.connect(sandbox_id, on_resume='restore')`）。在模板 `sdt-hojglb51` 上实测 resume 连续 4/4 失败（`500 InternalError.Unknown`），`pause()` 本身会把实例切到 STOPPED 而非 PAUSED，**已放弃**，详见 memory `ags_resume_blocked`。

**实际采用的做法：no-pause 常驻复用**——任务间不 pause/kill 实例，只是标记 idle/busy：

- 每个实例首次创建时部署好全部 31 个 app（一次性 clone + install + build + tmux 起 vite preview），然后保持 running，状态标记为 idle。
- 调度器需要实例时直接 `Sandbox.connect(sandbox_id)` 复用，不传 `on_resume`；任务完成后 `release(pause=False)`，实例继续 running 回到 idle，而不是 pause/kill。
- 真正需要 kill 的场景：实例异常、pool 需要缩减。
- 由于每个实例都部署全部 31 个 app（不是按 app_type 分流的单 app 实例），"app 类型切换"不存在——任何空闲实例都能服务任何 app_type 的任务。

这个策略让实际的 clone+install+build 只发生一次（per 实例 lifetime，176s），大幅提升吞吐。`SandboxPool`（`workspace/sandbox/pool.py`，已实现）的 `acquire/release` 默认是 **no-pause 复用**语义（`release(pause=False)`），不是 pause/resume 也不是 create/kill；`Sandbox.create(metadata=...)` + `Sandbox.list(query=SandboxQuery(metadata=...))` 被用作 registry 的校准真相源（`reconcile()`）。`pause=True` 路径仍保留在代码里但不作为默认路径使用。

### ✅ 已确认（补充）：实例上浏览器与 CDP 已就绪

**此前"沙箱里没有 google-chrome，要把 `launch_gui` 那行注释掉"的结论不准确**（该说法见 `gym/utils/ags_sandbox_env.py` 的 `download_task` 和旧 `smoke_test/test_task_e2e.py` 的注释）。在 all-in-one 模板的活跃实例上实测：

- `/usr/bin/chromium` 存在，Chromium 146.0.7680.164
- chromium 由 **s6 托管常驻运行**，`DISPLAY=:1`，Xvfb 已在跑（`:1 1920x1080x24`）
- **CDP 9222 已在监听**，且启动时就带着一个 page target
- 缺的只是**名为 `google-chrome` 的可执行文件**

所以正确做法不是注释掉 `launch_gui`，而是装一个 shim（`tasks/push.py` 的 `ensure_chrome_shim`）：

```sh
/usr/local/bin/google-chrome  ->  #!/bin/sh\nexec /usr/bin/chromium "$@"
```

实测以默认用户 `user` 调用 shim 打开任务 URL，chromium 输出 `Opening in existing browser session.`，页面随即出现在 CDP target 列表里。**shim 必须以默认用户执行**——chromium 拒绝以 root 运行而不加 `--no-sandbox`（`Running as root without --no-sandbox is not supported`），这正是之前误判的来源。写 `/usr/local/bin` 本身需要 root，所以只有建 shim 这一步用 `user="root"`，与 `deploy.ensure_host_mapping` 写 `/etc/hosts` 的处理一致。

这同时把 M1 的浏览器路径提前打通了：**M1 的 `PixelSandboxEnv` 不需要自己拉起浏览器**，直接 `get_host(9222)` + `connect_over_cdp` 连这个常驻实例即可。另外 `PUT /json/new?<url>` 也能直接开 tab，可作为不依赖 shim 的备选。

### ❓ 待确认

**a11y 树 API**：CDP `page.accessibility.snapshot()`（旧，Playwright 标记为 deprecated）还是 `locator.aria_snapshot()`（新，纯文本树，格式不同）？建议 M1 阶段做一个小 spike：对同一个 mock app 页面同时调两个 API，对比输出格式，再决定 `mm_agents` 里对应的 `observation_type` 配置方式。

**~~1505 vs 1075 的口径~~ ✅ 已确认**：`gym/bench/data/tasks.parquet` 共 10910 行，`platform` 分布为 `desktop` 8029 / `web` 1075 / `cross_app` 430。其中落在 31 个 mock app 内的 web 任务 1067 个，再扣掉 5 个上游数据瑕疵任务（见问题 3），**实际可用 1062 个**。1505 既不是 web 也不是 web+cross_app（=1505 恰好等于 1075+430，所以那个数字应当就是 web + cross_app 的合集口径）。本次只纳入 web，`cross_app` 的 430 个未处理。另有 8 个 `app_type=="mock_websites"` 的跨 app 任务（如 Stripe→Gmail），其 app_type 不在 31 个之列，当前被自动过滤。

---

## 5. 新增依赖

`workspace/requirements.txt`（待创建，草案）：
```
zstandard        # 解 cua_gym_tasks_v1.tar.zst，unpack_tasks.py 依赖
e2b==2.51.0       # 已装
playwright==1.63.0 # 已装，但需要 playwright install chromium（若从编排进程直连 CDP 需要本地也有 playwright python 包，不需要本地装 chromium 二进制，因为是 connect_over_cdp 到远端）
```

`pandas` / `pyarrow` **不再是必需**——任务筛选改为直接读任务目录自带的 `task.json`，不读 `tasks.parquet`（见问题 3）。两者仅在想交叉核对 parquet 统计口径时才需要。

环境变量沿用现有的 `E2B_API_KEY` / `E2B_DOMAIN`，无需新增。

---

## 6. 当前可跑的命令

```bash
# 取一个部署好 31 个 app 的实例（24h，复用池内 idle 实例，不 kill）
python workspace/run.py

# 【一次性】把归档解包成本地任务库 workspace/tasks_data/（~5s，1062 个任务）
python workspace/unpack_tasks.py

# 选一批任务推到实例（默认每个 app 3 个 = 84 个）
python workspace/push_tasks.py --per-app 3
python workspace/push_tasks.py --all                  # 全部 1062 个
python workspace/push_tasks.py --app slack_mock       # 只推某个 app
python workspace/push_tasks.py --dry-run              # 只看选中了哪些，不连实例

# 端到端验证：setup → launch_gui(CDP 检查) → reward
python workspace/smoke_test/test_task_from_archive.py
```

以上脚本**都不会 kill 实例**，跑完 `release(pause=False)` 让实例回到 idle 继续复用。
`unpack_tasks.py` 和 `push_tasks.py` 都是幂等的：前者跳过已解包任务（`--force` 强制重解），后者覆盖上传。
