import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.io.config import expand_env, load_yaml
from soc_itg.workspace import load_workspace, find_workspace, current_repo


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "workspace.yaml").write_text("name: ws\ndefault_top: repo_a\nrepos: [repo_a, repo_b]\n", encoding="utf-8")
        ra = self.root / "repo_a"
        ra.mkdir()
        (ra / "repo_a_info.yaml").write_text("name: repo_a\nvlnv: acme.com:Lib:a:1.0.0\n", encoding="utf-8")
        (ra / "soc.yaml").write_text("design:\n  name: top_a\n  instances: []\n", encoding="utf-8")
        rb = self.root / "repo_b"
        rb.mkdir()
        (rb / "repo_b_info.yaml").write_text("name: repo_b\nvlnv: acme.com:Lib:b:2.0.0\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_load(self):
        ws = load_workspace(self.root)
        self.assertEqual(ws.name, "ws")
        self.assertEqual(ws.default_top, "repo_a")
        self.assertEqual(set(ws.repos), {"repo_a", "repo_b"})
        self.assertEqual(ws.repo("repo_a").soc["design"]["name"], "top_a")

    def test_resolve_name_and_vlnv(self):
        ws = load_workspace(self.root)
        self.assertEqual(ws.resolve("repo_b").name, "repo_b")
        self.assertEqual(ws.resolve("acme.com:Lib:b:2.0.0").name, "repo_b")
        self.assertIsNone(ws.resolve("nope"))

    def test_find_and_current(self):
        (self.root / "repo_a" / "sub").mkdir()
        self.assertEqual(find_workspace(self.root / "repo_a" / "sub"), self.root.resolve())
        ws = load_workspace(self.root)
        self.assertEqual(current_repo(ws, self.root / "repo_a" / "sub").name, "repo_a")

    def test_env_expand(self):
        os.environ["MY_DIR"] = "/opt/x"
        cfg = self.root / "t.yaml"
        cfg.write_text("a: ${MY_DIR}/y\nb: ${UNSET_XYZ}\n", encoding="utf-8")
        data = load_yaml(cfg)
        self.assertEqual(data["a"], "/opt/x/y")
        self.assertEqual(data["b"], "${UNSET_XYZ}")
        self.assertEqual(expand_env("${MY_DIR}"), "/opt/x")


if __name__ == "__main__":
    unittest.main()
