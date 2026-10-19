"""MCP server that exposes the ask answer function as a single tool over stdio."""

from typing import Any

from mcp.server.mcpserver import MCPServer

from ask.access import get_role
from ask.answer import answer
from ask.store import connect

server = MCPServer("ask")


@server.tool()
def ask(question: str, repo: str | None = None) -> dict[str, Any]:
    """Answer where, who and status questions from repos added with the `ask` CLI, optionally scoped by `repo` (a repo name or absolute path). Every fact carries a repo:path:line citation, and owners come only from the `owners` field, never from `recent_committers` or `repo_info`. Status `not_found` means the answer is not in the added repos."""
    con = connect()
    try:
        return answer(con, question, get_role(), repo)
    finally:
        con.close()


def main() -> None:
    """Run the server over stdio."""
    server.run()
