"""Convert a LinkedIn PDF resume into Jake's Resume LaTeX."""

from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import NamedTuple

from dotenv import load_dotenv

from src.exception import ResumeError
from src.latex_generator import compile_tex, write_resume
from src.model import LinkedInDocument
from src.parser import parse_document
from src.pdf_reader import read_resume
from src.util.utils import configure_cli_logging, display_output_path, ensure_output_parent, validate_pdf_path

log = logging.getLogger(__name__)

_ENV_FILE = Path(__file__).resolve().parent / ".env"
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"", "0", "false", "no", "off"}


class Settings(NamedTuple):
    pdf_path: str
    compile_tex: bool
    template: str | None
    photo: str | None


def _as_bool(name: str, value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ResumeError(f"{name} in .env must be true or false")


def load_settings(env_file: Path | None = None) -> Settings:
    """Load conversion settings from the project .env file."""
    load_dotenv(env_file if env_file is not None else _ENV_FILE)
    pdf_path = os.getenv("PDF_PATH", "").strip()
    if not pdf_path:
        raise ResumeError(
            "Set PDF_PATH in .env to the LinkedIn-exported PDF resume. "
            "Copy .env.example to .env to get started."
        )
    template = os.getenv("TEMPLATE", "").strip() or None
    photo = os.getenv("PHOTO_PATH", "").strip() or None
    return Settings(
        pdf_path=pdf_path,
        compile_tex=_as_bool("COMPILE", os.getenv("COMPILE")),
        template=template,
        photo=photo,
    )


def convert(
    pdf_path: str,
    template_path: str | None = None,
    photo_path: str | None = None,
) -> Path:
    source = Path(pdf_path)
    validate_pdf_path(source, display=pdf_path)
    output_path = Path("output") / f"{source.stem}.tex"
    ensure_output_parent(output_path)

    document = read_resume(source)
    data = parse_document(document)
    write_resume(data, output_path, template_path, photo=photo_path)
    _write_debug(output_path, document, data)
    return output_path


def _write_debug(output_path: Path, document: LinkedInDocument, data) -> None:
    extracted = [
        document.name,
        *document.contact_lines,
        *document.summary_lines,
        *document.skill_lines,
        *document.language_lines,
        *document.certification_lines,
        *document.honor_lines,
    ]
    for entry in document.experience + document.education:
        extracted.append("")
        extracted.extend(entry)
    debug_dir = output_path.parent
    (debug_dir / "extracted.txt").write_text("\n".join(extracted), encoding="utf-8")
    (debug_dir / "parsed.json").write_text(
        json.dumps(data.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    configure_cli_logging()
    try:
        settings = load_settings()
    except ResumeError as exc:
        log.error("Error: %s", exc)
        return 1

    output_path = convert(
        pdf_path=settings.pdf_path,
        template_path=settings.template,
        photo_path=settings.photo,
    )

    log.info("Generated:")
    log.info(display_output_path(output_path))

    if settings.compile_tex:
        try:
            compile_tex(output_path)
        except ResumeError as exc:
            log.error("Error: %s", exc)
            traceback.print_exc()
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
