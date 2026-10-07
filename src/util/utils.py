"""Shared helpers for dates, paths, and CLI logging."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

from src.exception import ResumeError

_cli_logging_configured = False


def _from_application(record: logging.LogRecord) -> bool:
    name = record.name
    return name in {"main", "__main__"} or name == "src" or name.startswith("src.")


def configure_cli_logging() -> None:
    """Send INFO to stdout and WARNING/ERROR to stderr. Safe to call more than once."""
    global _cli_logging_configured
    if _cli_logging_configured:
        return

    formatter = logging.Formatter("%(message)s")
    stdout = logging.StreamHandler(sys.stdout)
    stdout.setLevel(logging.INFO)
    stdout.addFilter(lambda record: record.levelno <= logging.INFO)
    stdout.addFilter(_from_application)
    stdout.setFormatter(formatter)

    stderr = logging.StreamHandler(sys.stderr)
    stderr.setLevel(logging.WARNING)
    stderr.setFormatter(formatter)

    root = logging.root
    root.setLevel(logging.INFO)
    root.addHandler(stdout)
    root.addHandler(stderr)
    _cli_logging_configured = True


MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?"
)
YEAR = r"(?:19|20)\d{2}"
DATE_PART = rf"(?:{MONTH}\s+{YEAR}|{YEAR})"
PRESENT = r"(?:Present|Current|Now)"
DATE_RANGE = rf"{DATE_PART}\s*[-–—−]\s*(?:{DATE_PART}|{PRESENT})"
DATE_PREFIX = r"(?:Issued|Expires?|Expected)"

BULLET_RE = re.compile(r"^(?:[•●▪◦\-\*\u2022\u25E6]|\d+[.)])\s+")
DURATION_TAIL = re.compile(
    r"\s*(?:[·•]\s*)?\(?\s*\d+\s*(?:years?|yrs?|months?|mos?)"
    r"(?:\s+\d+\s*(?:months?|mos?))?\s*\)?\s*$",
    re.IGNORECASE,
)
DATE_LINE_RE = re.compile(
    rf"^(?:{DATE_PREFIX}\s+)?(?:{DATE_RANGE}|{DATE_PART})$",
    re.IGNORECASE,
)
RANGE_RE = re.compile(
    rf"^(?P<pre>{DATE_PREFIX}\s+)?(?P<a>{DATE_PART})\s*[-–—−]\s*"
    rf"(?P<b>{DATE_PART}|{PRESENT})$",
    re.IGNORECASE,
)
SINGLE_RE = re.compile(
    rf"^(?P<pre>{DATE_PREFIX}\s+)?(?P<a>{DATE_PART})$",
    re.IGNORECASE,
)


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_bullet(text: str) -> str:
    return BULLET_RE.sub("", text.strip()).strip()


def is_bullet(text: str) -> bool:
    return bool(BULLET_RE.match(text.strip()))


def split_duration(text: str) -> tuple[str, str]:
    """Split a trailing span such as ``· 1 yr 8 mos`` or ``(10 months)``."""
    cleaned = strip_bullet(text)
    match = DURATION_TAIL.search(cleaned)
    if not match:
        return squash(cleaned.strip(" ·•-–—")), ""
    head = cleaned[: match.start()].strip(" ·•-–—")
    return squash(head), squash(match.group(0))


def clean_for_date(text: str) -> str:
    head, _suffix = split_duration(text)
    return head


def is_date_line(text: str) -> bool:
    cleaned = clean_for_date(text)
    if not cleaned or len(cleaned) > 80:
        return False
    return bool(DATE_LINE_RE.fullmatch(cleaned))


def normalize_date(text: str) -> str:
    """Normalize dash glyphs in a date and keep a duration suffix.

    Do not invent missing months.
    """
    cleaned, suffix = split_duration(text)
    ranged = RANGE_RE.fullmatch(cleaned)
    if ranged:
        prefix = ranged.group("pre") or ""
        left = squash(ranged.group("a"))
        right = squash(ranged.group("b"))
        return _with_duration(f"{prefix}{left} -- {right}".strip(), suffix)
    single = SINGLE_RE.fullmatch(cleaned)
    if single:
        prefix = single.group("pre") or ""
        return _with_duration(f"{prefix}{squash(single.group('a'))}".strip(), suffix)
    return squash(text)


def _with_duration(base: str, suffix: str) -> str:
    if not suffix:
        return base
    return f"{base} {suffix}"


def validate_pdf_path(path: Path, display: str | None = None) -> None:
    label = display if display is not None else str(path)
    if not path.exists():
        raise ResumeError(f"PDF file does not exist: {label}")
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise ResumeError(f"Input file is not a PDF: {label}")
    try:
        with path.open("rb") as handle:
            header = handle.read(5)
    except OSError as exc:
        raise ResumeError(f"Unable to read PDF: {label}") from exc
    if not header.startswith(b"%PDF"):
        raise ResumeError(f"Input file is not a PDF: {label}")


def ensure_output_parent(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ResumeError(f"Unable to create output directory: {path.parent}") from exc


def display_output_path(path: Path) -> str:
    try:
        shown = path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        shown = path
    return shown.as_posix()
