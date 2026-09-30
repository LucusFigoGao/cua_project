"""任务目录的离线测试, 直接读仓库里的真实任务索引(需要 pandas + pyarrow)。"""
import unittest

try:
    import pyarrow  # noqa: F401

    HAVE_ARROW = True
except ImportError:
    HAVE_ARROW = False

from workspace.tasks import catalog


class SplitTests(unittest.TestCase):
    def test_split_apps(self):
        self.assertEqual(catalog.split_apps("slack_mock, notion_mock"), ["slack_mock", "notion_mock"])
        self.assertEqual(catalog.split_apps(None), [])
        self.assertEqual(catalog.split_apps(float("nan")), [])

    def test_is_web_app(self):
        self.assertTrue(catalog.is_web_app("gmail_mock"))
        self.assertFalse(catalog.is_web_app("mock_websites"))  # 泛标签
        self.assertFalse(catalog.is_web_app("libreoffice_calc"))


class PortAndReplacementTests(unittest.TestCase):
    def test_port_map_is_sorted_stable_and_unique(self):
        a = catalog.port_map(["slack_mock", "asana_mock", "gmail_mock"])
        self.assertEqual(a, {"asana_mock": 8000, "gmail_mock": 8001, "slack_mock": 8002})
        self.assertEqual(a, catalog.port_map(["gmail_mock", "slack_mock", "asana_mock", "gmail_mock"]))

    def test_replacements_cover_url_host_and_alias(self):
        ports = catalog.port_map(["notion_mock", "google_docs_mock"], base=9000)
        r = catalog.replacements(ports, ports)
        self.assertEqual(r["__CUA_GYM_GOOGLE_DOCS_URL__"], "http://localhost:9000")
        self.assertEqual(r["__CUA_GYM_GOOGLE_DOCS_HOST__"], "localhost:9000")
        self.assertEqual(r["__CUA_GYM_NOTION_URL__"], "http://localhost:9001")
        self.assertEqual(r["__CUA_GYM_NOTION_MOCK_URL__"], "http://localhost:9001")  # 别名

    def test_no_placeholder_is_a_prefix_of_another(self):
        # 逐个 str.replace 的前提: 完整占位符互不为前缀(都以 __ 结尾, 天然满足, 这里防止以后改坏)
        keys = list(catalog.replacements(["notion_mock", "gmail_mock"], catalog.port_map(["notion_mock", "gmail_mock"])))
        for k in keys:
            for other in keys:
                if k != other:
                    self.assertNotIn(k, other)


@unittest.skipUnless(HAVE_ARROW, "需要 pyarrow")
class RealIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = catalog.load_index()
        cls.tasks = catalog.select_tasks(cls.df)

    def test_counts_match_the_measured_numbers(self):
        web = [t for t in self.tasks if t.platform == "web"]
        cross = [t for t in self.tasks if t.platform == "cross_app"]
        self.assertEqual((len(web), len(cross), len(self.tasks)), (1075, 342, 1417))
        self.assertEqual(catalog.skipped_summary(self.df)["cross_app_with_desktop_apps"], 88)

    def test_thirty_one_apps_and_generic_tag_excluded(self):
        apps = catalog.required_apps(self.tasks)
        self.assertEqual(len(apps), 31)
        self.assertNotIn("mock_websites", apps)
        for expected in ("slack_mock", "notion_mock", "gmail_mock", "asana_mock", "discord_mock", "docusign_mock"):
            self.assertIn(expected, apps)
        self.assertEqual(sum(t.generic for t in self.tasks), 8)

    def test_every_placeholder_of_the_31_apps_is_covered(self):
        self.assertEqual(catalog.unknown_placeholders(catalog.required_apps(self.tasks)), [])

    def test_ports_are_8000_to_8030(self):
        ports = catalog.port_map(catalog.required_apps(self.tasks))
        self.assertEqual(sorted(ports.values()), list(range(8000, 8031)))

    def test_tasks_within_subset_only_uses_subset(self):
        sub = ["notion_mock", "gmail_mock", "slack_mock"]
        picked = catalog.tasks_within(self.tasks, sub)
        self.assertTrue(picked)
        for t in picked:
            self.assertTrue(set(t.apps) <= set(sub))
            self.assertFalse(t.generic)

    def test_sample_covers_every_app(self):
        apps = catalog.required_apps(self.tasks)
        sample = catalog.sample_tasks(self.tasks, apps, cross=3)
        self.assertEqual({a for t in sample for a in t.apps}, set(apps))
        self.assertEqual(len({t.id for t in sample}), len(sample))  # 没有重复
        # 没有单网页任务的三个网页, 是靠跨应用任务覆盖的
        web_only = {t.apps[0] for t in sample if t.platform == "web"}
        self.assertEqual(set(apps) - web_only, {"asana_mock", "discord_mock", "docusign_mock"})


if __name__ == "__main__":
    unittest.main()
