import re
from pathlib import Path

import openpyxl


def normalize(value):
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v or None
    return value


def normalize_key(value):
    if value is None:
        return ""
    return re.sub(r"\s+", "_", str(value).strip().lower())


def open_workbook(path):
    return openpyxl.load_workbook(Path(path), data_only=True)


def sheet_rows(worksheet):
    return [[normalize(c) for c in row] for row in worksheet.iter_rows(values_only=True)]


def find_sheet(workbook, names):
    wanted = {n.lower() for n in names}
    for title in workbook.sheetnames:
        if title.strip().lower() in wanted:
            return workbook[title]
    return None


def header_map(header, aliases):
    mapping = {}
    for i, cell_value in enumerate(header):
        key = normalize_key(cell_value)
        if key in aliases and aliases[key] not in mapping:
            mapping[aliases[key]] = i
    return mapping


def cell(row, index):
    if index is None or index < 0 or index >= len(row):
        return None
    return row[index]


def forward_fill(rows, indices):
    last = {}
    result = []
    for row in rows:
        new_row = list(row)
        for idx in indices:
            if idx is None or idx < 0:
                continue
            if idx >= len(new_row):
                new_row.extend([None] * (idx - len(new_row) + 1))
            value = new_row[idx]
            if value is None:
                new_row[idx] = last.get(idx)
            else:
                last[idx] = value
        result.append(new_row)
    return result


def parse_int(value, default=0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value).strip(), 0)
    except ValueError:
        return default


def parse_bits(value, width):
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value) & ((1 << width) - 1)
    text = str(value).strip().replace(",", "")
    if not text:
        return 0
    low = text.lower()
    try:
        if low.startswith("0b"):
            return int(text, 2) & ((1 << width) - 1)
        if low.startswith("0x"):
            return int(text, 16) & ((1 << width) - 1)
        if set(text) <= {"0", "1"} and len(text) == width:
            return int(text, 2) & ((1 << width) - 1)
        return int(text, 10) & ((1 << width) - 1)
    except ValueError:
        return 0
