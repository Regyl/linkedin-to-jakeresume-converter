"""Render Jake's Resume from structured data and validate the result."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader

from src.exception import ResumeError
from src.util.latex_escape_util import display_url, escape_latex, escape_latex_url
from src.model import SECTION_ORDER, ResumeData
from src.util.utils import configure_cli_logging

log = logging.getLogger(__name__)

STRUCTURAL_COMMANDS = [
    r"\documentclass",
    r"\begin{document}",
    r"\end{document}",
]

JAKE_COMMANDS = [
    r"\newcommand{\resumeItem}",
    r"\newcommand{\resumeSubheading}",
    r"\newcommand{\resumeProjectHeading}",
    r"\newcommand{\resumeSubItem}",
    r"\newcommand{\resumeItemListStart}",
    r"\newcommand{\resumeItemListEnd}",
]

_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = _ROOT / "data" / "templates" / "resume.tex"
_CONTACT_MAPPING_PATH = _ROOT / "data" / "contact_mapping.json"
# These characters break a LaTeX filename even inside \detokenize.
_PHOTO_PATH_BREAKERS = frozenset("%#{}")


def _load_site_names() -> tuple[tuple[str, str], ...]:
    mapping = json.loads(_CONTACT_MAPPING_PATH.read_text(encoding="utf-8"))
    return tuple((str(host).casefold(), str(name)) for host, name in mapping.items())


_SITE_NAMES = _load_site_names()


def link_label(link: object) -> str:
    """Short site name for a contact link. Unknown hosts use the PDF label."""
    url = str(getattr(link, "url", "") or "")
    label = str(getattr(link, "label", "") or "").strip()
    host = urlparse(url).netloc.casefold()
    if host.startswith("www."):
        host = host[4:]
    for suffix, name in _SITE_NAMES:
        if host == suffix or host.endswith("." + suffix):
            return name
    if label:
        return label
    return display_url(url)


def _resolve_template(template_path: Path | str | None) -> Path:
    if template_path is None:
        path = TEMPLATE_PATH
        label = str(TEMPLATE_PATH)
    else:
        path = Path(template_path)
        label = str(template_path)
    if not path.exists():
        raise ResumeError(f"Template file does not exist: {label}")
    if not path.is_file() or path.suffix.lower() != ".tex":
        raise ResumeError(f"Template file is not a .tex file: {label}")
    return path


def _is_builtin_template(path: Path) -> bool:
    return path.resolve() == TEMPLATE_PATH.resolve()


def resolve_photo_path(photo_path: Path | str | None) -> str | None:
    """Absolute forward-slash path safe to drop into a LaTeX filename.

    Compilation runs from the output directory, so a relative path would
    not be found. ``%``, ``#``, and braces still break TeX while it reads
    the ``\\detokenize`` argument.
    """
    if photo_path is None:
        return None
    raw = str(photo_path).strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_file():
        raise ResumeError(f"Photo file does not exist: {raw}")
    resolved = path.resolve().as_posix()
    broken = _PHOTO_PATH_BREAKERS.intersection(resolved)
    if broken:
        chars = ", ".join(sorted(broken))
        raise ResumeError(
            "Photo path contains characters LaTeX cannot use in a filename "
            f"({chars}): {resolved}"
        )
    return resolved


def render_resume(
    data: ResumeData,
    template_path: Path | str | None = None,
    photo: Path | str | None = None,
) -> str:
    path = _resolve_template(template_path)
    environment = Environment(
        loader=FileSystemLoader(str(path.parent)),
        autoescape=False,
        trim_blocks=False,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        # Jake's commands use {#1}. Keep that from being read as a Jinja comment.
        comment_start_string="<<#",
        comment_end_string="#>>",
    )
    environment.filters["latex"] = escape_latex
    environment.filters["latex_url"] = escape_latex_url
    environment.filters["url_display"] = display_url
    environment.filters["link_label"] = link_label
    template = environment.get_template(path.name)
    return template.render(
        name=data.name,
        headline=data.headline,
        contact=data.contact,
        summary=data.summary,
        experience=data.experience,
        experience_intro=data.experience_intro,
        education=data.education,
        education_intro=data.education_intro,
        skills=data.skills,
        projects=data.projects,
        certifications=data.certifications,
        awards=data.awards,
        publications=data.publications,
        languages=data.languages,
        additional=data.additional,
        section_order=SECTION_ORDER,
        photo=resolve_photo_path(photo),
    )


def validate_tex(tex: str, data: ResumeData, *, require_jake_commands: bool = True) -> None:
    try:
        tex.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ResumeError("Generated LaTeX is not valid UTF-8.") from exc

    required = list(STRUCTURAL_COMMANDS)
    if require_jake_commands:
        required.extend(JAKE_COMMANDS)
    missing = [command for command in required if command not in tex]
    if missing:
        raise ResumeError(
            "Generated LaTeX is missing required commands: " + ", ".join(missing)
        )

    if r"\begin{document}" not in tex:
        raise ResumeError("Generated LaTeX is missing \\begin{document}.")
    body = tex.split(r"\begin{document}", 1)[1]
    needs_entries = bool(data.experience or data.education or data.certifications or data.awards)
    if require_jake_commands and needs_entries and r"\resumeSubheading" not in body:
        raise ResumeError("Generated LaTeX is missing \\resumeSubheading entries.")

    issues = find_suspicious(body)
    if issues:
        raise ResumeError(
            "Generated LaTeX contains unescaped characters: " + "; ".join(issues[:8])
        )
    if not _balanced_braces(tex):
        raise ResumeError("Generated LaTeX has unbalanced braces.")


def find_suspicious(body: str) -> list[str]:
    """Find raw LaTeX specials that would come from unescaped resume text."""
    issues: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if body.startswith(r"\detokenize", index):
            index = _skip_detokenize(body, index)
            continue
        if char == "\\":
            nxt = body[index + 1 : index + 2]
            if nxt in set("&%$#_{}~^\\"):
                index += 2
                continue
            if nxt.isalpha():
                cursor = index + 1
                while cursor < len(body) and body[cursor].isalpha():
                    cursor += 1
                index = cursor
                continue
            issues.append(_snippet(body, index))
            index += 1
            continue
        if char == "$" and body.startswith("$|$", index):
            index += 3
            continue
        if char in "&%$#_~^":
            issues.append(_snippet(body, index))
        index += 1
    return issues


def _skip_detokenize(body: str, index: int) -> int:
    """Move past ``\\detokenize{...}``. Its contents are a filename, not resume text."""
    cursor = index + len(r"\detokenize")
    if cursor < len(body) and body[cursor].isalpha():
        return index + 1
    while cursor < len(body) and body[cursor].isspace():
        cursor += 1
    if cursor >= len(body) or body[cursor] != "{":
        return index + 1
    depth = 0
    while cursor < len(body):
        char = body[cursor]
        if char == "\\":
            cursor += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return cursor + 1
        cursor += 1
    return len(body)


def _snippet(body: str, index: int) -> str:
    start = max(0, index - 12)
    end = min(len(body), index + 12)
    sample = body[start:end].replace("\n", " ")
    return f"{body[index]!r} near {sample!r}"


def _balanced_braces(tex: str) -> bool:
    depth = 0
    index = 0
    while index < len(tex):
        char = tex[index]
        if char == "\\":
            index += 2
            continue
        if char == "%":
            newline = tex.find("\n", index)
            index = len(tex) if newline < 0 else newline + 1
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
        index += 1
    return depth == 0


def write_resume(
    data: ResumeData,
    output_path: Path,
    template_path: Path | str | None = None,
    photo: Path | str | None = None,
) -> str:
    path = _resolve_template(template_path)
    tex = render_resume(data, path, photo=photo)
    validate_tex(tex, data, require_jake_commands=_is_builtin_template(path))
    output_path.write_text(tex, encoding="utf-8")
    return tex


def compile_tex(tex_path: Path) -> None:
    configure_cli_logging()
    compiler = shutil.which("pdflatex") or shutil.which("xelatex")
    if not compiler:
        log.warning("Warning: pdflatex and xelatex were not found; skipped compilation.")
        return
    result = subprocess.run(
        [compiler, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
        cwd=tex_path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        compiler_output = (result.stdout or "") + "\n" + (result.stderr or "")
        tail = compiler_output[-1500:].strip()
        name = Path(compiler).name
        raise ResumeError(f"LaTeX compilation failed with {name}.\n{tail}")
