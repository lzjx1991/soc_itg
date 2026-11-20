import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.generators.rtl_ports import extract_ports

SRC = """module u (
  input clk,
  input [7:0] d,
  output reg q,
  inout [3:0] pad
);
endmodule
"""


class RtlPortsTest(unittest.TestCase):
    def test_extract(self):
        name, ports = extract_ports(SRC, module="u")
        self.assertEqual(name, "u")
        by_name = {p["name"]: p for p in ports}
        self.assertEqual(by_name["clk"]["width"], 1)
        self.assertEqual(by_name["d"]["width"], 8)
        self.assertEqual(by_name["d"]["direction"], "input")
        self.assertEqual(by_name["pad"]["direction"], "inout")
        self.assertEqual(by_name["pad"]["width"], 4)


if __name__ == "__main__":
    unittest.main()
