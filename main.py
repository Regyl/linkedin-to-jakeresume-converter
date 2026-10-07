"""Convert a LinkedIn PDF resume into Jake's Resume LaTeX."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path

from src.exception import ResumeError
from src.latex_generator import compile_tex, write_resume
from src.model import LinkedInDocument
from src.parser import parse_document
from src.pdf_reader import read_resume
from src.util.utils import configure_cli_logging, display_output_path, ensure_output_parent, validate_pdf_path

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a LinkedIn-exported PDF resume into Jake's Resume LaTeX."
    )
    parser.add_argument("pdf_path", help="Path to the LinkedIn-exported PDF resume")
    parser.add_argument(
        "--compile",
        action="store_true",
        dest="compile_tex",
        help="Compile the .tex file when pdflatex or xelatex is installed",
    )
    parser.add_argument(
        "--template",
        default=None,
        help="Jinja LaTeX template (.tex). Defaults to data/templates/resume.tex",
    )
    return parser


def convert(pdf_path: str, template_path: str | None = None) -> Path:
    source = Path(pdf_path)
    validate_pdf_path(source, display=pdf_path)
    output_path = Path("output") / f"{source.stem}.tex"
    ensure_output_parent(output_path)

    document = read_resume(source)
    data = parse_document(document)
    write_resume(data, output_path, template_path)
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


def main(argv: list[str] | None = None) -> int:
    configure_cli_logging()
    parser = build_parser()
    args = parser.parse_args(argv)
    output_path = convert(pdf_path=args.pdf_path, template_path=args.template)

    log.info("Generated:")
    log.info(display_output_path(output_path))

    if args.compile_tex:
        try:
            compile_tex(output_path)
        except ResumeError as exc:
            log.error("Error: %s", exc)
            traceback.print_exc()
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
