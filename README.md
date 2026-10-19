# ask

`ask` is a command line tool that answers "where does X live" and "who owns X" from repos you add. Every answer cites `repo:path:line`, and the quoted text is on that line. Owners come only from `services.json` or CODEOWNERS, and a role (employee or guest) decides which repos a question can see.

The write-up for the take-home is in [notes/WRITEUP.md](notes/WRITEUP.md).

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- git

There are no other dependencies. `ask` uses only the Python standard library.

## Run it

One command, once the repo is public:

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

`ask-mcp` runs an MCP server over stdio with one tool, `ask(question, repo?)`. It returns the same JSON as `ask --json`. To register it with Claude Code, run this from the clone:

```
claude mcp add ask -- uv run --directory <path-to-clone> --extra mcp ask-mcp
```

The role still comes from `ask rbac`. The server reads it on every call, and the tool has no role parameter. The server exposes no tool that changes roles or repos.

To run the MCP tests too:

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
