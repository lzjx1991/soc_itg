import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.model import Component, Port, BusInterface, Instance, SoC, Connection
from soc_itg.checkers.width import check_width


class WidthTest(unittest.TestCase):
    def _soc(self, aw, bw):
        a = Component(vlnv="a", ports=[Port(name="d", direction="out", width=aw)],
                      bus_interfaces=[BusInterface(name="B", mode="master", bus_type="X", port_maps={"D": "d"})])
        b = Component(vlnv="b", ports=[Port(name="d", direction="in", width=bw)],
                      bus_interfaces=[BusInterface(name="B", mode="slave", bus_type="X", port_maps={"D": "d"})])
        return SoC(top="t", instances=[Instance(name="a", vlnv="a"), Instance(name="b", vlnv="b")],
                   components={"a": a, "b": b},
                   connections=[Connection(a="a.B", b="b.B")])

    def test_mismatch(self):
        findings = check_width(self._soc(8, 16))
        self.assertTrue(any(f["code"] == "WIDTH_MISMATCH" for f in findings))

    def test_match(self):
        findings = check_width(self._soc(8, 8))
        self.assertEqual([f for f in findings if f["code"] == "WIDTH_MISMATCH"], [])


if __name__ == "__main__":
    unittest.main()
