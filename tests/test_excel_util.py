import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.io.excel import (
    sheet_rows, find_sheet, header_map, forward_fill, parse_int, parse_bits, cell,
)


class ExcelUtilTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xlsx = Path(self.tmp.name) / "t.xlsx"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "regs"
        ws.append(["REG", "FIELD", "DS[3]"])
        ws["A2"] = "SYS"
        ws.merge_cells("A2:A4")
        ws["B2"] = "A"
        ws["C2"] = "0b011"
        ws["B3"] = "B"
        ws["C3"] = "1"
        ws["B4"] = "C"
        ws["C4"] = "0x2"
        wb.save(self.xlsx)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sheet_and_header(self):
        import openpyxl as ox
        wb = ox.load_workbook(self.xlsx, data_only=True)
        ws = find_sheet(wb, ["regs"])
        rows = sheet_rows(ws)
        self.assertEqual(rows[0], ["REG", "FIELD", "DS[3]"])
        aliases = {"reg": "reg", "field": "field", "ds[3]": "ds"}
        hmap = header_map(rows[0], aliases)
        self.assertEqual(hmap, {"reg": 0, "field": 1, "ds": 2})

    def test_forward_fill_merged(self):
        import openpyxl as ox
        wb = ox.load_workbook(self.xlsx, data_only=True)
        rows = sheet_rows(find_sheet(wb, ["regs"]))
        aliases = {"reg": "reg", "field": "field", "ds[3]": "ds"}
        hmap = header_map(rows[0], aliases)
        filled = forward_fill(rows[1:], [hmap["reg"]])
        self.assertEqual([r[hmap["reg"]] for r in filled], ["SYS", "SYS", "SYS"])
        self.assertEqual(cell(filled[2], hmap["field"]), "C")

    def test_parsers(self):
        self.assertEqual(parse_bits("0b011", 3), 3)
        self.assertEqual(parse_bits("011", 3), 3)
        self.assertEqual(parse_bits("0,1,1", 3), 3)
        self.assertEqual(parse_bits("0x2", 3), 2)
        self.assertEqual(parse_bits(5, 3), 5)
        self.assertEqual(parse_int("0x10"), 16)
        self.assertEqual(parse_int("bad", 7), 7)


if __name__ == "__main__":
    unittest.main()
