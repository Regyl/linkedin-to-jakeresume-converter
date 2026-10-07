"""Tests for LaTeX escaping."""

from src.util.latex_escape_util import display_url, escape_latex, escape_latex_url


def test_escapes_special_characters():
    assert escape_latex("Java & Spring") == r"Java \& Spring"
    assert escape_latex("100%") == r"100\%"
    assert escape_latex("cost $5") == r"cost \$5"
    assert escape_latex("C#") == r"C\#"
    assert escape_latex("user_name") == r"user\_name"
    assert escape_latex("{braces}") == r"\{braces\}"
    assert escape_latex("~home") == r"\textasciitilde{}home"
    assert escape_latex("a^b") == r"a\textasciicircum{}b"
    assert escape_latex("A\\B") == r"A\textbackslash{}B"


def test_does_not_double_escape():
    assert escape_latex(r"Java \& Spring") == r"Java \& Spring"
    assert escape_latex(r"100\%") == r"100\%"
    assert escape_latex(r"user\_name") == r"user\_name"
    assert escape_latex(r"\{braces\}") == r"\{braces\}"
    assert escape_latex(r"\textbackslash{}") == r"\textbackslash{}"
    assert escape_latex(r"\textasciitilde{}") == r"\textasciitilde{}"
    assert escape_latex(r"\textasciicircum{}") == r"\textasciicircum{}"


def test_empty_and_plain_text():
    assert escape_latex("") == ""
    assert escape_latex("Developed backend services using Java and Spring Boot") == (
        "Developed backend services using Java and Spring Boot"
    )


def test_url_escaping():
    assert escape_latex_url("https://github.com/jane_doe") == r"https://github.com/jane\_doe"
    assert escape_latex_url("https://example.com/a%20b") == r"https://example.com/a\%20b"
    assert escape_latex_url(r"https://github.com/jane\_doe") == r"https://github.com/jane\_doe"
    assert display_url("https://linkedin.com/in/jane-doe/") == "linkedin.com/in/jane-doe"
    assert display_url("https://www.janedoe.dev") == "janedoe.dev"
