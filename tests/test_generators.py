import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.model import Component, Port, Instance, SoC, MemoryMap, Register, RegisterField
from soc_itg.generators.regblock import generate_regblock
from soc_itg.generators.pinmux import generate_pinmux
from soc_itg.pinmux.model import Pinmux, Pad, ConfigField, FunctionShareEntry, BistShareEntry, BistEntry
from soc_itg.pinmux.registers import build_registers


class RegblockTest(unittest.TestCase):
    def test_generates_apb4_with_security(self):
        mm = MemoryMap(name="m", registers=[
            Register(name="CTRL", offset="0x0", fields=[
                RegisterField(name="EN", msb=0, lsb=0, access="rw", reset=0, security="secure"),
            ]),
            Register(name="STAT", offset="0x4", fields=[
                RegisterField(name="CODE", msb=7, lsb=4, access="ro", reset=0),
            ]),
        ])
        text = generate_regblock("dut_regs", mm)
        self.assertIn("err_irq", text)
        self.assertIn("pprot[1]", text)
        self.assertIn("input  wire [3:0] i_stat_code", text)
        self.assertIn("output reg  o_ctrl_en", text)
        self.assertIn("pslverr", text)

    def test_supports_full_types(self):
        mm = MemoryMap(name="m", registers=[
            Register(name="INT", offset="0x0", fields=[
                RegisterField(name="IRQ", msb=0, lsb=0, access="rw", write_action="w1c"),
                RegisterField(name="CNT", msb=7, lsb=4, access="ro"),
            ]),
            Register(name="WO", offset="0x4", fields=[
                RegisterField(name="CFG", msb=0, lsb=0, access="wo"),
            ]),
            Register(name="RC", offset="0x8", fields=[
                RegisterField(name="V", msb=7, lsb=0, access="rw", read_action="rc"),
            ]),
            Register(name="ONCE", offset="0xC", fields=[
                RegisterField(name="K", msb=0, lsb=0, access="rw1"),
            ]),
        ])
        text = generate_regblock("dut_regs", mm)
        self.assertIn("pstrb", text)
        self.assertIn("o_int_irq & ~pwdata", text)
        self.assertIn("input  wire [3:0] i_int_cnt", text)
        self.assertIn("o_wo_cfg", text)
        self.assertIn("done_once_k", text)
        self.assertIn("o_rc_v <= 8'd0", text)


class PinmuxRegistersTest(unittest.TestCase):
    def _pinmux(self):
        return Pinmux(
            pads=[
                Pad(name="PAD_A", type="digital", wrapper="W", security="secure",
                    config={"DS": ConfigField(name="DS", width=3, default=3)}),
                Pad(name="PAD_ANA", type="analog", wrapper="A"),
            ],
            function_share=[FunctionShareEntry(group="A", pad="PAD_A", functions={"function0": "cpu.paddr"})],
            bist_share=[BistShareEntry(pad="PAD_A", functions={"bist_func0": "cpu.paddr"})],
            bist_entries=[BistEntry(bist_mode=0, pad="PAD_A", value=1)],
        )

    def test_register_model(self):
        pm = self._pinmux()
        reg_map, cfg_meta = build_registers(pm)
        names = [r.name for r in reg_map.registers]
        self.assertIn("cfg_PAD_A", names)
        self.assertIn("sel_A", names)
        self.assertIn("bist_mode", names)
        self.assertEqual(cfg_meta["PAD_A"]["width"], 8)
        self.assertEqual(cfg_meta["PAD_A"]["bits"], 3)

    def test_generate_pinmux(self):
        pm = self._pinmux()
        reg_map, cfg_meta = build_registers(pm)
        comp = Component(vlnv="acme:CPU:cpu:1", ports=[Port(name="paddr", direction="out", width=8)])
        soc = SoC(top="dut", instances=[Instance(name="cpu", vlnv="acme:CPU:cpu:1")],
                  components={"acme:CPU:cpu:1": comp})
        text = generate_pinmux(soc, pm, reg_map, cfg_meta)
        self.assertIn("module dut_pinmux", text)
        self.assertIn("pad_wrapper", text)
        self.assertIn("pad_a_din", text)
        self.assertIn("ip_cpu_paddr", text)
        self.assertIn("o_sel_a_sel", text)
        self.assertEqual(text.count("assign a_dout"), 1)


if __name__ == "__main__":
    unittest.main()
