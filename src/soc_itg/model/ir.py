from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

Direction = Literal["in", "out", "inout"]
InterfaceMode = Literal["master", "slave", "system", "monitor"]
Security = Literal["secure", "nonsecure"]


class Port(BaseModel):
    name: str
    direction: Direction = "in"
    width: int = 1


class BusInterface(BaseModel):
    name: str
    mode: InterfaceMode = "slave"
    bus_type: Optional[str] = None
    port_maps: dict[str, str] = Field(default_factory=dict)


class RegisterField(BaseModel):
    name: str
    msb: int = 0
    lsb: int = 0
    access: str = "rw"
    write_action: str = "none"
    read_action: str = "none"
    reset: int = 0
    security: Security = "nonsecure"


class Register(BaseModel):
    name: str
    offset: str = "0x0"
    fields: list[RegisterField] = Field(default_factory=list)


class MemoryMap(BaseModel):
    name: str
    registers: list[Register] = Field(default_factory=list)


class Component(BaseModel):
    vlnv: str
    ports: list[Port] = Field(default_factory=list)
    bus_interfaces: list[BusInterface] = Field(default_factory=list)
    memory_maps: list[MemoryMap] = Field(default_factory=list)

    def port(self, name: str) -> Optional[Port]:
        return next((p for p in self.ports if p.name == name), None)

    def bus_if(self, name: str) -> Optional[BusInterface]:
        return next((b for b in self.bus_interfaces if b.name == name), None)
