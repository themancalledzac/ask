from pathlib import Path

import pytest

from ask.files import read_text_lines
from ask.redact import redact_lines
from ask.store import list_repos


@pytest.fixture
def ask_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("ASK_HOME", str(home))
    return home


def check_quotes(con, result):
    paths = {r.name: Path(r.path) for r in list_repos(con)}
    for h in result["hits"]:
        lines = redact_lines(read_text_lines(paths[h["repo"]] / h["path"]))
        assert lines[h["line"] - 1].strip() == h["quote"]
