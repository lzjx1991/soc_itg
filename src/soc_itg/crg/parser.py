"""Input parsing: .xlsx (multi-sheet) or a directory of per-sheet .csv files."""
import csv
import os

from openpyxl import load_workbook

from .model import ClkNode, Field, Model, Port, Reg, RstNode

SHEET_COLS = {
    "top_cfg":    ({"KEY", "VALUE"}, set()),
    "ports":      ({"NAME", "KIND"}, {"FREQ_MHZ", "DESC"}),
    "clock_plan": ({"NAME", "TYPE", "PARENT"},
                   {"PARENT2", "RATIO_DEF", "RATIO_MAX", "GATE", "HW_EN",
                    "RST", "EXPORT", "DESC"}),
    "reset_plan": ({"NAME", "TYPE"},
                   {"PARENT", "HW_SRC", "SW", "CLK", "MCP", "EXPORT", "DESC"}),
    "reg_map":    ({"ADDR", "REG", "FIELD", "MSB", "LSB", "ACCESS", "RESET"},
                   {"DESC"}),
}
OPTIONAL_SHEETS = {"reg_map"}  # reg_map is auto-derived when absent

GATE_TRUE = {"是", "yes", "y", "1", "true", "on"}
GATE_FALSE = {"", "否", "no", "n", "0", "false", "off"}


def parse_gate(value, loc, issues):
    t = (value or "").strip().lower()
    if t in GATE_TRUE:
        return True
    if t in GATE_FALSE:
        return False
    issues.append(f"{loc}: GATE '{value}' must be 是/yes or 否/no")
    return False


def parse_export(value, loc, issues):
    """EXPORT column: empty/是 = top output port; 否 = internal only."""
    t = (value or "").strip().lower()
    if t in ("",) or t in GATE_TRUE:
        return True
    if t in ("否", "no", "n", "0", "false", "off"):
        return False
    issues.append(f"{loc}: EXPORT '{value}' must be 是/yes (or empty) or 否/no")
    return True


class CrgError(Exception):
    """Aggregated error report; msgs is a list of located messages."""

    def __init__(self, msgs):
        self.msgs = msgs
        super().__init__("\n".join(msgs))


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip()


def to_int(s, what, loc, issues):
    t = (s or "").strip().lower()
    if not t:
        return None
    try:
        if t.startswith("0x"):
            return int(t, 16)
        if t.startswith("0b"):
            return int(t, 2)
        return int(t, 10)
    except ValueError:
        issues.append(f"{loc}: {what} '{s}' is not a valid integer")
        return None


def load_rows(path):
    """Return ({sheet: [rowdict]}, issues). Rowdicts carry '_row' (1-based)."""
    issues = []
    rows = {}
    if os.path.isdir(path):
        for sheet in SHEET_COLS:
            f = os.path.join(path, sheet + ".csv")
            if not os.path.isfile(f):
                if sheet in OPTIONAL_SHEETS:
                    rows[sheet] = []
                    continue
                issues.append(f"input: missing required file {sheet}.csv in {path}")
                continue
            with open(f, newline="") as fh:
                rdr = csv.reader(fh)
                header = [_cell(c) for c in next(rdr, [])]
                rows[sheet] = _to_dicts(header, rdr, issues, sheet, csv=True)
    elif path.lower().endswith(".xlsx"):
        if not os.path.isfile(path):
            issues.append(f"input: file not found: {path}")
            return rows, issues
        wb = load_workbook(path, data_only=True, read_only=True)
        for sheet in SHEET_COLS:
            if sheet not in wb.sheetnames:
                if sheet in OPTIONAL_SHEETS:
                    rows[sheet] = []
                    continue
                issues.append(f"input: xlsx missing required sheet '{sheet}'")
                continue
            ws = wb[sheet]
            it = ws.iter_rows(values_only=True)
            header = [_cell(c) for c in next(it, [])]
            rows[sheet] = _to_dicts(header, it, issues, sheet, csv=False)
        wb.close()
    else:
        issues.append(f"input: '{path}' is neither a .xlsx nor a directory of csv files")
    return rows, issues


def _to_dicts(header, recs, issues, sheet, csv):
    req, opt = SHEET_COLS[sheet]
    known = req | opt
    for c in header:
        if c and c not in known:
            issues.append(f"{sheet}: unknown column '{c}' (row 1)")
    missing = [c for c in req if c not in header]
    if missing:
        issues.append(f"{sheet}: missing required column(s): {', '.join(missing)}")
        return []
    out = []
    for i, rec in enumerate(recs):
        rowno = i + 2
        vals = [_cell(v) for v in rec] if not csv else [_cell(v) for v in rec]
        if not any(vals):
            continue
        d = {"_row": rowno}
        for j, col in enumerate(header):
            if col:
                d[col] = vals[j] if j < len(vals) else ""
        out.append(d)
    return out


def _derive_regs(m, clocks, resets, issues):
    """Auto-create registers/fields for control references that are not
    explicitly defined in reg_map. Rules:
      - gate enable:   <node>_cfg.en     (1 bit RW, reset 0)
      - mux select:    <node>_cfg.sel    (1 bit RW, reset 0)
      - divider ratio: <node>_cfg.ratio  (RW, width = bits(RATIO_MAX),
                                          reset = RATIO_DEF; 0/1 = bypass)
      - SW reset:      rst_ctrl.<reset>  (1 bit RW, reset 0, active-high assert)
      - registers allocated 4-byte aligned in first-reference order,
        fields packed at the lowest free bit run of the required width
    Explicit reg_map entries win (address, width, access, reset value)."""
    def reg_by_name(name):
        for r in m.regs:
            if r.name == name:
                return r
        return None

    next_addr = 0
    for r in m.regs:
        next_addr = max(next_addr, r.addr + 4)

    refs = []
    for c in clocks:
        if c.en_field:
            refs.append((c.en_field, "gate enable", c.name, 1, 0))
        if c.sel_field:
            refs.append((c.sel_field, "mux select", c.name, 1, 0))
        if c.ratio_field:
            refs.append((c.ratio_field, "divider ratio", c.name,
                         c.ratio_width, c.ratio))
    for r in resets:
        if r.sw_field:
            refs.append((r.sw_field, "sw reset", r.name, 1, 0))

    for fq, kind, owner, width, reset in refs:
        if m.field(fq) is not None:
            continue  # explicitly defined
        if "." not in fq:
            continue  # format error reported by validate()
        regname, fldname = fq.split(".", 1)
        reg = reg_by_name(regname)
        if reg is None:
            reg = Reg(addr=next_addr, name=regname)
            m.regs.append(reg)
            next_addr += 4
        used = 0
        for f in reg.fields:
            used |= f.mask
        bit = None
        for b in range(0, 32 - width + 1):
            if (used >> b) & ((1 << width) - 1) == 0:
                bit = b
                break
        if bit is None:
            issues.append(f"'{owner}': register '{regname}' has no free "
                          f"{width}-bit field for '{fldname}'")
            continue
        reg.fields.append(Field(reg=regname, name=fldname, msb=bit + width - 1,
                                lsb=bit, access="RW", reset=reset,
                                desc=f"auto: {kind} for {owner}"))


def parse(path):
    rows, issues = load_rows(path)

    def s(row, col):
        return (row.get(col) or "").strip()

    cfg = {}
    for r in rows.get("top_cfg", []):
        if s(r, "KEY"):
            cfg[s(r, "KEY")] = s(r, "VALUE")
    module = cfg.get("MODULE", "")
    version = cfg.get("VERSION", "")
    if not module:
        issues.append("top_cfg: MODULE is required")
    if not version:
        issues.append("top_cfg: VERSION is required")

    ports = []
    for r in rows.get("ports", []):
        loc = f"ports row {r['_row']}"
        freq = None
        if s(r, "KIND") == "clk":
            try:
                freq = float(s(r, "FREQ_MHZ"))
            except ValueError:
                issues.append(f"{loc}: FREQ_MHZ '{s(r, 'FREQ_MHZ')}' is not a number")
        ports.append(Port(s(r, "NAME"), s(r, "KIND").lower(), freq, s(r, "DESC")))

    clocks = []
    for r in rows.get("clock_plan", []):
        loc = f"clock_plan row {r['_row']}"
        ratio = to_int(s(r, "RATIO_DEF"), "RATIO_DEF", loc, issues)
        ratio_max = to_int(s(r, "RATIO_MAX"), "RATIO_MAX", loc, issues)
        clocks.append(ClkNode(
            name=s(r, "NAME"), type=s(r, "TYPE").lower(), parent=s(r, "PARENT"),
            parent2=s(r, "PARENT2") or None, ratio=ratio, ratio_max=ratio_max,
            gate=parse_gate(s(r, "GATE"), loc, issues),
            hw_en=s(r, "HW_EN") or None,
            rst=s(r, "RST") or None, desc=s(r, "DESC"),
            exported=parse_export(s(r, "EXPORT"), loc, issues)))
    # auto control-field convention: <node>_cfg.en / .sel / .ratio
    for c in clocks:
        if c.gate:
            c.en_field = f"{c.name}_cfg.en"
        if c.type == "mux2":
            c.sel_field = f"{c.name}_cfg.sel"
        if c.sw_ratio:
            c.ratio_field = f"{c.name}_cfg.ratio"

    resets = []
    for r in rows.get("reset_plan", []):
        loc = f"reset_plan row {r['_row']}"
        resets.append(RstNode(
            name=s(r, "NAME"), type=s(r, "TYPE").lower(),
            parent=s(r, "PARENT") or None, hw_src=s(r, "HW_SRC") or None,
            sw=parse_gate(s(r, "SW"), loc, issues),
            clk=s(r, "CLK") or None, desc=s(r, "DESC"),
            mcp=to_int(s(r, "MCP"), "MCP", loc, issues),
            exported=parse_export(s(r, "EXPORT"), loc, issues)))
    for r in resets:
        if r.sw:
            r.sw_field = f"rst_ctrl.{r.name}"

    # reg_map: group rows by address into Reg/Field
    by_addr = {}
    for r in rows.get("reg_map", []):
        loc = f"reg_map row {r['_row']}"
        addr = to_int(s(r, "ADDR"), "ADDR", loc, issues)
        msb = to_int(s(r, "MSB"), "MSB", loc, issues)
        lsb = to_int(s(r, "LSB"), "LSB", loc, issues)
        rstv = to_int(s(r, "RESET"), "RESET", loc, issues)
        regname = s(r, "REG")
        fldname = s(r, "FIELD")
        if regname and fldname:
            key = regname if addr is None else addr
            ent = by_addr.setdefault(key, {"addr": addr, "reg": regname, "fields": []})
            if ent["reg"] != regname:
                issues.append(f"{loc}: REG '{regname}' conflicts with "
                              f"'{ent['reg']}' at same address")
            ent["fields"].append((r["_row"], fldname, msb, lsb,
                                  s(r, "ACCESS").upper(), rstv, s(r, "DESC")))
    regs = []
    for key, ent in by_addr.items():
        if ent["addr"] is None:
            issues.append(f"reg_map: REG '{ent['reg']}' has invalid/missing ADDR")
            continue
        reg = Reg(addr=ent["addr"], name=ent["reg"])
        for rowno, fldname, msb, lsb, acc, rstv, desc in ent["fields"]:
            reg.fields.append(Field(reg=ent["reg"], name=fldname, msb=msb or 0,
                                    lsb=lsb or 0, access=acc, reset=rstv or 0,
                                    desc=desc))
        regs.append(reg)
    regs.sort(key=lambda r: r.addr)

    if issues:
        raise CrgError(issues)
    m = Model(module=module, version=version, input_path=path,
              ports=ports, clocks=clocks, resets=resets, regs=regs)
    _derive_regs(m, clocks, resets, issues)
    m.regs.sort(key=lambda r: r.addr)
    if issues:
        raise CrgError(issues)
    return m
