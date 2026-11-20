"""Semantic validation of a parsed Model: names, graph, registers, cross-refs."""
from .model import is_ident


def _topo(nodes, parent_of, exists, errs, what):
    """Kahn topological sort; edges parent->node for parents that are nodes.
    A None parent contributes no edge (reset nodes may be HW_SRC-only)."""
    names = [n.name for n in nodes]
    indeg = {n.name: 0 for n in nodes}
    dependents = {n.name: [] for n in nodes}
    for n in nodes:
        p = parent_of(n)
        if p is None:
            continue
        if p in indeg:
            indeg[n.name] += 1
            dependents[p].append(n.name)
        elif not exists(p):
            errs.append(f"{what}: '{n.name}' parent '{p}' does not exist")
    order = []
    ready = [n for n in names if indeg[n] == 0]
    while ready:
        cur = ready.pop()
        order.append(cur)
        for d in dependents[cur]:
            indeg[d] -= 1
            if indeg[d] == 0:
                ready.append(d)
    if len(order) != len(names):
        cyc = sorted(set(names) - set(order))
        errs.append(f"{what}: cycle detected involving: {', '.join(cyc)}")
        return None
    return order


def validate(m):
    """Return (errors, warnings, clk_order, rst_order)."""
    errs, warns = [], []
    loc_all = "top"

    # ---- namespace uniqueness ----------------------------------------
    seen = {}
    for p in m.ports:
        if not is_ident(p.name):
            errs.append(f"ports row: '{p.name}' is not a valid lowercase identifier")
        if p.name in seen:
            errs.append(f"ports row: duplicate name '{p.name}'")
        seen[p.name] = "port"
    if not m.input_clks:
        errs.append("ports: at least one input clock (KIND=clk) is required")
    if not m.input_rsts:
        errs.append("ports: at least one input reset (KIND=rst) is required")
    for p in m.ports:
        if p.kind not in ("clk", "rst", "ena"):
            errs.append(f"ports row: '{p.name}' KIND must be clk/rst/ena, got "
                        f"'{p.kind}'")
        elif p.kind == "clk" and (p.freq_mhz is None or p.freq_mhz <= 0):
            errs.append(f"ports row: clock '{p.name}' needs FREQ_MHZ > 0")
        elif p.kind != "clk" and p.freq_mhz is not None:
            warns.append(f"ports row: '{p.name}' has FREQ_MHZ set; ignored")

    for c in m.clocks:
        if not is_ident(c.name):
            errs.append(f"clock_plan: '{c.name}' is not a valid lowercase identifier")
        if c.name in seen:
            errs.append(f"clock_plan: name '{c.name}' collides with {seen.get(c.name)}")
        seen[c.name] = "clock"
        if c.type not in ("divider", "mux2", ""):
            errs.append(f"clock_plan '{c.name}': TYPE must be divider/mux2 or "
                        f"empty (passthrough), got '{c.type}'")
    for r in m.resets:
        if not is_ident(r.name):
            errs.append(f"reset_plan: '{r.name}' is not a valid lowercase identifier")
        if r.name in seen:
            errs.append(f"reset_plan: name '{r.name}' collides with {seen.get(r.name)}")
        seen[r.name] = "reset"

    # ---- clock nodes ---------------------------------------------------
    default_rst = m.input_rsts[0].name if m.input_rsts else None
    for c in m.clocks:
        loc = f"clock_plan '{c.name}'"
        if not m.is_clk_source(c.parent):
            errs.append(f"{loc}: PARENT '{c.parent}' is not a known clock")
        if c.type == "divider":
            if c.ratio is None or c.ratio < 2:
                errs.append(f"{loc}: divider RATIO_DEF must be an integer >= 2 "
                            f"(got {c.ratio})")
            if c.ratio_max is not None:
                if c.ratio_max < 2:
                    errs.append(f"{loc}: RATIO_MAX must be >= 2 "
                                f"(got {c.ratio_max})")
                elif c.ratio is not None and c.ratio_max < c.ratio:
                    errs.append(f"{loc}: RATIO_MAX ({c.ratio_max}) must be >= "
                                f"RATIO_DEF ({c.ratio})")
                elif c.ratio_max > (1 << 16):
                    errs.append(f"{loc}: RATIO_MAX > 65536 is not supported")
        elif c.type == "mux2":
            if not c.parent2:
                errs.append(f"{loc}: mux2 requires PARENT2")
            elif not m.is_clk_source(c.parent2):
                errs.append(f"{loc}: PARENT2 '{c.parent2}' is not a known clock")
        else:
            if c.ratio or c.parent2:
                errs.append(f"{loc}: passthrough node cannot have "
                            f"RATIO_DEF/RATIO_MAX/PARENT2")
        if c.hw_en:
            hp = m.port(c.hw_en)
            if hp is None or hp.kind != "ena":
                errs.append(f"{loc}: HW_EN '{c.hw_en}' is not a declared enable "
                            f"port (ports KIND=ena)")
        if c.rst and not m.is_rst_source(c.rst):
            errs.append(f"{loc}: RST '{c.rst}' is not a known reset")
        if not c.rst and default_rst:
            c.rst = default_rst
        for attr, minw in (("en_field", 1), ("sel_field", 1),
                           ("ratio_field", 2)):
            fq = getattr(c, attr)
            if fq:
                if "." not in fq:
                    errs.append(f"{loc}: internal {attr} '{fq}' must be "
                                f"REG.FIELD")
                else:
                    f = m.field(fq)
                    if f is None:
                        errs.append(f"{loc}: {attr} '{fq}' is not defined")
                    elif f.access != "RW":
                        errs.append(f"{loc}: {attr} '{fq}' must be RW")
                    elif f.width < minw:
                        errs.append(f"{loc}: control '{fq}' must be at least "
                                    f"{minw} bit(s) wide")
                if attr == "ratio_field" and c.ratio is not None:
                    f = m.field(fq)
                    if f and (1 << f.width) <= c.ratio_max:
                        errs.append(f"{loc}: ratio field '{fq}' too narrow "
                                    f"for RATIO_MAX {c.ratio_max}")

    # ---- reset nodes ---------------------------------------------------
    for r in m.resets:
        loc = f"reset_plan '{r.name}'"
        if r.type not in ("sync", "passthrough"):
            errs.append(f"{loc}: TYPE must be sync/passthrough, got '{r.type}'")
        if not r.parent and not r.hw_src:
            errs.append(f"{loc}: needs PARENT and/or HW_SRC")
        if r.parent and not m.is_rst_source(r.parent):
            errs.append(f"{loc}: PARENT '{r.parent}' is not a known reset")
        if r.hw_src:
            hp = m.port(r.hw_src)
            if hp is None or hp.kind != "rst":
                errs.append(f"{loc}: HW_SRC '{r.hw_src}' is not a declared "
                            f"reset input port")
        if r.type == "sync":
            if not r.clk:
                errs.append(f"{loc}: sync reset requires CLK")
            elif not m.is_clk_source(r.clk):
                errs.append(f"{loc}: CLK '{r.clk}' is not a known clock")
        if r.sw and r.type == "passthrough":
            warns.append(f"{loc}: SW reset on passthrough releases "
                         f"asynchronously (prefer type=sync)")
        if r.mcp is not None:
            if r.type != "sync":
                errs.append(f"{loc}: MCP requires TYPE=sync")
            if not (1 <= r.mcp <= 255):
                errs.append(f"{loc}: MCP must be 1..255 (got {r.mcp})")
            if r.clk and m.clock(r.clk) is None:
                errs.append(f"{loc}: MCP requires CLK to be a generated "
                            f"clock node (not an input clock port)")

    # ---- MCP domain consistency: one gating policy per clock domain -------
    dom = {}
    for r in m.resets:
        if r.clk:
            dom.setdefault(r.clk, []).append(r)
    for clk, rs in dom.items():
        vals = {r.mcp for r in rs}
        if None in vals and len(vals) > 1:
            errs.append(f"reset_plan: CLK domain '{clk}' mixes MCP and "
                        f"non-MCP resets; all resets in a gated domain "
                        f"must carry the same MCP value")
        elif len(vals - {None}) > 1:
            errs.append(f"reset_plan: CLK domain '{clk}' has conflicting "
                        f"MCP values {sorted(v for v in vals if v)}")

    # ---- reset/clock dependency deadlock ---------------------------------
    # A sync reset releases only in its CLK domain; a clock whose generation
    # is (transitively) held by that reset is frozen, so the reset can never
    # release. Detect cycles reset -> clk -> (rst/parents) -> reset.
    # MCP-aware: a clock node gated by MCP resets is frozen while those
    # resets are asserted; an MCP reset's 2FF runs on the node's FREE
    # (pre-gate) clock, i.e. the node's divider output + upstream chain.
    # path_r/path_c track the CURRENT recursion path (backtracked on exit),
    # so membership means a genuine wait cycle, not a mere revisit.
    def _mcp_of(cname):
        return any(r.mcp and r.clk == cname for r in m.resets)

    def _clk_waits(cname, path_r, path_c):
        c = m.clock(cname)
        if c is None:
            return False          # input clock port: always running
        if cname in path_c:
            return False          # clock-graph cycle: reported separately
        path_c.add(cname)
        try:
            if c.rst and m.reset(c.rst) is not None:
                if c.rst in path_r or _rst_waits(c.rst, path_r, path_c):
                    return True
            if _mcp_of(cname):    # output gated: frozen by domain MCP resets
                for r2 in m.resets:
                    if r2.mcp and r2.clk == cname:
                        if r2.name in path_r or _rst_waits(r2.name, path_r,
                                                           path_c):
                            return True
            for p in (c.parent, c.parent2):
                if p and _clk_waits(p, path_r, path_c):
                    return True
            return False
        finally:
            path_c.discard(cname)

    def _clk_free_waits(cname, path_r, path_c):
        """FREE version of clock node cname: divider output + upstream chain
        (own divider RST applies, own SW/MCP gates do not)."""
        c = m.clock(cname)
        if c is None:
            return _clk_waits(cname, path_r, path_c)
        if c.rst and m.reset(c.rst) is not None:
            if c.rst in path_r or _rst_waits(c.rst, path_r, path_c):
                return True
        for p in (c.parent, c.parent2):
            if p and _clk_waits(p, path_r, path_c):
                return True
        return False

    def _rst_waits(rname, path_r, path_c):
        r = m.reset(rname)
        if r is None:
            return False
        if rname in path_r:
            return True           # reset-chain cycle on the current path
        path_r.add(rname)
        try:
            if r.clk:
                if r.mcp:
                    if _clk_free_waits(r.clk, path_r, path_c):
                        return True
                elif _clk_waits(r.clk, path_r, path_c):
                    return True
            if r.parent and m.reset(r.parent) is not None:
                if _rst_waits(r.parent, path_r, path_c):
                    return True
            return False
        finally:
            path_r.discard(rname)

    for r in m.resets:
        if r.type != "sync":
            continue
        if _rst_waits(r.name, set(), set()):
            errs.append(f"reset_plan '{r.name}': reset/clock deadlock - its "
                        f"CLK domain clock is (transitively) held by this "
                        f"reset")

    # ---- registers ------------------------------------------------------
    addrs = {}
    for reg in m.regs:
        if not is_ident(reg.name):
            errs.append(f"reg_map: '{reg.name}' is not a valid lowercase identifier")
        if reg.addr in addrs:
            errs.append(f"reg_map: address 0x{reg.addr:x} used by both "
                        f"'{addrs[reg.addr]}' and '{reg.name}'")
        addrs[reg.addr] = reg.name
        if reg.addr % 4:
            errs.append(f"reg_map '{reg.name}': ADDR 0x{reg.addr:x} must be "
                        f"4-byte aligned")
        if not reg.fields:
            errs.append(f"reg_map '{reg.name}': no fields defined")
        fnames = {}
        for f in reg.fields:
            if not is_ident(f.name):
                errs.append(f"reg_map '{reg.name}': field '{f.name}' is not a "
                            f"valid lowercase identifier")
            if f.name in fnames:
                errs.append(f"reg_map '{reg.name}': duplicate field '{f.name}'")
            fnames[f.name] = True
            if not (0 <= f.lsb <= f.msb <= 31):
                errs.append(f"reg_map '{reg.name}.{f.name}': bad bit range "
                            f"[{f.msb}:{f.lsb}]")
            else:
                if f.access not in ("RW", "RO"):
                    errs.append(f"reg_map '{reg.name}.{f.name}': ACCESS must be "
                                f"RW/RO")
                if f.reset >= (1 << f.width):
                    errs.append(f"reg_map '{reg.name}.{f.name}': RESET {f.reset} "
                                f"does not fit in {f.width} bit(s)")
        if reg.fields:
            fs = sorted(reg.fields, key=lambda x: x.lsb)
            for a, b in zip(fs, fs[1:]):
                if b.lsb <= a.msb:
                    errs.append(f"reg_map '{reg.name}': fields '{a.name}' "
                                f"[{a.msb}:{a.lsb}] and '{b.name}' "
                                f"[{b.msb}:{b.lsb}] overlap")

    # ---- topological orders --------------------------------------------
    clk_order = _topo(m.clocks, lambda n: n.parent, lambda p: m.is_clk_source(p),
                      errs, "clock_plan")
    rst_order = _topo(m.resets, lambda n: n.parent, lambda p: m.is_rst_source(p),
                      errs, "reset_plan")
    # mux2 second parent also participates in the clock DAG.
    # Deterministic Kahn: nodes are emitted in sheet order whenever possible.
    if clk_order is not None:
        by = {c.name: c for c in m.clocks}
        ordered = []
        remaining = [c.name for c in m.clocks]
        while remaining:
            progressed = False
            for n in remaining:
                c = by[n]
                deps = [c.parent] + ([c.parent2] if c.parent2 else [])
                if all(d not in remaining for d in deps):
                    ordered.append(n)
                    remaining.remove(n)
                    progressed = True
            if not progressed:
                errs.append(f"clock_plan: cycle detected involving: "
                            f"{', '.join(sorted(remaining))}")
                return errs, warns, None, None
        clk_order = ordered

    # ---- unused field warning -------------------------------------------
    used = set()
    for c in m.clocks:
        if c.en_field:
            used.add(c.en_field)
        if c.sel_field:
            used.add(c.sel_field)
        if c.ratio_field:
            used.add(c.ratio_field)
    for r in m.resets:
        if r.sw_field:
            used.add(r.sw_field)
    for reg in m.regs:
        for f in reg.rw_fields:
            if f.fq not in used:
                warns.append(f"reg_map: RW field '{f.fq}' is not referenced by "
                             f"any clock_plan node")

    # ---- sanity on derived frequencies (all enables on) -------------------
    if clk_order:
        memo = {}
        for n in clk_order:
            freq = _freq_all_on(m, n, memo)
            if freq and freq > 3000:
                warns.append(f"clock_plan '{n}': derived frequency {freq:.3f} MHz "
                             f"looks suspicious (> 3 GHz)")

    # ---- internal (EXPORT=否) nodes must have an internal consumer --------
    for c in m.clocks:
        if c.exported:
            continue
        used = any(x.parent == c.name or x.parent2 == c.name
                   for x in m.clocks) or \
            any(r.clk == c.name for r in m.resets)
        if not used:
            warns.append(f"clock_plan '{c.name}': internal node "
                         f"(EXPORT=否) is not used anywhere")
    for r in m.resets:
        if r.exported:
            continue
        used = any(x.parent == r.name for x in m.resets) or \
            any(c.rst == r.name for c in m.clocks)
        if not used:
            warns.append(f"reset_plan '{r.name}': internal node "
                         f"(EXPORT=否) is not used anywhere")

    return errs, warns, clk_order, rst_order


def _freq_all_on(m, name, memo):
    p = m.port(name)
    if p and p.kind == "clk":
        return p.freq_mhz
    c = m.clock(name)
    if c is None:
        return None
    pf = _freq_all_on(m, c.parent, memo)
    if c.type == "divider":
        # SW-configurable dividers can be set to /2: use worst case for sanity
        ratio = 2 if c.sw_ratio else c.ratio
        return None if (pf is None or ratio is None) else (pf / ratio
                                                           if pf else 0.0)
    if c.type == "gate":
        return pf
    if c.type == "mux2":
        return pf
    return None
