import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.ipxact import read_component, detect_version
from soc_itg.ipxact.resolve import resolve, repo_components
from soc_itg.workspace import load_workspace

XML_2014 = """<?xml version="1.0"?>
<ipxact:component xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2014">
  <ipxact:vendor>acme.com</ipxact:vendor>
  <ipxact:library>L</ipxact:library>
  <ipxact:name>core</ipxact:name>
  <ipxact:version>1.0</ipxact:version>
  <ipxact:model>
    <ipxact:ports>
      <ipxact:port><ipxact:name>clk</ipxact:name><ipxact:direction>in</ipxact:direction></ipxact:port>
    </ipxact:ports>
  </ipxact:model>
  <ipxact:busInterfaces>
    <ipxact:busInterface ipxact:interfaceMode="target">
      <ipxact:name>APB</ipxact:name>
      <ipxact:busType vendor="amba.com" library="AMBA3" name="APB" version="r2p0_0"/>
    </ipxact:busInterface>
  </ipxact:busInterfaces>
</ipxact:component>
"""


class MultiVersionTest(unittest.TestCase):
    def test_2014_interface_mode(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "core.xml"
            f.write_text(XML_2014, encoding="utf-8")
            self.assertEqual(detect_version(f), "ieee-1685-2014")
            comp = read_component(f)
            self.assertEqual(comp.vlnv, "acme.com:L:core:1.0")
            self.assertEqual(comp.bus_if("APB").mode, "slave")


class ResolveTest(unittest.TestCase):
    def test_resolve_by_name_and_vlnv(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "workspace.yaml").write_text("name: ws\nrepos: [ip_a]\n", encoding="utf-8")
            repo = root / "ip_a"
            (repo / "ipxact").mkdir(parents=True)
            (repo / "ip_a_info.yaml").write_text("name: ip_a\nvlnv: acme.com:L:core:1.0\n", encoding="utf-8")
            (repo / "ipxact" / "core.xml").write_text(XML_2014, encoding="utf-8")
            ws = load_workspace(root)
            r1, c1 = resolve(ws, "ip_a")
            self.assertEqual(r1.name, "ip_a")
            self.assertEqual(c1.vlnv, "acme.com:L:core:1.0")
            r2, c2 = resolve(ws, "acme.com:L:core:1.0")
            self.assertEqual(r2.name, "ip_a")
            self.assertIn("acme.com:L:core:1.0", repo_components(ws.repo("ip_a")))


if __name__ == "__main__":
    unittest.main()
