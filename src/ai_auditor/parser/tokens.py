"""Approximate token counting.

Exact counts need the provider's tokenizer (or its count_tokens endpoint, which is
a network call this tool does not make by default). We use ``tiktoken`` when it is
installed, otherwise a piece-based heuristic that tracks BPE behaviour better than
``len/4`` on code, JSON and non-English text. Every number derived from this module
is labelled as an estimate in reports.
"""

from __future__ import annotations

import re
from functools import lru_cache

_PIECE = re.compile(r"[A-Za-zÀ-ÿ]+|\d+|\s+|[^\sA-Za-zÀ-ÿ\d]")

try:  # optional dependency
    import tiktoken  # type: ignore

    _ENC = tiktoken.get_encoding("cl100k_base")
    METHOD = "tiktoken:cl100k_base (approximation of provider tokenizers)"
except Exception:  # pragma: no cover - depends on environment
    _ENC = None
    METHOD = "heuristic (word pieces; expect ±25% vs provider tokenizers)"


@lru_cache(maxsize=4096)
def count_tokens(text: str) -> int:
    if not text:
        return 0
    if _ENC is not None:
        return len(_ENC.encode(text))
    n = 0
    for piece in _PIECE.findall(text):
        if piece.isspace():
            n += piece.count("\n") // 2  # runs of blank lines cost tokens; single spaces merge into words
        elif piece.isalpha():
            n += 1 if len(piece) <= 6 else -(-len(piece) // 5)
        elif piece.isdigit():
            n += -(-len(piece) // 3)
        else:
            n += 1
    return max(n, 1)
