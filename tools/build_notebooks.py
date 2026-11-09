#!/usr/bin/env python3
"""Converts src/notebooks/*.py (percent format) into Fabric-importable .ipynb files in dist/notebooks/.

    python tools/build_notebooks.py

Cell markers:  '# %%' code cell, '# %% [markdown]' markdown cell,
               '# %% tags=["parameters"]' parameter cell (Fabric: "Toggle parameter cell").
Only needed for the first import; afterwards the workspace is synced with Git (folder workspace/)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "notebooks"
OUT = ROOT / "dist" / "notebooks"


def cells_of(text):
    cells, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^# %%(.*)$", line)
        if m:
            if cur:
                cells.append(cur)
            header = m.group(1)
            cur = {"type": "markdown" if "[markdown]" in header else "code",
                   "tags": ["parameters"] if "parameters" in header else [], "lines": []}
            continue
        if cur is None:
            continue
        if cur["type"] == "markdown":
            line = line[2:] if line.startswith("# ") else line.lstrip("#")
        cur["lines"].append(line)
    if cur:
        cells.append(cur)
    nb_cells = []
    for i, c in enumerate(cells):
        lines = c["lines"]
        while lines and not lines[-1].strip():
            lines.pop()
        while lines and not lines[0].strip():
            lines.pop(0)
        source = [l + "\n" for l in lines[:-1]] + lines[-1:]
        if c["type"] == "markdown":
            nb_cells.append({"cell_type": "markdown", "id": f"cell{i:02d}", "metadata": {}, "source": source})
        else:
            nb_cells.append({"cell_type": "code", "id": f"cell{i:02d}", "execution_count": None, "outputs": [],
                             "metadata": {"tags": c["tags"]} if c["tags"] else {}, "source": source})
    return nb_cells


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for py in sorted(SRC.glob("*.py")):
        nb = {"nbformat": 4, "nbformat_minor": 5,
              "metadata": {"kernel_info": {"name": "synapse_pyspark"},
                           "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark", "language": "Python"},
                           "language_info": {"name": "python"}},
              "cells": cells_of(py.read_text(encoding="utf-8"))}
        (OUT / f"{py.stem}.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
        print("built", OUT / f"{py.stem}.ipynb")


if __name__ == "__main__":
    main()
