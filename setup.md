# CUA-Gym × AGS 沙箱 全链路验证记录

本文档记录了在腾讯云 Agent Runtime（AGS）All-In-One 沙箱中，验证 CUA-Gym web task 评测闭环的完整过程。每一步都配有实际跑通的代码，可直接复用。

固定使用的沙箱实例：`edvcir3u2sbf3bigeg52ibdvkwkkx7htijlfbshy`（模板 `sdt-2nn0tz4x`）。所有代码均从开发机通过 SDK `Sandbox.connect()` 连接到这个实例执行，**不会 kill 它**。

---

## 0. 通用连接头

后面所有代码块都假设已经执行过这一段：

```python
import os
os.environ.setdefault("NO_PROXY", "*.tencentags.com,*.woa.com,*.tencentyun.com")

import e2b.envd.rpc as _rpc
_rpc.default_username = "root"

from e2b import Sandbox

sbx = Sandbox.connect("edvcir3u2sbf3bigeg52ibdvkwkkx7htijlfbshy")
print("已连接实例:", sbx.sandbox_id)
sbx.set_timeout(86400)  # 续期，避免中途超时被回收
```

---

## 1. 沙箱资源规格确认

**目的**：确认这个沙箱工具（AIO 类型）实际分配的 CPU/内存/磁盘，作为后续资源预估的依据。

```python
r = sbx.commands.run("nproc")
print("CPU核数:", r.stdout)

r = sbx.commands.run("free -h")
print(r.stdout)

r = sbx.commands.run("df -h /")
print(r.stdout)

r = sbx.commands.run("cat /proc/cpuinfo | grep 'model name' | head -1")
print(r.stdout)
```

**结果**：4 核 / 7.8Gi 内存 / 8.0G 系统盘（overlay2）。

---

## 2. CDP 浏览器自动化连通性验证

**目的**：验证 Playwright 能否通过 CDP 控制沙箱内置的 Chromium（外部连接方式，走 `9000/cdp` + 双重鉴权）。

```python
token = sbx._envd_access_token
host = sbx.get_host(9000)
cdp_url = f"https://{host}/cdp?access_token={token}"

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(
        cdp_url,
        headers={"X-Access-Token": str(token)}
    )
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://www.baidu.com")
    print("页面标题:", page.title())
    browser.close()
```

**结果**：`页面标题: 百度一下，你就知道` —— CDP 外部连接可行。

---

## 3. 部署 CUA-Gym-Hub（notion_mock）

**目的**：把 CUA-Gym-Hub 的 mock 网页环境（这里用 `notion_mock` 作为验证对象）部署进沙箱，跑成后台服务。

```python
# 克隆仓库
r = sbx.commands.run("git clone https://github.com/xlang-ai/CUA-Gym-Hub.git", user="root", timeout=120)
print(r.stdout, r.stderr)

# 装依赖
r = sbx.commands.run("cd /mnt/workspace/CUA-Gym-Hub/websites/notion_mock && npm install", user="root", timeout=120)
print(r.stdout[-500:])

# 后台起服务，监听 5173
r = sbx.commands.run(
    "cd /mnt/workspace/CUA-Gym-Hub/websites/notion_mock && npm run dev",
    user="root", background=True
)
print("notion_mock 已在后台启动，pid =", r.pid)
```

**结果**：`Local: http://localhost:5173/`，服务正常监听。

---

## 4. State API 验证（注入 / 读取状态）

**目的**：验证 Hub mock 的 HTTP State API（`/post`、`/go`）在沙箱内部工作正常，且符合 `sid` 隔离设计。

```python
# 注入一条测试状态
r = sbx.commands.run(
    '''curl -X POST "http://localhost:5173/post?sid=test_001" '''
    '''-H "Content-Type: application/json" '''
    '''-d '{"action":"set","state":{"hello":"world"}}' ''',
    user="root"
)
print(r.stdout)

# 读取状态确认
r = sbx.commands.run("curl -s 'http://localhost:5173/go?sid=test_001'", user="root")
print(r.stdout)
```

**结果**：返回 `{"initial_state":{"hello":"world"},"current_state":{"hello":"world"},"state_diff":{}}`，State API 工作正常。

---

## 5. 浏览器渲染验证（NoVNC 人工确认）

**目的**：确认沙箱内浏览器能正确渲染这个 mock 页面。

```python
token = sbx._envd_access_token
host = sbx.get_host(9000)
live_url = f"https://{host}/novnc/vnc_lite.html?access_token={token}&path=websockify%3Faccess_token%3D{token}"
print("在浏览器中打开这个链接看沙箱桌面:", live_url)
```

在弹出的远程桌面里打开浏览器访问 `http://localhost:5173/?sid=test_001`，确认 Notion mock 页面（侧边栏、封面图、页面内容）正常渲染。

---

## 6. CDP 程序化控制验证（截图）

**目的**：验证 Playwright 能否通过沙箱内部的 CDP（`localhost:9222`）程序化控制、截图这个 mock 页面（跟第 2 步走的外部 CDP 不同，这里走内部直连，agent 实际操作会走这条路）。

```python
screenshot_script = '''
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()
    page.goto("http://localhost:5173/?sid=test_001", timeout=15000)
    page.wait_for_timeout(1000)
    print("页面标题:", page.title())
    page.screenshot(path="/mnt/workspace/notion_test.png", full_page=True)
    print("截图已保存")
    browser.close()
'''
sbx.files.write("/mnt/workspace/test_cdp.py", screenshot_script)

r = sbx.commands.run("python3 /mnt/workspace/test_cdp.py", user="root", timeout=30)
print(r.stdout)
```

**结果**：`页面标题: Xotion Clone`，截图保存成功。

---

## 7. 下载真实 CUA-Gym task

**目的**：从 CUA-Gym 官方数据集里拉一个真实的、纯 notion_mock 单应用 task，用于验证完整评测闭环（而不是自己编的假数据）。

```python
# 装依赖（清华源在这个网络下被 403，改用腾讯云镜像）
r = sbx.commands.run(
    "pip install -U datasets huggingface_hub -i https://mirrors.cloud.tencent.com/pypi/simple",
    user="root", timeout=180
)
print(r.stdout[-300:])

# 筛选出一个纯 notion 单应用的 task
find_task_script = '''
import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
from datasets import load_dataset

tasks = load_dataset("xlangai/CUA-Gym", "tasks", split="train")
notion_only = tasks.filter(lambda row: row["app_type"] == "notion_mock")
print("找到", len(notion_only), "个纯 notion 单应用 task")

t = notion_only[0]
print("task_id:", t["id"])
print("instruction:", t["instruction"])
print("archive_member:", t["archive_member"])
'''
sbx.files.write("/mnt/workspace/find_task.py", find_task_script)

r = sbx.commands.run("cd /mnt/workspace && python3 find_task.py", user="root", timeout=300)
print(r.stdout)
```

**结果**：拿到 task `06f4ea77-02c8-5f39-bbf8-afece5294546`（"搭建带子页面的项目 wiki"）。

**下载并解压这个 task 的文件包**（数据集的 zstd 压缩包里没有系统 `zstd` 命令可用，改用 Python `zstandard` 库流式解压）：

```python
task_id = "06f4ea77-02c8-5f39-bbf8-afece5294546"

r = sbx.commands.run(
    "pip install zstandard -i https://mirrors.cloud.tencent.com/pypi/simple",
    user="root", timeout=120
)

download_script = '''
import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
from huggingface_hub import hf_hub_download

path = hf_hub_download(
    repo_id="xlangai/CUA-Gym",
    repo_type="dataset",
    filename="artifacts/cua_gym_tasks_v1.tar.zst",
    local_dir="/mnt/workspace/CUA-Gym-data"
)
print("下载到:", path)
'''
sbx.files.write("/mnt/workspace/download_task.py", download_script)
r = sbx.commands.run("cd /mnt/workspace && python3 download_task.py", user="root", timeout=600)
print(r.stdout)

extract_script = f'''
import zstandard, tarfile

task_id = "{task_id}"
dctx = zstandard.ZstdDecompressor()
with open("/mnt/workspace/CUA-Gym-data/artifacts/cua_gym_tasks_v1.tar.zst", "rb") as f:
    with dctx.stream_reader(f) as reader:
        with tarfile.open(fileobj=reader, mode="r|") as tar:
            for member in tar:
                if member.name.startswith(task_id + "/"):
                    tar.extract(member, path="/mnt/workspace/cua_gym_tasks")
                    print("解压:", member.name)
'''
sbx.files.write("/mnt/workspace/extract_task.py", extract_script)
r = sbx.commands.run("python3 /mnt/workspace/extract_task.py", user="root", timeout=300)
print(r.stdout)
```

解压后得到 `task.json`（执行配置）、`initial_setup.py`（构造初始状态）、`reward.py`（评分逻辑）三个文件。

---

## 8. 跑通真实 task 的评测闭环（初始状态 → 0 分）

**目的**：验证"下载 task → 替换 URL 占位符 → 注入初始状态 → 浏览器渲染 → 评分"这条完整链路。

```python
task_id = "06f4ea77-02c8-5f39-bbf8-afece5294546"
task_dir = f"/mnt/workspace/cua_gym_tasks/{task_id}"

# 1. 替换数据集里的 URL 占位符为本地部署地址
r = sbx.commands.run(
    f"sed -i 's|__CUA_GYM_NOTION_URL__|http://localhost:5173|g' {task_dir}/initial_setup.py {task_dir}/reward.py",
    user="root"
)

# 2. 注释掉 initial_setup.py 里尝试拉起 google-chrome 桌面窗口的那一行
#    （这是给真实 OSWorld 桌面 VM 准备的，沙箱里没有这个命令，注释掉不影响状态注入）
r = sbx.commands.run(
    f"sed -i \"/launch_gui(f'google-chrome/s/^/#/\" {task_dir}/initial_setup.py",
    user="root"
)

r = sbx.commands.run("pip install requests -i https://mirrors.cloud.tencent.com/pypi/simple", user="root", timeout=60)

# 3. 跑 initial_setup.py，注入初始状态、生成 sid
r = sbx.commands.run(f"cd {task_dir} && python3 initial_setup.py", user="root", timeout=60)
print(r.stdout)

# 4. 读出生成的 sid
r = sbx.commands.run("cat /tmp/task_web_sid", user="root")
sid = r.stdout.strip()
print("sid:", sid)

# 5. 确认状态注入成功
r = sbx.commands.run(f"curl -s 'http://localhost:5173/go?sid={sid}'", user="root")
print(r.stdout[:300])

# 6. CDP 截图确认页面渲染
screenshot_script = f'''
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()
    page.goto("http://localhost:5173/?sid={sid}", timeout=15000)
    page.wait_for_timeout(1000)
    page.screenshot(path="/mnt/workspace/task_initial.png", full_page=True)
    browser.close()
'''
sbx.files.write("/mnt/workspace/screenshot_task.py", screenshot_script)
sbx.commands.run("python3 /mnt/workspace/screenshot_task.py", user="root", timeout=30)

# 7. 跑 reward.py（此时啥都没做，预期 0 分）
r = sbx.commands.run(f"cd {task_dir} && python3 reward.py", user="root", timeout=30)
print(r.stdout)
```

**结果**：`initial_state has 3 pages (expected 3)`，5 个评分项全部 `FAIL`，`REWARD: 0.0` —— 符合预期。

---

## 9. 验证 reward 机制可信（模拟正确答案 → 满分）

**目的**：证明 `reward.py` 不是摆设——手动构造一份"任务已完成"的 `current_state`，验证能否正确打出满分，从而确认整套评测机制可信。

```python
sid = "2db55eb1-d6c3-49fc-aff2-2f0e5114270b"  # 复用第 8 步生成的 sid

verify_script = f'''
import json, copy, requests

sid = "{sid}"
BASE_URL = "http://localhost:5173"
data = requests.get(f"{{BASE_URL}}/go?sid={{sid}}", timeout=10).json()
current_state = copy.deepcopy(data["initial_state"])

wiki_id, arch_id, api_id, deploy_id = "page-wiki-test", "page-arch-test", "page-api-test", "page-deploy-test"
now = "2026-09-28T12:00:00.000Z"

current_state["pages"][wiki_id] = {{
    "id": wiki_id, "title": "Project Atlas Wiki", "icon": "", "cover": None,
    "parentId": None, "blockIds": [], "favorite": False,
    "createdDate": now, "lastEditedDate": now, "properties": {{}}
}}
current_state["pages"][arch_id] = {{
    "id": arch_id, "title": "Architecture Overview", "icon": "", "cover": None,
    "parentId": wiki_id, "blockIds": ["blk-arch-h1", "blk-arch-b1", "blk-arch-b2", "blk-arch-b3"],
    "favorite": False, "createdDate": now, "lastEditedDate": now, "properties": {{}}
}}
current_state["pages"][api_id] = {{
    "id": api_id, "title": "API Reference", "icon": "", "cover": None,
    "parentId": wiki_id, "blockIds": ["blk-api-h1", "blk-api-code"],
    "favorite": False, "createdDate": now, "lastEditedDate": now, "properties": {{}}
}}
current_state["pages"][deploy_id] = {{
    "id": deploy_id, "title": "Deployment Guide", "icon": "", "cover": None,
    "parentId": wiki_id, "blockIds": ["blk-deploy-h1", "blk-deploy-n1", "blk-deploy-n2", "blk-deploy-n3"],
    "favorite": False, "createdDate": now, "lastEditedDate": now, "properties": {{}}
}}

current_state["blocks"].update({{
    "blk-arch-h1": {{"id": "blk-arch-h1", "type": "heading-1", "content": "System Components", "properties": {{}}, "createdDate": now, "lastEditedDate": now}},
    "blk-arch-b1": {{"id": "blk-arch-b1", "type": "bullet-list", "content": "Auth Service", "properties": {{}}, "createdDate": now, "lastEditedDate": now}},
    "blk-arch-b2": {{"id": "blk-arch-b2", "type": "bullet-list", "content": "Data Pipeline", "properties": {{}}, "createdDate": now, "lastEditedDate": now}},
    "blk-arch-b3": {{"id": "blk-arch-b3", "type": "bullet-list", "content": "Notification Engine", "properties": {{}}, "createdDate": now, "lastEditedDate": now}},
    "blk-api-h1": {{"id": "blk-api-h1", "type": "heading-1", "content": "Endpoints", "properties": {{}}, "createdDate": now, "lastEditedDate": now}},
    "blk-api-code": {{"id": "blk-api-code", "type": "code", "content": "GET /api/v2/users — Returns paginated user list", "properties": {{}}, "createdDate": now, "lastEditedDate": now}},
    "blk-deploy-h1": {{"id": "blk-deploy-h1", "type": "heading-1", "content": "Prerequisites", "properties": {{}}, "createdDate": now, "lastEditedDate": now}},
    "blk-deploy-n1": {{"id": "blk-deploy-n1", "type": "numbered-list", "content": "Docker 24+", "properties": {{}}, "createdDate": now, "lastEditedDate": now}},
    "blk-deploy-n2": {{"id": "blk-deploy-n2", "type": "numbered-list", "content": "Kubernetes 1.28+", "properties": {{}}, "createdDate": now, "lastEditedDate": now}},
    "blk-deploy-n3": {{"id": "blk-deploy-n3", "type": "numbered-list", "content": "Helm 3.x", "properties": {{}}, "createdDate": now, "lastEditedDate": now}},
}})
current_state["pageOrder"] = current_state.get("pageOrder", []) + [wiki_id]

resp = requests.post(f"{{BASE_URL}}/post?sid={{sid}}", json={{"action": "set_current", "state": current_state}}, timeout=30)
print("写入结果:", resp.status_code)
'''
sbx.files.write("/mnt/workspace/simulate_success.py", verify_script)
sbx.commands.run("python3 /mnt/workspace/simulate_success.py", user="root", timeout=30)

# 再跑一次 reward.py
r = sbx.commands.run(f"cd {task_dir} && python3 reward.py", user="root", timeout=30)
print(r.stdout)
```

**结果**：5 个评分项全部 `PASS`，`REWARD: 1.0` —— reward 机制经过双向验证（0 分 / 满分）都符合预期，可信。

---

## 10. 模型推理连通性验证（沙箱内部调用 <ichat-woa>）

**目的**：验证 agent 未来做决策要用的内部模型网关，能否从沙箱内部直接访问（决定 agent 主循环是否可以整体放进沙箱）。

```python
r = sbx.commands.run("curl -sI --max-time 5 http://<ichat-woa>/api/external", user="root")
print(r.stdout)
```

返回 `HTTP/1.1 404 Not Found` + `x-proxy-by: SmartGate` —— 404 只是因为 HEAD 请求打的是裸路径，但请求确实打到了内部网关，说明**网络是通的**。

**实际调用验证**：

```python
test_llm_script = '''
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["ICHAT_API_KEY"],
    base_url="http://<ichat-woa>/api/external"
)
response = client.chat.completions.create(
    model="gpt-5",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
)
print(response.choices[0].message.content)
'''
sbx.files.write("/mnt/workspace/test_llm.py", test_llm_script)

r = sbx.commands.run("pip install openai -i https://mirrors.cloud.tencent.com/pypi/simple", user="root", timeout=60)

import os as dev_os
api_key = dev_os.environ.get("ICHAT_API_KEY", "")
r = sbx.commands.run(
    "python3 /mnt/workspace/test_llm.py",
    user="root", envs={"ICHAT_API_KEY": api_key}, timeout=30
)
print(r.stdout)
```

**结果**：`Hi! How can I help you today?` —— 模型调用从沙箱内部发出，正常拿到回复。

---

## 总结：已验证能力清单

| 能力 | 对应章节 | 状态 |
|---|---|---|
| 沙箱资源规格查询 | §1 | ✅ |
| CDP 外部连接（Playwright） | §2 | ✅ |
| CUA-Gym-Hub 环境部署 | §3 | ✅ |
| Hub State API（注入/读取，session 隔离） | §4 | ✅ |
| 浏览器渲染（人工确认） | §5 | ✅ |
| CDP 内部连接 + 程序化截图 | §6 | ✅ |
| 官方数据集下载 + 单 task 解压 | §7 | ✅ |
| 真实 task 完整闭环（0 分场景） | §8 | ✅ |
| reward 机制可信性（满分场景） | §9 | ✅ |
| 沙箱内部调用内部模型网关 | §10 | ✅ |

**尚未验证 / 下一步**：把 §10 的模型决策能力和 §6 的 CDP 操作能力接成一个完整的 agent 主循环（观察页面 → 模型决策动作 → 执行动作 → 循环 → 打分），并确定具体的 action space（点击坐标 / DOM 元素定位 / 现成 GUI agent 框架协议）。