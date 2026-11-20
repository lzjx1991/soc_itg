import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.hierarchical import build_hierarchy, emit_hierarchy

INSTANCES = [
    {"name": "insta"},
    {"name": "instb", "parent": "insta"},
    {"name": "instc", "parent": "instb", "module": "instc_mod",
     "ports": [{"name": "c", "direction": "inout", "width": 1}]},
]


class HierarchicalTest(unittest.TestCase):
    def test_feedthrough(self):
        modules, top = build_hierarchy(INSTANCES, ["insta.a = insta.instb.instc.c"])
        self.assertEqual(top, "insta")
        self.assertEqual(set(modules), {"insta", "instb"})

        instb = modules["instb"]
        self.assertTrue(any(p["name"] == "net_0_pt" for p in instb.ports))
        text_b = emit_hierarchy(modules)["instb"]
        self.assertIn("assign net_0_pt = net_0_w_instb;", text_b)
        self.assertIn(".c(net_0_w_instb)", text_b)

        insta = modules["insta"]
        self.assertTrue(any(p["name"] == "a" for p in insta.ports))
        text_a = emit_hierarchy(modules)["insta"]
        self.assertIn(".net_0_pt(net_0)", text_a)
        self.assertIn("assign a = net_0;", text_a)

    def test_siblings(self):
        instances = [
            {"name": "top"},
            {"name": "x", "parent": "top", "module": "x_mod", "ports": [{"name": "p", "direction": "out", "width": 8}]},
            {"name": "y", "parent": "top", "module": "y_mod", "ports": [{"name": "q", "direction": "in", "width": 8}]},
        ]
        modules, top = build_hierarchy(instances, [{"a": "top.x.p", "b": "top.y.q", "width": 8}])
        self.assertIn("top", modules)
        text = emit_hierarchy(modules)["top"]
        self.assertIn(".p(net_0)", text)
        self.assertIn(".q(net_0)", text)


if __name__ == "__main__":
    unittest.main()
