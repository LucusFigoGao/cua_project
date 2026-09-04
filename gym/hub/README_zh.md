# CUA-Gym-Hub（中文说明）

> 本文档是 [README.md](README.md) 的中文导读，内容以英文原文为准，此处仅作梳理与简介。

CUA-Gym-Hub 是一套包含 **98 个自包含 mock Web 应用**的环境套件，作为计算机使用智能体（Computer-Use Agent, CUA）的**强化学习训练环境**而构建，并以子模块形式包含在 [CUA-Gym](https://github.com/xlang-ai/CUA-Gym) 中。

每个 mock 都是一个生产级质量的 React 单页应用（SPA），忠实复刻真实商业产品的 UI 和交互行为——但**没有登录鉴权、没有网络请求、没有外部依赖**。所有状态都保存在本地、可检查、可通过统一的 HTTP API 重置，因此每个 mock 都是一个确定性、可复现的 agent 训练沙盒。

> **仅供研究使用。** 所有第三方产品名称、标识和商业外观仍归各自所有者所有。mock 界面中显示的是刻意修改过的品牌名（如 "Xmail" 而非 "Gmail"），详见 [TRADEMARKS.md](TRADEMARKS.md)。

---

## 一、目录结构

```
CUA-Gym-Hub/
├── websites/                      # 98 个 mock 应用（每个是独立的 Vite 项目）
│   ├── gmail_mock/
│   ├── notion_mock/
│   ├── slack_mock/
│   └── ...                        # 共 98 个，命名均为 <app>_mock
├── shared/
│   └── secureMockApiPlugin.mjs    # UDA 加固会话模式的共享插件
├── deploy-all.sh                  # 一键部署全部 98 个 mock 的脚本（tmux）
├── DEPLOY.md                      # 部署文档：端口分配、反向代理、OSWorld 集成
├── SANDBOX_COMPLETENESS_GUIDE.md  # mock 沙盒的完备性/验收标准指南
├── TRADEMARKS.md / NOTICE         # 商标与法律声明
├── figures/                       # README 配图
├── icons/                         # 各应用图标素材
└── .claude/                       # 用于"开发新 mock"的多 agent 流水线（非运行期组件）
    ├── agents/                    # orchestrator / plan / dev / audit / playwright
    ├── commands/
    └── skills/
```

**单个 mock 内部结构**（所有应用遵循同一模板）：

```
websites/<app>_mock/
├── src/
│   ├── App.jsx                    # React Router 路由，导航时保留 ?sid= 参数
│   ├── context/AppContext.jsx     # 全局状态（Context / Redux / Zustand）
│   ├── utils/dataManager.js       # 会话初始化、localStorage、与服务端状态同步
│   ├── utils/stateTracker.js      # 为 /go 端点计算扁平化状态 diff
│   ├── components/                # 可复用 UI 组件
│   └── pages/                     # 路由级页面组件
├── vite.config.js                 # Vite 配置 + 状态 API 中间件插件
├── package.json
├── SCHEMA.md                      # 状态 schema + "可观察状态变化"对照表
└── index.html
```

**技术栈**：React 18 · React Router 6 · Vite 5 · 基于文件的服务端状态（`.mock-states/`）· 可选的 UDA 加固会话模式。

---

## 二、如何启动

### 1. 运行单个 mock

```bash
cd websites/notion_mock
npm install
npm run dev        # → http://localhost:5173
```

构建后以生产模式预览（会启用 `configurePreviewServer`——构建模式下状态 API 必须靠它注册）：

```bash
npm run build
npm run preview    # → http://localhost:4173
```

### 2. 单机部署全部 98 个 mock

需要 Node.js ≥ 18 和 tmux：

```bash
./deploy-all.sh                            # 安装依赖 + 构建 + 启动全部
./deploy-all.sh --skip-install             # 跳过 npm install
./deploy-all.sh --skip-build --no-attach   # 跳过重新构建，后台运行
```

- 每个 mock 按 `websites/` 下的目录名字典序，从 **8000 端口**开始依次分配端口（8000–8097）；
- 全部跑在一个名为 `cua-gym-hub` 的 tmux 会话中，每个应用一个窗口，均为 `npm run preview --host 0.0.0.0`；
- 运行期状态写入各应用目录下的 `.mock-states/`，上传文件写入 `.mock-files/`（均被 git 忽略，可直接删除以重置）。

### 3. 反向代理（共享/生产部署）

在 tmux 管理的 preview 服务前放置反向代理，为每个 mock 映射独立域名或路径，然后在 CUA-Gym 数据集的端点变量中使用这些 URL：

```bash
CUA_GYM_GMAIL_URL=https://your-gmail-mock.example.com
CUA_GYM_SLACK_URL=https://your-slack-mock.example.com
CUA_GYM_NOTION_URL=https://your-notion-mock.example.com
```

> 不要依赖官方 `xlang.ai` 托管端点做大规模训练或评测。

### 4. Agent 回合的典型用法（配合 CUA-Gym 任务包）

```bash
# ① episode 开始前：注入任务初始状态
curl -X POST "http://localhost:5173/post?sid=task_042" \
  -H "Content-Type: application/json" \
  -d '{"action":"set","state":{...任务的初始状态...}}'

# ② agent 在浏览器中打开 /?sid=task_042 并进行 GUI 操作

# ③ episode 结束后：检查状态变化（reward 函数消费 state_diff）
curl "http://localhost:5173/go?sid=task_042"
# → {"initial_state":{...}, "current_state":{...}, "state_diff":{...}}

# ④ 为下一个 episode 重置
curl -X POST "http://localhost:5173/post?sid=task_042" -d '{"action":"reset"}'
```

---

## 三、技术细节简介

### 3.1 为什么能当训练环境用：两个关键设计

1. **状态注入（State injection）**：任务创建时，合成流水线会把 JSON 初始状态连同 `reward.py` 一起 POST 给 mock。浏览器加载 `?sid=<task_id>` 后就会渲染出那个精确的"世界"（邮件、项目看板、日历、工单……）。**同一个 mock 无需改代码就能承载任意多个不同的任务世界**——这就是一个 `gmail_mock` 能服务几十个分诊/搜索/起草/跨应用任务的原因。

2. **会话隔离（Session isolation）**：每个 URL 自带独立的会话 id（`sid`）。状态文件、上传、重置全部按 `.mock-states/<sid>.json` 命名空间隔离。**多个并行 RL worker 在同一个 mock 上训练时互不可见对方的修改**——这对数百个 episode 并发打同一个 mock 后端的分布式 rollout 至关重要。每个 episode 只需一个 `POST` 即可干净重置。

### 3.2 统一状态 API

每个 mock 暴露相同的 HTTP API。在开发模式（`npm run dev`）和生产预览（`npm run preview`）下，端点都由 `vite.config.js` 中的 Vite 插件注册：

| 端点 | 方法 | 请求体 / 响应 |
|------|------|----------------|
| `/post?sid=<sid>` | POST | `{"action":"set","state":{...}}` —— 同时设置初始状态和当前状态 |
| `/post?sid=<sid>` | POST | `{"action":"set_current","state":{...}}` —— 只更新当前状态，保留初始状态 |
| `/post?sid=<sid>` | POST | `{"action":"reset"}` —— 将当前状态恢复为初始状态 |
| `/go?sid=<sid>` | GET | 返回 `{initial_state, current_state, state_diff}` |
| `/state?sid=<sid>` | GET | 返回 `{stored_state, has_custom_state, sid}` |
| `/upload?sid=<sid>` | POST | multipart/form-data → `{files:[{url, original_name, stored_name, size}]}` |
| `/files/<sid>/<filename>` | GET | 以正确的 Content-Type 返回已上传文件 |

要点：

- **会话隔离**：`sid` 会被清洗（只保留字母数字下划线横线），用作 `.mock-states/<sid>.json` 的文件名。不带 `sid` 时使用共享的默认状态。**每个训练 episode 应使用唯一 `sid`**（如任务 ID），避免 episode 之间互相污染。
- **状态 diff**：服务端在每次 `/go` 调用时计算的扁平键路径对象。RL reward 函数用它来检测任务是否完成（例如"发送消息"任务后，`messages[C001]` 是否新增了一条）。
- 每个 mock 的 **`SCHEMA.md`** 记录完整的状态 schema 和**"可观察状态变化"对照表**（用户动作 → 受影响的状态字段），是编写 reward 函数的首要参考。

### 3.3 UDA 加固模式（Hardened Mode）

默认的 CUA-Gym 状态 API 是刻意完全可检查的（适合纯 computer-use 训练）。但当 benchmark 同时给 agent **shell 和浏览器**两种访问权限时，agent 可能绕过 GUI 直接读状态文件作弊。此时启用混合加固模式，让新的 harness 流量使用服务端私有状态，同时保持旧流量向后兼容：

```bash
export CUA_GYM_HARDENED=1
export CUA_GYM_ADMIN_TOKEN="$(openssl rand -hex 32)"
npm run preview        # 或 ./deploy-all.sh --skip-install --no-attach
```

加固模式要点：

- 每个 mock 在旧版 API 中间件之前先加载 `shared/secureMockApiPlugin.mjs`；带 admin token、有效 HttpOnly 会话或 `sid=__cua_session__` 占位符的请求走加固路径，其余请求落回旧的 `/post`、`/state`、`/go` 处理器；
- 加固模式下 `/post` 的 `set`/`reset` 必须带 `X-CUA-Admin-Token` 或 `Authorization: Bearer`；
- admin `set` 成功后返回一次性 `launch_url`（如 `/_cua_session?token=...`）。浏览器应打开这个 `launch_url` 而不是 `/?sid=<真实sid>`——一次性 token 会换成 HttpOnly cookie 并跳转到 `/?sid=__cua_session__`，真实 `sid` 不会出现在 URL 或浏览器进程参数里；
- 加固的 `/go` 读取同样需要 admin token；
- 页面级 localStorage shim 只作用于加固会话，把大状态对象留在内存而不写入 Chrome profile，防止 CLI agent 从 Chrome LevelDB 文件中提取完整任务状态。

设置 `CUA_GYM_HARDENED=0` 或不设置，即使用旧版完全可检查的 API。

### 3.4 Mock 质量标准

每个 mock 都要达到以下标准（完整判据见 [SANDBOX_COMPLETENESS_GUIDE.md](SANDBOX_COMPLETENESS_GUIDE.md)）：

- **没有死控件**：每个可见的按钮、菜单、控件都必须有连贯的行为。CUA 会点遍所有东西，占位行为会破坏训练。
- **状态可检查**：所有用户可见的修改都持久化到本地状态，并通过 `/go?sid=...` 以 `{initial_state, current_state, state_diff}` 暴露，供 RL reward 函数消费。
- **文件交互是一等公民**：上传、下载、导入、导出、附件流程用真实浏览器 File API 实现，不是 stub。
- **无外部调用**：协作功能（分享对话框、通知、版本历史）用本地模拟实现，运行时从不访问网络。

### 3.5 Mock 应用一览（98 个）

| 类别 | 应用 |
|------|------|
| 通信与社交（18） | `discord` · `dingtalk` · `facebook` · `feishu` · `gmail` · `instagram` · `linkedin` · `microsoft_teams` · `outlook_web` · `pinterest` · `reddit` · `slack` · `twitter` · `wechat` · `weibo` · `xiaohongshu` · `zhihu` · `zoom_web` |
| 生产力与文档（16+） | `airtable` · `asana` · `canva` · `canvas` · `Canvas-LMS` · `confluence` · `google_calendar` · `google_docs` · `google_drive` · `google_sheets` · `jira` · `lattice` · `linear` · `lucidchart` · `miro` · `monday` · `notion` · `openreview` · `trello` |
| 开发与云（12） | `aliyun` · `aws_console` · `azure` · `circleci` · `cloudflare` · `datadog` · `github` · `gitlab` · `postman` · `sentry` · `vercel` · `wandb` |
| 电商与旅行（11） | `amazon` · `amazon_seller` · `booking_com` · `ebay` · `expedia` · `instacart` · `shopify_admin` · `taobao_seller` · `tripadvisor` · `uber_eats` · `woocommerce` |
| 金融与企业（20） | `adp` · `bamboohr` · `clio` · `coinbase` · `contractbook` · `docusign` · `Expensify` · `greenhouse` · `gusto` · `hubspot` · `hubspot_marketing` · `paypal` · `quickbooks` · `robinhood` · `salesforce` · `SAP` · `ServiceNow` · `stripe_dashboard` · `TradingView` · `workday` |
| 分析与营销（10） | `amplitude` · `google_ads` · `google_analytics` · `hotjar` · `klaviyo` · `looker_studio` · `mailchimp` · `meta_ads` · `mixpanel` · `tableau` |
| 其他（9） | `12306` · `epic-health` · `google_flights` · `PACS-viewer` · `westlaw` · `youtube` · `Zendesk` · `zillow` 等 |

### 3.6 多 agent 开发流水线（用于造新 mock）

每个 mock 都是用 `.claude/agents/` 中定义的 Claude Code agent 团队协作构建的：

| Agent | 职责 |
|-------|------|
| `orchestrator` | 驱动开发循环，协调其他所有 agent，自己不写代码 |
| `plan` | 网络调研 + 截图分析 → 产出 `TODO.md`、`DESIGN.md`、`assets/` |
| `dev` | 实现全部源代码，解决 `AUDIT.md` 和 `TEST.md` 中的问题 |
| `audit` | 检测死处理器、未跟踪的状态、缺失的 `/go` 覆盖；编写 `SCHEMA.md` |
| `playwright` | 用浏览器测试每条路由上的每个可交互元素，产出 `TEST.md` 缺陷报告 |

orchestrator 最多跑 10 轮 `dev → audit → playwright`，直到同时满足：`TODO.md` 所有 P0/P1 项完成、`AUDIT.md` 无 P0 问题、`TEST.md` 无 P0/P1 缺陷、`SCHEMA.md` 记录全部可观察状态变化、`npm run build` 通过。

要用同一套流水线构建新 mock，在本仓库中调用 orchestrator agent：

```
Build a new mock for Figma with full state API support.
```

---

## 四、引用

如果在研究中使用了 CUA-Gym-Hub，请引用 CUA-Gym 论文：

```bibtex
@misc{wang2026cuagymscalingverifiabletraining,
      title={CUA-Gym: Scaling Verifiable Training Environments and Tasks for Computer-Use Agents},
      author={Bowen Wang and Dunjie Lu and Junli Wang and Tianyi Bai and Shixuan Liu and Zhipeng Zhang and Haiquan Wang and Hao Hu and Tianbao Xie and Shuai Bai and Dayiheng Liu and Que Shen and Junyang Lin and Tao Yu},
      year={2026},
      eprint={2605.25624},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2605.25624},
}
```

**许可证**：[Apache 2.0](LICENSE) · CUA-Gym 的一部分。
