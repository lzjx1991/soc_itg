from __future__ import annotations
from pydantic import BaseModel, Field
from .ir import Component, MemoryMap

TIE_LITERALS = {"1'b0", "0", "1'b1", "1"}


class Instance(BaseModel):
    name: str
    vlnv: str
    params: dict = Field(default_factory=dict)


class Connection(BaseModel):
    """A connection entry. Its kind is inferred from the fields, no explicit 'type'.

    - fanout (broadcast): has ``driver`` + ``loads``
    - concat: either side is a list (several 1-bit drivers -> one bus)
    - tie: ``b`` is a constant literal (``1'b0`` / ``1'b1``)
    - unconnect: ``b`` == ``none``
    - interconnection: everything else (``a`` / ``b`` are string paths)
    """

    a: str | list[str] = ""
    b: str | list[str] = ""
    net: str = ""
    driver: str = ""
    loads: list[str] = Field(default_factory=list)

    def kind(self) -> str:
        if self.driver and self.loads:
            return "fanout"
        if isinstance(self.a, list) or isinstance(self.b, list):
            return "concat"
        if isinstance(self.b, str):
            lit = self.b.lower().replace(" ", "")
            if lit in TIE_LITERALS:
                return "tie"
            if lit == "none":
                return "unconnect"
        return "interconnection"

    def tie_value(self) -> int:
        lit = self.b.lower().replace(" ", "") if isinstance(self.b, str) else ""
        return 1 if lit in ("1'b1", "1") else 0


class AddressRegion(BaseModel):
    region: str
    base: str
    size: str


class SoC(BaseModel):
    schema_version: int = 1
    tool_version: str = "0.1.0"
    top: str = "top"
    instances: list[Instance] = Field(default_factory=list)
    components: dict[str, Component] = Field(default_factory=dict)
    connections: list[Connection] = Field(default_factory=list)
    address_map: list[AddressRegion] = Field(default_factory=list)
    register_models: dict[str, list[MemoryMap]] = Field(default_factory=dict)

    def instance(self, name: str) -> Instance | None:
        return next((i for i in self.instances if i.name == name), None)

    def component_of(self, name: str) -> Component | None:
        inst = self.instance(name)
        return self.components.get(inst.vlnv) if inst is not None else None
