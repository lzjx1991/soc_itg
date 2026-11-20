from .model import Pad, ConfigField, FunctionShareEntry, PadShareEntry, BistShareEntry, BistEntry, Pinmux
from .excel import read_pinmux
from .validate import validate


def merge(models):
    merged = Pinmux()
    for model in models:
        merged.pads.extend(model.pads)
        merged.function_share.extend(model.function_share)
        merged.padshare.extend(model.padshare)
        merged.bist_share.extend(model.bist_share)
        merged.bist_entries.extend(model.bist_entries)
    return merged


__all__ = [
    "Pad", "ConfigField", "FunctionShareEntry", "PadShareEntry", "BistShareEntry", "BistEntry",
    "Pinmux", "read_pinmux", "validate", "merge",
]
