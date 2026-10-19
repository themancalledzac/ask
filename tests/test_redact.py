import pytest

from ask.redact import redact, redact_lines

AKIA = "AKIA" + "IOSFODNN7" + "EXAMPLE"
GHP = "ghp_" + "a1b2c3d4e5f6" + "a1b2c3d4e5f6"
GITHUB_PAT = "github_pat_" + "FAKE0123456789" + "abcdefgh"
SK = "sk-" + "fake0123456789" + "abcdefgh"
SLACK = "xoxb-" + "fake0123456789" + "abcdefgh"
JWT = "eyJ" + "fakehead" + "." + "fakebody" + "." + "fakesig"


@pytest.mark.parametrize(
    "line",
    [
        f"key {AKIA} end",
        f"token {GHP} end",
        f"use {GITHUB_PAT}",
        f"openai {SK}",
        f"slack {SLACK}",
        f"jwt {JWT} done",
    ],
)
def test_secret_patterns_are_redacted(line):
    out = redact(line)
    assert "[redacted]" in out
    for secret in (AKIA, GHP, GITHUB_PAT, SK, SLACK, JWT):
        assert secret not in out


def test_url_password_is_redacted():
    pw = "hunter" + "2pass"
    out = redact(f"postgres://admin:{pw}@db.example.com/app")
    assert out == "postgres://[redacted]@db.example.com/app"


@pytest.mark.parametrize("name", ["api_key", "api-key", "apikey", "secret", "token", "password", "passwd"])
def test_assignment_replaces_only_the_value(name):
    value = "s3cr3t" + "value99"
    assert redact(f'{name} = "{value}"') == f'{name} = "[redacted]"'
    assert redact(f"{name}: {value}") == f"{name}: [redacted]"


def test_short_assignment_value_is_kept():
    assert redact("password = short") == "password = short"


@pytest.mark.parametrize(
    "line",
    [
        "see https://example.com/path for details",
        "the token is described in the docs",
        "risk-management-plan-v2-final-draft",
        "ask-me-anything-about-things-sk-short",
    ],
)
def test_ordinary_text_is_untouched(line):
    assert redact(line) == line


def test_pem_block_keeps_line_count():
    lines = [
        "before",
        "-----BEGIN RSA PRIVATE KEY-----",
        "MIIfakefakefake",
        "-----END RSA PRIVATE KEY-----",
        "after",
    ]
    assert redact_lines(lines) == ["before", "[redacted]", "[redacted]", "[redacted]", "after"]


def test_three_line_pem_block():
    lines = ["-----BEGIN PRIVATE KEY-----", "abc", "-----END PRIVATE KEY-----"]
    assert redact_lines(lines) == ["[redacted]"] * 3


def test_unterminated_pem_redacts_to_end():
    lines = ["-----BEGIN PRIVATE KEY-----", "abc", "def"]
    assert redact_lines(lines) == ["[redacted]"] * 3


def test_redact_lines_applies_single_line_patterns_and_keeps_length():
    lines = ["x", f"k {AKIA}", ""]
    out = redact_lines(lines)
    assert len(out) == 3
    assert out[0] == "x"
    assert AKIA not in out[1]
