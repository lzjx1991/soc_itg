from __future__ import annotations
from pydantic import BaseModel, Field


class Endpoint(BaseModel):
    instance: str = ""
    port: str
    direction: str = "inout"


class Net(BaseModel):
    name: str
    width: int = 1
    tri_state: bool = False
    endpoints: list[Endpoint] = Field(default_factory=list)


class PortSpec(BaseModel):
    name: str
    direction: str = "inout"
    width: int = 1


class InstanceSpec(BaseModel):
    name: str
    module: str
    ports: list[PortSpec] = Field(default_factory=list)


class TieBinding(BaseModel):
    instance: str
    port: str
    value: int = 0


class Netlist(BaseModel):
    schema_version: int = 1
    tool_version: str = "0.1.0"
    top: str = "top"
    ports: list[PortSpec] = Field(default_factory=list)
    instances: list[InstanceSpec] = Field(default_factory=list)
    nets: list[Net] = Field(default_factory=list)
    ties: list[TieBinding] = Field(default_factory=list)
