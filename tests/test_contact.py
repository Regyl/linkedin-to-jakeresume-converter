"""Contact sidebar parsing."""

from src.model import LinkedInDocument
from src.parser import parse_document

CONTACT_LINES = [
    "fakemail@gmail.com",
    "www.linkedin.com/in/eugene-",
    "novikov-regyl (LinkedIn)",
    "leetcode.com/u/novikovevgeny1/",
    "(Portfolio)",
    "github.com/Regyl (Portfolio)",
    "medium.com/@regyl (Blog)",
    "tryhackme.com/p/regyl (Portfolio)",
    "ieee-collabratec.ieee.org/app/p/",
    "Regyl (Blog)",
    "t.me/corgidile (Personal)",
]


def test_contact_lines_keep_every_link() -> None:
    data = parse_document(
        LinkedInDocument(contact_lines=CONTACT_LINES, skill_lines=["Java"])
    )
    contact = data.contact

    assert contact.email == "fakemail@gmail.com"
    assert contact.linkedin == "https://www.linkedin.com/in/eugene-novikov-regyl"
    assert contact.github == "https://github.com/Regyl"
    assert contact.website == ""
    assert [(link.url, link.label) for link in contact.links] == [
        ("https://www.linkedin.com/in/eugene-novikov-regyl", "LinkedIn"),
        ("https://leetcode.com/u/novikovevgeny1/", "Portfolio"),
        ("https://github.com/Regyl", "Portfolio"),
        ("https://medium.com/@regyl", "Blog"),
        ("https://tryhackme.com/p/regyl", "Portfolio"),
        ("https://ieee-collabratec.ieee.org/app/p/Regyl", "Blog"),
        ("https://t.me/corgidile", "Personal"),
    ]


def test_single_other_link_fills_website() -> None:
    data = parse_document(
        LinkedInDocument(
            contact_lines=["notes.example.com/me (Site)"],
            skill_lines=["Java"],
        )
    )

    assert data.contact.website == "https://notes.example.com/me"
    assert data.contact.linkedin == ""
    assert data.contact.links[0].label == "Site"
