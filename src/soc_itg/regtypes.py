TYPE_MAP = {
    "rw": ("rw", "none", "none"),
    "ro": ("ro", "none", "none"),
    "wo": ("wo", "none", "none"),
    "w1c": ("rw", "w1c", "none"),
    "w1s": ("rw", "w1s", "none"),
    "w1t": ("rw", "w1t", "none"),
    "w0c": ("rw", "w0c", "none"),
    "w0s": ("rw", "w0s", "none"),
    "w0t": ("rw", "w0t", "none"),
    "rc": ("rw", "none", "rc"),
    "rs": ("rw", "none", "rs"),
    "rw1": ("rw1", "none", "none"),
    "w1": ("w1", "none", "none"),
}

TYPE_REFERENCE = [
    ("type", "access", "write_action", "read_action", "中文含义"),
    ("rw", "rw", "none", "none", "读写"),
    ("ro", "ro", "none", "none", "只读"),
    ("wo", "wo", "none", "none", "只写"),
    ("w1c", "rw", "w1c", "none", "写1清零"),
    ("w1s", "rw", "w1s", "none", "写1置位"),
    ("w1t", "rw", "w1t", "none", "写1翻转"),
    ("w0c", "rw", "w0c", "none", "写0清零"),
    ("w0s", "rw", "w0s", "none", "写0置位"),
    ("w0t", "rw", "w0t", "none", "写0翻转"),
    ("rc", "rw", "none", "rc", "读清零"),
    ("rs", "rw", "none", "rs", "读置位"),
    ("rw1", "rw1", "none", "none", "只写一次(读写)"),
    ("w1", "w1", "none", "none", "只写一次(只写)"),
]


def resolve_type(value):
    key = str(value or "rw").strip().lower()
    return TYPE_MAP.get(key, TYPE_MAP["rw"])
