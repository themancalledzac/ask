import os

import pytest

from ask.access import can_see, get_role
from ask.cli import main


def test_unset_role_is_guest(ask_home):
    assert get_role() == "guest"
    assert main(["rbac"]) == 0


def test_unset_role_prints_guest(ask_home, capsys):
    main(["rbac"])
    assert capsys.readouterr().out.strip() == "guest"


def test_set_then_print_employee(ask_home, capsys):
    assert main(["rbac", "employee"]) == 0
    assert capsys.readouterr().out.strip() == "role set to employee"
    assert main(["rbac"]) == 0
    assert capsys.readouterr().out.strip() == "employee"


def test_unknown_role_exits_3_with_one_line(ask_home, capsys):
    assert main(["rbac", "admin"]) == 3
    err = capsys.readouterr().err
    assert len(err.strip().splitlines()) == 1
    assert "admin" in err
    assert get_role() == "guest"


def test_config_written_to_ask_home(ask_home):
    main(["rbac", "employee"])
    assert (ask_home / "config.toml").read_text() == 'role = "employee"\n'


def test_invalid_role_in_config_reads_as_guest(ask_home):
    ask_home.mkdir()
    (ask_home / "config.toml").write_text('role = "admin"\n')
    assert get_role() == "guest"


def test_question_cannot_set_role(ask_home):
    assert main(["rbac", "--role", "employee"]) == 3
    assert main(["where is the thing", "--role", "employee"]) == 3
    assert get_role() == "guest"


def test_bare_ask_prints_usage_and_exits_3(ask_home, capsys):
    assert main([]) == 3
    assert "usage" in capsys.readouterr().err


def test_can_see_pairs():
    assert can_see("guest", "employee") is False
    assert can_see("guest", "guest") is True
    assert can_see("employee", "employee") is True
    assert can_see("employee", "guest") is True


def test_config_with_bad_utf8_reads_as_guest(ask_home):
    ask_home.mkdir()
    (ask_home / "config.toml").write_bytes(b'role = "\xff"\n')
    assert get_role() == "guest"


def test_config_that_is_a_directory_reads_as_guest(ask_home):
    (ask_home / "config.toml").mkdir(parents=True)
    assert get_role() == "guest"


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores mode 000")
def test_unreadable_config_reads_as_guest(ask_home):
    ask_home.mkdir()
    config = ask_home / "config.toml"
    config.write_text('role = "employee"\n')
    config.chmod(0)
    try:
        assert get_role() == "guest"
    finally:
        config.chmod(0o644)
