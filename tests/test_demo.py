import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.ipxact import read_component, detect_version
from soc_itg.assemble import assemble
from soc_itg.checkers import run_checks
from soc_itg.model import SoC

DEMO = ROOT / "examples" / "demo_soc"


class DemoPipelineTest(unittest.TestCase):
    def test_detect_version(self):
        self.assertEqual(detect_version(DEMO / "ip" / "cpu.xml"), "ieee-1685-2009")

    def test_parse_component(self):
        comp = read_component(DEMO / "ip" / "uart.xml")
        self.assertEqual(comp.vlnv, "acme.com:PERIPH:uart:1.0.0")
        self.assertIsNotNone(comp.bus_if("APB_Slave"))
        self.assertEqual(comp.bus_if("APB_Slave").port_maps["PADDR"], "paddr")
        self.assertEqual(len(comp.memory_maps[0].registers), 3)
        int_reg = next(r for r in comp.memory_maps[0].registers if r.name == "INT")
        irq = next(f for f in int_reg.fields if f.name == "IRQ")
        cnt = next(f for f in int_reg.fields if f.name == "CNT")
        self.assertEqual(irq.write_action, "w1c")
        self.assertEqual(cnt.access, "ro")

    def test_assemble_and_check(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            components = {}
            for f in sorted((DEMO / "ip").glob("*.xml")):
                comp = read_component(f)
                components[comp.vlnv] = json.loads(comp.model_dump_json())
            ipdb = td / "ipdb.json"
            ipdb.write_text(json.dumps({"schema_version": 1, "tool_version": "0.1.0", "components": components}), encoding="utf-8")
            soc_path = td / "soc.json"
            assemble(str(ipdb), str(DEMO / "soc.yaml"), str(soc_path))
            soc = SoC.model_validate_json(soc_path.read_text(encoding="utf-8"))
            findings = run_checks(soc)
            errors = [f for f in findings if f["level"] == "error"]
            self.assertEqual(errors, [])
            self.assertEqual(len(soc.instances), 2)
            self.assertIn("uart0", soc.register_models)


if __name__ == "__main__":
    unittest.main()
