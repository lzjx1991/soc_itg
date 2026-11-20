import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.model import Component, Port, BusInterface, MemoryMap, Register, RegisterField, FileItem, FileSet
from soc_itg.ipxact.writer import write_component_file
from soc_itg.ipxact import read_component


class WriterTest(unittest.TestCase):
    def test_roundtrip(self):
        comp = Component(
            vlnv="acme.com:L:u:1.0",
            ports=[Port(name="clk", direction="in", width=1), Port(name="d", direction="out", width=8)],
            bus_interfaces=[BusInterface(name="APB", mode="slave", bus_type="APB", port_maps={"PCLK": "clk"})],
            memory_maps=[MemoryMap(name="M", registers=[
                Register(name="CTRL", offset="0x0", fields=[RegisterField(name="EN", msb=0, lsb=0, access="rw", reset=0)])])],
            file_sets=[FileSet(name="rtl", files=[FileItem(name="rtl/u.v", file_type="verilogSource")])],
        )
        with tempfile.TemporaryDirectory() as td:
            path = write_component_file(comp, Path(td) / "u.xml")
            back = read_component(path)
            self.assertEqual(back.vlnv, "acme.com:L:u:1.0")
            self.assertEqual(back.port("d").width, 8)
            self.assertEqual(back.bus_if("APB").port_maps["PCLK"], "clk")
            self.assertEqual(back.memory_maps[0].registers[0].fields[0].name, "EN")
            self.assertEqual(back.file_sets[0].files[0].name, "rtl/u.v")


if __name__ == "__main__":
    unittest.main()
