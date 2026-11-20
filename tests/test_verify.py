import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.model.netlist import Netlist, PortSpec
from soc_itg.generators.verify import generate_tb


class VerifyTest(unittest.TestCase):
    def test_tb_skeleton(self):
        netlist = Netlist(top="demo", ports=[
            PortSpec(name="pad_a", direction="inout", width=1),
            PortSpec(name="pad_d", direction="inout", width=8),
        ])
        text = generate_tb(netlist)
        self.assertIn("module tb_demo;", text)
        self.assertIn("demo u_dut (", text)
        self.assertIn(".pad_a(pad_a)", text)
        self.assertIn(".pad_d(pad_d)", text)
        self.assertIn("$finish;", text)


if __name__ == "__main__":
    unittest.main()
