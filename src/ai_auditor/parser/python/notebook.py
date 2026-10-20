"""Jupyter notebooks as Python sources: code cells concatenated, IPython syntax neutralized.

Line numbers in findings refer to this converted script; each cell starts with a ``# %% [cell N]`` marker so a
location can be traced back to its cell. Cells that still fail to parse are dropped one by one (and reported) so a
single broken cell does not hide the rest of the notebook.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

_PY_CELL_MAGICS = {"capture", "time", "timeit", "prun", "debug"}  # the cell body is still Python
_LINE_MAGIC = re.compile(r"^(\s*)([%!]|\?\?|\?)(.*)$")


def _cell_lines(source: str) -> list[str] | None:
    lines = source.splitlines()
    if lines and lines[0].lstrip().startswith("%%"):
        magic = lines[0].lstrip()[2:].split(maxsplit=1)[0] if lines[0].lstrip()[2:].strip() else ""
        if magic not in _PY_CELL_MAGICS:
            return None  # %%bash, %%writefile, %%html ...: not Python
        lines = ["# " + lines[0].strip()] + lines[1:]
    out = []
    for ln in lines:
        m = _LINE_MAGIC.match(ln)
        if m and not ln.lstrip().startswith("#"):
            # keep the line count stable; `x = !ls` and `%pip install` become comments / no-ops
            out.append(f"{m.group(1)}pass  # {m.group(2)}{m.group(3)}"[:400])
        elif re.match(r"^\s*\w[\w.]*\s*=\s*[%!]", ln):
            out.append(re.sub(r"=\s*[%!].*$", "= None  # magic", ln))
        else:
            out.append(ln)
    return out


def parse(text: str, rel: str) -> ast.Module:
    return compile(text, rel, "exec", flags=ast.PyCF_ONLY_AST | ast.PyCF_ALLOW_TOP_LEVEL_AWAIT, dont_inherit=True)  # type: ignore[return-value]


def notebook_source(path: Path) -> tuple[str, list[str]]:
    """(python source, warnings). Raises ValueError when the file is not a readable notebook."""
    try:
        nb = json.loads(path.read_text(errors="replace"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"not a valid notebook: {exc.msg}") from exc
    cells = nb.get("cells") if isinstance(nb, dict) else None
    if not isinstance(cells, list):
        raise ValueError("not a valid notebook: no cells")
    chunks: list[str] = []
    warnings: list[str] = []
    for i, cell in enumerate(cells, 1):
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        src = cell.get("source", "")
        src = "".join(src) if isinstance(src, list) else str(src)
        lines = _cell_lines(src)
        if lines is None:
            continue
        body = "\n".join(lines)
        try:
            parse(body, f"cell {i}")
        except SyntaxError as exc:
            warnings.append(f"cell {i}: SyntaxError: {exc.msg} (skipped)")
            continue
        chunks.append(f"# %% [cell {i}]\n{body}\n")
    return "\n".join(chunks), warnings
