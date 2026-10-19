import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ask.access import set_role
from ask.answer import answer
from ask.cli import main
from ask.model import NOT_FOUND, REFUSED
from ask.owners import remote_info
from ask.store import add_repo, connect, set_repo_role

ROOT = Path(__file__).resolve().parent.parent
CODEOWNERS_FIXTURE = ROOT / "eval" / "fixtures" / "codeowners"
NAME = "plain.app"
MESSAGE = f"No CODEOWNERS file in {NAME}, so no owner is recorded."
REMOTE = {"host": "github.com", "org": "acme", "name": "plain.app"}
WHOLE_REPO = [{"name": "Ben Ko", "commits": 2}, {"name": "Ana Lee", "commits": 1}]
APP_ONLY = [{"name": "Ana Lee", "commits": 1}]
TOKEN = "ghp_" + "A1b2" * 9


def git(root, *args, author=None):
    cmd = ["git", "-C", str(root), "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
    if author:
        cmd += ["-c", f"user.name={author}", "-c", f"user.email={author.split()[0].lower()}@x.test"]
    subprocess.run(cmd + list(args), check=True, capture_output=True)


def make_repo(root, url="git@github.com:acme/plain.app.git"):
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "src" / "app.py").write_text("print('app')\n")
    (root / "docs" / "notes.md").write_text("notes\n")
    git(root, "init", "-q")
    git(root, "remote", "add", "origin", url)
    git(root, "add", ".")
    git(root, "commit", "-qm", "first", author="Ana Lee")
    notes = root / "docs" / "notes.md"
    notes.write_text(notes.read_text() + "more\n")
    git(root, "commit", "-qam", "second", author="Ben Ko")
    notes.write_text(notes.read_text() + "again\n")
    git(root, "commit", "-qam", "third", author="Ben Ko")
    return root


@pytest.fixture
def plain(ask_home, tmp_path):
    con = connect()
    add_repo(con, make_repo(tmp_path / "plain"), NAME)
    return con


def expected(committers):
    return [{"repo": NAME, "remote": REMOTE, "recent_committers": committers}]


def assert_no_codeowners(result, committers):
    assert result["status"] == "not_found"
    assert result["kind"] == "owner"
    assert result["message"] == MESSAGE
    assert result["owners"] == []
    assert result["hits"] == [] and result["recent_committers"] == []
    assert result["repo_info"] == expected(committers)


def test_repo_flag_on_repo_without_codeowners(plain):
    assert_no_codeowners(answer(plain, "who owns this repo?", "employee", NAME), WHOLE_REPO)


def test_question_names_dotted_repo(plain):
    assert_no_codeowners(answer(plain, "who owns Plain.App?", "employee"), WHOLE_REPO)


def test_path_in_repo_without_codeowners_scopes_committers(plain):
    assert_no_codeowners(answer(plain, "who owns src/app.py?", "employee"), APP_ONLY)
    assert_no_codeowners(answer(plain, "who owns src/?", "employee"), APP_ONLY)


def test_owner_question_with_no_target_is_plain_not_found(plain):
    result = answer(plain, "who owns kubernetes?", "employee")
    assert result["message"] == NOT_FOUND
    assert result["kind"] is None and result["repo_info"] == []


def test_repo_flag_with_an_unrelated_subject_is_plain_not_found(plain):
    result = answer(plain, "who owns kubernetes?", "employee", NAME)
    assert result["status"] == "not_found"
    assert result["message"] == NOT_FOUND
    assert result["kind"] is None and result["repo_info"] == []


def test_repo_flag_with_the_repo_name_or_a_repo_word_targets_it(plain):
    for question in ("who owns plain app?", "who owns the codebase?", "who owns plain.app?"):
        assert answer(plain, question, "employee", NAME)["message"] == MESSAGE


def test_cli_text_labels_org_and_committers_as_not_owners(plain, capsys):
    assert main(["rbac", "employee"]) == 0
    capsys.readouterr()
    assert main(["who", "owns", "this", "repo?", "--repo", NAME]) == 1
    assert capsys.readouterr().out.splitlines() == [
        MESSAGE,
        "GitHub org (not an owner): acme on github.com",
        "Recent committers, not owners: Ben Ko (2), Ana Lee (1)",
    ]


def test_cli_prefixes_lines_with_repo_when_several_repos(plain, tmp_path, capsys):
    add_repo(plain, make_repo(tmp_path / "other", "git@gitlab.com:beta/other.app.git"), "other.app")
    assert main(["rbac", "employee"]) == 0
    capsys.readouterr()
    assert main(["who", "owns", "plain.app", "and", "other.app?"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "No CODEOWNERS file in other.app, so no owner is recorded. " + MESSAGE,
        "other.app: GitHub org (not an owner): beta on gitlab.com",
        "other.app: Recent committers, not owners: Ben Ko (2), Ana Lee (1)",
        f"{NAME}: GitHub org (not an owner): acme on github.com",
        f"{NAME}: Recent committers, not owners: Ben Ko (2), Ana Lee (1)",
    ]


@pytest.mark.parametrize(
    "url, info",
    [
        ("git@github.com:acme/widget.git", {"host": "github.com", "org": "acme", "name": "widget"}),
        ("git@github.com:acme/widget", {"host": "github.com", "org": "acme", "name": "widget"}),
        ("ssh://git@github.com/acme/widget.git", {"host": "github.com", "org": "acme", "name": "widget"}),
        ("ssh://git@git.example.com:2222/acme/widget", {"host": "git.example.com", "org": "acme", "name": "widget"}),
        ("https://github.com/acme/edens.zac.git", {"host": "github.com", "org": "acme", "name": "edens.zac"}),
        ("https://user:secretvalue@github.com/acme/widget.git", {"host": "github.com", "org": "acme", "name": "widget"}),
        (f"https://{TOKEN}@github.com/acme/widget.git", {"host": "github.com", "org": "acme", "name": "widget"}),
        ("/srv/git/widget.git", None),
        ("https://github.com/widget", None),
    ],
)
def test_remote_info_parses_origin(tmp_path, url, info):
    git(tmp_path, "init", "-q")
    git(tmp_path, "remote", "add", "origin", url)
    assert remote_info(tmp_path) == info


def test_remote_info_without_origin_is_none(tmp_path):
    git(tmp_path, "init", "-q")
    assert remote_info(tmp_path) is None


def test_remote_info_outside_git_is_none(tmp_path):
    assert remote_info(tmp_path) is None


def test_remote_info_in_a_subfolder_of_a_git_repo_is_none(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "remote", "add", "origin", "git@github.com:acme/widget.git")
    (tmp_path / "inner").mkdir()
    assert remote_info(tmp_path / "inner") is None


def test_token_in_remote_never_reaches_output(ask_home, tmp_path, capsys):
    url = f"https://user:{TOKEN}@github.com/acme/plain.app.git"
    con = connect()
    add_repo(con, make_repo(tmp_path / "plain", url), NAME)
    result = answer(con, "who owns plain.app?", "employee")
    assert main(["rbac", "employee"]) == 0
    capsys.readouterr()
    assert main(["who", "owns", "plain.app?"]) == 1
    assert main(["who", "owns", "plain.app?", "--json"]) == 1
    out = capsys.readouterr().out
    for text in (out, json.dumps(result)):
        assert TOKEN not in text
        assert "user:" not in text
        assert "user@" not in text
    assert "GitHub org (not an owner): acme on github.com" in out
    assert result["repo_info"][0]["remote"] == REMOTE


def test_codeowners_rule_with_no_owners_stays_plain_not_found(ask_home, tmp_path):
    root = tmp_path / "owned"
    shutil.copytree(CODEOWNERS_FIXTURE, root)
    con = connect()
    add_repo(con, root, "owned")
    for result in (
        answer(con, "who owns vendor/lib.txt?", "employee"),
        answer(con, "who owns vendor/lib.txt?", "employee", "owned"),
    ):
        assert result["status"] == "not_found"
        assert result["message"] == NOT_FOUND
        assert result["kind"] is None and result["repo_info"] == []


def test_guest_naming_employee_repo_gets_plain_not_found(plain, tmp_path, capsys):
    open_root = tmp_path / "open"
    open_root.mkdir()
    (open_root / "readme.md").write_text("hello\n")
    add_repo(plain, open_root, "open")
    set_repo_role(plain, "open", "guest")
    result = answer(plain, "who owns plain.app?", "guest")
    assert result["status"] == "not_found"
    assert result["message"] == NOT_FOUND
    assert result["repo_info"] == []
    assert NAME not in json.dumps(result)
    assert answer(plain, "who owns this repo?", "guest", NAME)["message"] == REFUSED
    assert main(["who", "owns", "plain.app?"]) == 1
    assert main(["who", "owns", "plain.app?", "--json"]) == 1
    assert NAME not in capsys.readouterr().out


def test_mcp_tool_returns_repo_info(plain):
    pytest.importorskip("mcp")
    from ask.mcp_server import server

    set_role("employee")
    result = asyncio.run(server.call_tool("ask", {"question": "who owns this repo?", "repo": NAME}))
    assert result.structured_content["owners"] == []
    assert result.structured_content["repo_info"] == expected(WHOLE_REPO)


def test_repo_flag_with_an_unmatched_path_token_is_plain_not_found(plain):
    for question in ("who owns kubernetes.io?", "who owns lib/missing.py?"):
        result = answer(plain, question, "employee", NAME)
        assert result["status"] == "not_found"
        assert result["message"] == NOT_FOUND
        assert result["kind"] is None and result["repo_info"] == []
