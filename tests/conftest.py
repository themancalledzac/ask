import pytest


@pytest.fixture
def ask_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("ASK_HOME", str(home))
    return home
