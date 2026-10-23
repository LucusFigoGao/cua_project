# CUA-Gym Web 任务评估

## 架构

每个任务独占一个 AGS 沙箱，任务结束即 kill。app 在沙箱内本地部署，不依赖开发机。

```
开发机                              AGS 沙箱 ×N
  app_bundles/<app>.tar.gz  ──→    /tmp/cua_apps/websites/<app>/   vite preview :80XX
  src/cli/batch_run.py      ──envd→ OSWorld server :5000
                                    chromium + Xvfb :1 (CDP 9222)
                                    /etc/hosts: 127.0.0.1 host.docker.internal
                                    任务脚本在沙箱内跑
```

任务脚本硬编码的 `http://host.docker.internal:80XX` 通过 `/etc/hosts → 127.0.0.1` 落到沙箱本地的 vite preview。

---

## 目录结构

```
workspace/
├── configs/
│   ├── apps.json              31 个 app → 固定端口（事实来源）
│   └── sandbox_pool.json      池 registry（运行期状态，gitignore）
├── app_bundles/               app dist tarball（本地将app打包为tar.gz）
├── tasks_data/                解包产物 1062 个任务
├── results/                   轨迹 + 截图（gitignore）
└── src/
    ├── settings.py            路径 / 模板 / 端口等共享常量
    ├── cli/
    │   ├── pack_app_bundles.py  打包 app dist → app_bundles/
    │   ├── unpack_tasks.py      归档 → tasks_data/（一次性）
    │   ├── run_task.py          单任务闭环
    │   ├── batch_run.py         批量并发跑任务
    │   ├── manage_pool.py       池运维
    │   ├── push_tasks.py        调试用：手动推任务到沙箱
    │   └── serve_apps.py        旧模式：开发机起 app（已弃用）
    ├── sandbox/
    │   ├── app_deploy.py      沙箱内部署 app：上传 bundle + npm ci + vite preview
    │   ├── pool.py            SandboxPool：实例获取 / 归还 / kill / reconcile
    │   ├── osworld_server.py  把 OSWorld agent server 装进沙箱
    │   ├── pixel_env.py       瘦客户端：全屏观测 + pyautogui 动作
    │   ├── apps_host.py       旧模式：开发机侧 app 管理
    │   └── deploy.py          旧模式：写 hosts 映射到开发机
    ├── tasks/
    │   ├── catalog.py         读 tasks_data/，支持筛选 / 取样；TaskSpec.apps 记录多 app 依赖
    │   ├── push.py            tar 上传 + google-chrome shim + 单任务推送
    │   └── urlmap.py          占位符替换表（从 apps.json 推导）
    ├── agents/
    │   ├── registry.py        统一接口 + 注册表 + 装载校验
    │   └── adapters/          qwen_cua / qwen3vl / claude_cu / gemini_cu / raw_vlm
    └── runner/
        ├── episode.py         episode 循环：观测 → predict → 执行
        ├── task.py            run_one()：单任务完整生命周期
        └── batch_runner.py    多线程批跑引擎
```

---

## 启动

```bash
cd workspace
```

确保环境变量 `ICHAT_API_KEY` / `ICHAT_BASE_URL` / `E2B_API_KEY` 已设置。

### 一次性准备

```bash
# 解包任务（1062 个任务 → tasks_data/）
python -m src.cli.unpack_tasks

# 打包 app dist bundle（需要 CUA_HUB_DIR/websites/ 已 build，默认 /data/workspace/cua_hub）
python -m src.cli.pack_app_bundles          # 全部
python -m src.cli.pack_app_bundles --force  # 强制重打
```

> 新增 app 时：在 `configs/apps.json` 加一条 `{app, port}`，把源码放进 `CUA_HUB_DIR/websites/<app>/`，再跑 `pack_app_bundles`。

### 跑任务

```bash
# 单任务（调试用）
python -m src.cli.run_task --list-tasks
python -m src.cli.run_task --task <id> --agent qwen-cua --max-steps 15

# 批跑（默认kill-per-task 模式）
python -m src.cli.batch_run --agent qwen-cua --workers 4 --sample-per-app 3
python -m src.cli.batch_run --agent qwen-cua --workers 20 --sample-per-app 1 --max-steps 10

# 常用选项
--exclude-app monday_mock,discord_mock   # 排除指定 app
--resume                                 # 跳过已有 result.json 的任务
--no-kill-per-task                       # 关闭 kill-per-task，改为复用沙箱（旧模式）
--app-bundles /path/to/bundles           # 指定 bundle 目录（默认 workspace/app_bundles）
```

### 池运维

```bash
python -m src.cli.manage_pool --status                  # 查看实例状态
python -m src.cli.manage_pool --release-all             # 释放全部实例（内存记录状态从busy改回idle）
python -m src.cli.manage_pool --kill-all --yes          # 停止全部实例
```

---

## 关键约束

- **端口暴露**：模板未暴露任何沙箱端口，只有 envd（49983）可达；沙箱出向访问开发机正常
- **a11y 树不可用**：沙箱 Python 3.12 与 `pyatspi` 的 `_gi` C 扩展（为 3.13 编译）不兼容，`observation_type` 只能用 `screenshot`
- **已知 reward 解析缺失**：`twitter_mock` 的 reward 输出格式暂未覆盖（返回 `None`）

---

## 依赖

```
zstandard    # 解 cua_gym_tasks_v1.tar.zst
e2b==2.51.0
```

沙箱内由 `osworld_server.ensure_server()` 自动安装：`flask pyautogui python-xlib pillow lxml numpy` + apt 的 `gnome-screenshot xdotool`。

开发机侧需要 node（v20+）、npm、tmux（仅旧模式 serve_apps 需要）。
