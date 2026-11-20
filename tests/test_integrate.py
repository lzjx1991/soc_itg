import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.integrate import plan_integration, integration_order
from soc_itg.workspace import load_workspace


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class IntegrateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        _write(root / "workspace.yaml", "name: ws\ndefault_top: repo_top\nrepos: [repo_top, repo_a, repo_b]\n")
        _write(root / "repo_top" / "repo_top_info.yaml", "name: repo_top\nvlnv: acme.com:L:top:1.0\n")
        _write(root / "repo_top" / "soc.yaml",
               "design:\n  name: top\n  instances:\n"
               "    - { name: a, repo: repo_a, integrate: true }\n"
               "    - { name: b, repo: repo_b, integrate: false }\n")
        _write(root / "repo_a" / "repo_a_info.yaml", "name: repo_a\nvlnv: acme.com:L:a:1.0\n")
        _write(root / "repo_b" / "repo_b_info.yaml", "name: repo_b\nvlnv: acme.com:L:b:1.0\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_order(self):
        ws = load_workspace(Path(self.tmp.name))
        order = integration_order(ws, ws.repo("repo_top"))
        self.assertEqual(order, ["repo_a", "repo_top"])
        self.assertNotIn("repo_b", order)

    def test_plan(self):
        ws, repo, repos = plan_integration(Path(self.tmp.name) / "repo_top")
        self.assertEqual(repo.name, "repo_top")
        self.assertEqual([r.name for r in repos], ["repo_a", "repo_top"])


if __name__ == "__main__":
    unittest.main()
