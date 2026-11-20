import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.release import release
from soc_itg.workspace import load_repo


class ReleaseTest(unittest.TestCase):
    def test_release(self):
        with tempfile.TemporaryDirectory() as td:
            repo_path = Path(td) / "repo_a"
            (repo_path / "generated" / "rtl").mkdir(parents=True)
            (repo_path / "generated" / "rtl" / "x.v").write_text("module x; endmodule\n", encoding="utf-8")
            repo = load_repo(repo_path)
            out = release(repo, "1.0.0")
            self.assertTrue((out / "generated" / "rtl" / "x.v").exists())
            self.assertTrue((out / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
