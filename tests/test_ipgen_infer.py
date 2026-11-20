import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.model import Port
from soc_itg.generators.ipgen import infer_apb


class IpgenInferTest(unittest.TestCase):
    def test_infer_apb(self):
        ports = [Port(name=n, direction="in") for n in
                 ["pclk", "presetn", "paddr", "psel", "penable", "pwrite", "pwdata", "prdata", "pready", "pslverr"]]
        bus = infer_apb(ports)
        self.assertIsNotNone(bus)
        self.assertEqual(bus.bus_type, "APB")
        self.assertEqual(bus.port_maps["PCLK"], "pclk")
        self.assertEqual(bus.port_maps["PSELx"], "psel")

    def test_not_apb(self):
        self.assertIsNone(infer_apb([Port(name="a"), Port(name="b")]))


if __name__ == "__main__":
    unittest.main()
