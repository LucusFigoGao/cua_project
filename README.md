# AGS All-In-One 沙箱使用指南

本沙箱基于腾讯云 Agent Runtime（AGS）的 **All-In-One（AIO）沙箱**类型，兼容 E2B SDK，在单个实例中同时提供代码执行、终端、文件系统、浏览器自动化、远程桌面、VSCode Web IDE 等能力。

---

## 1. 环境准备

### 1.1 安装依赖

```bash
pip install e2b playwright -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 1.2 配置环境变量

推荐使用 `.env` 文件管理凭证，或直接在代码中设置 `os.environ`。

```bash
# .env
E2B_DOMAIN=ap-guangzhou.tencentags.com
E2B_API_KEY=ark_xxxxxxxx
```

| 变量 | 说明 |
|---|---|
| `E2B_DOMAIN` | AGS 服务域名，按地域选择（如广州为 `ap-guangzhou.tencentags.com`） |
| `E2B_API_KEY` | AGS 控制台"API Keys"中创建的密钥，`ark_` 开头 |

### 1.3 网络要求

沙箱服务仅在**办公网**或 **DevCloud 内网**环境下可访问，需确保当前网络环境满足此条件（公司内网直连，或已正确接入 VPN）。

---

## 2. 创建与连接沙箱

### 2.1 创建新实例

```python
import os
from e2b import Sandbox

os.environ["E2B_DOMAIN"] = "ap-guangzhou.tencentags.com"
os.environ["E2B_API_KEY"] = "your_api_key"

sbx = Sandbox.create(
    template="sdt-hojglb51",  # AGS 控制台创建的沙箱工具 ID
    timeout=3600,             # 超时时间（秒），到期自动销毁，最长 86400（24h）
)
print("沙箱已启动，实例 ID：", sbx.sandbox_id)
```

### 2.2 连接已有实例

```python
sbx = Sandbox.connect("已有的实例ID")
```

### 2.3 生命周期管理

```python
# 查询沙箱信息
info = sbx.get_info()
print(info.template_id, info.started_at, info.end_at)

# 动态续期
sbx.set_timeout(7200)

# 主动销毁（推荐用完即销毁，避免资源浪费）
sbx.kill()
```

---

## 3. 终端命令执行

```python
# 默认身份执行
r = sbx.commands.run("whoami && pwd")
print(r.exit_code, r.stdout)

# 指定身份执行（支持 user 和 root）
r = sbx.commands.run("ls /root", user="root")
```

### 流式输出

```python
sbx.commands.run(
    "for i in 1 2 3; do echo line-$i; sleep 0.3; done",
    on_stdout=lambda s: print("[stream]", s.rstrip()),
)
```

### 后台执行

```python
proc = sbx.commands.run("python3 -m http.server 8000", background=True)
print("后台进程 pid =", proc.pid)

# 等待完成
response = proc.wait(on_stdout=lambda data: print(data))

# 列出正在运行的后台命令
for cmd in sbx.commands.list():
    print(cmd)

# 结束后台命令
sbx.commands.kill(proc.pid)
```

### 发送 stdin

```python
sbx.commands.send_stdin(proc.pid, "input\n")
```

---

## 4. 文件系统操作

```python
# 写入文件
sbx.files.write("/tmp/demo.txt", "hello from ags sandbox\n")

# 批量写入
sbx.files.write_files([
    {"path": "/tmp/a.txt", "data": "content-a"},
    {"path": "/tmp/b.txt", "data": "content-b"},
])

# 读取文件
content = sbx.files.read("/tmp/demo.txt")

# 二进制读写
with open("./local.bin", "rb") as f:
    sbx.files.write("/tmp/up.bin", f.read())
open("./down.bin", "wb").write(sbx.files.read("/tmp/up.bin", format="bytes"))

# 列目录
files = sbx.files.list("/tmp")

# 检查文件是否存在
exists = sbx.files.exists("/tmp/demo.txt")

# 重命名 / 创建目录
sbx.files.rename("/tmp/old.txt", "/tmp/new.txt")
sbx.files.make_dir("/tmp/newdir")

# 监控目录变化
watch_handle = sbx.files.watch_dir(".")
sbx.files.write("tempfile.txt", "temp")
sbx.files.remove("tempfile.txt")
for event in watch_handle.get_new_events():
    print(event)
```

---

## 5. 代码执行（Jupyter 内核）

AIO 沙箱内置代码执行能力，兼容 E2B 协议，支持 Python / JavaScript / TypeScript / Java / R / Bash。

```python
response = sbx.run_code('print("hello")')

# 指定语言
response = sbx.run_code('console.log("hello")', "javascript")

# 创建独立上下文（同一上下文共享变量）
ctx = sbx.create_code_context(language="python")
response = sbx.run_code('print("hello")', context=ctx)

# 流式返回
sbx.run_code(
    code,
    on_stdout=lambda data: print(data),
    on_stderr=lambda data: print(data),
    on_result=lambda data: print(data),
    on_error=lambda data: print(data),
)

# 指定环境变量 / 超时
response = sbx.run_code('print("hello")', envs={"foo": "bar"})
response = sbx.run_code('print("hello")', timeout=60)
```

---

## 6. 浏览器自动化（Playwright + CDP）

沙箱内置 Chromium，已预装 `playwright`、`selenium`、`pyautogui`、`pillow` 等自动化相关包。

### 6.1 获取访问凭证与地址

```python
token = sbx._envd_access_token
host = sbx.get_host(9000)
```

> AIO 沙箱通过 Nginx（端口 `9000`）统一对外暴露服务，所有 UI 类服务的鉴权凭证均为 `sbx._envd_access_token`。

### 6.2 远程连接浏览器（CDP）

```python
from playwright.sync_api import sync_playwright

cdp_url = f"https://{host}/cdp?access_token={token}"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(
        cdp_url,
        headers={"X-Access-Token": str(token)},
    )
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://www.baidu.com")
    print("页面标题:", page.title())
    page.screenshot(path="./screenshot.png")
    browser.close()
```

**要点**：
- `access_token` 必须**同时**作为 query 参数和 `X-Access-Token` 请求头传递
- 路径固定为 `/cdp`，端口固定为 `9000`

### 6.3 沙箱内部直连（无需外部凭证）

在沙箱内部执行的脚本（通过 `sbx.commands.run()` 触发）可以直接连接本地端口，无需任何鉴权：

```python
# 写入并在沙箱内部执行的脚本
script = '''
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://www.baidu.com")
    print(page.title())
    browser.close()
'''
sbx.files.write("/tmp/task.py", script)
r = sbx.commands.run("python3 /tmp/task.py")
print(r.stdout)
```

---

## 7. 可视化远程桌面（NoVNC）

```python
live_url = f"https://{host}/novnc/vnc_lite.html?access_token={token}&path=websockify%3Faccess_token%3D{token}"
print(live_url)  # 在浏览器中直接打开即可看到沙箱桌面画面
```

---

## 8. VSCode Web IDE

```python
vscode_url = f"https://{host}/vscode-sw-boot.html?access_token={token}"
print(vscode_url)
```

---

## 9. WebShell 终端（网页版）

```python
ttyd_url = f"https://{host}/ttyd/?access_token={token}"
print(ttyd_url)
```

---

## 10. 服务导航首页

```python
index_url = f"https://{host}/?access_token={token}"
print(index_url)
```

也可以从控制台获取：登录 Agent 沙箱服务控制台 → 环境工具 → All-In-One 沙箱 → 点击工具名称进入详情页 → 实例列表 → 对应实例的 **操作 > 预览**。

---

## 11. 完整示例：创建沙箱 + 浏览器自动化 + 清理

```python
import os
from e2b import Sandbox
from playwright.sync_api import sync_playwright

os.environ["E2B_DOMAIN"] = "ap-guangzhou.tencentags.com"
os.environ["E2B_API_KEY"] = "your_api_key"

sbx = Sandbox.create(template="sdt-hojglb51", timeout=3600)
print("沙箱已启动:", sbx.sandbox_id)

try:
    token = sbx._envd_access_token
    host = sbx.get_host(9000)
    cdp_url = f"https://{host}/cdp?access_token={token}"

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(
            cdp_url,
            headers={"X-Access-Token": str(token)},
        )
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.baidu.com")
        print("页面标题:", page.title())
        browser.close()

finally:
    sbx.kill()
    print("沙箱已销毁")
```

---

## 12. 常用能力速查表

| 能力 | 方法 | 访问端口/路径 |
|---|---|---|
| 创建/连接沙箱 | `Sandbox.create()` / `Sandbox.connect()` | — |
| 命令执行 | `sbx.commands.run()` | — |
| 代码执行 | `sbx.run_code()` | `49999`（兼容 E2B 协议） |
| 文件读写 | `sbx.files.*` | `49983` |
| 浏览器远程控制（CDP） | `playwright.chromium.connect_over_cdp()` | `9000/cdp` |
| 浏览器内部直连 | 沙箱内部脚本连 `localhost:9222` | 仅限沙箱内部 |
| 远程桌面 | 浏览器打开 `live_url` | `9000/novnc/` |
| VSCode Web IDE | 浏览器打开 `vscode_url` | `9000/vscode/` |
| WebShell 终端 | 浏览器打开 `ttyd_url` | `9000/ttyd/` |

---

## 13. 注意事项

- 沙箱默认执行身份为 `user`，非 `root`；需要 root 权限时在 `commands.run()` 显式传入 `user="root"`
- 所有涉及 `9000` 端口的外部访问（CDP、远程桌面、VSCode、WebShell）都需要携带 `sbx._envd_access_token`
- CDP 远程连接必须同时传递 query 参数 `access_token` 和请求头 `X-Access-Token`，二者缺一不可
- 沙箱用完建议主动 `sbx.kill()`，避免资源占用超时自动销毁前的浪费
- `create` 方法的 `metadata`、`envs`、`secure`、`allow_internet_access` 参数暂不可用