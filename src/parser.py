"""Map an already-split LinkedIn resume onto structured entries."""

from __future__ import annotations

import re

from src.exception import ResumeError
from src.model import (
    CertificationEntry,
    Contact,
    ContactLink,
    EducationEntry,
    ExperienceEntry,
    LinkedInDocument,
    ResumeData,
    SkillGroup,
)
from src.util.utils import is_bullet, is_date_line, normalize_date, squash, strip_bullet

_EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
_URL_RE = re.compile(
    r"^(?:https?://|www\.)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s]*)?$",
    re.IGNORECASE,
)
_LABEL_ONLY_RE = re.compile(r"^\(([^)]+)\)\s*$")
_TRAILING_LABEL_RE = re.compile(r"\s*\(([^)]+)\)\s*$")
_TENURE_RE = re.compile(
    r"^(?:\d+\s+years?(?:\s+\d+\s+months?)?|\d+\s+months?)$",
    re.IGNORECASE,
)
_EMBEDDED_DATE_RE = re.compile(r"\s*[·•]\s*\(([^)]+)\)\s*$")


def parse_document(document: LinkedInDocument) -> ResumeData:
    data = ResumeData()
    data.name = document.name
    _fill_contact(document.contact_lines, data.contact)
    if document.summary_lines:
        # LinkedIn's about block is the headline under the name.
        data.headline = squash(" ".join(document.summary_lines))
    data.experience_intro = _wrap(document.honor_lines)
    company = ""
    for lines in document.experience:
        entry, company = _role(lines, company)
        data.experience.append(entry)
    data.education = [_school(lines) for lines in document.education if lines]
    if document.skill_lines:
        data.skills.append(SkillGroup("Skills", _wrap(document.skill_lines)))
    data.certifications = [
        CertificationEntry(name=name) for name in _wrap(document.certification_lines)
    ]
    data.languages = [line for line in document.language_lines if line]
    if not data.has_sections():
        raise ResumeError("No recognizable resume sections were found.")
    return data


def _fill_contact(lines: list[str], contact: Contact) -> None:
    index = 0
    while index < len(lines):
        raw = lines[index].strip()
        index += 1
        if not raw:
            continue
        if _EMAIL_RE.fullmatch(raw):
            if not contact.email:
                contact.email = raw
            continue

        body, label = _split_label(raw)
        if not body:
            continue
        if index < len(lines):
            nxt = lines[index].strip()
            label_only = _LABEL_ONLY_RE.match(nxt)
            if label_only:
                label = label_only.group(1).strip()
                index += 1
            elif _url_continues(body, nxt):
                token, next_label = _split_label(nxt)
                body = f"{body}{token}"
                if next_label:
                    label = next_label
                index += 1
        if not _URL_RE.fullmatch(body):
            continue
        contact.links.append(ContactLink(url=_normalize_link(body), label=label))
    _fill_legacy_urls(contact)


def _split_label(text: str) -> tuple[str, str]:
    match = _TRAILING_LABEL_RE.search(text)
    if not match:
        return text.strip(), ""
    return text[: match.start()].strip(), match.group(1).strip()


def _url_continues(url: str, nxt: str) -> bool:
    """Join a URL cut by a line wrap onto a non-domain token."""
    if not url.endswith(("-", "/")) or not _URL_RE.fullmatch(url):
        return False
    token, _label = _split_label(nxt)
    if not token or _URL_RE.fullmatch(token):
        return False
    return _URL_RE.fullmatch(f"{url}{token}") is not None


def _normalize_link(url: str) -> str:
    cleaned = url.rstrip(".,);")
    lower = cleaned.casefold()
    if lower.startswith("http://") or lower.startswith("https://"):
        return cleaned
    return "https://" + cleaned


def _fill_legacy_urls(contact: Contact) -> None:
    others: list[str] = []
    for link in contact.links:
        lower = link.url.casefold()
        if "linkedin.com" in lower:
            if not contact.linkedin:
                contact.linkedin = link.url
        elif "github.com" in lower:
            if not contact.github:
                contact.github = link.url
        else:
            others.append(link.url)
    if len(others) == 1:
        contact.website = others[0]


def _role(lines: list[str], company: str) -> tuple[ExperienceEntry, str]:
    date_index = next((index for index, line in enumerate(lines) if is_date_line(line)), None)
    if date_index is None:
        return ExperienceEntry(bullets=_wrap(lines)), company
    header = [line for line in lines[:date_index] if not _TENURE_RE.match(line)]
    title = ""
    if len(header) >= 2:
        company, title = header[0], header[1]
    elif header:
        title = header[0]
    rest = lines[date_index + 1 :]
    location = ""
    if rest and "," in rest[0] and not is_bullet(rest[0]):
        location = rest[0]
        rest = rest[1:]
    return (
        ExperienceEntry(
            title=title,
            company=company,
            dates=normalize_date(lines[date_index]),
            location=location,
            bullets=_wrap(rest),
        ),
        company,
    )


def _school(lines: list[str]) -> EducationEntry:
    merged = _join_open_dates(lines)
    school = merged[0] if merged else ""
    degree = merged[1] if len(merged) > 1 else ""
    dates = ""
    peeled, embedded = _peel_date(degree)
    if embedded:
        degree = peeled
        dates = embedded
    return EducationEntry(school=school, degree=degree, dates=dates)


def _join_open_dates(lines: list[str]) -> list[str]:
    joined: list[str] = []
    index = 0
    while index < len(lines):
        current = lines[index]
        if current.count("(") > current.count(")") and index + 1 < len(lines):
            joined.append(squash(f"{current} {lines[index + 1]}"))
            index += 2
            continue
        joined.append(current)
        index += 1
    return joined


def _peel_date(text: str) -> tuple[str, str]:
    match = _EMBEDDED_DATE_RE.search(text)
    if not match or not is_date_line(match.group(1)):
        return text, ""
    return text[: match.start()].strip(" ·•"), normalize_date(match.group(1))


def _wrap(lines: list[str]) -> list[str]:
    """Join a visual line wrap. A new bullet always starts a new item."""
    items: list[str] = []
    for raw in lines:
        bullet = is_bullet(raw)
        text = strip_bullet(raw) if bullet else raw.strip()
        if not text:
            continue
        if items and not bullet and _continues(items[-1], text):
            items[-1] = f"{items[-1]} {text}"
        else:
            items.append(text)
    return items


def _continues(previous: str, text: str) -> bool:
    if text[0].islower():
        return True
    return previous.endswith((",", "/", "&", "-"))
