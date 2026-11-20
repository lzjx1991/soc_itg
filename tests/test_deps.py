import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.deps import check
from soc_itg.workspace import load_workspace


class DepsTest(unittest.TestCase):
    def test_missing_repo(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "workspace.yaml").write_text("name: ws\nrepos: [repo_a, repo_b]\n", encoding="utf-8")
            (root / "repo_a").mkdir()
            (root / "repo_a" / "repo_a_info.yaml").write_text("name: repo_a\n", encoding="utf-8")
            ws = load_workspace(root)
            findings = check(ws)
            self.assertTrue(any(f["code"] == "REPO_MISSING" and "repo_b" in f["msg"] for f in findings))


if __name__ == "__main__":
    unittest.main()
