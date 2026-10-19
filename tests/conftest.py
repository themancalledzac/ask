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
    cites = list(result["hits"]) + [o["citation"] for o in result.get("owners", [])]
    for c in cites:
        lines = redact_lines(read_text_lines(paths[c["repo"]] / c["path"]))
        assert lines[c["line"] - 1].strip() == c["quote"]
