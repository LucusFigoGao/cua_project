---
license: cc-by-4.0
language:
- en
task_categories:
- reinforcement-learning
- text-generation
pretty_name: CUA-Gym
size_categories:
- 10K<n<100K
tags:
- computer-use-agents
- gui-agents
- desktop-agents
- web-agents
- rlvr
- verifiable-rewards
- programmatic-reward
- synthetic-data
- osworld
- webarena
configs:
- config_name: tasks
  data_files:
  - split: train
    path: data/tasks.parquet
---

# CUA-Gym

CUA-Gym is a collection of verifiable computer-use agent tasks for reinforcement learning with verifiable rewards (RLVR). Each task pairs a natural-language instruction with executable setup artifacts and a Python reward function that checks task completion programmatically. For details, see the paper [CUA-Gym: Scaling Verifiable Training Environments and Tasks for Computer-Use Agents](https://arxiv.org/abs/2605.25624).

This release contains the full public CUA-Gym task set after the necessary data review.

This release follows a two-layer Hugging Face layout:

1. **Parquet metadata tables** under `data/` for fast Dataset Viewer browsing and programmatic filtering.
2. **A compressed artifact archive** under `artifacts/` containing the original executable task bundles.

This keeps the Dataset Viewer focused on one clean task table while avoiding tens of thousands of tiny files in the Hub repository.

## Important Notice: Self-Host Web Endpoints

Some web task setup and reward files require CUA-Gym-Hub mock-application endpoints. The public release stores these endpoints as placeholders such as `__CUA_GYM_GMAIL_URL__`, not as hard-coded hosted URLs.

For reliable use, deploy the corresponding CUA-Gym-Hub apps yourself, set the endpoint variables listed in `url_variables.json`, and materialize the extracted task files before running setup or reward code. The release-hosted `xlang.ai` endpoints are provided only as references and for smoke tests; they should not be used as a dependency for large-scale training or evaluation.

## News

- **2026.6.3:** We release the full public CUA-Gym task set after the required data administrative review.

## Repository Layout

```text
README.md
stats.json
url_variables.json
data/
  tasks.parquet
artifacts/
  cua_gym_tasks_v1.tar.zst
scripts/
  materialize_dataset_urls.py
```

The archive contains one directory per task:

```text
<task_id>/
  task.json
  reward.py
  initial_setup.py | initial_setup.sh | initial_setup.xlsx | initial_setup.docx | initial_setup.pptx
```

## Dataset Viewer

The Dataset Viewer exposes a single `tasks` table for browsing, filtering, sampling, and lightweight analysis.

| Field | Description |
| --- | --- |
| `id` | Stable task identifier. |
| `instruction` | Natural-language task instruction shown to the agent. |
| `app_type` | Application or environment label, such as `libreoffice_calc`, `vscode`, `instagram_mock`, or `multi_apps`. |
| `app_family` | Coarse family inferred from `app_type`: `desktop_office`, `desktop`, `mock_web`, `multi_apps`, or `other`. |
| `platform` | Coarse platform: `desktop`, `web`, or `cross_app` when inferable. |
| `difficulty` | Difficulty label when available. Some tasks are currently unlabeled. |
| `setup_kind` | Setup artifact type, for example `py`, `sh`, `xlsx`, `docx`, or `pptx`. |
| `num_setup_steps` | Number of setup actions in the original task config. |
| `num_setup_files` | Number of setup artifacts referenced by the config. |
| `has_ground_truth` | Whether the original task metadata contains a `ground_truth` field. |
| `archive_path` | Archive file containing the raw task bundle. |
| `archive_member` | Task directory inside the archive. |
| `task_json_member` | `task.json` path inside the archive. |
| `reward_member` | `reward.py` path inside the archive. |
| `setup_file_members` | Setup artifact paths inside the archive. |

## Quick Start

Install the standard Hugging Face dataset tooling:

```bash
pip install datasets huggingface_hub
```

Load the viewer-friendly task table:

```python
from datasets import load_dataset

tasks = load_dataset("xlangai/CUA-Gym", "tasks", split="train")
print(tasks[0]["instruction"])
```

Filter tasks by application or difficulty:

```python
calc_hard = tasks.filter(
    lambda row: row["app_type"] == "libreoffice_calc"
    and row["difficulty"] == "hard"
)
print(len(calc_hard))
```

Inspect app-level coverage from the task table:

```python
from collections import Counter

counts = Counter(tasks["app_type"])
print(counts.most_common(10))
```

## Downloading Raw Task Bundles

The `datasets` library loads metadata. To execute tasks, download the archive, manifest, and helper script into a local directory:

```bash
huggingface-cli download xlangai/CUA-Gym \
  --repo-type dataset \
  --local-dir ./CUA-Gym-data \
  --include "artifacts/cua_gym_tasks_v1.tar.zst" \
            "scripts/materialize_dataset_urls.py" \
            "url_variables.json" \
            "data/tasks.parquet"
```

Extract the archive:

```bash
mkdir -p ./cua_gym_tasks
tar --zstd -xf ./CUA-Gym-data/artifacts/cua_gym_tasks_v1.tar.zst -C ./cua_gym_tasks
```

Then use the `archive_member`, `task_json_member`, and `reward_member` fields from the `tasks` table to locate a task bundle. The exact original execution config is stored inside each extracted `<task_id>/task.json`.

## Materializing Web Endpoint Placeholders

Before executing web tasks, replace endpoint placeholders with your own CUA-Gym-Hub deployment URLs. Generate an env-file template from the manifest, then edit the values to point to your own deployed mock apps:

```bash
python - <<'PY' > .env.cua-gym
import json

variables = json.load(open("./CUA-Gym-data/url_variables.json"))["variables"]
env_values = {}
for spec in variables.values():
    if spec["kind"] != "host":
        env_values[spec["env"]] = spec["default"]
for name, value in sorted(env_values.items()):
    print(f"{name}={value}")
PY
```

Edit `.env.cua-gym`, then materialize the extracted task files:

```bash
python ./CUA-Gym-data/scripts/materialize_dataset_urls.py ./cua_gym_tasks \
  --manifest ./CUA-Gym-data/url_variables.json \
  --env-file .env.cua-gym
```

The script fails fast if any required `CUA_GYM_*` variables are missing. For a short smoke test only, you may pass `--use-hosted-defaults` to restore the release-hosted `xlang.ai` endpoints.

## Executing a Task

Each task follows this high-level pattern:

1. Read `<task_id>/task.json`.
2. Apply its `config` steps to prepare the environment.
3. Give `instruction` to an agent.
4. Run `<task_id>/reward.py` in the final environment to compute the score.

Example skeleton after extraction:

```python
import json
from pathlib import Path

task_dir = Path("cua_gym_tasks") / "0018392e-cfed-5e2f-8278-a4580d64a00a"
task = json.loads((task_dir / "task.json").read_text())

print(task["instruction"])
print(task["config"])
print(task["evaluator"])
```

Important: setup and reward files are executable code. Run them only in isolated VMs, containers, or sandboxes designed for computer-use agent evaluation.

## Dataset Statistics

Current release:

| Metric | Value |
| --- | ---: |
| Tasks | 10,910 |
| Raw task files | 32,730 |
| Uncompressed local artifact size | about 294 MB |
| `app_type` values | 327 |
| Tasks with difficulty labels | 7,365 |
| Tasks without difficulty labels | 3,545 |

Largest app categories in this subset include:

- `libreoffice_calc`
- `libreoffice_writer`
- `libreoffice_impress`
- `multi_apps`
- `vscode`
- `pdf`
- mock web applications such as `instagram_mock`, `hubspot_mock`, `google_docs_mock`, `outlook_web_mock`, and `google_sheets_mock`

## Intended Use

CUA-Gym is intended for research on:

- computer-use agents and GUI agents
- RLVR and programmatic reward design
- synthetic task generation
- executable desktop and web evaluation
- post-training data filtering and scaling studies

The dataset is not intended as a direct benchmark leaderboard by itself unless users standardize the execution environment, action interface, observation format, and reward invocation protocol.

## Safety and Execution Notes

The artifact archive includes Python and shell scripts that create files, modify local state, open applications, and run reward checks. Treat them as untrusted executable artifacts:

- Run tasks inside disposable virtual machines or containers.
- Do not run setup scripts on a personal workstation.
- Disable access to private files, credentials, cloud tokens, and production services.
- Review scripts before executing them in a new environment.

Some tasks contain synthetic credentials, passwords, API keys, or tokens as part of the task state. These are intended as mock data for evaluation and should not be interpreted as real secrets.

## Known Limitations

- Rewards evaluate final environment state, not the full process by which an agent reached that state.
- Some tasks do not currently include difficulty labels.
- Mock web tasks may omit real-world behaviors such as authentication, network latency, rate limits, third-party integrations, and production error states.
- The dataset includes heterogeneous setup artifacts (`.py`, `.sh`, `.xlsx`, `.docx`, `.pptx`), so downstream runners need application-specific support.

## Citation

If you use CUA-Gym, please cite the paper and dataset:

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

@misc{cua-gym-dataset,
      title={CUA-Gym Dataset},
      author={{CUA-Gym Team}},
      year={2026},
      howpublished={\url{https://huggingface.co/datasets/xlangai/CUA-Gym}},
}
```

## Contact

For questions, issues, or release updates, please open a discussion on the Hugging Face dataset page or contact the maintainers through the project repository.
