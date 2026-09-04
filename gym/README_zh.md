# CUA-Gym（中文说明）

> 本文档是 [README.md](README.md) 的中文导读，内容以英文原文为准，此处仅作梳理与简介。

CUA-Gym 是一个可扩展的流水线，用于为**计算机使用智能体（Computer-Use Agent, CUA）**合成**可验证的强化学习（RLVR）训练数据**。给定一个主题（如"LibreOffice Calc 格式化操作"），它会联合产出**任务指令、环境状态、奖励函数**三元组，并对三者进行验证——用编码智能体（coding agent）承担过去需要人类专家完成的工程工作。

相关资源：[📄 论文](https://arxiv.org/abs/2605.25624) · [🤗 数据集](https://huggingface.co/datasets/xlangai/CUA-Gym) · [🔎 数据查看器](https://huggingface.co/datasets/xlangai/CUA-Gym/viewer/tasks/train) · [🧩 CUA-Gym-Hub](https://github.com/xlang-ai/CUA-Gym-Hub)

---

## 一、目录结构

```
CUA-Gym/
├── scripts/                          # 可执行入口脚本
│   ├── batch_orchestrator.py         # 批量对抗式联合生成循环（核心入口）
│   ├── env_cli.py                    # VM 环境操作 CLI（子智能体用，见下文）
│   └── materialize_dataset_urls.py   # 将数据集中的端点占位符替换为你的部署地址
├── utils/                            # 公共工具库
│   ├── env.py                        # VM 生命周期与操作封装（阿里云 ECS / SSH 隧道）
│   ├── llm_utils.py                  # LLM 调用工具
│   ├── logger.py                     # 日志
│   └── reward_judge.py               # 锁定的 LLM judge 助手（部署到 VM 供 reward.py 使用）
├── filter/                           # 任务过滤器
│   ├── majority_vote_filter.py       # LLM 多数投票过滤（主过滤器）
│   ├── critic_prompt.py              # 评审 prompt
│   ├── run_critic_benchmark.py       # 评审基准测试
│   ├── benchmark_tasks.json          # 基准任务
│   └── taxonomy.yaml                 # 任务分类法
├── hub/                              # CUA-Gym-Hub 子模块挂载点（94 个 mock 网站）
├── figures/                          # README 配图
├── .claude/                          # Claude Code 智能体与技能定义
│   ├── agents/                       # task-gen / orchestrator / setup-gen / reward-gen
│   ├── commands/
│   └── skills/                       # 17 个环境操作技能（见下文）
├── pyproject.toml                    # Python 包定义与依赖
├── vm_requirements.txt               # VM 内需要安装的 Python 包清单
├── .env.example                      # 环境变量模板（LLM API + 阿里云 + OSWorld）
├── CONTRIBUTING.md / LICENSE
└── README.md
```

`.claude/agents/` 中的四个智能体是流水线的核心角色：

| 智能体 | 职责 |
|--------|------|
| `task-gen` | 根据主题生成任务指令集合（输出 `output/task_generation/<topic>.json`） |
| `orchestrator` | 编排器：准备环境、为每个任务创建两台隔离 VM、驱动下面的对抗循环、收集最终产物 |
| `setup-gen`（Generator） | 编写并执行 `initial_setup.py`（初始环境）和 `golden_patch.py`（目标状态） |
| `reward-gen`（Discriminator） | 仅凭任务描述编写 `reward.py`，并在 VM 上验证 |

`.claude/skills/` 中的 17 个技能供 setup-gen / reward-gen 操作各类应用环境：`blender`、`chrome`、`drawio`、`excalidraw`、`gimp`、`grafana`、`libreoffice-calc`、`libreoffice-impress`、`libreoffice-writer`、`mock_websites`（即 CUA-Gym-Hub 的 mock 网站）、`openshot`、`os`、`overleaf`、`pdf`、`penpot`、`vlc`、`vs-code`。

---

## 二、安装与使用

### 1. 安装

```bash
git clone https://github.com/xlang-ai/CUA-Gym
cd CUA-Gym
pip install -e ".[dev]"
cp .env.example .env   # 填入 OPENAI_API_KEY 和 ALIYUN_* 凭据
```

`.env` 需要配置三组变量：

- **LLM API**：`OPENAI_API_KEY`（必需，任务生成与过滤用），可选 `OPENAI_BASE_URL`、`ANTHROPIC_API_KEY`；
- **阿里云 ECS**：`ALIYUN_ACCESS_KEY_ID`、`ALIYUN_ACCESS_KEY_SECRET`、`ALIYUN_REGION`、`ALIYUN_IMAGE_ID`、`ALIYUN_INSTANCE_TYPE`、`ALIYUN_VSWITCH_ID`、`ALIYUN_SECURITY_GROUP_ID` 等（创建/销毁运行任务的 VM 用）；
- **OSWorld**：`OSWORLD_DIR`（默认 `~/OSWorld-RL`）、`OSWORLD_VENV`（默认 `~/.venvs/osworld-py312`），可选 `SSH_GATEWAY_*`（远程编排模式）。

### 2. 为某个领域生成任务

在 CUA-Gym 目录下的 Claude Code 中调用 `task-gen` 智能体：

```
Generate 50 LibreOffice Calc tasks covering formatting and formula operations.
```

输出：`output/task_generation/<topic>.json`

### 3. 运行对抗式联合生成循环（核心步骤）

```bash
python scripts/batch_orchestrator.py output/task_generation/calc_formatting.json
```

验证通过的三元组落在 `output/final/<task_id>/`。常用选项：

```bash
python3 scripts/batch_orchestrator.py -c 5 ...              # 并发数（受 VM 预算限制）
python3 scripts/batch_orchestrator.py --dry-run ...         # 只看会处理哪些任务
python3 scripts/batch_orchestrator.py --retry-failed ...    # 只重试失败的
python3 scripts/batch_orchestrator.py --task-id <id> ...    # 处理单个任务
```

### 4. 运行多数投票过滤

```bash
export OPENAI_API_KEY=sk-...
python filter/majority_vote_filter.py \
  --tasks-dir output/final \
  --votes 3 \
  --model gpt-4o \
  --write
```

### 5. 下载与使用现成数据集

```bash
pip install -U datasets huggingface_hub
huggingface-cli download xlangai/CUA-Gym --repo-type dataset --local-dir data/
```

在 Python 中加载任务索引：

```python
from datasets import load_dataset
tasks = load_dataset("xlangai/CUA-Gym", "tasks", split="train")
example = tasks[0]
print(example["instruction"])
print(example["app_type"], example["platform"], example["setup_kind"])
```

**执行 web 任务前**，需解包任务包并把端点占位符替换成你自己部署的 CUA-Gym-Hub 地址（数据集中存的是 `__CUA_GYM_GMAIL_URL__` 这类占位符）：

```bash
mkdir -p ./cua_gym_tasks
tar --zstd -xf ./data/artifacts/cua_gym_tasks_v1.tar.zst -C ./cua_gym_tasks

cat > .env.cua-gym <<'EOF'
CUA_GYM_GMAIL_URL=https://your-gmail-mock.example.com
CUA_GYM_SLACK_URL=https://your-slack-mock.example.com
CUA_GYM_NOTION_URL=https://your-notion-mock.example.com
EOF

python scripts/materialize_dataset_urls.py ./cua_gym_tasks \
  --manifest ./data/url_variables.json \
  --env-file .env.cua-gym
```

### 6. VM 操作 CLI（子智能体 / 手动调试用）

`scripts/env_cli.py` 封装了 `utils/env.py`，可直接在命令行操作远程 VM：

```bash
python3 scripts/env_cli.py --config env_config.json <command> [args]
# 命令：execute / run-python / run-bash / upload / download /
#       screenshot / screen-size / launch / dir-tree / create / delete
```

---

## 三、技术细节简介

### 3.1 核心问题与三元组

用强化学习训练 CUA 需要一致的三元组：**（任务指令，可执行环境，可验证奖励）**。人工编写哪怕一个三元组也要花数小时，CUA-Gym 将其自动化、规模化。

### 3.2 流水线：三个协作智能体

每个任务由三个智能体协作完成：

- **Generator（`setup-gen`）**：构造初始与黄金环境状态（`initial_setup.py`、`golden_patch.py`）；
- **Discriminator（`reward-gen`）**：仅凭任务描述编写 `reward.py`，看不到 Generator 的代码（**信息屏障**，防止判别器作弊）；
- **Orchestrator**：驱动两者迭代多轮，直到在执行下同时满足 **`reward(golden) = 1.0`** 且 **`reward(initial) = 0.0`**。

每个任务会创建**两台隔离的 VM**（`initial_env` 与 `golden_env`），状态隔离由环境隔离保证。编排循环的工作目录布局：

```
output/adversarial/<task_id>/      # 主工作目录（task_config、env_config、脚本、REVIEW.md）
output/reward_sandbox/<task_id>/   # reward-gen 的隔离沙盒（看不到 setup-gen 的文件）
output/final/<task_id>/            # 最终验证通过的产物（含 OSWorld 风格 config.json）
```

### 3.3 过滤

验证通过的元组先经过 **LLM 多数投票过滤器**（`filter/majority_vote_filter.py`）：每个任务由评审 LLM 独立打分 N 次（默认 3），多数票决定 `reject` / `modify_query` / `keep`，剔除奖励脆弱、含糊或不一致的任务。之后还有**教师模型 rollout** 的第二级过滤。

### 3.4 环境与数据集规模

- **环境**：共 **110 个**——16 个桌面应用 + 94 个合成的 mock 网站（后者即 [CUA-Gym-Hub](https://github.com/xlang-ai/CUA-Gym-Hub)，挂载在本仓库 `hub/` 目录）。
- **数据集**：[CUA-Gym 数据集](https://huggingface.co/datasets/xlangai/CUA-Gym)含 **32,112** 条验证过的 RLVR 训练元组。

与其他 CUA RLVR 数据集对比：

| 数据集 | 平台 | 数据量 | 环境数 | 奖励 | 开源 |
|--------|------|-------:|-------:|------|:----:|
| GUI-Genesis | 移动端 | 969 | 1 | 程序化 | 否 |
| WebArena-Infinity | Web | 1,260 | 10 | 程序化 | 是 |
| InfiniteWeb | Web | 600 | — | 程序化 | 部分 |
| UltraCUA | 桌面 | 17,000 | 9 | 程序化 | 部分 |
| Gym-Anything | 桌面 | 7,277 | 193 | VLM | 是 |
| **CUA-Gym** | **桌面 + Web** | **32,122** | **110** | **程序化** | **是** |

### 3.5 数据集组织与任务包

数据集围绕一张便于查看的表 + 可执行产物组织：

```
data/
  tasks.parquet                     # 任务索引表（指令、环境元数据、setup/reward 文件引用）
artifacts/
  cua_gym_tasks_v1.tar.zst          # 完整任务包归档
  url_variables.json                # URL 占位符清单
scripts/
  materialize_dataset_urls.py       # 占位符替换脚本
```

每个任务包内容：

```
<task_id>/
  task.json                         # 任务定义
  reward.py                         # 程序化奖励函数
  initial_setup.py | .sh | .xlsx | .docx | .pptx   # 环境初始化脚本/文件
```

**执行一个任务的流程**：解包归档 → 读 `<task_id>/task.json` → 在目标环境中执行其中的 setup 步骤 → 让 agent 与环境交互 → 运行 `<task_id>/reward.py` 计算程序化分数。

> 注意：部分 web 任务的 setup 与 reward 文件依赖 CUA-Gym-Hub 端点。公共数据集以 `__CUA_GYM_GMAIL_URL__` 这类占位符存储端点。请自行部署对应应用，设置 `CUA_GYM_*_URL` 变量并用 `materialize_dataset_urls.py` 物化，不要依赖官方托管的 `xlang.ai` 端点做大规模实验。

### 3.6 VM 执行架构（`utils/env.py`）

任务在**阿里云 ECS 虚拟机**上执行，每台 VM 内运行一个端口 5000 的服务（OSWorld 风格），提供 `/screenshot`（截屏）、`/setup/execute`（执行命令）、`/setup/launch`（启动应用）、`/accessibility`（可访问性树）等接口。`Env` 类封装了创建/删除实例、截屏、执行命令、上传下载文件等操作，支持两种连接模式：

- **默认**：服务器直连（VM 私有 IP，无 SSH）；
- **遗留**：本地 → SSH 网关 → VM 的端口转发隧道。

### 3.7 实验结果

CUA-Gym 通过在桌面和 Web 环境上的可验证 RL 训练提升 CUA。在 OSWorld-Verified 与 WebArena 上的评测（节选）：

| 模型 | OSWorld-Verified | WebArena |
|------|:----------------:|:--------:|
| Claude Sonnet 4.6 | 72.9 | 65.6 |
| Claude Opus 4.7 | 78.0 | — |
| GPT-5.5 | 78.7 | — |
| Qwen3.5-35B-A3B（基座） | 54.0 | 40.8 |
| Qwen3.5-397B-A17B（基座） | 62.2 | 54.0 |
| **CUA-Gym-A3B** | **62.1** | **44.5** |
| **CUA-Gym-A17B** | **72.6** | **56.0** |

两个模型均达到同规模开源 CUA 的最先进水平；CUA-Gym-A3B 以更小约 10 倍的激活参数量追平更大的 A17B 基座。

---

## 四、许可证与引用

- **代码、工具与流水线**：[Apache License 2.0](LICENSE)
- **数据集**：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/versions/4.0/)

如果在研究或公开材料中使用了 CUA-Gym（包括其代码、流水线、数据集、模型、CUA-Gym-Hub 环境等），请引用论文：

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

**禁止事项**（详见英文 README）：不得用于违反法律法规的用途；不得用于非法、不道德、欺骗性、侵犯隐私或有害的活动；不得在未经授权的情况下针对真实第三方服务、账户、凭据或生产系统。
