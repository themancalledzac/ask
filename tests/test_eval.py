import json
import os

import pytest

from ask.eval import main


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.delenv("ASK_HOME", raising=False)
    (tmp_path / "eval").mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "notes.txt").write_text("the zebra crossing is on elm street\n")
    (proj / "CODEOWNERS").write_text("* @ops\n")
    return tmp_path


def _write(workspace, rows, repos=None):
    rows_file = workspace / "eval" / "seen.jsonl"
    rows_file.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    repos = repos or {"repos": [{"path": "proj", "role": "employee", "name": "proj"}]}
    (workspace / "eval" / "repos.json").write_text(json.dumps(repos))
    return rows_file


def test_counts_passes_and_fails(workspace, capsys):
    rows = [
        {"q": "zebra crossing", "role": "employee", "status": "answered", "path_endswith": "notes.txt"},
        {"q": "zebra crossing", "role": "employee", "status": "not_found"},
    ]
    code = main([str(_write(workspace, rows))])
    assert code == 0
    assert capsys.readouterr().out.strip() == "1/2 passed"


def test_wrong_status_is_a_fail(workspace, capsys):
    rows = [{"q": "zebra crossing", "role": "employee", "status": "refused"}]
    assert main([str(_write(workspace, rows))]) == 0
    assert capsys.readouterr().out.strip() == "0/1 passed"


def test_must_not_contain_is_case_insensitive(workspace, capsys):
    rows = [
        {"q": "zebra crossing", "role": "employee", "status": "answered", "must_not_contain": ["ELM STREET"]},
        {"q": "zebra crossing", "role": "employee", "status": "answered", "must_not_contain": ["absent"]},
    ]
    main([str(_write(workspace, rows))])
    assert capsys.readouterr().out.strip() == "1/2 passed"


def test_path_endswith_must_match(workspace, capsys):
    rows = [{"q": "zebra crossing", "role": "employee", "status": "answered", "path_endswith": "other.txt"}]
    main([str(_write(workspace, rows))])
    assert capsys.readouterr().out.strip() == "0/1 passed"


def test_owners_include_fails_when_no_owner(workspace, capsys):
    rows = [{"q": "zebra crossing", "role": "employee", "status": "answered", "owners_include": ["ops"]}]
    main([str(_write(workspace, rows))])
    assert capsys.readouterr().out.strip() == "0/1 passed"


def test_guest_row_cannot_see_employee_repo(workspace, capsys):
    rows = [{"q": "zebra crossing", "role": "guest", "status": "not_found", "must_not_contain": ["notes.txt"]}]
    main([str(_write(workspace, rows))])
    assert capsys.readouterr().out.strip() == "1/1 passed"


def test_repo_field_scopes_the_search(workspace, capsys):
    rows = [{"q": "zebra crossing", "role": "guest", "repo": "proj", "status": "refused"}]
    main([str(_write(workspace, rows))])
    assert capsys.readouterr().out.strip() == "1/1 passed"


def test_detail_prints_failing_question_and_reason(workspace, capsys):
    rows = [{"q": "zebra crossing", "role": "employee", "status": "refused"}]
    main([str(_write(workspace, rows)), "--detail"])
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[-1] == "0/1 passed"
    assert "zebra crossing" in lines[0]
    assert "status" in lines[0]


def test_non_detail_never_prints_hit_text(workspace, capsys):
    rows = [{"q": "zebra crossing", "role": "employee", "status": "refused"}]
    main([str(_write(workspace, rows))])
    out = capsys.readouterr().out
    assert "elm street" not in out
    assert "zebra" not in out


def test_missing_repo_is_skipped_with_a_stderr_line(workspace, capsys):
    repos = {
        "repos": [
            {"path": "proj", "role": "employee", "name": "proj"},
            {"path": "nowhere", "role": "employee", "name": "nowhere"},
        ],
    }
    rows = [{"q": "zebra crossing", "role": "employee", "status": "answered"}]
    code = main([str(_write(workspace, rows, repos))])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == "1/1 passed"
    assert len(captured.err.strip().splitlines()) == 1
    assert "nowhere" in captured.err


def test_does_not_touch_ask_home_env_permanently(workspace, monkeypatch):
    monkeypatch.setenv("ASK_HOME", "/nonexistent-ask-home")
    rows = [{"q": "zebra crossing", "role": "employee", "status": "answered"}]
    main([str(_write(workspace, rows))])
    assert os.environ["ASK_HOME"] == "/nonexistent-ask-home"


def test_explicit_repos_option(workspace, capsys):
    rows_file = _write(workspace, [{"q": "zebra crossing", "role": "employee", "status": "answered"}])
    (workspace / "cfg").mkdir()
    elsewhere = workspace / "cfg" / "other.json"
    elsewhere.write_text(json.dumps({"repos": [{"path": "proj", "role": "employee", "name": "proj"}]}))
    (workspace / "eval" / "repos.json").unlink()
    assert main([str(rows_file), "--repos", str(elsewhere)]) == 0
    assert capsys.readouterr().out.strip() == "1/1 passed"
