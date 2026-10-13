"""
把 OSWorld 的 agent server（osworld/desktop_env/server/main.py）装进 AGS 沙箱并常驻跑起来。

用 OSWorld 的 server 而不是自写环境层，因为 cua-gym 的 Env 本身就是它的瘦客户端：
Env.screenshot()/execute()/get_accessibility_tree() 逐一对应 server 的 /screenshot、
/setup/execute、/accessibility 路由。这里只是把底层从 ECS 换成 AGS 沙箱。另外
osworld/mm_agents 下 50+ 个 agent 全部按"全屏截图 + pyautogui 代码"来 prompt，用这个
server 就不必自写动作/观测的翻译层。

部署上有三处 AGS 沙箱的客观约束：
  1. 不用 systemd（沙箱里跑不起来），用 setsid+nohup 托管。
  2. DISPLAY 用 :1——沙箱的 Xvfb 跑在 :1（`Xvfb :1 -screen 0 1920x1080x24`）。
  3. 必须以默认用户 user 跑。root 跑 chromium 会被拒（"Running as root without
     --no-sandbox is not supported"），只有装系统包那一步用 root。

已知不可用：/accessibility（a11y 树）。python3-pyatspi 装得上，但它依赖的 _gi 是为
Python 3.13 编译的 C 扩展，而沙箱 python3 是 3.12，import 直接失败。要修得重做模板。
因此 observation_type 只用 screenshot，不用 a11y_tree 系列。
"""
import time

from e2b import Sandbox

from src.settings import (DISPLAY, OSWORLD_SERVER_DIR as REMOTE_DIR, PYXCURSOR_SRC,
                          SERVER_LOG, SERVER_PORT, SERVER_SRC)

# server 真正需要的最小集。requirements.txt 里的 pywinauto 是 Windows 专用，
# pynput 要编译、pygame 只被录屏用到，都不装。
PIP_PACKAGES = "flask pyautogui python-xlib pillow lxml numpy requests"
# pyautogui 在 Linux 上截图要调 gnome-screenshot；xdotool 给窗口操作兜底
APT_PACKAGES = "gnome-screenshot xdotool"


# main.py 的 Linux 分支是模块级 `import pyatspi`，在沙箱里必定失败（见模块 docstring），
# 整个 server 都起不来。pyatspi 只被 /accessibility 和 /terminal 用到，所以包成
# try/except：失败时把符号置空，server 正常起，只有那两个路由调用时才报错。
_ATSPI_SHIM = '''
if platform_name == "Linux":
    try:
        import pyatspi
        from pyatspi import Accessible, StateType, STATE_SHOWING
        from pyatspi import Action as ATAction
        from pyatspi import Component
        from pyatspi import Text as ATText
        from pyatspi import Value as ATValue
    except Exception:  # 沙箱内 pyatspi 不可用，见 src/sandbox/osworld_server.py
        pyatspi = None
        Accessible = Any
        StateType = Any
        STATE_SHOWING = None
        ATAction = Any
        Component = Any
        ATText = Any
        ATValue = Any

    BaseWrapper = Any
'''

_ATSPI_ORIG = '''if platform_name == "Linux":
    import pyatspi
    from pyatspi import Accessible, StateType, STATE_SHOWING
    from pyatspi import Action as ATAction
    from pyatspi import Component  # , Document
    from pyatspi import Text as ATText
    from pyatspi import Value as ATValue

    BaseWrapper = Any
'''


def _patch_server_source(src: str) -> str:
    """
    对上传副本做两处最小改动（osworld/ 下的原文件不动）：
      1. pyatspi 的模块级 import 包成 try/except（见上）
      2. 关掉 Flask 的 debug/reloader——debug 会拉起 reloader 子进程，两个进程监听同
         一端口，pkill 容易留孤儿。常驻服务不需要热重载。
    """
    if _ATSPI_ORIG in src:
        src = src.replace(_ATSPI_ORIG, _ATSPI_SHIM.lstrip("\n"), 1)
    src = src.replace(
        'app.run(debug=True, host="0.0.0.0")',
        'app.run(debug=False, use_reloader=False, host="0.0.0.0", threaded=True)',
        1,
    )
    return src


class OSWorldServerError(Exception):
    pass


def is_running(sbx: Sandbox, port: int = SERVER_PORT, timeout: int = 60) -> bool:
    """
    探活。用 /platform 而不是 /screenshot：前者是纯字符串返回、无 X 依赖，
    不会因为抓屏慢或 X 暂时不可用而误判成"没起来"。
    """
    r = sbx.commands.run(
        f"curl -s -o /dev/null -w '%{{http_code}}' -m 10 "
        f"http://127.0.0.1:{port}/platform 2>/dev/null || echo 000",
        timeout=timeout,
    )
    return (r.stdout or "").strip().endswith("200")


def install_deps(sbx: Sandbox, timeout: int = 900) -> dict:
    """
    幂等地装好 server 的依赖。

    apt 那一步用 root（装系统包需要），pip 用默认用户。
    注意沙箱镜像里 novnc 的 dpkg trigger 会报错，apt-get 整体返回非 0 但我们要的包
    其实装好了，所以这里不拿 apt 的退出码当失败依据——以最后的 import 探测为准。
    """
    sbx.commands.run(
        f"apt-get update -qq 2>/dev/null; "
        f"apt-get install -y -qq --no-install-recommends {APT_PACKAGES} 2>&1 | tail -2; true",
        user="root", timeout=timeout,
    )
    sbx.commands.run(f"pip install -q {PIP_PACKAGES} 2>&1 | tail -2; true", timeout=timeout)

    probe = (
        "import sys\n"
        "mods = ['flask', 'pyautogui', 'Xlib', 'PIL', 'lxml', 'numpy']\n"
        "missing = []\n"
        "for m in mods:\n"
        "    try:\n"
        "        __import__(m)\n"
        "    except Exception:\n"
        "        missing.append(m)\n"
        "print('MISSING=' + ','.join(missing))\n"
        "try:\n"
        "    import pyautogui\n"
        "    pyautogui.screenshot()\n"
        "    print('SHOT=ok')\n"
        "except Exception as e:\n"
        "    print('SHOT=fail:' + str(e)[:80])\n"
    )
    sbx.files.write("/tmp/_osw_probe.py", probe)
    r = sbx.commands.run(
        f"DISPLAY={DISPLAY} python3 /tmp/_osw_probe.py 2>&1 | tail -3", timeout=180)
    out = r.stdout or ""
    missing = ""
    shot = ""
    for line in out.splitlines():
        if line.startswith("MISSING="):
            missing = line.split("=", 1)[1].strip()
        elif line.startswith("SHOT="):
            shot = line.split("=", 1)[1].strip()
    return {"missing": [m for m in missing.split(",") if m], "screenshot": shot}


def ensure_server(sbx: Sandbox, port: int = SERVER_PORT, wait: float = 60.0,
                  force_restart: bool = False, install: bool = True) -> dict:
    """
    保证沙箱里有一个常驻的 OSWorld server 在 port 上监听。

    幂等：已在跑且 force_restart=False 就直接返回。
    """
    if not force_restart and is_running(sbx, port):
        return {"started": False, "already_running": True, "port": port}

    if not SERVER_SRC.exists():
        raise OSWorldServerError(f"找不到 OSWorld server 源码: {SERVER_SRC}")

    dep = {}
    if install:
        dep = install_deps(sbx)
        if dep.get("missing"):
            raise OSWorldServerError(f"依赖缺失，server 起不来: {dep['missing']}")

    # 上传 server。main.py 的 Linux 截图分支要 from pyxcursor import Xcursor，
    # 所以同目录还得放 pyxcursor.py。
    sbx.commands.run(f"mkdir -p {REMOTE_DIR}/screenshots", user="root", timeout=60)
    sbx.commands.run(f"chown -R user:user {REMOTE_DIR}", user="root", timeout=60)
    sbx.files.write(f"{REMOTE_DIR}/main.py", _patch_server_source(SERVER_SRC.read_text()))
    if PYXCURSOR_SRC.exists():
        sbx.files.write(f"{REMOTE_DIR}/pyxcursor.py", PYXCURSOR_SRC.read_text())

    if force_restart:
        # pkill 的模式要避开自身命令行，否则会把执行这条命令的 shell 一起杀掉
        sbx.commands.run("pkill -f '[o]sworld_server/main.py' || true", timeout=60)
        time.sleep(1.5)

    # 拉起 server。`>log 2>&1 </dev/null &` 三个流都要重定向：只要还有一个流连着
    # envd 的管道，commands.run 就会一直等着读而不返回（实测会卡到超时）。
    # 外面再套 `sh -c '...' >/dev/null 2>&1` 把启动命令自己的输出也断开。
    sbx.commands.run(
        f"sh -c 'cd {REMOTE_DIR} && DISPLAY={DISPLAY} setsid nohup "
        f"python3 {REMOTE_DIR}/main.py >{SERVER_LOG} 2>&1 </dev/null &' "
        f">/dev/null 2>&1; echo started",
        timeout=60,
    )

    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(2.0)
        if is_running(sbx, port):
            return {"started": True, "already_running": False, "port": port, "deps": dep}

    log = (sbx.commands.run(f"tail -30 {SERVER_LOG} 2>/dev/null || true",
                            timeout=60).stdout or "")
    raise OSWorldServerError(f"server 未能在 {wait:.0f}s 内就绪。日志：\n{log}")


def stop_server(sbx: Sandbox) -> None:
    sbx.commands.run("pkill -f '[o]sworld_server/main.py' || true", timeout=60)


def server_log(sbx: Sandbox, lines: int = 40) -> str:
    return (sbx.commands.run(f"tail -{lines} {SERVER_LOG} 2>/dev/null || true",
                             timeout=60).stdout or "")
