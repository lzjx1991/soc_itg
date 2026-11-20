"""Code generation: model -> context -> Jinja2 templates -> output tree.

Generated hierarchy (three sub-blocks under the top):
    <mod>_top      : wiring only (clk_tree + rst_tree + regs)
    <mod>_clk_tree : divider / mux2 / software+HW gates
    <mod>_rst_tree : reset synchronizers (SW reset + external HW source merge)
    <mod>_regs     : APB register block
"""
import datetime
import hashlib
import json
import math
import os
import shutil

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from . import __version__
from .parser import parse
from .validate import validate

WINDOW_NS = 20000     # TB measurement window per phase
TOL = 8               # edge-count tolerance
PCLK_HALF_NS = 10     # TB APB clock half period (50 MHz)

_HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(_HERE, "templates")
LIB_DIR = os.path.join(_HERE, "lib")
LIB_FILES = ["crg_sync_cell.sv", "crg_reset_sync.sv", "crg_clk_divider.sv",
             "crg_clk_gate.sv", "crg_clk_mux2_glitchless.sv",
             "crg_rst_mcp.sv", "crg_clk_gate_mcp.sv"]


def _input_digest(path):
    """sha256 of an input file, or of all files in an input directory."""
    h = hashlib.sha256()
    if os.path.isdir(path):
        for fn in sorted(os.listdir(path)):
            h.update(fn.encode())
            with open(os.path.join(path, fn), "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
    else:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    return h.hexdigest()


def _hw_val(node, hw):
    """HW-enable value for a clock node in a phase (default 1)."""
    if node.hw_en:
        return hw.get(node.hw_en, 1)
    return 1


def _field_val(m, fq, val):
    f = m.field(fq)
    if f is None:
        return None
    return val.get(fq, f.reset)


def _freq(m, name, val, hw, memo):
    """Frequency (MHz) of a clock source under SW field values `val` and HW
    enable values `hw`. 0.0 = no edges (gated off); None = unpredictable."""
    if name in memo:
        return memo[name]
    p = m.port(name)
    if p and p.kind == "clk":
        f = p.freq_mhz
    else:
        c = m.clock(name)
        if c is None:
            f = None
        else:
            if c.type == "divider":
                pf = _freq(m, c.parent, val, hw, memo)
                if c.ratio_field:
                    rv = _field_val(m, c.ratio_field, val)
                    if rv is None:
                        f = None
                    elif pf is None:
                        f = None
                    elif rv <= 1:
                        f = pf          # bypass (ratio 0/1)
                    elif pf == 0:
                        f = 0.0
                    else:
                        f = pf / rv
                else:
                    f = None if pf is None else (0.0 if pf == 0
                                                 else pf / c.ratio)
            elif c.type == "mux2":
                sel = _field_val(m, c.sel_field, val)
                if sel in (0, 1):
                    f = _freq(m, c.parent if sel == 0 else c.parent2,
                              val, hw, memo)
                else:
                    f = None
            else:
                f = _freq(m, c.parent, val, hw, memo)
            if (c.gate or c.hw_en) and f is not None:
                on = 1
                if c.gate and c.en_field and \
                        _field_val(m, c.en_field, val) == 0:
                    on = 0
                if _hw_val(c, hw) == 0:
                    on = 0
                f = f if on else 0.0
    memo[name] = f
    return f


def _build_phases(m):
    """Generic auto phases:
    p1 reset defaults -> p2 SW enables on -> p3 mux select = 1
    -> p4 HW enables off (if any) -> p5 SW reset toggle (if any)."""
    ens = [c.en_field for c in m.clocks if c.gate and c.en_field]
    sels = [c.sel_field for c in m.clocks if c.sel_field]
    hw_ports = [c.hw_en for c in m.clocks if c.hw_en]
    sw_resets = [r for r in m.resets if r.sw]
    words = {r.name: r.q_reset for r in m.regs}
    written = {r.name: r.q_reset for r in m.regs}
    phases = []

    def expects_for(val, hw):
        memo = {}
        out = []
        for c in m.clocks:
            fr = _freq(m, c.name, val, hw, memo)
            if fr is None:
                continue
            out.append({"name": c.name,
                        "count": int(round(fr * WINDOW_NS / 1000))})
        return out

    def csr_writes(val):
        writes = []
        for fq, v in val.items():
            f = m.field(fq)
            if f is None:
                continue
            words[f.reg] = (words[f.reg] & ~f.mask) | \
                ((v & ((1 << f.width) - 1)) << f.lsb)
        for r in m.regs:
            if any(f.access == "RW" for f in r.fields) and \
                    words[r.name] != written[r.name]:
                writes.append({"addr": f"32'h{r.addr:08x}", "reg": r.name,
                               "value": f"32'h{words[r.name]:08x}"})
                written[r.name] = words[r.name]
        return writes

    def add(name, desc, kind, val=None, hw=None, ena=None, writes=None,
            sw_resets_list=None, ena_post=None):
        phases.append({
            "name": name, "desc": desc, "kind": kind,
            "writes": writes if writes is not None else csr_writes(val or {}),
            "ena": ena or [],
            "ena_post": ena_post or [],
            "expects": expects_for(val or {}, hw or {}),
            "sw_resets": sw_resets_list or [],
        })

    add("p1_reset_defaults", "CSR reset defaults, HW enables on", "normal")
    add("p2_enable", "all SW gate enables on", "normal",
        val={fq: 1 for fq in ens})
    add("p3_mux_switch", "mux select = 1 (enables stay on)", "normal",
        val={**{fq: 1 for fq in ens}, **{fq: 1 for fq in sels}})
    if hw_ports:
        add("p4_hw_disable", "all HW enables off (SW enables stay on)", "hw_off",
            val={**{fq: 1 for fq in ens}, **{fq: 1 for fq in sels}},
            hw={p: 0 for p in hw_ports},
            ena=[(p, 0) for p in hw_ports],
            ena_post=[(p, 1) for p in hw_ports])
    if sw_resets:
        rst_ctrl = next((r for r in m.regs if r.name == "rst_ctrl"), None)
        if rst_ctrl:
            mask = 0
            for r in sw_resets:
                f = m.field(r.sw_field)
                if f:
                    mask |= f.mask
            add("p5_sw_reset", "SW reset assert then de-assert all domains",
                "sw_rst",
                writes=[{"addr": f"32'h{rst_ctrl.addr:08x}", "reg": "rst_ctrl",
                         "value": f"32'h{mask:08x}"}],
                sw_resets_list=[r.name for r in sw_resets])
            words["rst_ctrl"] = 0   # TB clears it at the end of the phase
            written["rst_ctrl"] = 0
    # SW-configurable divider ratios: write a test ratio, then restore default
    div_cfg = [(c, c.ratio_field) for c in m.clocks if c.ratio_field]
    if div_cfg:
        def test_ratio(c):
            return 2 * c.ratio if 2 * c.ratio <= c.ratio_max else c.ratio + 1
        base = {**{fq: 1 for fq in ens}, **{fq: 1 for fq in sels}}
        add("p6a_ratio_test", "write test ratios into SW dividers", "normal",
            val={**base,
                 **{fq: test_ratio(c) for c, fq in div_cfg}})
        add("p6b_ratio_default", "restore default divider ratios", "normal",
            val={**base,
                 **{fq: c.ratio for c, fq in div_cfg}})
    return [p for p in phases
            if p["writes"] or p["kind"] != "normal"
            or p["name"] == "p1_reset_defaults"]


def _sdc_defs(m, clk_order):
    """Per clock node: list of generated-clock definitions.
    Each def: {name, src_kind('port'|'clock'), src, div}. Mux nodes carry one
    def per input branch (-add); dividers inherit and scale parent defs."""
    defs = {}
    for p in m.input_clks:
        defs[p.name] = [{"name": p.name, "src_kind": "port", "src": p.name,
                         "div": 1}]
    by = {c.name: c for c in m.clocks}
    for name in clk_order:
        c = by[name]
        if c.type == "mux2":
            nd = []
            for branch in (c.parent, c.parent2):
                for d in defs[branch]:
                    nd.append({"name": f"{name}_{d['name']}",
                               "src_kind": "clock", "src": d["name"],
                               "div": d["div"]})
        else:
            pd = defs[c.parent]
            mult = c.ratio if c.type == "divider" else 1
            nd = [{"name": name if len(pd) == 1 else f"{name}_{d['name']}",
                   "src_kind": d["src_kind"], "src": d["src"],
                   "div": d["div"] * mult} for d in pd]
        defs[name] = nd
    return defs


def build_context(m, clk_order, rst_order, gen_tb):
    by_clk = {c.name: c for c in m.clocks}
    by_rst = {r.name: r for r in m.resets}
    default_rst = m.input_rsts[0].name if m.input_rsts else None

    # MCP (reset clock gating) domains: one gate per clock node
    mcp_domains = {}
    for r in m.resets:
        if r.mcp and r.clk:
            mcp_domains.setdefault(r.clk, {"n": r.mcp, "resets": []})
            mcp_domains[r.clk]["resets"].append(r)

    # top-level consumers of internal (EXPORT=否) signals: a signal with no
    # consumer is left unconnected at top (TB probes it inside the sub-tree)
    rt_clk_nonfree = {r.clk for r in m.resets if r.clk and not r.mcp}
    ct_rst_refs = {c.rst for c in m.clocks if c.rst}

    def clk_sig_in_ct(name):
        """clock signal inside clk_tree: input port name, node _w wire, or
        MCP-gated _mcp_w wire for children of gated nodes"""
        if m.port(name):
            return name
        return f"{name}_mcp_w" if name in mcp_domains else f"{name}_w"

    clocks = []
    for name in clk_order:
        c = by_clk[name]
        rst_name = c.rst or default_rst
        has_gate = c.gate or c.hw_en
        sw_en_wire = m.field(c.en_field).wire if (c.gate and c.en_field) else ""
        sel_wire = m.field(c.sel_field).wire if c.sel_field else ""
        ratio_wire = m.field(c.ratio_field).wire if c.ratio_field else ""
        en_expr = " & ".join(x for x in (sw_en_wire, c.hw_en) if x) or "1'b1"
        # match crg_clk_divider port [$clog2(MAX_RATIO):0]
        _r = c.ratio or 2
        ratio_w = c.ratio_width if c.sw_ratio \
            else ((_r - 1).bit_length() + 1 if _r >= 2 else 2)
        ratio_max = c.ratio_max if c.sw_ratio else (c.ratio or 2)
        ratio_conn = ratio_wire if ratio_wire \
            else f"{ratio_w}'d{c.ratio}"
        clocks.append({
            "name": c.name, "type": c.type, "desc": c.desc,
            "parent": c.parent, "parent2": c.parent2,
            "parent_wire": clk_sig_in_ct(c.parent),
            "parent2_wire": clk_sig_in_ct(c.parent2) if c.parent2 else "",
            "ratio": c.ratio, "ratio_max": ratio_max, "ratio_w": ratio_w,
            "sw_ratio": c.sw_ratio,
            "ratio_fq": c.ratio_field or "", "ratio_conn": ratio_conn,
            "gate": has_gate, "sw_gate": c.gate,
            "hw_en": c.hw_en or "", "en_expr": en_expr,
            "en_wire": sw_en_wire, "sel_wire": sel_wire,
            "en_fq": c.en_field or "", "sel_fq": c.sel_field or "",
            "pre_wire": f"{c.name}_pre_w" if c.type else "",
            "rst_wire": rst_name, "rst": rst_name,
            "exported": c.exported,
            "mcp_n": mcp_domains.get(c.name, {}).get("n", 0),
            "conn": c.exported or c.name in rt_clk_nonfree,
        })

    resets = []
    in_expr_by_name = {}
    for name in rst_order:
        r = by_rst[name]
        sw_wire = m.field(r.sw_field).wire if r.sw_field else ""
        # async sources merged inside rst_tree: parent (& HW source) (& ~SW)
        srcs = [x for x in (r.parent, r.hw_src) if x]
        base = " & ".join(srcs) if srcs else "1'b1"
        in_expr = f"({base}) & ~{sw_wire}" if sw_wire else base
        in_expr_by_name[r.name] = in_expr
        parent_sig = r.parent if (not r.parent or m.port(r.parent)) \
            else f"{r.parent}_w"
        clk_ref = f"{r.clk}_free" if (r.mcp and r.clk) else (r.clk or "")
        resets.append({
            "name": r.name, "type": r.type, "desc": r.desc,
            "parent": r.parent or "", "hw_src": r.hw_src or "",
            "parent_wire": parent_sig,
            "clk_wire": clk_ref, "clk": r.clk or "",
            "sw": r.sw, "sw_wire": sw_wire, "sw_fq": r.sw_field or "",
            "mcp": r.mcp or 0,
            "in_expr": in_expr, "inst": f"u_rst_{r.name}",
            "exported": r.exported,
            "conn": r.exported or r.name in ct_rst_refs,
        })

    mcp_list = [{"clk": clk, "n": d["n"],
                 "src_expr": " & ".join(f"{r.name}_in"
                                        for r in d["resets"]),
                 "sync_expr": " & ".join(f"{r.name}_w"
                                         for r in d["resets"])}
                for clk, d in sorted(mcp_domains.items())]
    mcp_en_names = [f"en_{d['clk']}" for d in mcp_list]

    regs = []
    rw_fields = []
    max_addr = 0
    for r in m.regs:
        max_addr = max(max_addr, r.addr)
        fields = [{"name": f.name, "msb": f.msb, "lsb": f.lsb, "width": f.width,
                   "wire": f.wire, "access": f.access, "reset": f.reset,
                   "mask_hex": f"32'h{f.mask:08x}", "shift": f.shift,
                   "mask_c": f"0x{f.mask:08x}u", "desc": f.desc}
                  for f in sorted(r.fields, key=lambda x: -x.msb)]
        regs.append({
            "name": r.name, "NAME": r.name.upper(),
            "addr_hex": f"32'h{r.addr:08x}", "addr": r.addr,
            "addr_c": f"0x{r.addr:08x}u", "waddr": (r.addr >> 2),
            "fields": fields, "has_q": bool(r.rw_fields),
            "q_reset_hex": f"32'h{r.q_reset:08x}",
            "rw_mask_hex": f"32'h{r.rw_mask:08x}",
            "ro_const_hex": f"32'h{r.ro_const:08x}",
        })
        rw_fields.extend(
            {"wire": f.wire, "reg": r.name, "msb": f.msb, "lsb": f.lsb,
             "width": f.width, "fq": f.fq}
            for f in r.rw_fields)

    apb_addr_w = max(12, (max_addr + 4).bit_length() + 1)

    # ---- sub-module port sets --------------------------------------------
    def _sw_ports(kind):
        """SW control ports for a sub-tree: [{name, width}] from field refs."""
        out = {}
        if kind == "ct":
            for c in m.clocks:
                fqs = []
                if c.gate and c.en_field:
                    fqs.append(c.en_field)
                fqs += [x for x in (c.sel_field, c.ratio_field) if x]
                for fq in fqs:
                    f = m.field(fq)
                    if f:
                        out[f.wire] = f.width
        else:
            for r in m.resets:
                if r.sw_field:
                    f = m.field(r.sw_field)
                    if f:
                        out[f.wire] = f.width
        return [{"name": k, "width": v} for k, v in sorted(out.items())]

    ct_clks_in = sorted({c.parent for c in m.clocks if m.port(c.parent)} |
                        {c.parent2 for c in m.clocks
                         if c.type == "mux2" and c.parent2
                         and m.port(c.parent2)})
    ct_enas_in = sorted({c.hw_en for c in m.clocks if c.hw_en})
    ct_rsts_in = sorted({c.rst for c in m.clocks if c.rst})
    ct_sw_in = _sw_ports("ct")
    rt_rsts_in = sorted({x for r in m.resets
                         for x in (r.parent, r.hw_src) if x and m.port(x)})
    rt_sw_in = _sw_ports("rt")
    rt_clks_in = sorted({(f"{r.clk}_free" if (r.mcp and r.clk) else r.clk)
                         for r in m.resets if r.clk})

    reset_pairs = [{"child": r.name, "parent": r.parent, "clk": r.clk}
                   for r in m.resets
                   if r.type == "sync" and m.reset(r.parent) is not None]

    sva_conns = []
    for p in reset_pairs:
        if p["clk"]:
            sva_conns += [
                {"port": f"rst_{p['child']}_clk", "sig": p["clk"]},
                {"port": f"rst_{p['child']}_child", "sig": p["child"]},
                {"port": f"rst_{p['child']}_parent", "sig": p["parent"]},
            ]
    sva_rst = [{"child": p["child"], "parent": p["parent"], "clk": p["clk"]}
               for p in reset_pairs if p["clk"]]

    sdc_defs = _sdc_defs(m, clk_order)
    by = {c.name: c for c in m.clocks}
    sdc_clocks = []
    for name in clk_order:
        for i, d in enumerate(sdc_defs[name]):
            gated_target = (f"[get_ports {name}]" if by[name].exported
                            else f"[get_pins u_clk_tree/{name}]")
            sdc_clocks.append({
                "name": d["name"],
                "source": (f"[get_ports {d['src']}]" if d["src_kind"] == "port"
                           else f"[get_clocks {d['src']}]"),
                "div": d["div"], "port": name, "add": i > 0,
                "target": gated_target,
                "sw_ratio": by[name].sw_ratio,
                "ratio": by[name].ratio,
                "ratio_max": by[name].ratio_max})
            if name in mcp_domains:
                # free (pre-gate) tap: clocks the rst_tree 2FF + sequencer
                sdc_clocks.append({
                    "name": f"{d['name']}_free",
                    "source": (f"[get_ports {d['src']}]"
                               if d["src_kind"] == "port"
                               else f"[get_clocks {d['src']}]"),
                    "div": d["div"], "port": name, "add": i > 0,
                    "target": f"[get_pins u_clk_tree/{name}_free]",
                    "sw_ratio": by[name].sw_ratio,
                    "ratio": by[name].ratio,
                    "ratio_max": by[name].ratio_max})
    sdc_excl = [{"clocks": [d["name"] for d in sdc_defs[name]]}
                for name in clk_order if len(sdc_defs[name]) > 1]

    # per-def period (ns, reset values) for MCP distribution budgets
    def_by_name = {d["name"]: d
                   for defs in sdc_defs.values() for d in defs}

    def _def_period(d):
        cur = d
        while cur["src_kind"] != "port":
            cur = def_by_name[cur["src"]]
        p = m.port(cur["src"])
        return (1000.0 / p.freq_mhz) * d["div"] \
            if p and p.freq_mhz else None

    def _clk_period_ns(name):
        per = [x for x in (_def_period(d) for d in sdc_defs.get(name, []))
               if x]
        return min(per) if per else None

    def _fmt_ns(v):
        return f"{v:.3f}".rstrip("0").rstrip(".")

    mcp_budget = {}
    for r in m.resets:
        if r.mcp and r.clk and r.clk not in mcp_budget:
            per = _clk_period_ns(r.clk)
            mcp_budget[r.clk] = (_fmt_ns(r.mcp * per)
                                 if per else str(r.mcp))

    # TB settle time: MCP sequencing (2 guard + 128 pulse + margin + slack)
    # on the slowest ancestor input clock of any gated domain, 2x margin
    settle_ns = 2000
    if mcp_domains:
        nmax = max(d["n"] for d in mcp_domains.values())
        anc = set()

        def _collect_anc(name):
            c = m.clock(name)
            if c is None:
                anc.add(name)
            else:
                for p in (c.parent, c.parent2):
                    if p:
                        _collect_anc(p)

        for clk in mcp_domains:
            _collect_anc(clk)
        freqs = [p.freq_mhz for p in m.input_clks
                 if p.name in anc and p.freq_mhz]
        if freqs:
            settle_ns = max(2000, int(math.ceil((140 + nmax) * 2000
                                                / min(freqs))))

    # final SW image + RO read values for readback checks
    readbacks = []
    for r in m.regs:
        if r.rw_fields:
            val = r.q_reset
            for c in m.clocks:
                for fq in (c.en_field, c.sel_field):
                    if fq:
                        f = m.field(fq)
                        if f and f.reg == r.name:
                            val |= 1 << f.lsb
            for rst in m.resets:
                if rst.sw_field:
                    f = m.field(rst.sw_field)
                    if f and f.reg == r.name:
                        val &= ~f.mask   # SW reset ends de-asserted
            readbacks.append({"reg": r.name, "addr": f"32'h{r.addr:08x}",
                              "expect": f"32'h{val:08x}", "access": "RW"})
        else:
            readbacks.append({"reg": r.name, "addr": f"32'h{r.addr:08x}",
                              "expect": f"32'h{r.ro_const:08x}", "access": "RO"})

    ctx = {
        "gen": {"version": __version__,
                "date": datetime.date.today().isoformat(),
                "input_name": os.path.basename(m.input_path)},
        "m": {
            "module": m.module, "MODULE": m.module.upper(), "version": m.version,
            "apb_addr_w": apb_addr_w,
            "clk_inputs": [{"name": p.name, "freq": p.freq_mhz, "desc": p.desc,
                            "half": 1000.0 / (2.0 * p.freq_mhz)}
                           for p in m.input_clks],
            "rst_inputs": [{"name": p.name, "desc": p.desc}
                           for p in m.input_rsts],
            "ena_inputs": [{"name": p.name, "desc": p.desc}
                           for p in m.ports if p.kind == "ena"],
            "clocks": clocks, "resets": resets, "regs": regs,
            "exported_clocks": [c for c in clocks if c["exported"]],
            "internal_clocks": [c for c in clocks if not c["exported"]],
            "exported_resets": [r for r in resets if r["exported"]],
            "internal_resets": [r for r in resets if not r["exported"]],
            "free_clk_out": [c for c in clocks if c["mcp_n"]],
            "has_free_clks": bool(mcp_list),
            "mcp_en_wires": mcp_en_names,
            "free_clk_wires": [{"name": d["clk"]} for d in mcp_list],
            "has_mcp": bool(mcp_list),
            "rw_fields": rw_fields,
            "ct": {"clks_in": ct_clks_in, "enas_in": ct_enas_in,
                   "rsts_in": ct_rsts_in, "sw_in": ct_sw_in,
                   "has_mcp": bool(mcp_list), "mcp_en_in": mcp_en_names},
            "rt": {"rsts_in": rt_rsts_in, "sw_in": rt_sw_in,
                   "clks_in": rt_clks_in, "mcp_domains": mcp_list,
                   "mcp_en_out": mcp_en_names},
            "reset_pairs": reset_pairs, "sva_conns": sva_conns,
            "sva_rst": sva_rst,
            "sdc": {"clocks": sdc_clocks, "excl": sdc_excl,
                    "input_periods": [
                        {"name": p.name,
                         "period": f"{1000.0 / p.freq_mhz:.3f}"}
                        for p in m.input_clks],
                    "async_group": len(m.input_clks) > 1,
                    "false_path_ports": [p.name for p in m.ports
                                         if p.kind in ("rst", "ena")] +
                    (["test_en"] if mcp_list else []),
                    "mcp_rsts": [{"name": r.name, "clk": r.clk, "n": r.mcp,
                                  "exported": r.exported,
                                  "budget": mcp_budget.get(r.clk, "")}
                                 for r in m.resets if r.mcp]},
            "tb": {"window_ns": WINDOW_NS, "tol": TOL,
                   "pclk_half": PCLK_HALF_NS, "settle_ns": settle_ns,
                   "phases": _build_phases(m), "readbacks": readbacks},
        },
        "gen_tb": gen_tb,
        "lib_files": LIB_FILES,
    }
    return ctx


def generate(input_path, out_dir, gen_tb=True):
    m = parse(input_path)
    errs, warns, clk_order, rst_order = validate(m)
    for w in warns:
        print("WARN :", w)
    if errs:
        from .parser import CrgError
        raise CrgError(errs)
    if clk_order is None or rst_order is None:
        from .parser import CrgError
        raise CrgError(["graph has a cycle; cannot generate"])

    ctx = build_context(m, clk_order, rst_order, gen_tb)

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR),
                      undefined=StrictUndefined, trim_blocks=True,
                      lstrip_blocks=True, keep_trailing_newline=True)

    rtl_dir = os.path.join(out_dir, "rtl")
    lib_dst = os.path.join(rtl_dir, "lib")
    inc_dir = os.path.join(rtl_dir, "include")
    sw_dir = os.path.join(out_dir, "sw")
    doc_dir = os.path.join(out_dir, "doc")
    tb_dir = os.path.join(out_dir, "tb")
    for d in (rtl_dir, lib_dst, inc_dir, sw_dir, doc_dir):
        os.makedirs(d, exist_ok=True)
    if gen_tb:
        os.makedirs(tb_dir, exist_ok=True)

    outputs = []

    def render(template, dest):
        text = env.get_template(template).render(**ctx)
        with open(dest, "w") as f:
            f.write(text)
        outputs.append(os.path.relpath(dest, out_dir))
        print("wrote", os.path.relpath(dest, out_dir))

    mod = m.module
    render("clk_tree.sv.j2", os.path.join(rtl_dir, f"{mod}_clk_tree.sv"))
    render("rst_tree.sv.j2", os.path.join(rtl_dir, f"{mod}_rst_tree.sv"))
    render("regs.sv.j2", os.path.join(rtl_dir, f"{mod}_regs.sv"))
    render("top.sv.j2", os.path.join(rtl_dir, f"{mod}_top.sv"))
    render("reg_pkg.sv.j2", os.path.join(rtl_dir, f"{mod}_reg_pkg.sv"))
    render("regs.svh.j2", os.path.join(inc_dir, f"{mod}_regs.svh"))
    render("regs.h.j2", os.path.join(sw_dir, f"{mod}_regs.h"))
    render("sva.sv.j2", os.path.join(rtl_dir, f"{mod}_sva.sv"))
    render("sdc.j2", os.path.join(out_dir, f"{mod}.sdc"))
    render("regmap.md.j2", os.path.join(doc_dir, f"{mod}_regmap.md"))
    render("regmap.csv.j2", os.path.join(doc_dir, f"{mod}_regmap.csv"))
    if gen_tb:
        render("tb_smoke.sv.j2", os.path.join(tb_dir, f"tb_{mod}.sv"))
    render("filelist.f.j2", os.path.join(out_dir, "filelist.f"))
    if gen_tb:
        render("filelist_sim.f.j2", os.path.join(out_dir, "filelist_sim.f"))
    render("README.md.j2", os.path.join(out_dir, "README.md"))

    for lf in LIB_FILES:
        shutil.copyfile(os.path.join(LIB_DIR, lf), os.path.join(lib_dst, lf))
        print("copied rtl/lib/" + lf)

    with open(os.path.join(out_dir, "model.json"), "w") as f:
        json.dump(ctx["m"], f, indent=2)
    outputs.append("model.json")

    manifest = {
        "generator": "crg_gen", "generator_version": __version__,
        "module": m.module, "version": m.version,
        "input": os.path.abspath(input_path),
        "input_sha256": _input_digest(input_path),
        "date": datetime.datetime.now().isoformat(timespec="seconds"),
        "outputs": {p: _input_digest(os.path.join(out_dir, p))
                    for p in outputs},
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("wrote manifest.json")
    return manifest
