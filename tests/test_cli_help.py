import pytest

from ask.cli import main

COMMANDS = ["add-repo", "list-repos", "remove-repo", "update-repo", "rbac", "--json", "--repo"]


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_prints_usage_and_exits_0(ask_home, capsys, flag):
    assert main([flag]) == 0
    out, err = capsys.readouterr()
    assert err == ""
    for command in COMMANDS:
        assert command in out
    assert "ask rbac" in out
    assert "role" in out


def test_help_does_not_ask_a_question(ask_home, capsys):
    main(["--help"])
    assert "Not found" not in capsys.readouterr().out
