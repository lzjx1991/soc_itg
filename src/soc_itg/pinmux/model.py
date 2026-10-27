from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

PadType = Literal["digital", "analog"]
Security = Literal["secure", "nonsecure"]


class ConfigField(BaseModel):
    name: str
    width: int
    default: int


class Pad(BaseModel):
    name: str
    type: PadType
    wrapper: str = ""
    security: Security = "nonsecure"
    config: dict[str, ConfigField] = Field(default_factory=dict)


class FunctionShareEntry(BaseModel):
    group: str = "default"
    pad: str
    functions: dict[str, str] = Field(default_factory=dict)


class PadShareEntry(BaseModel):
    pad: str
    pins: dict[str, str] = Field(default_factory=dict)


class BistShareEntry(BaseModel):
    pad: str
    functions: dict[str, str] = Field(default_factory=dict)


class BistEntry(BaseModel):
    bist_mode: int
    pad: str
    value: int


class Pinmux(BaseModel):
    pads: list[Pad] = Field(default_factory=list)
    function_share: list[FunctionShareEntry] = Field(default_factory=list)
    padshare: list[PadShareEntry] = Field(default_factory=list)
    bist_share: list[BistShareEntry] = Field(default_factory=list)
    bist_entries: list[BistEntry] = Field(default_factory=list)

    def pad(self, name: str) -> Pad | None:
        return next((p for p in self.pads if p.name == name), None)

    def digital_pads(self) -> list[Pad]:
        return [p for p in self.pads if p.type == "digital"]

    def groups(self) -> list[str]:
        result = []
        for entry in self.function_share:
            if entry.group not in result:
                result.append(entry.group)
        return result
