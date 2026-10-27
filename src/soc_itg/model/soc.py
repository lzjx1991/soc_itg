from __future__ import annotations
from pydantic import BaseModel, Field
from .ir import Component, MemoryMap


class Instance(BaseModel):
    name: str
    vlnv: str
    params: dict = Field(default_factory=dict)


class Connection(BaseModel):
    type: str = "interconnection"
    a: str = ""
    b: str = ""
    net: str = ""
    driver: str = ""
    loads: list[str] = Field(default_factory=list)


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

    def component_of(self, inst_name: str) -> Component | None:
        inst = self.instance(inst_name)
        return self.components.get(inst.vlnv) if inst else None
