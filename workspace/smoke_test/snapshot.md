# Snapshot 固化验证方案

## 背景 / 目的

当前问题：`sdt-2nn0tz4x` 模板没有预制镜像，每个新沙箱实例都要现场 `git clone` CUA-Gym-Hub 仓库 + 对 31 个 mock app 跑 `npm install` + `npm run build`，依赖 GitHub/HuggingFace 的网络下载，耗时且不稳定。之前尝试过 `e2b template build`（Dockerfile 构建自定义镜像）这条路不可行。

`e2b` SDK 里另有一组独立于 template build 的 **snapshot API**（`Sandbox.create_snapshot` / `list_snapshots` / `delete_snapshot`），可以从一个**正在运行的沙箱**现场打快照，文档明确写"snapshot 持久化，不随沙箱销毁而消失"，且可以用 `Sandbox.create(template=snapshot_id)` 从快照直接新建沙箱。本方案验证：这条路是否能把"clone+install+build+部署 31 个 app"这个耗时流程**固化成一次性操作**，之后所有新实例都从快照秒级启动，不再依赖 GitHub/HuggingFace。

需要验证的具体问题：
1. `create_snapshot()` 能否成功执行，返回的 `snapshot_id` 是否可用。
2. 从 `snapshot_id` 新建的沙箱，文件系统状态（clone 下来的仓库、`node_modules`、`dist`）是否原样保留。
3. 更关键的——31 个 `vite preview` 进程（以及它们监听的 tmux session）是否也保留在"运行中"状态，还是快照只保留文件系统、进程需要重新拉起。
4. 从快照新建一个实例，到 31 个端口全部可访问，总耗时是多少（对比从裸模板 clone+build 的耗时）。
5. 快照是否跨 session 持久——这次验证做完、沙箱全部 kill 掉之后，快照是否还能在下一次会话里继续使用（即不依赖本次进程里的任何本地状态）。

---

## 前置准备

- 复用 `workspace/sandbox/pool.py` 里已验证的 `Sandbox.create` / `pause` / `connect` 调用方式，不新增依赖。
- 需要把 `gym/hub/deploy-all.sh` 改一个**31-app 白名单过滤版**（先只在本地改，不动原脚本）：
  - 白名单来源：`gym/bench/url_variables.json` 里的 31 个 app 名（asana, discord, docusign, facebook, github, gitlab, gmail, google_calendar, google_docs, google_drive, google_sheets, hubspot, instacart, instagram, jira, linkedin, microsoft_teams, monday, notion, outlook_web, pinterest, postman, reddit, salesforce, shopify_admin, slack, stripe_dashboard, trello, twitter, uber_eats, wechat），按字母顺序排列正好对应端口 8000–8030。
  - 过滤方式：把原脚本里 `MOCKS=($(find "$WEBSITES_DIR" ... -name '*_mock' ...))` 替换成显式的白名单数组，而不是 `find` 全部 99 个目录。
- CUA-Gym-Hub 仓库的获取方式待确认（git clone 的实际 URL / HuggingFace repo id），需要在动手前先核实一次能否在沙箱里直接访问。

---

## 步骤

### 1. 新建"建材"实例并引导部署

```python
sbx = Sandbox.create(template="sdt-2nn0tz4x", timeout=1800, metadata={"pool": "snapshot_test", "stage": "bootstrap"})
```

- 耗时较长（预计 clone 30-60s + 31 个 app 的 npm install + build 数分钟），timeout 设宽裕一点（建议 1800s）。
- 在沙箱内执行：
  1. `git clone <CUA-Gym-Hub 仓库地址>`（具体地址待确认）
  2. 拷贝/生成 31-app 白名单版 `deploy-all.sh`
  3. 执行 `./deploy-all.sh --no-attach`（装依赖 + build + tmux 启动 31 个 `vite preview`）
- 记录：clone 耗时、install+build 总耗时、31 个端口是否全部 `curl` 返回 200（用 `sbx.get_host(port)` 一个个探测，或者直接在沙箱内部 `curl 127.0.0.1:800X`）。

### 2. 打快照

```python
snapshot_info = sbx.create_snapshot(name="cua-gym-hub-31apps-v1")
snapshot_id = snapshot_info.snapshot_id  # 具体字段名以实际返回对象为准，先 print(snapshot_info) 确认
```

- 记录打快照本身的耗时（文档说"打快照时沙箱会被 pause"，预期和单纯 `pause()` 耗时量级相近）。
- 打完快照后，**不要 kill 这个建材实例**，先继续用它验证 fork（可选，见步骤 5），最后统一在 `finally` 里清理。

### 3. 从快照新建一个全新沙箱，验证冷启动效果

```python
sbx2 = Sandbox.connect(..)  # 不对，应为
sbx2 = Sandbox.create(template=snapshot_id, timeout=300, metadata={"pool": "snapshot_test", "stage": "from_snapshot"})
```

验证清单：
- [ ] 创建耗时（预期应该接近普通 `Sandbox.create` 的耗时量级，远小于 clone+build）
- [ ] 文件系统：`ls` 检查 clone 下来的仓库目录、各 app 的 `node_modules`、`dist` 是否都在
- [ ] 进程状态：`ps aux | grep vite` 看 31 个 `vite preview` 进程是不是**已经在跑**（无需任何额外命令）
- [ ] tmux session 是否还在（`tmux list-sessions`）
- [ ] 31 个端口是否可以直接 `curl 127.0.0.1:800X/go` 拿到 200 + 合法 JSON（不需要手动重启任何东西）
- 如果进程/tmux 没保留、只有文件系统保留：记录下来，退化方案是"快照里再加一条 `@reboot`/启动脚本，新建后自动跑 `tmux new-session ... deploy-all.sh --skip-install --skip-build`"，仍然省掉 clone+install+build，只是不是"零操作冷启动"。

### 4. 跨 session 持久性验证

- 执行 `sbx.kill()` 把步骤 1 的建材实例彻底销毁。
- 用 `Sandbox.list_snapshots()`（或 `Sandbox.create(template=snapshot_id)` 直接再试一次）确认快照本身独立于沙箱实例存在，销毁原实例不影响快照可用性。
- 如果条件允许，建议特别在**下一次对话 session**里再跑一次"从 snapshot_id 新建沙箱"确认完全脱离本次进程状态（因为 snapshot_id 本身应该是 API 侧持久化的字符串，不依赖本地任何文件）。

### 5.（可选）对比 `fork()`

- 在步骤 2 打快照之前，先用建材实例试一次 `sbx.fork(count=2)`，看是否能现场复制出两个马上可用的沙箱，对比 `create_snapshot` 路线的耗时和恢复完整度差异。
- 这一步主要是信息收集，不是必须项——目的是搞清楚 `fork` 和 `create_snapshot` 该用在什么场景（`fork` 更适合"运行中扩容"，`create_snapshot` 更适合"固化成可重复使用的起点"）。

---

## 清理

- `finally` 块里统一 kill 掉本次验证创建的所有沙箱实例（建材实例 + 从快照新建的实例 + fork 出来的实例，如果做了步骤 5）。
- **快照本身不删除**——如果验证通过，这个快照就是后续 `SandboxPool` 要长期复用的资产，只有验证失败/要重新制作时才调 `delete_snapshot(snapshot_id)` 清理掉旧快照。
- 把最终确认有效的 `snapshot_id` 记录下来（存到 memory 或者写进 `workspace/configs/pool_config.json`），后续 `pool.py` 的 `template` 参数直接替换成这个值。

---

## 待确认 / 风险点

1. **CUA-Gym-Hub 仓库获取地址**：之前 README 提到"从 git/HuggingFace clone"，需要先确认具体仓库 URL，以及沙箱出网能否正常访问 GitHub/HuggingFace（如果访问慢或被限速，这正是要靠本次验证的快照方案绕开的问题，但第一次建材实例仍然要能拉下来）。
2. **配额占用**：本次验证至少会同时起 2-3 个沙箱实例（建材 + 快照新建，可能再加 fork 测试），相对 12 个并发上限不大，但仍是真实配额消耗，且耗时较长（clone+build 阶段可能到几分钟到十几分钟）。
3. **快照创建/存储是否有额外计费或容量限制**：目前没有查到 AGS 侧对 snapshot 数量/大小的配额文档，建议打完快照后用 `list_snapshots()` 顺手确认一下返回里有没有相关限额信息。
4. **进程保留的不确定性**：这是本方案最大的未知数，步骤 3 的验证清单就是专门为了把这一点钉死。如果进程没保留，方案依然成立（省掉 clone+install+build），只是需要在快照里补一条自启动脚本。
