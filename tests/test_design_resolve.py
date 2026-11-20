import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.design.resolve import build_tree, resolve_path, lca, plan_connection

INSTANCES = [
    {"name": "insta"},
    {"name": "instb", "parent": "insta"},
    {"name": "instc", "parent": "instb"},
    {"name": "other"},
]


class DesignResolveTest(unittest.TestCase):
    def setUp(self):
        self.roots, self.nodes = build_tree(INSTANCES)

    def test_path(self):
        chain = resolve_path(self.nodes, "insta.instb.instc")
        self.assertEqual([n.name for n in chain], ["insta", "instb", "instc"])
        self.assertEqual(self.nodes["instc"].path(), "insta.instb.instc")
        self.assertIsNone(resolve_path(self.nodes, "insta.instx"))

    def test_lca(self):
        a = resolve_path(self.nodes, "insta")
        b = resolve_path(self.nodes, "insta.instb.instc")
        self.assertEqual(lca(a, b).name, "insta")

    def test_plan_feedthrough(self):
        plan = plan_connection(self.nodes, "insta", "insta.instb.instc")
        self.assertEqual(plan["lca"].name, "insta")
        self.assertEqual(plan["endpoint_b"].name, "instc")
        self.assertEqual([n.name for n in plan["side_b"]], ["instb"])
        self.assertEqual(plan["side_a"], [])

    def test_plan_siblings(self):
        self.nodes["d"] = None
        roots, nodes = build_tree([
            {"name": "top"},
            {"name": "a", "parent": "top"},
            {"name": "b", "parent": "top"},
        ])
        plan = plan_connection(nodes, "top.a", "top.b")
        self.assertEqual(plan["lca"].name, "top")
        self.assertEqual(plan["side_a"], [])
        self.assertEqual(plan["side_b"], [])


if __name__ == "__main__":
    unittest.main()
