"""Custom LaTeX template rendering."""

import os
from pathlib import Path

import pytest

from main import load_settings
from src.exception import ResumeError
from src.latex_generator import write_resume
from src.model import (
    CertificationEntry,
    Contact,
    ContactLink,
    EducationEntry,
    ExperienceEntry,
    ResumeData,
)

LINKS_TEMPLATE = Path(__file__).resolve().parents[1] / "data" / "templates" / "regyl_template.tex"

CUSTOM_TEMPLATE = """\\documentclass{article}
\\begin{document}
{{ name | latex }}
\\end{document}
"""


def test_custom_template_renders_without_jake_commands(tmp_path: Path) -> None:
    template = tmp_path / "custom.tex"
    template.write_text(CUSTOM_TEMPLATE, encoding="utf-8")
    data = ResumeData(
        name="Ada & Lovelace",
        experience=[ExperienceEntry(title="Engineer")],
    )

    tex = write_resume(data, tmp_path / "out.tex", template)

    assert r"Ada \& Lovelace" in tex
    assert r"\newcommand{\resumeSubheading}" not in tex


def test_missing_template_raises(tmp_path: Path) -> None:
    with pytest.raises(ResumeError, match="does not exist"):
        write_resume(ResumeData(name="Ada"), tmp_path / "out.tex", tmp_path / "missing.tex")


def test_template_must_be_tex(tmp_path: Path) -> None:
    template = tmp_path / "custom.txt"
    template.write_text("not latex", encoding="utf-8")
    with pytest.raises(ResumeError, match="not a .tex file"):
        write_resume(ResumeData(name="Ada"), tmp_path / "out.tex", template)


def test_links_template_names_sites_and_shrinks_certifications(tmp_path: Path) -> None:
    data = ResumeData(
        name="Ada",
        contact=Contact(
            email="ada@example.com",
            links=[
                ContactLink(url="https://github.com/ada", label="Portfolio"),
                ContactLink(url="https://tryhackme.com/p/ada", label="Portfolio"),
                ContactLink(url="https://t.me/ada", label="Personal"),
                ContactLink(url="https://notes.example.com/ada", label="Notes"),
            ],
        ),
        experience=[ExperienceEntry(title="Engineer")],
        certifications=[CertificationEntry(name="EF SET", issuer="EF", dates="2024")],
    )

    tex = write_resume(data, tmp_path / "out.tex", LINKS_TEMPLATE)

    assert "GitHub" in tex
    assert "TryHackMe" in tex
    assert "Telegram" in tex
    assert "Notes" in tex
    certifications = tex.split(r"\section{Certifications}", 1)[1]
    assert r"\resumeItem{EF SET, EF (2024)}" in certifications
    assert r"\resumeSubheading" not in certifications


def test_regyl_template_uses_summary_font_for_role_meta(tmp_path: Path) -> None:
    data = ResumeData(
        summary="Builds reliable systems.",
        experience=[
            ExperienceEntry(
                title="Engineer",
                company="Acme",
                dates="2020 -- 2024",
                location="Moscow, Russia",
            )
        ],
        education=[
            EducationEntry(
                school="State University",
                degree="B.Sc. Computer Science",
                dates="2016 -- 2020",
                location="Kazan, Russia",
            )
        ],
    )

    tex = write_resume(data, tmp_path / "out.tex", LINKS_TEMPLATE)
    experience = tex.split(r"\section{Experience}", 1)[1].split(r"\section{Education}", 1)[0]
    education = tex.split(r"\section{Education}", 1)[1]

    assert r"{\small Builds reliable systems.\par}" in tex
    assert r"{\small{2020 -- 2024}}" in experience
    assert r"{\small{Acme}}" in experience
    assert r"{\small{Moscow, Russia}}" in experience
    assert r"\textit" not in experience
    assert r"{\small{2016 -- 2020}}" in education
    assert r"\textit{\small{B.Sc. Computer Science}}" in education


def test_regyl_template_omits_avatar_without_photo(tmp_path: Path) -> None:
    tex = write_resume(ResumeData(name="Ada"), tmp_path / "out.tex", LINKS_TEMPLATE)

    assert r"\includegraphics" not in tex
    assert r"\usepackage{graphicx}" not in tex


def test_regyl_template_renders_circular_avatar(tmp_path: Path) -> None:
    photo = tmp_path / "my_photo.jpg"
    photo.write_bytes(b"")

    tex = write_resume(
        ResumeData(name="Ada"),
        tmp_path / "out.tex",
        LINKS_TEMPLATE,
        photo=photo,
    )

    expected = photo.resolve().as_posix()
    assert r"\usepackage{graphicx}" in tex
    assert r"\usepackage{tikz}" in tex
    assert r"\clip (0,0) circle (1.05cm);" in tex
    assert r"\includegraphics[height=2.1cm]{\detokenize{" + expected + "}}" in tex


def test_missing_photo_raises(tmp_path: Path) -> None:
    with pytest.raises(ResumeError, match="does not exist"):
        write_resume(
            ResumeData(name="Ada"),
            tmp_path / "out.tex",
            LINKS_TEMPLATE,
            photo=tmp_path / "missing.jpg",
        )


def test_photo_path_rejects_latex_breakers(tmp_path: Path) -> None:
    photo = tmp_path / "a#b.jpg"
    photo.write_bytes(b"")

    with pytest.raises(ResumeError, match="cannot use in a filename"):
        write_resume(
            ResumeData(name="Ada"),
            tmp_path / "out.tex",
            LINKS_TEMPLATE,
            photo=photo,
        )


def test_settings_load_from_dotenv(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    keys = ("PDF_PATH", "COMPILE", "TEMPLATE", "PHOTO_PATH")
    previous = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)

        env_file.write_text("PDF_PATH=resume.pdf\nCOMPILE=false\nTEMPLATE=\n", encoding="utf-8")
        settings = load_settings(env_file)
        assert settings.pdf_path == "resume.pdf"
        assert settings.compile_tex is False
        assert settings.template is None
        assert settings.photo is None

        for key in keys:
            os.environ.pop(key, None)
        env_file.write_text(
            "PDF_PATH=resume.pdf\nCOMPILE=true\nTEMPLATE=custom.tex\n"
            "PHOTO_PATH=photo.jpg\n",
            encoding="utf-8",
        )
        settings = load_settings(env_file)
        assert settings.compile_tex is True
        assert settings.template == "custom.tex"
        assert settings.photo == "photo.jpg"
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
