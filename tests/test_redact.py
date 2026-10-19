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


VALUE = "abcd1234" + "efgh5678"
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/" + "bPxRfiCYEXAMPLEKEY"
SK_LIVE = "sk_live_" + "abcdefghijklmnop1234"
SK_TEST = "sk_test_" + "abcdefghijklmnop1234"
RK_LIVE = "rk_live_" + "abcdefghijklmnop1234"
BEARER = "abcdefghijklmnop" + "qrstuvwxyz123456"


@pytest.mark.parametrize(
    "line, secret",
    [
        (f'"password": "{VALUE}"', VALUE),
        (f'"secret": "{VALUE}",', VALUE),
        (f'"token": "{VALUE}"', VALUE),
        (f"'api_key': '{VALUE}'", VALUE),
        (f"SECRET_KEY = '{VALUE}'", VALUE),
        (f"DB_PASSWORD={VALUE}", VALUE),
        (f"github_token: {VALUE}", VALUE),
        (f"Stripe_Secret = {VALUE}", VALUE),
        (f"aws_secret_access_key = {AWS_SECRET}", AWS_SECRET),
        (f'export STRIPE_KEY="{SK_LIVE}"', SK_LIVE),
        (f"stripe {SK_TEST} test", SK_TEST),
        (f"restricted {RK_LIVE}", RK_LIVE),
        (f"Authorization: Bearer {BEARER}", BEARER),
        (f'headers = {{"Authorization": "Bearer {BEARER}"}}', BEARER),
    ],
)
def test_more_secret_shapes_are_redacted(line, secret):
    out = redact(line)
    assert secret not in out
    assert "[redacted]" in out


@pytest.mark.parametrize("password", ["pa/" + "ss1234", "p@" + "ss1234", "a/b@" + "c1234"])
def test_url_password_with_slash_or_at_is_redacted(password):
    out = redact(f"postgres://admin:{password}@db.example.com/app")
    assert out == "postgres://[redacted]@db.example.com/app"


def test_json_key_keeps_its_name_and_quotes():
    assert redact(f'"password": "{VALUE}",') == '"password": "[redacted]",'


@pytest.mark.parametrize(
    "line",
    [
        "reset your password in the account settings page",
        "send a Bearer header with each request",
        "the primary key is the user id",
    ],
)
def test_more_ordinary_text_is_untouched(line):
    assert redact(line) == line


def test_redact_lines_keeps_count_with_new_shapes():
    lines = [f'"password": "{VALUE}"', "", f"Bearer {BEARER}"]
    assert len(redact_lines(lines)) == 3
