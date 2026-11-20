from __future__ import annotations
from pydantic import BaseModel, Field
from .ir import MemoryMap


class TopCSRBinding(BaseModel):
    reg: str
    field: str
    access: str = "rw"
    width: int = 1
    targets: list[str] = Field(default_factory=list)


class TopCSR(BaseModel):
    module: str = "top_regs"
    memory_map: MemoryMap
    bindings: list[TopCSRBinding] = Field(default_factory=list)
