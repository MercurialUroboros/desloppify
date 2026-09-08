"""Source views: alternative renderings of a file's text for analysis.

A *source view* keeps the file's line count and character positions so line
numbers reported by detectors map straight back to the file on disk, while
hiding text that the language tooling cannot parse.

Currently one view exists: the **script view** of a Vue single-file component,
which blanks everything outside ``<script>`` / ``<script setup>`` blocks so the
TypeScript detectors and the tree-sitter TSX grammar see only code.
"""

from __future__ import annotations

import re

VUE_SFC_SUFFIX = ".vue"

_SCRIPT_BLOCK_RE = re.compile(
    r"<script\b[^>]*>(?P<body>.*?)</script\s*>",
    re.DOTALL | re.IGNORECASE,
)


def has_source_view(filepath: str) -> bool:
    """True when *filepath* is rendered through a source view for analysis."""
    return filepath.lower().endswith(VUE_SFC_SUFFIX)


def vue_script_view(text: str) -> str:
    """Return *text* with everything outside ``<script>`` blocks blanked.

    Every character outside a script body becomes a space and newlines are
    kept, so the result has the same length, the same line count and the same
    column positions as the original SFC. Both ``<script>`` and
    ``<script setup>`` blocks are kept; a component with no script block yields
    an all-blank view.
    """
    if "<script" not in text.lower():
        return _blank_keep_newlines(text)

    pieces: list[str] = []
    cursor = 0
    for match in _SCRIPT_BLOCK_RE.finditer(text):
        body_start, body_end = match.start("body"), match.end("body")
        pieces.append(_blank_keep_newlines(text[cursor:body_start]))
        pieces.append(text[body_start:body_end])
        cursor = body_end
    pieces.append(_blank_keep_newlines(text[cursor:]))
    return "".join(pieces)


def source_view(filepath: str, text: str) -> str:
    """Return the analysis view of *text* for *filepath* (identity for most files)."""
    if has_source_view(filepath):
        return vue_script_view(text)
    return text


def _blank_keep_newlines(chunk: str) -> str:
    return "".join("\n" if ch == "\n" else " " for ch in chunk)


__all__ = ["VUE_SFC_SUFFIX", "has_source_view", "source_view", "vue_script_view"]
