# ask

`ask` is a command line tool that answers "where does X live" and "who owns X" from repos you add. Every answer cites `repo:path:line`, and the quoted text is on that line. Owners come only from `services.json` or CODEOWNERS, and a role (employee or guest) decides which repos a question can see.

The write-up for the take-home is in [notes/WRITEUP.md](notes/WRITEUP.md).

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- git

`ask` uses only the Python standard library. The MCP server needs the optional `mcp` extra (see below).

## Run it

One command, without installing:

```
uvx --from git+https://github.com/themancalledzac/ask ask --help
```

Replace `--help` with any command below.

Or clone it and run through uv:

```
git clone https://github.com/themancalledzac/ask
cd ask
uv run ask --help
```

## Demo

These six commands use the context bundle that ships in the repo. Run them from the repo root. This output is from a fresh `ASK_HOME`.

```
$ ask rbac employee
role set to employee

$ ask add-repo context-bundle
added context-bundle (8 files, role employee)

$ ask "who owns billing now?"
Owner of ledger:
Sofia Reyes (Ops)  context-bundle:services.json:37  "owner": "Sofia Reyes",

$ ask "how do I deploy to prod?"
Found in:
context-bundle:docs/deploy-pipeline.md:11  3. Staging deploy is automatic. **Production requires a manual approval** in the
context-bundle:services.json:5  "description": "Core GraphQL/REST API behind the product",

$ ask rbac guest
role set to guest

$ ask "how do I deploy to prod?"
Not found in added repos.
```

The guest gets "Not found" because new repos default to the employee role. Naming the repo directly is refused:

```
$ ask "how do I deploy to prod?" --repo context-bundle
Refused: needs employee access
```

To let guests see the bundle, an employee runs `ask update-repo context-bundle guest`.

## Commands

| Command | What it does |
| --- | --- |
| `ask "<question>"` | Answer from the repos your role can see. |
| `ask "<question>" --json` | The same answer as JSON: status, kind, message, owners, hits, recent committers and repo info. |
| `ask "<question>" --repo NAME` | Search only that repo. |
| `ask rbac` | Print your role. It starts as guest. |
| `ask rbac employee` or `ask rbac guest` | Set your role. |
| `ask add-repo <path> [--name N]` | Index a folder or git repo. A git repo indexes every tracked file. Employee only. |
| `ask list-repos` | List the repos your role can see. |
| `ask remove-repo <name>` | Delete a repo from the index. Employee only. |
| `ask update-repo <name> <employee\|guest>` | Change which role can see a repo. Employee only. |
| `ask --help` | Print usage. |

An owner question about a repo with no CODEOWNERS file says `No CODEOWNERS file in <repo>, so no owner is recorded.` and exits 1. The question targets a repo by its name, by a path in it, or with `--repo` when it asks about the repo itself (`who owns this repo?`). It also prints the GitHub org parsed from the `origin` remote and the top recent committers, both labelled as not owners. In `--json` they are under `repo_info`, and `owners` stays empty. Only the host, org and repo name of the remote are shown, never the URL or any user or token in it.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | Answered |
| 1 | Not found |
| 2 | Refused |
| 3 | Usage or input error |

## Use it from an agent (MCP)

`ask-mcp` runs an MCP server over stdio with one tool, `ask(question, repo?)`. It returns the same JSON as `ask --json`. Follow the steps in order. The server reads the role and the index that the CLI writes, and it has no tool to set either. So set the role and add a repo with the CLI before you register the server.

You need uv and Claude Code. No clone is needed.

### 1. Install

```
uv tool install "ask[mcp] @ git+https://github.com/themancalledzac/ask"
```

This puts both `ask` and `ask-mcp` on your PATH. The last line of its output is:

```
Installed 2 executables: ask, ask-mcp
```

If your shell can't find `ask` after this, run `uv tool update-shell` and open a new terminal.

### 2. Set your role

```
$ ask rbac employee
role set to employee
```

### 3. Add a repo

The check in step 5 uses the context bundle that ships in this repo. Without a clone, clone it just for the bundle:

```
$ git clone --depth 1 https://github.com/themancalledzac/ask /tmp/ask-src
$ ask add-repo /tmp/ask-src/context-bundle
added context-bundle (8 files, role employee)
```

Any folder with a `services.json` or a git repo of your own works too. The check below only works with `context-bundle` added.

### 4. Register the server for every folder

```
claude mcp add -s user ask -- ask-mcp
```

`-s user` makes the server available in every folder, not only the one you ran it in.

If you work from a clone instead of the installed tool, register this form:

```
claude mcp add -s user ask -- uv run --directory <path-to-clone> --extra mcp ask-mcp
```

### 5. Check it works

In Claude Code, run `/mcp`. `ask` should be listed as connected. Then ask Claude "who owns ledger?". The answer should be Sofia Reyes (Ops), cited `context-bundle:services.json:37`. The same question from the CLI:

```
$ ask "who owns ledger?"
Owner of ledger:
Sofia Reyes (Ops)  context-bundle:services.json:37  "owner": "Sofia Reyes",
```

Steps 1 to 3 and the ledger question were run in a temp `UV_TOOL_DIR`, `UV_TOOL_BIN_DIR` and `ASK_HOME`. `ask-mcp` was started there and answered `initialize`, `tools/list` and a `tools/call` for "who owns ledger?" over stdio with the same answer. The `claude mcp add` commands and the `/mcp` check were not run against a real Claude Code config.

### Notes

The role still comes from `ask rbac`. The server reads it on every call, and the tool has no role parameter. The server exposes no tool that changes roles or repos. To change either, use the CLI. The server picks up the change on the next call.

To try the CLI once without installing:

```
uvx --from git+https://github.com/themancalledzac/ask ask --help
```

To run the MCP tests from a clone:

```
uv run --extra mcp pytest -q
```

## Tests and eval

```
uv run pytest -q
uv run python -m ask.eval eval/seen.jsonl --detail
```

The eval loads the repos in `eval/repos.json` into a temp `ASK_HOME`, asks each row in `eval/seen.jsonl`, and prints the pass count. Two of those repos (`../edens.zac` and `../edens.zac.backend`) sit beside this repo on my machine. On a fresh clone they are skipped with a message, and the rows that need them fail. Scores per step are in [notes/SCOREBOARD.md](notes/SCOREBOARD.md).

## Where state lives

The role (`config.toml`) and the SQLite index (`index.db`) live in `~/.config/ask`. Set `ASK_HOME` to use another folder:

```
ASK_HOME=$(mktemp -d) uv run ask rbac employee
```
