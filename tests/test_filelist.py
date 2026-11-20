import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.generators.filelist import parse_filelist, generate_filelists
from soc_itg.workspace import load_repo

COMP = """<?xml version="1.0"?>
<spirit:component xmlns:spirit="http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009">
  <spirit:vendor>acme.com</spirit:vendor><spirit:library>L</spirit:library>
  <spirit:name>u</spirit:name><spirit:version>1.0</spirit:version>
  <spirit:fileSets><spirit:fileSet><spirit:name>rtl</spirit:name>
    <spirit:file><spirit:name>rtl/uart.v</spirit:name><spirit:fileType>verilogSource</spirit:fileType></spirit:file>
  </spirit:fileSet></spirit:fileSets>
</spirit:component>
"""


class FilelistTest(unittest.TestCase):
    def test_parse_filelist(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "inner.f").write_text("rtl/inner.v\n", encoding="utf-8")
            (d / "top.f").write_text(
                "# comment\n+incdir+inc\n+define+FOO=1\n-y lib\n-v cells.v\n-f inner.f\nrtl/a.v \\\n  rtl/b.v\n",
                encoding="utf-8",
            )
            result = parse_filelist(d / "top.f")
            self.assertIn("inc", result["incdirs"])
            self.assertIn("FOO=1", result["defines"])
            self.assertIn("lib", result["lib_dirs"])
            self.assertIn("cells.v", result["lib_files"])
            self.assertIn("rtl/inner.v", result["files"])
            self.assertIn("rtl/a.v", result["files"])
            self.assertIn("rtl/b.v", result["files"])

    def test_generate_filelists(self):
        with tempfile.TemporaryDirectory() as td:
            repo_path = Path(td) / "repo_u"
            (repo_path / "ipxact").mkdir(parents=True)
            (repo_path / "ipxact" / "comp.xml").write_text(COMP, encoding="utf-8")
            gen = repo_path / "generated" / "rtl"
            gen.mkdir(parents=True)
            (gen / "top.v").write_text("module top; endmodule\n", encoding="utf-8")
            (gen / "pkg.sv").write_text("package pkg; endpackage\n", encoding="utf-8")
            repo = load_repo(repo_path)
            result = generate_filelists(repo, top_name="top")
            files = result["files"]
            self.assertTrue(files[0].endswith("pkg.sv"))
            self.assertTrue(files[-1].endswith("top.v"))
            self.assertTrue(any(f.endswith("uart.v") for f in files))
            self.assertTrue((repo_path / "generated" / "filelist" / "sim.f").exists())


if __name__ == "__main__":
    unittest.main()
