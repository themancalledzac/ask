import json
import shutil
from pathlib import Path

import pytest

from ask.answer import answer
from ask.cli import main
from ask.model import NOT_FOUND, REFUSED
from ask.redact import redact_lines
from ask.files import read_text_lines
from ask.store import add_repo, connect, list_repos, set_repo_role

SECRETS = {
    "aws": "AKIAABCDEFGHIJKLMNOP",
    "ghp": "ghp_abcdefghijklmnopqrstuvwx",
    "url": "hunter2password",
    "jwt": "eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.SflKxwRJSMeKKF2QT4",
    "assign": "supersecretvalue123",
    "pem": "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC",
}

SECRET_FILE = "\n".join(
    [
        f"awsmarker AKIA{SECRETS['aws'][4:]}",
        "",
        f"ghpmarker token {SECRETS['ghp']}",
        "",
        f"urlmarker postgres://admin:{SECRETS['url']}@db.internal/app",
        "",
        f"jwtmarker bearer {SECRETS['jwt']}",
        "",
        f"assignmarker password = \"{SECRETS['assign']}\"",
        "",
        "pemmarker",
        "-----BEGIN RSA PRIVATE KEY-----",
        SECRETS["pem"],
        "-----END RSA PRIVATE KEY-----",
        "",
    ]
)


def make(tmp_path, name, files, role="employee", con=None):
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    for fname, text in files.items():
        (root / fname).write_text(text)
    con = con or connect()
    add_repo(con, root, name)
    set_repo_role(con, name, role)
    return con


def check_quotes(con, result):
    paths = {r.name: Path(r.path) for r in list_repos(con)}
    for h in result["hits"]:
        lines = redact_lines(read_text_lines(paths[h["repo"]] / h["path"]))
        assert lines[h["line"] - 1].strip() == h["quote"]


@pytest.fixture
def two_repos(ask_home, tmp_path):
    con = make(tmp_path, "vault", {"notes.md": "the zorbquill service lives here\n"})
    make(tmp_path, "pub", {"readme.md": "public readme\nnothing special\n"}, "guest", con)
    return con


def test_guest_no_visible_match_gets_exact_not_found(two_repos, capsys):
    result = answer(two_repos, "zorbquill", "guest")
    assert result["status"] == "not_found"
    assert result["message"] == NOT_FOUND
    assert result["kind"] is None
    assert result["hits"] == [] and result["owners"] == [] and result["recent_committers"] == []
    assert main(["zorbquill"]) == 1
    assert capsys.readouterr().out == NOT_FOUND + "\n"


def test_guest_naming_employee_repo_is_refused_without_hints(two_repos, capsys):
    result = answer(two_repos, "zorbquill", "guest", repo="vault")
    assert result["status"] == "refused"
    assert result["message"] == REFUSED
    assert result["kind"] is None
    assert main(["zorbquill", "--repo", "vault"]) == 2
    out = capsys.readouterr().out
    assert out == REFUSED + "\n"
    assert "zorbquill" not in out and "notes.md" not in out


def test_guest_naming_employee_repo_by_path_is_refused(two_repos):
    path = next(r.path for r in list_repos(two_repos) if r.name == "vault")
    assert answer(two_repos, "zorbquill", "guest", repo=path)["status"] == "refused"
    assert answer(two_repos, "zorbquill", "guest", repo=path + "/sub")["status"] == "refused"


def test_employee_gets_hit_with_matching_quote(two_repos, capsys):
    result = answer(two_repos, "zorbquill", "employee")
    assert result["status"] == "answered"
    assert result["kind"] == "search"
    assert [(h["repo"], h["path"], h["line"]) for h in result["hits"]] == [("vault", "notes.md", 1)]
    check_quotes(two_repos, result)
    assert main(["rbac", "employee"]) == 0
    capsys.readouterr()
    assert main(["zorbquill"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "Found in:"
    assert lines[1] == "  vault:notes.md:1  the zorbquill service lives here"


def test_unknown_repo_is_not_found_even_for_guest(two_repos, tmp_path):
    assert answer(two_repos, "zorbquill", "guest", repo="nope")["status"] == "not_found"
    assert answer(two_repos, "zorbquill", "employee", repo=str(tmp_path / "elsewhere"))["status"] == "not_found"


def test_repo_by_name_scopes_search(ask_home, tmp_path):
    con = make(tmp_path, "one", {"a.md": "shared word\n"})
    make(tmp_path, "two", {"b.md": "shared word\n"}, con=con)
    result = answer(con, "shared", "employee", repo="two")
    assert {h["repo"] for h in result["hits"]} == {"two"}


def test_repo_by_path_inside_repo_resolves(ask_home, tmp_path):
    con = make(tmp_path, "one", {"a.md": "shared word\n"})
    make(tmp_path, "two", {"b.md": "shared word\n"}, con=con)
    inside = str(tmp_path / "one" / "deeper")
    result = answer(con, "shared", "employee", repo=inside)
    assert {h["repo"] for h in result["hits"]} == {"one"}


@pytest.mark.parametrize("key", list(SECRETS))
def test_no_output_contains_raw_secret(ask_home, tmp_path, capsys, key):
    con = make(tmp_path, "sec", {"conf.txt": SECRET_FILE})
    marker = {"aws": "awsmarker", "ghp": "ghpmarker", "url": "urlmarker",
              "jwt": "jwtmarker", "assign": "assignmarker", "pem": "pemmarker"}[key]
    result = answer(con, marker, "employee")
    assert result["status"] == "answered"
    check_quotes(con, result)
    assert SECRETS[key] not in json.dumps(result)
    assert main(["rbac", "employee"]) == 0
    capsys.readouterr()
    for flags in ([], ["--json"]):
        main([marker, *flags])
        out = capsys.readouterr().out
        assert out
        for secret in SECRETS.values():
            assert secret not in out


def test_odd_syntax_question_does_not_raise(two_repos):
    answer(two_repos, 'atlas-api "quoted" OR *:', "employee")


def test_empty_and_stopword_only_questions_exit_1(two_repos):
    assert main([""]) == 1
    assert main(["who is the"]) == 1
    assert answer(two_repos, "", "employee")["status"] == "not_found"


def test_three_words_two_cooccur_hits_on_fallback(ask_home, tmp_path):
    con = make(tmp_path, "r", {"a.md": "alpha beta\n\ngamma\n"})
    result = answer(con, "alpha beta zzzz", "employee")
    assert result["status"] == "answered"
    check_quotes(con, result)


def test_three_words_one_occurs_is_not_found(ask_home, tmp_path):
    con = make(tmp_path, "r", {"a.md": "alpha\n\nbeta\n"})
    assert answer(con, "alpha zzzz yyyy", "employee")["status"] == "not_found"


def test_two_words_one_occurs_is_not_found(ask_home, tmp_path):
    con = make(tmp_path, "r", {"a.md": "alpha\n"})
    assert answer(con, "alpha zzzz", "employee")["status"] == "not_found"


def test_single_missing_word_is_not_found(ask_home, tmp_path):
    con = make(tmp_path, "r", {"a.md": "alpha\n"})
    assert answer(con, "zzzz", "employee")["status"] == "not_found"


def test_services_overview_copy_does_not_know_aperture(ask_home, tmp_path):
    source = Path(__file__).resolve().parent.parent / "context-bundle" / "docs" / "services-overview.md"
    root = tmp_path / "docs"
    root.mkdir()
    shutil.copy(source, root / "services-overview.md")
    con = connect()
    add_repo(con, root, "docs")
    assert answer(con, "aperture", "employee")["status"] == "not_found"


def test_json_output_is_the_result_dict(two_repos, capsys):
    assert main(["rbac", "employee"]) == 0
    capsys.readouterr()
    assert main(["zorbquill", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "answered" and data["kind"] == "search"
    assert set(data) == {"status", "kind", "message", "owners", "hits", "recent_committers"}
    assert set(data["hits"][0]) == {"repo", "path", "line", "quote"}


def test_json_not_found_and_refused(two_repos, capsys):
    assert main(["zorbquill", "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "not_found" and data["kind"] is None
    assert main(["--json", "zorbquill", "--repo", "vault"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "refused"


def test_multiple_words_join_and_flags_anywhere(two_repos, capsys):
    assert main(["rbac", "employee"]) == 0
    capsys.readouterr()
    assert main(["zorbquill", "service", "--repo", "vault", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "answered"


def test_unknown_flag_and_missing_repo_value_are_usage_errors(two_repos, capsys):
    assert main(["zorbquill", "--role", "employee"]) == 3
    assert main(["zorbquill", "--repo"]) == 3
    assert capsys.readouterr().err
