import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.create import scaffold_repo, scaffold_workspace, create_project

DIRS = ["pinmux", "crg", "csr", "rtl", "glue", "ipxact", "filelist", "generated", "release"]


class CreateTest(unittest.TestCase):
    def test_scaffold_repo(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "repo_x"
            scaffold_repo(path)
            self.assertTrue((path / "repo_x_info.yaml").exists())
            self.assertTrue((path / "soc.yaml").exists())
            for d in DIRS:
                self.assertTrue((path / d).is_dir(), d)

    def test_scaffold_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ws"
            scaffold_workspace(path, default_top="")
            self.assertTrue((path / "workspace.yaml").exists())

    def test_create_project_no_git(self):
        with tempfile.TemporaryDirectory() as td:
            create_project("ws", sub="repo_a", no_git=True, base=td)
            self.assertTrue((Path(td) / "ws" / "workspace.yaml").exists())
            self.assertTrue((Path(td) / "ws" / "repo_a" / "soc.yaml").exists())


if __name__ == "__main__":
    unittest.main()
