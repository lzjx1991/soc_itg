from .excel import read_topcsr
from ..model.topcsr import TopCSR, TopCSRBinding
from ..model.ir import MemoryMap


def merge(models, module=None):
    registers = []
    bindings = []
    for model in models:
        registers.extend(model.memory_map.registers)
        bindings.extend(model.bindings)
    name = module or (models[0].module if models else "top_regs")
    return TopCSR(module=name, memory_map=MemoryMap(name=name, registers=registers), bindings=bindings)


__all__ = ["read_topcsr", "TopCSR", "TopCSRBinding", "merge"]
