# CUA-Gym Web 任务评估

在**不修改** `gym/` 与 `osworld/` 的前提下，跑 CUA-Gym 的 web 任务。
`workspace/` 下的代码只 `import` 引用那两个目录。

---

## 1. 架构

```
┌─ 开发机 ────────────────────────┐      ┌─ AGS 沙箱 ×N ─────────────────┐
│  31 个 vite preview :8000-8030  │←HTTP─│  OSWorld server :5000          │
│  src/cli/* + pool + agent       │─envd→│  chromium + Xvfb :1 (CDP 9222) │
└─────────────────────────────────┘      │  /etc/hosts: <开发机IP> h.d.i  │
                                         │  任务脚本在沙箱内跑            │
                                         └────────────────────────────────┘
```

**app 跑在开发机上**，一份服务所有沙箱。app 是无状态静态服务，沙箱不部署它们，
因此新实例秒级可用。任务脚本里硬编码的 `http://host.docker.internal:8027`
不需要改——沙箱 `/etc/hosts` 把 `host.docker.internal` 指向开发机 IP，请求自然落到开发机。

**任务脚本必须在沙箱内执行**，两个硬约束：

- `initial_setup.py` 把 sid 写到 `/tmp/task_web_sid`，`reward.py` 从那里读，两者必须同机
- `initial_setup.py` 末尾 `launch_gui('google-chrome ...')` 要在沙箱的 chromium 里开页面

**并发安全**：每个任务 `initial_setup.py` 生成随机 UUID 作 `sid`，所有读写都带上它
（`POST /post?sid=<sid>`），不同沙箱 sid 不同，共享一份 app 是安全的。

**单点**：开发机一挂，所有在跑的评估都失败。IP 由 `apps_host.detect_host_ip()`
自动探测（连外部地址看内核选了哪个源 IP，避开 `docker0` 的 `172.17.0.1`），
需要覆盖时设 `CUA_APP_HOST`。

---

## 2. 目录结构

```
workspace/
├── README.md / TODO.md
├── env.sh                     设 PYTHONPATH + 加载 ~/.bashrc
├── configs/
│   ├── apps.json              31 个 app → 固定端口（事实来源）
│   └── sandbox_pool.json      池 registry（运行期状态，gitignore）
├── tasks_data/                解包产物 1062 个任务（gitignore）
├── results/                   轨迹 + 截图（gitignore）
└── src/
    ├── settings.py            路径 / 模板 / 端口等共享常量
    ├── cli/
    │   ├── serve_apps.py      【开发机】起/停/查 31 个 app
    │   ├── manage_pool.py     池运维：预热 / 查看 / 回收 busy / 销毁
    │   ├── unpack_tasks.py    【一次性】归档 → tasks_data/
    │   ├── push_tasks.py      选任务打 tar 推实例
    │   └── run_task.py        单任务闭环：setup → agent → reward
    ├── sandbox/
    │   ├── apps_host.py       开发机侧：clone / build / tmux 起 app / 探活 / 探测 IP
    │   ├── deploy.py          沙箱侧：写 hosts 映射 + 探活
    │   ├── pool.py            SandboxPool：no-pause 常驻复用
    │   ├── osworld_server.py  把 OSWorld agent server 装进沙箱常驻
    │   └── pixel_env.py       瘦客户端：全屏观测 + pyautogui 动作
    ├── tasks/
    │   ├── urlmap.py          占位符替换表（从 apps.json 推导）
    │   ├── catalog.py         读 tasks_data/，筛选 + 分层取样
    │   └── push.py            tar 上传 + google-chrome shim
    ├── agents/
    │   ├── registry.py        统一接口 + 注册表 + 装载校验
    │   └── adapters/          每个 agent 一个 adapter：qwen_cua / qwen3vl / claude_cu / gemini_cu / raw_vlm
    ├── runner/
    │   └── episode.py         episode 循环：观测 → predict → 执行，直到 DONE/FAIL/步数用完
    └── smoke_test/
        ├── test_pool.py               池的获取/归还/校准
        ├── test_task_from_archive.py  任务解包→推送→setup→reward
        └── test_osworld_server.py     观测 + 坐标动作（11/11）
```

所有模块用绝对导入（`from src.xxx import` / `from mm_agents.xxx import`），
路径由 `env.sh` 的 `PYTHONPATH` 提供。唯一例外是 `src/agents/registry.py` 会把 `osworld/`
补进 `sys.path`，保证不经 `env.sh` 直接 import adapter 时也能找到 `mm_agents`。

---

## 3. 启动

```bash
cd workspace
source env.sh                  # PYTHONPATH + ICHAT_API_KEY / ICHAT_BASE_URL
```

`env.sh` 必须先 source：它把 `cua_project/` 和 `osworld/` 放进 `PYTHONPATH`
（`osworld/` 自己也要在路径上，因为 `mm_agents/agent.py` 内部是 `from mm_agents...` 导入的），
并加载 `~/.bashrc` 里的 `ICHAT_API_KEY` / `ICHAT_BASE_URL`（跑 agent 必需，
非交互 shell 不会自动加载）。

```bash
# ── 一次性准备 ──────────────────────────────────────────────
python -m src.cli.serve_apps --start    # 开发机起 31 个 app（首次 clone+build 约 3-5 min）
python -m src.cli.unpack_tasks          # 归档 → tasks_data/（~5s，1062 个任务）

# ── app 服务管理（开发机）───────────────────────────────────
python -m src.cli.serve_apps --status -v
python -m src.cli.serve_apps --restart
python -m src.cli.serve_apps --stop

# ── 实例与任务 ──────────────────────────────────────────────
python -m src.cli.manage_pool           # 预热：保证池里有一个就绪实例（24h，复用不 kill）
python -m src.cli.manage_pool --status  # 列出实例及 idle/busy
python -m src.cli.manage_pool --release-all   # 回收卡在 busy 的实例（确认无其他任务在跑）
python -m src.cli.manage_pool --kill-all --yes
python -m src.cli.push_tasks --per-app 3 # 推任务（默认每 app 3 个）
python -m src.cli.push_tasks --all       # 推全部 1062 个
python -m src.cli.push_tasks --dry-run   # 只看选中了哪些

# ── 跑任务 ──────────────────────────────────────────────────
python -m src.cli.run_task --list
python -m src.cli.run_task --list-agents                     # 列出已注册的 agent
python -m src.cli.run_task --task <id> --agent qwen-cua --max-steps 10
python -m src.cli.run_task --task <id> --agent raw-vlm --model gemini-3.5-flash

# ── 验证 ────────────────────────────────────────────────────
python -m src.smoke_test.test_osworld_server      # 观测+动作（11/11）
python -m src.smoke_test.test_task_from_archive   # 任务链路
python -m src.smoke_test.test_pool                # 池的获取/归还/校准
```

所有脚本假定 app 已在开发机上跑着；没跑的话 `manage_pool.py` / `run_task.py` 直接提示去执行
`serve_apps.py --start`，不会白白建实例。**所有脚本都不 kill 实例**，跑完
`release()` 回到 idle 继续复用。`unpack_tasks.py` 和 `push_tasks.py` 幂等。

---

## 4. 各部分说明

### 沙箱池（`src/sandbox/pool.py`）

```python
@dataclass
class PoolInstanceConfig:
    sandbox_id: str; template: str; created_at: str
    status: str                      # "idle" | "busy"
    app_type: Optional[str] = None
    app_host: Optional[str] = None   # app 实际跑在哪
    apps_ready: bool = False         # hosts 映射已配好且探活通过

class SandboxPool:
    def acquire(app_type=None, block=True, ...) -> tuple[PoolInstanceConfig, Sandbox]
    def release(sandbox_id)
    def reconcile() -> dict      # 以 Sandbox.list(metadata=POOL_TAG) 为真相源校准
    def kill(sandbox_id) / kill_all()
```

registry 落盘 JSON，批跑前 `reconcile()` 用远端 metadata 核对，避免「本地记录活着、
实际已销毁」的脏状态。池满时 `acquire()` 用 `threading.Condition` 阻塞等待。

每次 acquire 都重写 hosts 而不是靠 `apps_ready` 跳过——开发机 IP 变了、或实例是从远端
reconcile 回来的，都要重配；hosts 写入幂等，成本可忽略。app 不可达时抛
`AppsUnreachableError` 而不 kill 实例（那是开发机侧的问题）。

**实例复用：no-pause 常驻。** pause/resume 在模板 `sdt-hojglb51` 上 resume 连续
4/4 失败（`500 InternalError.Unknown`），`pause()` 还会把实例切到 STOPPED 而非 PAUSED。
任务间只标记 idle/busy 让实例保持 running，只有实例异常或池缩减才 kill。

### 任务侧（`src/tasks/` + `unpack_tasks.py` + `push_tasks.py`）

数据源是 `gym/bench/artifacts/cua_gym_tasks_v1.tar.zst`（52MB），不读 `tasks.parquet`：
`app_type ∈ apps.json 的 31 个 app` 与 parquet 的 `platform=="web" and setup_kind=="py"`
完全等价（都是 1067 条），而 `app_type` 就在每个任务的 `task.json` 里。任务目录自描述，
新增任务不必同步维护索引。

归档里的脚本是**未替换的占位符**，两种形式（实测 38 种）：

| 占位符 | 替换为 |
|---|---|
| `__CUA_GYM_<APP>_URL__` | `http://host.docker.internal:<port>` |
| `__CUA_GYM_<APP>_HOST__` | `host.docker.internal:<port>`（**无 scheme**） |

替换表由 `tasks/urlmap.py` 从 `configs/apps.json` 推导（去掉 `_mock` 后缀再大写），
31/31 全命中。两道质量门禁：替换后仍残留 `__CUA_GYM_*__` 的、脚本未引用本 app 端口的，
都不入库——后者筛掉 5 个上游瑕疵任务（4 个归档里写死了 `172.17.46.46:80xx`，
1 个 google_sheets 是 LibreOffice 本地操作不走 HTTP）。**最终 1062 个可用任务，覆盖 28 个 app**
（`asana_mock` / `discord_mock` / `docusign_mock` 没有 web 任务）。

### 观测与动作（`src/sandbox/osworld_server.py` + `pixel_env.py`）

复用 OSWorld 的 agent server，因为 **cua-gym 的 `Env` 本身就是该 server 的瘦客户端**
（`gym/utils/env.py` 的方法与 server 路由逐一对应），我们只是把底层从 ECS 换成 AGS 沙箱、
传输层从直连 HTTP 换成 envd + curl：

| `gym/utils/env.py` | OSWorld server 路由 |
|---|---|
| `screenshot()` | `GET /screenshot` |
| `execute()` | `POST /setup/execute` |
| `execute_python_command()` | `POST /execute`（argv 形式） |
| `get_accessibility_tree()` | `GET /accessibility` |

不自建 CDP 层还有一个原因：`osworld/mm_agents/` 下 50+ 个 agent 全部按
**「1920x1080 全屏截图 + pyautogui 代码」** prompt，给浏览器 viewport（1280x800）的截图
会让模型坐标判断系统性偏移。契约在模型侧，适配比改它便宜。

对上传副本打两个最小补丁（**`osworld/` 原文件不动**）：`pyatspi` 的模块级 import 包成
`try/except`（装不上整个 server 起不来，而它只被 `/accessibility` 和 `/terminal` 用到）；
`app.run(debug=True)` → `debug=False, use_reloader=False`（debug 会拉起 reloader 子进程，
两个进程监听同端口，`pkill` 容易留孤儿）。

部署与 OSWorld 原版三处差异：不用 systemd（沙箱里跑不了，用 `setsid`+`nohup`）；
`DISPLAY=:1` 而非 `:0`；**必须以默认用户 `user` 跑**，root 会被 chromium 拒
（`Running as root without --no-sandbox is not supported`），只有装系统包那步用 root。

实测 11/11 通过：`/screenshot` 1920x1080 PNG ~550KB、240-400ms，非黑像素 98.6%；
动作单步 ~540-600ms；纯坐标点击+滚动能改变画面。单步 540ms = envd 往返 35ms +
起 python3 子进程 60ms + `import pyautogui` 416ms，后者是 OSWorld 协议固有的
（每动作走 subprocess 重新 import），相对 agent 一次推理可忽略。

### agent 接入（`src/agents/` + `src/runner/episode.py`）

**类比：相机机身 + 卡口 + 镜头 + 转接环。**（只在这里用来帮助理解，代码里统一叫 env / registry / adapter。）

| 类比 | 代码 | 职责 |
|---|---|---|
| 机身 | `PixelSandboxEnv` + `runner/episode.py` | 截图、执行动作、跑交互循环、记日志。不认识任何具体模型 |
| 卡口 | `agents/registry.py` | 统一接口 `predict(instruction, obs) -> (text, actions)` / `reset(logger)`，装载时校验观测能力 |
| 镜头 | `osworld/mm_agents/*` 里的 agent | 提示词、历史、解析——**原样复用，一行不改** |
| 转接环 | `agents/adapters/*.py` | 把各 agent 接到卡口上：注入 base_url、补 HTTP 层缺陷、翻译动作格式 |

换模型 = 换 adapter（`--agent`），机身不动。卡口标准沿用 `mm_agents` 下 36 个 agent 的既有约定，
不是新发明的。动作两种格式机身都接受：`str` 当 pyautogui 代码，`dict` 当 computer_13。

| `--agent` | 包的 agent | 通道 | 坐标 | adapter 做了什么 |
|---|---|---|---|---|
| `qwen-cua`（默认） | `mm_agents.qwen.QwenAgent`（Qwen-CUA 官方） | openai | relative | 关掉每步写 `./draft/` 的调试转储 |
| `qwen3vl` | `mm_agents.qwen3vl_agent.Qwen3VLAgent` | openai | relative | 替换 HTTP 层：直传 base_url、合并 `reasoning_content`、补 temperature、失败抛错、去掉 30s×5 外层重试 |
| `claude-cu` | `mm_agents.anthropic.AnthropicAgent` | anthropic | absolute | 经 `ANTHROPIC_BASE_URL` 注入；tool_use dict 摊平成 pyautogui 串 |
| `gemini-cu` | `mm_agents.gemini_agent.GeminiFCAgent` | google_genai | relative | function call 翻成 pyautogui、0-999 换算像素；重试 500→4 |
| `raw-vlm` | 自写 `ScreenshotAgent`（提示词与解析从 `mm_agents` import） | openai | 未声明 | 自发请求，因为 `PromptAgent` 只认 `gpt*` 走 OpenAI 且 URL 带 `/v1`（ichat 404） |

`qwen-cua` 与 `qwen3vl` 是同一家两代 scaffold，tool_call 格式不同（XML vs JSON），不能共用一个 adapter。

qwen3.x 会先输出思维链（`reasoning_content`）再给 `content`，`max_tokens` 给小了
`content` 会是空的；各 adapter 默认 `max_tokens=16384`，`raw-vlm` / `qwen3vl` 遇空 content 翻倍重试。

---

## 5. 约束与已确认事实

### 并发配额（AGS 账号单地域）

| 配额项 | 限制 | 含义 |
|---|---|---|
| 沙箱实例数 | 50 | 池中总数上限 |
| CPU 总和 | 50C | 50C / 4C每实例 = 最多 12 并发 |
| 内存总和 | 100Gi | 100Gi / 8Gi每实例 = 最多 12 并发 |
| 暂停实例数 | 20 | — |

有效并发上限 **12 个实例**。

### 模板没暴露任何沙箱端口

`5000 / 9222 / 8000 / 8018 / 5900 / 6080` 全部 HTTP 500
（`The requested sandbox endpoint is not configured`），只有 envd（49983）可达。
鉴权是通的（带 `X-Access-Token` 能把 401 变 500），卡的是端口没开；
`SandboxNetworkOpts(allow_public_traffic=True, https_ports=[9222])` 也无效——
端口暴露是**模板级固定**的。这条约束只限制入向，出向（沙箱访问开发机）实测通畅：
`21.6.127.153:18099` HTTP 200 / 3.7ms，改 hosts 后 4.5ms。

### a11y 树不可用

`python3-pyatspi` 装得上，但它依赖的 `_gi` 是为 **Python 3.13** 编译的 C 扩展，
沙箱 `python3` 是 **3.12**，`import pyatspi` 直接 `ImportError`。要修得重做模板。
因此 `observation_type` 只能用 `screenshot`，`a11y_tree` / `screenshot_a11y_tree` /
`som`（依赖 a11y 画框）均不可用。

### 资源实测

| 项 | 值 |
|---|---|
| 31 个 vite preview 内存合计 | 1.68GB（单个均值 18MB） |
| 开发机可用内存 / 磁盘 | 8GB / 70GB |

扩展到更多网页时，磁盘（build 产物）会先于内存成为瓶颈。

### 数据口径

`tasks.parquet` 共 10910 行：`desktop` 8029 / `web` 1075 / `cross_app` 430。
落在 31 个 app 内的 web 任务 1067 个，扣掉 5 个上游瑕疵，**实际可用 1062 个**。
（1505 = 1075 + 430 是 web + cross_app 的合集口径；本次只做 web。）

### 环境变量

| 变量 | 用途 |
|---|---|
| `E2B_API_KEY` / `E2B_DOMAIN` | AGS 沙箱 |
| `ICHAT_API_KEY` / `ICHAT_BASE_URL` | 模型 API，定义在 `~/.bashrc`，由 `env.sh` 加载 |
| `CUA_APP_HOST` | 覆盖自动探测的开发机 IP（可选） |

---

## 6. 依赖

```
zstandard          # 解 cua_gym_tasks_v1.tar.zst
e2b==2.51.0
```

`pandas` / `pyarrow` 不需要（任务筛选直接读 `task.json`）；`playwright` 不需要
（浏览器操作由沙箱内的 pyautogui 完成）。

沙箱内由 `osworld_server.ensure_server()` 自动安装：`flask` `pyautogui` `python-xlib`
`pillow` `lxml` `numpy` + apt 的 `gnome-screenshot` `xdotool`。
开发机侧需要 node（v22.23.2）、npm（10.9.8）、tmux。

---

## 7. 进度

| 阶段 | 内容 | 状态 |
|---|---|---|
| M0 | `sandbox/pool.py`：创建/连接/回收 + registry 落盘 | ✅ |
| M1 | OSWorld server 进沙箱 + 瘦客户端（全屏观测 + pyautogui 动作） | ✅ 11/11 |
| M2 | 任务解包 / 筛选 / 推送，setup→reward 闭环 | ✅ 1062 个任务 |
| M3 | agent 接入，单任务全链路 | ✅ 闭环跑通 |
| M3.5 | app 搬到开发机 | ✅ |
| M4 | `runner/batch_runner.py`：多实例并行跑全量 | 未开始 |

待办见 [TODO.md](TODO.md)。
