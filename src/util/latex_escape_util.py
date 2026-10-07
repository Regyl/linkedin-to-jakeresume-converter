"""Escape plain text and URLs for LaTeX."""

from __future__ import annotations

import re

_CHAR_ESCAPES = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

_PROTECTED_COMMANDS = (
    "textbackslash{}",
    "textasciitilde{}",
    "textasciicircum{}",
)
_SIMPLE_ESCAPES = set("&%$#_{}\\")


def _protected_sequence(rest: str) -> str | None:
    for sequence in _PROTECTED_COMMANDS:
        if rest.startswith(sequence):
            return sequence
    if rest[:1] in _SIMPLE_ESCAPES:
        return rest[:1]
    return None


def escape_latex(text: str) -> str:
    """Escape LaTeX special characters without double-escaping.

    Backslashes are escaped first. Sequences that are already escaped
    (``\\&``, ``\\%``, ``\\textbackslash{}``, and similar) are left as-is.
    """
    if text is None:
        return ""
    value = str(text)
    output: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\":
            protected = _protected_sequence(value[index + 1 :])
            if protected:
                output.append("\\" + protected)
                index += 1 + len(protected)
                continue
            output.append(r"\textbackslash{}")
            index += 1
            continue
        output.append(_CHAR_ESCAPES.get(char, char))
        index += 1
    return "".join(output)


def escape_latex_url(url: str) -> str:
    """Escape characters that break ``\\href`` URLs."""
    if url is None:
        return ""
    value = str(url).strip()
    output: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and value[index + 1 : index + 2] in _SIMPLE_ESCAPES:
            output.append(value[index : index + 2])
            index += 2
            continue
        output.append(_CHAR_ESCAPES.get(char, char))
        index += 1
    return "".join(output)


def display_url(url: str) -> str:
    text = url.strip()
    text = re.sub(r"^https?://", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^www\.", "", text, flags=re.IGNORECASE)
    return text.rstrip("/")
