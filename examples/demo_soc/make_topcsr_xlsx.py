import sys
from pathlib import Path
import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from soc_itg.regtypes import TYPE_REFERENCE

OUT = Path(__file__).resolve().parent / "top_csr.xlsx"

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "registers"
ws.append(["block", "reg", "offset", "field", "msb", "lsb", "type", "reset", "security", "bind"])
ws.append(["TOP", "SYS_CTRL", "0x0", "EN", 0, 0, "rw", 0, "nonsecure", "uart0.test_en"])
ws.append(["TOP", "SYS_CTRL", "0x0", "MODE", 2, 1, "rw", 0, "nonsecure", None])
ws.append(["TOP", "STATUS", "0x4", "BUSY", 0, 0, "ro", 0, "nonsecure", "uart0.irq"])
ws.append(["TOP", "INT", "0x8", "IRQ", 0, 0, "w1c", 0, "nonsecure", None])
ws.append(["TOP", "SCRATCH", "0xC", "VAL", 7, 0, "rw", 0, "nonsecure", None])

ref = wb.create_sheet("type_ref")
for row in TYPE_REFERENCE:
    ref.append(list(row))

wb.save(OUT)
print(f"wrote {OUT}")
