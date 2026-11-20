import os
import re
from pathlib import Path

import yaml

_ENV_RE = re.compile(r"\$\{([^}]+)\}")


def expand_env(value):
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)
    if isinstance(value, list):
        return [expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: expand_env(v) for k, v in value.items()}
    return value


def load_yaml(path):
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    return expand_env(data)
