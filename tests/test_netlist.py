import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.ipxact import read_component
from soc_itg.assemble import assemble
from soc_itg.model import SoC
from soc_itg.pinmux import read_pinmux
from soc_itg.connectivity import build_netlist
from soc_itg.generators.netlist_emit import emit_netlist

DEMO = ROOT / "examples" / "demo_soc"


class NetlistTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        td = Path(self.tmp.name)
        components = {}
        for f in sorted((DEMO / "ip").glob("*.xml")):
            comp = read_component(f)
            components[comp.vlnv] = json.loads(comp.model_dump_json())
        ipdb = td / "ipdb.json"
        ipdb.write_text(json.dumps({"components": components}), encoding="utf-8")
        soc_path = td / "soc.json"
        assemble(str(ipdb), str(DEMO / "soc.yaml"), str(soc_path))
        self.soc = SoC.model_validate_json(soc_path.read_text(encoding="utf-8"))
        self.pinmux = read_pinmux(DEMO / "pinmux.xlsx")

    def tearDown(self):
        self.tmp.cleanup()

    def test_ports_are_pads(self):
        netlist = build_netlist(self.soc, self.pinmux)
        names = [p.name for p in netlist.ports]
        self.assertIn("PAD_GPIO0", names)
        self.assertEqual(len(netlist.ports), len(self.pinmux.pads))

    def test_pinmux_instance_and_pad_nets(self):
        netlist = build_netlist(self.soc, self.pinmux)
        self.assertTrue(any(i.name == "u_pinmux" for i in netlist.instances))
        self.assertTrue(any(n.name == "PAD_GPIO0" for n in netlist.nets))

    def test_emit_top(self):
        netlist = build_netlist(self.soc, self.pinmux)
        text = emit_netlist(netlist)
        self.assertIn("module demo_soc (", text)
        self.assertIn("inout  wire PAD_GPIO0", text)
        self.assertIn("demo_soc_pinmux u_pinmux", text)
        self.assertIn(".pad_gpio0(PAD_GPIO0)", text)

    def test_no_double_driver_on_pads(self):
        netlist = build_netlist(self.soc, self.pinmux)
        for net in netlist.nets:
            if net.tri_state:
                continue
            drivers = [ep for ep in net.endpoints if ep.direction == "out"]
            self.assertLessEqual(len(drivers), 1, f"net {net.name} has multiple drivers")

    def test_tie_and_unconnect(self):
        netlist = build_netlist(self.soc, self.pinmux)
        ties = {(t.instance, t.port): t.value for t in netlist.ties}
        self.assertEqual(ties.get(("cpu0", "halt")), 0)
        text = emit_netlist(netlist)
        self.assertIn(".halt(1'b0)", text)
        self.assertIn(".dbg()", text)


if __name__ == "__main__":
    unittest.main()
