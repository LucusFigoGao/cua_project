"""预制流程的离线测试: 提取逻辑用仓库里的真实压缩包, 其余用假 Shell, 都不需要网络和 AGS。"""
import json
import re
import tempfile
import unittest
from pathlib import Path

from workspace.sandbox import prewarm
from workspace.sandbox.prewarm import Paths, Plan
from workspace.sandbox.task_extract import extract_tasks, transform_text
from workspace.tasks import catalog

try:
    import zstandard  # noqa: F401
    import pyarrow  # noqa: F401

    HAVE_DEPS = catalog.ARCHIVE_PATH.exists()
except ImportError:
    HAVE_DEPS = False


class TransformTests(unittest.TestCase):
    def test_placeholders_replaced_and_launch_line_commented(self):
        src = "u = '__CUA_GYM_GMAIL_URL__/x'\nlaunch_gui(f'google-chrome {u}')\nprint(1)\n"
        out = transform_text("initial_setup.py", src, {"__CUA_GYM_GMAIL_URL__": "http://localhost:8006"})
        self.assertIn("http://localhost:8006/x", out)
        self.assertIn("#launch_gui(f'google-chrome", out)
        self.assertIn("\nprint(1)", out)

    def test_launch_line_only_touched_in_initial_setup(self):
        src = "launch_gui(f'google-chrome x')\n"
        self.assertEqual(transform_text("reward.py", src, {}), src)


@unittest.skipUnless(HAVE_DEPS, "需要 zstandard、pyarrow 和仓库里的压缩包")
class ExtractRealArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tasks = catalog.select_tasks(catalog.load_index())
        cls.apps = ["notion_mock", "gmail_mock", "slack_mock"]
        cls.picked = catalog.tasks_within(tasks, cls.apps)[:5]
        cls.ports = catalog.port_map(cls.apps, base=9100)
        cls.repl = catalog.replacements(cls.apps, cls.ports)

    def _extract(self, out, repl=None):
        return extract_tasks(str(catalog.ARCHIVE_PATH), out, [t.id for t in self.picked], self.repl if repl is None else repl)

    def test_extracts_three_files_per_task_and_skips_mac_resource_forks(self):
        with tempfile.TemporaryDirectory() as out:
            rep = self._extract(out)
            self.assertEqual((rep["extracted"], rep["missing"]), (len(self.picked), []))
            for t in self.picked:
                names = sorted(p.name for p in (Path(out) / t.id).iterdir())
                self.assertEqual(names, ["initial_setup.py", "reward.py", "task.json"])

    def test_placeholders_are_resolved_to_local_ports(self):
        with tempfile.TemporaryDirectory() as out:
            rep = self._extract(out)
            self.assertEqual(rep["unresolved"], {})
            text = "".join(p.read_text() for p in Path(out).rglob("*.py"))
            self.assertNotRegex(text, r"__CUA_GYM_[A-Z0-9_]+__")
            self.assertRegex(text, r"http://localhost:91\d\d")

    def test_unreplaced_placeholders_are_reported_not_hidden(self):
        with tempfile.TemporaryDirectory() as out:
            rep = self._extract(out, repl={})
            self.assertTrue(rep["unresolved"])
            self.assertTrue(all(re.fullmatch(r"__CUA_GYM_[A-Z0-9_]+__", p) for v in rep["unresolved"].values() for p in v))

    def test_extract_is_idempotent(self):
        with tempfile.TemporaryDirectory() as out:
            self._extract(out)
            first = {str(p): p.read_bytes() for p in Path(out).rglob("*") if p.is_file()}
            self._extract(out)
            second = {str(p): p.read_bytes() for p in Path(out).rglob("*") if p.is_file()}
            self.assertEqual(first, second)


class SandboxShellTests(unittest.TestCase):
    """SandboxShell 对 e2b 异常的映射: 命令失败返回退出码, 超时和网络错误照常抛出。"""

    def _shell(self, behavior):
        import e2b

        from workspace.sandbox.shells import SandboxShell

        class Commands:
            def run(self, cmd, user=None, timeout=None, background=False):
                return behavior(e2b, cmd)

        class Sbx:
            commands = Commands()

        return SandboxShell(Sbx())

    def test_success_returns_stdout(self):
        class R:
            stdout = "hello"

        self.assertEqual(self._shell(lambda e2b, cmd: R()).run("echo"), (0, "hello"))

    def test_nonzero_exit_is_returned_not_raised(self):
        def boom(e2b, cmd):
            raise e2b.CommandExitException(stderr="bad", stdout="out", exit_code=3, error="x")

        self.assertEqual(self._shell(boom).run("false"), (3, "outbad"))

    def test_timeout_is_raised(self):
        def slow(e2b, cmd):
            raise e2b.TimeoutException("timed out")

        with self.assertRaises(Exception) as cm:
            self._shell(slow).run("sleep 99")
        self.assertEqual(type(cm.exception).__name__, "TimeoutException")


class FakeShell:
    """只模拟 prewarm 用到的几类命令。"""

    def __init__(self, free=100000, alive=()):
        self.free = free
        self.alive = set(alive)
        self.commands = []
        self.spawned = []
        self.files = {}

    def run(self, cmd, timeout=60):
        self.commands.append(cmd)
        if "probe_ports.py" in cmd:
            ports = json.loads(re.search(r"'(\[[^']*\])'", cmd).group(1))
            return 0, json.dumps({str(p): p in self.alive for p in ports})
        if "df --output=avail" in cmd:
            return 0, f"Avail\n{self.free}\n"
        if "du -sm" in cmd:
            return 0, "100\n"
        return 0, ""

    def write(self, path, data):
        self.files[path] = data

    def put_file(self, local, remote):
        pass

    def spawn(self, cmd):
        self.spawned.append(cmd)
        self.alive.add(int(re.search(r"--port (\d+)", cmd).group(1)))


def make_plan(apps=("notion_mock", "gmail_mock"), **kw):
    ports = catalog.port_map(apps, base=8000)
    return Plan(apps=list(apps), ports=ports, task_ids=[], replacements={}, **kw)


class PrewarmLogicTests(unittest.TestCase):
    def test_low_disk_skips_install_and_reports_it(self):
        sh = FakeShell(free=300)
        rec = prewarm.build_app(sh, make_plan(min_free_mb=1500), Paths(), "notion_mock")
        self.assertEqual((rec["ok"], rec["skipped"], rec["free_mb"]), (False, "disk", 300))
        self.assertFalse(any("npm install" in c for c in sh.commands))

    def test_enough_disk_runs_install_then_build(self):
        sh = FakeShell(free=5000)
        rec = prewarm.build_app(sh, make_plan(), Paths(), "notion_mock")
        self.assertTrue(rec["ok"])
        joined = "\n".join(sh.commands)
        self.assertLess(joined.index("npm install"), joined.index("npm run build"))

    def test_only_dead_servers_are_started_and_port_is_strict(self):
        plan = make_plan()
        sh = FakeShell(alive={plan.ports["gmail_mock"]})
        up = prewarm.start_servers(sh, plan, Paths(), ["notion_mock", "gmail_mock"], wait=5)
        self.assertEqual(up, {"notion_mock": True, "gmail_mock": True})
        self.assertEqual(len(sh.spawned), 1)
        self.assertIn(f"--port {plan.ports['notion_mock']} --strictPort", sh.spawned[0])
        self.assertIn("websites/notion_mock", sh.spawned[0])

    def test_server_that_never_comes_up_is_reported_false(self):
        class Stuck(FakeShell):
            def spawn(self, cmd):
                self.spawned.append(cmd)  # 启动了但端口一直没起来

        plan = make_plan(apps=("notion_mock",))
        up = prewarm.start_servers(Stuck(), plan, Paths(), ["notion_mock"], wait=1)
        self.assertEqual(up, {"notion_mock": False})

    def test_free_mb_parses_df_and_survives_garbage(self):
        self.assertEqual(prewarm.free_mb(FakeShell(free=1234), "/x"), 1234)

        class Garbage(FakeShell):
            def run(self, cmd, timeout=60):
                return 0, "???"

        self.assertEqual(prewarm.free_mb(Garbage(), "/x"), -1)

    def test_verify_task_parses_reward_and_reports_failures(self):
        class S(FakeShell):
            def run(self, cmd, timeout=60):
                if "initial_setup.py" in cmd and "test -f" not in cmd:
                    return 0, ""
                if "cat /tmp/task_web_sid" in cmd:
                    return 0, "sid_abc\n"
                if "reward.py" in cmd:
                    return 0, "some log\nREWARD: 0.5\n"
                return 0, ""

        r = prewarm.verify_task(S(), Paths(), "t1")
        self.assertEqual((r["ok"], r["reward"], r["sid"]), (True, 0.5, "sid_abc"))

        class NoReward(S):
            def run(self, cmd, timeout=60):
                return (0, "no score here") if "reward.py" in cmd else super().run(cmd, timeout)

        r = prewarm.verify_task(NoReward(), Paths(), "t1")
        self.assertFalse(r["ok"])
        self.assertIn("REWARD", r["error"])

        class Missing(FakeShell):
            def run(self, cmd, timeout=60):
                return (1, "") if "test -f" in cmd else (0, "")

        self.assertIn("没提取", prewarm.verify_task(Missing(), Paths(), "t1")["error"])


if __name__ == "__main__":
    unittest.main()
