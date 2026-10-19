import json
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import check_quotes

from ask.answer import answer
from ask.cli import main
from ask.model import NOT_FOUND
from ask.owners import load_services, recent_committers
from ask.store import add_repo, connect, set_repo_role

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "context-bundle"
CODEOWNERS_FIXTURE = ROOT / "eval" / "fixtures" / "codeowners"

SHARED_DESCRIPTIONS = {
    "services": [
        {"name": "alpha", "description": "Payments intake", "team": "A", "owner": "Ada One"},
        {"name": "beta", "description": "Payments refunds", "team": "B", "owner": "Bo Two"},
        {"name": "gamma", "description": "Refunds ledger only", "team": "C", "owner": "Cy Three"},
    ]
}


def git(root, *args, author=None):
    cmd = ["git", "-C", str(root), "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
    if author:
        cmd += ["-c", f"user.name={author}", "-c", f"user.email={author.split()[0].lower()}@x.test"]
    subprocess.run(cmd + list(args), check=True, capture_output=True)


@pytest.fixture
def bundle(ask_home):
    con = connect()
    add_repo(con, BUNDLE, "bundle")
    return con


@pytest.fixture
def owned(ask_home, tmp_path):
    root = tmp_path / "owned"
    shutil.copytree(CODEOWNERS_FIXTURE, root)
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-qm", "first", author="Ana Lee")
    api = root / "services" / "billing" / "api.py"
    api.write_text(api.read_text() + "\nchanged = 1\n")
    git(root, "commit", "-qam", "second", author="Ben Ko")
    api.write_text(api.read_text() + "\nchanged = 2\n")
    git(root, "commit", "-qam", "third", author="Ben Ko")
    con = connect()
    add_repo(con, root, "owned")
    return con


@pytest.fixture
def mixed(owned, tmp_path):
    root = tmp_path / "owned"
    (root / "vendor" / "billing").mkdir(parents=True)
    (root / "vendor" / "billing" / "notes.txt").write_text("vendored billing notes\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "vendor", author="Ana Lee")
    add_repo(owned, root, "owned")
    add_repo(owned, BUNDLE, "bundle")
    return owned


def owner_names(result):
    return [o["name"] for o in result["owners"]]


def test_ledger_owner_cites_services_json_owner_line(bundle):
    result = answer(bundle, "who owns ledger? billing export looks off", "employee")
    assert result["status"] == "answered"
    assert result["kind"] == "owner"
    assert owner_names(result) == ["Sofia Reyes"]
    owner = result["owners"][0]
    assert owner["team"] == "Ops"
    assert owner["citation"] == {
        "repo": "bundle",
        "path": "services.json",
        "line": 37,
        "quote": '"owner": "Sofia Reyes",',
    }
    assert result["hits"] == []
    assert result["recent_committers"] == []
    check_quotes(bundle, result)


def test_billing_description_word_names_ledger_owner(bundle):
    result = answer(bundle, "who owns billing now? I thought it was someone who left", "employee")
    assert result["status"] == "answered"
    assert owner_names(result) == ["Sofia Reyes"]
    check_quotes(bundle, result)


def test_unknown_service_is_not_found(bundle):
    result = answer(bundle, "who owns kubernetes?", "employee")
    assert result["status"] == "not_found"
    assert result["message"] == NOT_FOUND
    assert result["owners"] == [] and result["hits"] == []


def test_review_question_names_forge_owner(bundle):
    result = answer(bundle, "who should review my PR for forge?", "employee")
    assert result["status"] == "answered"
    assert owner_names(result) == ["Priya Nadkarni"]
    assert result["owners"][0]["citation"]["line"] == 47
    check_quotes(bundle, result)


def test_hyphenated_name_needs_every_part(bundle):
    assert owner_names(answer(bundle, "who owns atlas-api?", "employee")) == ["Priya Nadkarni"]
    assert answer(bundle, "who owns atlas?", "employee")["status"] == "not_found"


def test_codeowners_path_gives_last_match_with_committers(owned):
    result = answer(owned, "who owns services/billing/api.py?", "employee")
    assert result["status"] == "answered"
    assert result["kind"] == "owner"
    assert result["owners"] == [
        {
            "name": "@fixture-ana",
            "team": None,
            "citation": {
                "repo": "owned",
                "path": ".github/CODEOWNERS",
                "line": 5,
                "quote": "/services/billing/api.py @fixture-ana",
            },
        }
    ]
    assert result["recent_committers"] == [
        {"name": "Ben Ko", "commits": 2},
        {"name": "Ana Lee", "commits": 1},
    ]
    check_quotes(owned, result)


def test_codeowners_directory_question(owned):
    result = answer(owned, "who owns services/billing/?", "employee")
    assert owner_names(result) == ["@fixture/billing", "@fixture-ben"]
    assert result["owners"][0]["citation"]["line"] == 4
    check_quotes(owned, result)


def test_codeowners_rule_with_no_owners_is_not_found(owned):
    result = answer(owned, "who owns vendor/lib.txt?", "employee")
    assert result["status"] == "not_found"
    assert result["message"] == NOT_FOUND


def test_cli_labels_committers_as_not_owners(owned, capsys):
    assert main(["rbac", "employee"]) == 0
    capsys.readouterr()
    assert main(["who", "owns", "services/billing/api.py?"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "Owner of services/billing/api.py:"
    assert lines[1] == "@fixture-ana  owned:.github/CODEOWNERS:5  /services/billing/api.py @fixture-ana"
    assert lines[2] == "Recent committers, not owners: Ben Ko (2), Ana Lee (1)"


def test_cli_owner_line_shows_team(bundle, capsys):
    assert main(["rbac", "employee"]) == 0
    capsys.readouterr()
    assert main(["who", "owns", "ledger?"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "Owner of ledger:",
        'Sofia Reyes (Ops)  bundle:services.json:37  "owner": "Sofia Reyes",',
    ]


def test_guest_gets_exact_not_found_for_employee_services(ask_home, tmp_path, capsys):
    root = tmp_path / "private"
    root.mkdir()
    shutil.copy(BUNDLE / "services.json", root / "services.json")
    con = connect()
    add_repo(con, root, "private")
    assert answer(con, "who owns ledger?", "employee")["status"] == "answered"
    result = answer(con, "who owns ledger?", "guest")
    assert result["status"] == "not_found"
    assert result["message"] == NOT_FOUND
    assert main(["who", "owns", "ledger?"]) == 1
    assert capsys.readouterr().out == NOT_FOUND + "\n"


def test_owner_never_comes_from_markdown(ask_home, tmp_path):
    root = tmp_path / "docsonly"
    root.mkdir()
    (root / "README.md").write_text("The zorbit service is owned by Zed Quill.\nZed Quill owns zorbit and its alerts.\n")
    con = connect()
    add_repo(con, root, "docsonly")
    set_repo_role(con, "docsonly", "guest")
    result = answer(con, "who owns zorbit?", "employee")
    assert result["status"] == "not_found"
    assert result["message"] == NOT_FOUND
    assert "Zed Quill" not in json.dumps(result)


def test_description_word_shared_by_two_services_is_not_found(ask_home, tmp_path):
    root = tmp_path / "shared"
    root.mkdir()
    (root / "services.json").write_text(json.dumps(SHARED_DESCRIPTIONS, indent=2))
    con = connect()
    add_repo(con, root, "shared")
    assert answer(con, "who owns payments?", "employee")["status"] == "not_found"
    assert owner_names(answer(con, "who owns intake?", "employee")) == ["Ada One"]


def test_load_services_finds_owner_lines():
    services = load_services(BUNDLE)
    assert [s.name for s in services][:2] == ["atlas-api", "beacon"]
    assert {s.name: s.owner_line for s in services}["ledger"] == 37
    assert services[0].owner_line == 7


def test_recent_committers_outside_git_is_empty(tmp_path):
    assert recent_committers(tmp_path, None) == []


def test_mixed_empty_owner_rule_is_not_found(mixed):
    result = answer(mixed, "who owns vendor/billing/notes.txt?", "employee")
    assert result["status"] == "not_found"
    assert result["message"] == NOT_FOUND
    assert "Sofia" not in json.dumps(result)


def test_mixed_path_question_answers_from_codeowners_only(mixed):
    result = answer(mixed, "who owns services/billing/api.py?", "employee")
    assert owner_names(result) == ["@fixture-ana"]
    text = json.dumps(result)
    assert "Sofia" not in text and "Priya" not in text
    check_quotes(mixed, result)


def test_mixed_service_named_outside_path_still_answers(mixed):
    result = answer(mixed, "who owns ledger and services/billing/api.py?", "employee")
    assert owner_names(result) == ["Sofia Reyes", "@fixture-ana"]
    check_quotes(mixed, result)


def test_file_name_without_directory_is_not_found(owned):
    result = answer(owned, "who owns README.md?", "employee")
    assert result["status"] == "not_found"
    assert result["message"] == NOT_FOUND


def test_recent_committers_needs_git_root(tmp_path):
    root = tmp_path / "outer"
    inner = root / "inner"
    inner.mkdir(parents=True)
    (inner / "a.txt").write_text("a\n")
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-qm", "one", author="Ana Lee")
    assert recent_committers(root, "inner/a.txt") == [{"name": "Ana Lee", "commits": 1}]
    assert recent_committers(inner, "a.txt") == []


def test_owner_listed_before_name_cites_its_own_line(ask_home, tmp_path):
    root = tmp_path / "odd"
    root.mkdir()
    (root / "services.json").write_text(
        '{"services": [\n  {"owner": "Al First",\n   "name": "alpha"},\n  {"name": "beta",\n   "owner": "Bo Two"}\n]}\n'
    )
    con = connect()
    add_repo(con, root, "odd")
    result = answer(con, "who owns alpha?", "employee")
    assert owner_names(result) == ["Al First"]
    assert result["owners"][0]["citation"]["line"] == 2
    assert owner_names(answer(con, "who owns beta?", "employee")) == ["Bo Two"]


ORDER_MIX = """{"services": [
  {
    "owner": "Priya Nadkarni",
    "name": "alpha"
  },
  {
    "name": "beta",
    "owner": "Priya Nadkarni"
  },
  {
    "owner": "Ann Lee",
    "name": "gamma"
  },
  {
    "name": "delta",
    "owner": "Marcus Webb"
  },
  {
    "name": "epsilon",
    "team": "E"
  },
  {
    "owner": "Anna Lee",
    "name": "zeta"
  }
]}
"""


def test_owner_line_stays_inside_its_own_service(ask_home, tmp_path):
    root = tmp_path / "mix"
    root.mkdir()
    (root / "services.json").write_text(ORDER_MIX)
    lines = {s.name: s.owner_line for s in load_services(root)}
    assert lines == {"alpha": 3, "beta": 8, "gamma": 11, "delta": 16, "epsilon": 0, "zeta": 23}
    con = connect()
    add_repo(con, root, "mix")
    for name, owner, line in (("alpha", "Priya Nadkarni", 3), ("gamma", "Ann Lee", 11), ("zeta", "Anna Lee", 23)):
        result = answer(con, f"who owns {name}?", "employee")
        assert owner_names(result) == [owner]
        assert result["owners"][0]["citation"]["line"] == line
        check_quotes(con, result)
    assert answer(con, "who owns epsilon?", "employee")["status"] == "not_found"
