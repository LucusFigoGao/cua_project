"""
本机端到端演练(不连 AGS): 用 LocalShell 在临时目录里真实执行完整的预制流程,
对 3 个网页做 npm install -> build -> vite preview -> 健康检查 -> 提取任务数据 -> 跑任务脚本。

需要本机有 node/npm、pandas、pyarrow、zstandard、requests, 并且能访问 npm 源。耗时几分钟, 默认跳过:
    RUN_LOCAL_E2E=1 python -m unittest workspace.tests.test_prewarm_local -v
"""
import json
import os
import shutil
import tempfile
import unittest

from workspace.sandbox.prewarm import Paths, Plan, prewarm_instance, probe_ports, verify_task
from workspace.sandbox.shells import LocalShell
from workspace.tasks import catalog

APPS = ["notion_mock", "gmail_mock", "slack_mock"]
BASE = 18000  # 用不常见的端口, 避免和本机已有服务冲突


@unittest.skipUnless(os.environ.get("RUN_LOCAL_E2E") == "1" and shutil.which("npm"), "设置 RUN_LOCAL_E2E=1 并安装 node 后运行")
class LocalEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="prewarm_e2e_")
        tasks = catalog.select_tasks(catalog.load_index())
        cls.tasks = catalog.tasks_within(tasks, APPS)
        ports = catalog.port_map(APPS, base=BASE)
        cls.paths = Paths(
            repo_dir=f"{cls.tmp}/hub",
            data_dir=f"{cls.tmp}/data",
            tasks_dir=f"{cls.tmp}/tasks",
            tmp_dir=f"{cls.tmp}/tmp",
        )
        cls.plan = Plan(
            apps=APPS,
            ports=ports,
            task_ids=[t.id for t in cls.tasks],
            replacements=catalog.replacements(APPS, ports),
            repo_copy_from=str(catalog.REPO_ROOT / "gym" / "hub"),
            archive_local=str(catalog.ARCHIVE_PATH),
            min_free_mb=500,
        )
        cls.shell = LocalShell()
        cls.report = prewarm_instance(cls.shell, cls.plan, cls.paths)
        print("\n预制报告:", json.dumps(cls.report, ensure_ascii=False, indent=1)[:3000])

    @classmethod
    def tearDownClass(cls):
        cls.shell.close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_report_ok(self):
        self.assertTrue(self.report["ok"], json.dumps(self.report, ensure_ascii=False)[:1500])

    def test_all_ports_alive(self):
        alive = probe_ports(self.shell, self.paths, list(self.plan.ports.values()))
        self.assertTrue(all(alive.values()), alive)

    def test_tasks_extracted_and_placeholders_resolved(self):
        data = self.report["data"]
        self.assertEqual(data["extracted"], len(self.tasks))
        self.assertEqual(data["missing"], [])
        self.assertEqual(data["unresolved"], {}, "这些任务替换后仍有占位符")

    def test_state_api_answers_in_preview_mode(self):
        p = self.plan.ports["notion_mock"]
        code, out = self.shell.run(f"curl -s 'http://localhost:{p}/go?sid=probe_1'", timeout=30)
        self.assertEqual(code, 0)
        self.assertIn("current_state", out)

    def test_sample_tasks_run_setup_and_reward(self):
        for t in catalog.sample_tasks(self.tasks, APPS, cross=2):
            with self.subTest(task=t.id, apps=t.apps):
                r = verify_task(self.shell, self.paths, t.id)
                self.assertTrue(r["ok"], r)

    def test_rerun_is_idempotent_and_fast(self):
        again = prewarm_instance(self.shell, self.plan, self.paths)
        self.assertTrue(again["ok"], json.dumps(again, ensure_ascii=False)[:1500])
        self.assertLess(again["seconds"], self.report["seconds"])


if __name__ == "__main__":
    unittest.main()
