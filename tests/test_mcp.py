import asyncio
import json

import pytest

pytest.importorskip("mcp")

from conftest import check_quotes
from ask.access import set_role
from ask.mcp_server import server
from ask.model import REFUSED
from ask.store import add_repo, connect

WORD = "plimvortex"


@pytest.fixture
def vault(ask_home, tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "notes.md").write_text(f"intro\n\nthe {WORD} service lives here\n")
    con = connect()
    add_repo(con, root)
    return con


def call(question, repo=None):
    args = {"question": question}
    if repo is not None:
        args["repo"] = repo
    result = asyncio.run(server.call_tool("ask", args))
    text = "".join(c.text for c in result.content)
    return text, result.structured_content


def test_only_ask_tool():
    tools = asyncio.run(server.list_tools())
    assert [t.name for t in tools] == ["ask"]


def test_schema_has_no_role():
    tool = asyncio.run(server.list_tools())[0]
    assert set(tool.input_schema["properties"]) == {"question", "repo"}
    assert tool.input_schema["required"] == ["question"]


def test_guest_naming_employee_repo_is_refused(vault):
    set_role("guest")
    text, result = call(f"where is {WORD}", repo="vault")
    assert result["status"] == "refused"
    assert result["message"] == REFUSED
    assert REFUSED in text
    assert WORD not in text
    assert WORD not in json.dumps(result)


def test_employee_finds_word_with_real_citation(vault):
    set_role("employee")
    text, result = call(f"where is {WORD}")
    assert result["status"] == "answered"
    assert result["hits"][0]["path"] == "notes.md"
    assert result["hits"][0]["line"] == 3
    check_quotes(vault, result)
