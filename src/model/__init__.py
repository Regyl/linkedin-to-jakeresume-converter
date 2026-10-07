"""Structured resume data produced by the parser."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


# Single place that controls section order in the generated resume.
SECTION_ORDER = [
    "summary",
    "experience",
    "education",
    "skills",
    "projects",
    "certifications",
    "awards",
    "publications",
    "languages",
    "additional",
]


@dataclass
class LinkedInDocument:
    """A default LinkedIn export, already split into independent sections."""

    name: str = ""
    contact_lines: list[str] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)
    skill_lines: list[str] = field(default_factory=list)
    language_lines: list[str] = field(default_factory=list)
    certification_lines: list[str] = field(default_factory=list)
    honor_lines: list[str] = field(default_factory=list)
    experience: list[list[str]] = field(default_factory=list)
    education: list[list[str]] = field(default_factory=list)


@dataclass
class ContactLink:
    url: str = ""
    label: str = ""


@dataclass
class Contact:
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""
    location: str = ""
    links: list[ContactLink] = field(default_factory=list)


@dataclass
class ExperienceEntry:
    title: str = ""
    company: str = ""
    dates: str = ""
    location: str = ""
    bullets: list[str] = field(default_factory=list)


@dataclass
class EducationEntry:
    school: str = ""
    degree: str = ""
    dates: str = ""
    location: str = ""
    details: list[str] = field(default_factory=list)


@dataclass
class ProjectEntry:
    name: str = ""
    technologies: str = ""
    dates: str = ""
    bullets: list[str] = field(default_factory=list)


@dataclass
class CertificationEntry:
    name: str = ""
    issuer: str = ""
    dates: str = ""


@dataclass
class SimpleEntry:
    title: str = ""
    subtitle: str = ""
    dates: str = ""
    details: list[str] = field(default_factory=list)


@dataclass
class SkillGroup:
    category: str
    names: list[str] = field(default_factory=list)


@dataclass
class ExtraSection:
    title: str
    entries: list[SimpleEntry] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)


@dataclass
class ResumeData:
    name: str = ""
    headline: str = ""
    contact: Contact = field(default_factory=Contact)
    summary: str = ""
    experience: list[ExperienceEntry] = field(default_factory=list)
    experience_intro: list[str] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    education_intro: list[str] = field(default_factory=list)
    skills: list[SkillGroup] = field(default_factory=list)
    projects: list[ProjectEntry] = field(default_factory=list)
    certifications: list[CertificationEntry] = field(default_factory=list)
    awards: list[SimpleEntry] = field(default_factory=list)
    publications: list[SimpleEntry] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    additional: list[ExtraSection] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def has_sections(self) -> bool:
        return any(
            [
                self.summary,
                self.experience,
                self.experience_intro,
                self.education,
                self.education_intro,
                self.skills,
                self.projects,
                self.certifications,
                self.awards,
                self.publications,
                self.languages,
                self.additional,
            ]
        )
