"""Data model for a parsed CRG specification."""
import re
from dataclasses import dataclass, field as dfield
from typing import List, Optional

IDENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def is_ident(s: str) -> bool:
    return bool(s) and IDENT_RE.match(s) is not None


@dataclass
class Port:
    name: str
    kind: str            # 'clk' | 'rst'
    freq_mhz: Optional[float] = None
    desc: str = ""


@dataclass
class Field:
    reg: str
    name: str
    msb: int
    lsb: int
    access: str          # 'RW' | 'RO'
    reset: int
    desc: str = ""

    @property
    def width(self) -> int:
        return self.msb - self.lsb + 1

    @property
    def shift(self) -> int:
        return self.lsb

    @property
    def mask(self) -> int:
        return ((1 << self.width) - 1) << self.lsb

    @property
    def fq(self) -> str:
        return f"{self.reg}.{self.name}"

    @property
    def wire(self) -> str:
        return f"{self.reg}_{self.name}"


@dataclass
class Reg:
    addr: int
    name: str
    fields: List[Field] = dfield(default_factory=list)

    @property
    def rw_fields(self) -> List[Field]:
        return [f for f in self.fields if f.access == "RW"]

    @property
    def ro_fields(self) -> List[Field]:
        return [f for f in self.fields if f.access == "RO"]

    @property
    def rw_mask(self) -> int:
        m = 0
        for f in self.rw_fields:
            m |= f.mask
        return m

    @property
    def ro_const(self) -> int:
        v = 0
        for f in self.ro_fields:
            v |= (f.reset & ((1 << f.width) - 1)) << f.lsb
        return v

    @property
    def q_reset(self) -> int:
        v = 0
        for f in self.rw_fields:
            v |= (f.reset & ((1 << f.width) - 1)) << f.lsb
        return v


@dataclass
class ClkNode:
    name: str
    type: str            # 'divider' | 'mux2' | '' (passthrough)
    parent: str          # branch 0 for mux2
    parent2: Optional[str] = None
    ratio: Optional[int] = None
    ratio_max: Optional[int] = None  # > ratio => SW-configurable divider
    gate: bool = False           # insert software clock gate on this node
    hw_en: Optional[str] = None  # external HW enable port name (ANDed with SW en)
    # auto-populated control field refs (convention: <node>_cfg.en / .sel / .ratio)
    en_field: Optional[str] = None
    sel_field: Optional[str] = None
    ratio_field: Optional[str] = None
    rst: Optional[str] = None        # reset for node internals, None = default
    exported: bool = True            # False = internal only, no top port
    desc: str = ""

    @property
    def sw_ratio(self) -> bool:
        return (self.ratio is not None and self.ratio_max is not None
                and self.ratio_max > self.ratio)

    @property
    def ratio_width(self) -> int:
        # match crg_clk_divider port [$clog2(MAX_RATIO):0]
        return (self.ratio_max - 1).bit_length() + 1 if self.ratio_max >= 2 \
            else 2


@dataclass
class RstNode:
    name: str
    type: str            # 'sync' | 'passthrough'
    parent: Optional[str] = None   # parent reset (node or rst input port)
    hw_src: Optional[str] = None   # external HW reset source (rst input port), ANDed
    sw: bool = False              # software reset (auto rst_ctrl.<name> bit, active-high assert)
    clk: Optional[str] = None
    sw_field: Optional[str] = None  # auto-populated: rst_ctrl.<name>
    mcp: Optional[int] = None  # MCP clock gating: idle cycles after release
    exported: bool = True           # False = internal only, no top port
    desc: str = ""


@dataclass
class Model:
    module: str
    version: str
    input_path: str
    ports: List[Port] = dfield(default_factory=list)
    clocks: List[ClkNode] = dfield(default_factory=list)
    resets: List[RstNode] = dfield(default_factory=list)
    regs: List[Reg] = dfield(default_factory=list)

    # ---- lookups -----------------------------------------------------
    def port(self, name):
        for p in self.ports:
            if p.name == name:
                return p
        return None

    def clock(self, name):
        for c in self.clocks:
            if c.name == name:
                return c
        return None

    def reset(self, name):
        for r in self.resets:
            if r.name == name:
                return r
        return None

    def field(self, fq):
        if "." not in fq:
            return None
        reg, fld = fq.split(".", 1)
        for r in self.regs:
            if r.name == reg:
                for f in r.fields:
                    if f.name == fld:
                        return f
        return None

    @property
    def input_clks(self):
        return [p for p in self.ports if p.kind == "clk"]

    @property
    def input_rsts(self):
        return [p for p in self.ports if p.kind == "rst"]

    def clk_freq(self, name):
        p = self.port(name)
        return p.freq_mhz if p and p.kind == "clk" else None

    def is_clk_source(self, name):
        p = self.port(name)
        if p:
            return p.kind == "clk"
        return self.clock(name) is not None

    def is_rst_source(self, name):
        return self.reset(name) is not None or \
            (self.port(name) is not None and self.port(name).kind == "rst")
