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
from soc_itg.topcsr import read_topcsr
from soc_itg.connectivity import build_netlist
from soc_itg.generators.netlist_emit import emit_netlist

DEMO = ROOT / "examples" / "demo_soc"


class TopCSRTest(unittest.TestCase):
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
        self.topcsr = read_topcsr(DEMO / "top_csr.xlsx", module="demo_soc_top_regs")

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_registers_and_bindings(self):
        regs = [r.name for r in self.topcsr.memory_map.registers]
        self.assertEqual(regs, ["SYS_CTRL", "STATUS", "INT", "SCRATCH"])
        self.assertEqual(len(self.topcsr.bindings), 2)
        en = next(b for b in self.topcsr.bindings if b.field == "EN")
        self.assertEqual(en.targets, ["uart0.test_en"])
        busy = next(b for b in self.topcsr.bindings if b.field == "BUSY")
        self.assertEqual(busy.access, "ro")
        int_reg = next(r for r in self.topcsr.memory_map.registers if r.name == "INT")
        irq = next(f for f in int_reg.fields if f.name == "IRQ")
        self.assertEqual(irq.access, "rw")
        self.assertEqual(irq.write_action, "w1c")

    def test_netlist_includes_top_regs(self):
        netlist = build_netlist(self.soc, self.pinmux, self.topcsr)
        self.assertTrue(any(i.name == "u_top_regs" for i in netlist.instances))
        names = [n.name for n in netlist.nets]
        self.assertIn("sys_ctrl_en_uart0_test_en", names)
        self.assertIn("status_busy_uart0_irq", names)

    def test_emit_binds(self):
        netlist = build_netlist(self.soc, self.pinmux, self.topcsr)
        text = emit_netlist(netlist)
        self.assertIn("demo_soc_top_regs u_top_regs", text)
        self.assertIn(".o_sys_ctrl_en(sys_ctrl_en_uart0_test_en)", text)
        self.assertIn(".i_status_busy(status_busy_uart0_irq)", text)


if __name__ == "__main__":
    unittest.main()
