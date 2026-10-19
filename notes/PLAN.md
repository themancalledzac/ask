# `ask` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every task brief carries its GOAL / MUST HOLD / OUT OF SCOPE / DONE WHEN block verbatim (builder-handoff).

**Goal:** A Python CLI, `ask`, that answers where X lives, who owns X, and its status from repos the user adds, with a file-and-line citation on every answer and two access roles.

**Architecture:** `ask add-repo` walks a folder (`git ls-files`, or a text-file walk for non-git folders), redacts secrets, and writes line-numbered chunks into one SQLite FTS5 table in `$ASK_HOME/index.db`. A question goes to one of two paths. An owner question resolves through services.json or CODEOWNERS only. Any other question runs an all-words FTS5 match with one fallback. Every path filters repos by the caller's role from `$ASK_HOME/config.toml` before it reads a row.

**Tech Stack:** Python 3.11+ standard library (`sqlite3` with FTS5, `tomllib`, `argparse`, `subprocess`), uv, pytest (dev only). Optional extra `mcp` for step 4.

**Spec:** notes/PREPLAN-PROMPT.md. Brief: notes/BRIEF.md.

## Global Constraints

- No runtime dependencies beyond the standard library. MCP is the one exception, as an optional extra.
- Roles: `employee` sees everything. `guest` sees only repos set to guest.
- The caller's role comes only from `$ASK_HOME/config.toml` (default `~/.config/ask/`), written by `ask rbac <role>`. It never comes from the question, a flag on `ask "<question>"`, or an agent tool argument. If no role is set, the caller is `guest`.
- New repos default to `employee`.
- `add-repo`, `remove-repo` and `update-repo` need the employee role.
- A guest with no visible match gets exactly `Not found in added repos.`
- A guest who names an employee repo with `--repo` gets exactly `Refused: needs employee access`, with no file names or hints.
- Owners come only from services.json or CODEOWNERS, never doc text, a model, or git log. Git log committers may appear, labelled "recent committers, not owners".
- Not found: a free-text hit has to contain every content word, with stopwords removed. If nothing does, retry once allowing one missing word. Anything looser is `Not found in added repos.` There is no BM25 score cutoff.
- Secrets are redacted before text goes into the index: API keys, passwords in URLs, and signed tokens (JWTs). `.env*` files are skipped.
- Every citation is `repo:path:line`. The quoted text equals the redacted text of that exact line, with whitespace trimmed.
- A git repo indexes every `git ls-files` file, code and `.github/` included. A non-git folder indexes every text file, skipping `.git` and binaries.
- A path that can't be read gives a one-line error that says how to fix it.
- Held-out repo: ../mempalace at a938e3c. No builder or reviewer agent reads it, searches its mempalace wing, or runs the held-out eval. The main session runs it and passes only the score on.
- Exit codes: 0 answered, 1 not found, 2 refused, 3 usage or input error.
- No inline comments in code (user's global rule). Docblocks of three sentences or fewer.

## Review Focus

1. A question with FTS5 syntax characters (`atlas-api`, `"`, `*`, `:`, `OR`) must not raise. It is a normal search. Test in Task 4.
2. A question that is empty or only stopwords gives not found, exit 1. Test in Task 4.
3. `add-repo` on a missing path, a file, or an unreadable folder gives a one-line error, exit 3. Test in Task 3.
4. A file with CRLF endings or a 5,000-character line still cites the right line number. Test in Task 2.
5. Adding the same repo name twice re-indexes it in place, and removing an unknown name is a one-line error. Test in Task 3.

## File structure

```
pyproject.toml            package `ask`, script `ask = "ask.cli:main"`, dev group pytest, extra mcp
.gitignore                .idea/ .venv/ __pycache__/ *.db
src/ask/model.py          ROLES, REFUSED, NOT_FOUND, Citation, AskError
src/ask/home.py           ask_home() and the config file
src/ask/access.py         roles, get_role, set_role, can_see
src/ask/files.py          list_files, read_text_lines
src/ask/redact.py         redact
src/ask/store.py          SQLite schema, repo registry, indexing
src/ask/search.py         content_words, fts_search
src/ask/owners.py         CODEOWNERS and services.json lookup, recent committers
src/ask/answer.py         answer(): routing, access, the JSON result
src/ask/cli.py            argparse and output
src/ask/eval.py           eval runner
src/ask/mcp_server.py     step 4 only
tests/                    one test file per module, fixtures built in tmp_path
eval/seen.jsonl           rows written by the golden subagent, checked by the user
eval/heldout.jsonl        rows written by the user
eval/repos.json           which repos each eval adds, with roles
notes/SCOREBOARD.md       one row per step: seen and held-out scores
notes/AI-LOG.md           per step: delegated, by hand, where agents were wrong
notes/WRITEUP.md          the brief's write-up sections (BRIEF:19-23)
README.md                 prerequisites and one run command
```

## Shared interfaces

These live in `src/ask/model.py`, created in Task 1.

```python
ROLES = ("employee", "guest")
REFUSED = "Refused: needs employee access"
NOT_FOUND = "Not found in added repos."

@dataclass
class Citation:
    repo: str
    path: str
    line: int
    quote: str

class AskError(Exception):
    """A usage or input error. The message is one line and says how to fix it."""
```

Output: refusals, not-found messages and answers go to stdout. `AskError` messages go to stderr with exit 3.

Line numbers: a file's lines are `text.split("\n")` with one trailing `\r` removed from each line. Every module uses this, so line numbers match an editor.

The JSON result from `answer()` and `ask --json`:

```json
{"status": "answered" | "not_found" | "refused",
 "kind": "owner" | "search" | null,
 "message": "one line for people",
 "owners": [{"name": "Sofia Reyes", "team": "Ops", "citation": {...}}],
 "hits": [{"repo": "...", "path": "...", "line": 12, "quote": "..."}],
 "recent_committers": [{"name": "...", "commits": 4}]}
```

`owners`, `hits` and `recent_committers` are empty lists when unused. A refused or not_found result has all three empty.

---

## Step 0: base commit on main

The repo has no commits. Each step opens a PR against main, so main needs a root commit first. The main session commits `.gitignore`, `notes/` and `context-bundle/` to main after the user says yes. Then it opens branch `step-1-index-access`.

---

## Step 1: repos, index, access, search (~40 min)

Branch `step-1-index-access`, one PR. Tasks 1 to 6.

### Task 1: scaffold, home and rbac

**Files:** Create `pyproject.toml`, `.gitignore`, `src/ask/__init__.py`, `src/ask/model.py`, `src/ask/home.py`, `src/ask/access.py`, `src/ask/cli.py`. Test: `tests/test_access.py`, `tests/conftest.py`.

**Interfaces:**
- Produces: `ask_home() -> Path` (from `$ASK_HOME`, else `~/.config/ask`, created if missing). `get_role() -> str` (`guest` when unset). `set_role(role: str) -> None` (raises `ValueError` for a role not in `ROLES`). `can_see(caller_role: str, repo_role: str) -> bool`. `main(argv: list[str] | None = None) -> int` in cli.py. The first argv item that is a command name (`add-repo`, `list-repos`, `remove-repo`, `update-repo`, `rbac`) dispatches to it. Anything else is a question, with multiple words joined by spaces. A bare `ask` prints usage and exits 3. A `role` value in config.toml that isn't in `ROLES` is read as `guest`. `conftest.py` fixture `ask_home` sets `ASK_HOME` to a tmp dir.

GOAL: `ask rbac employee` stores the caller's role and `ask rbac` prints it. Nothing else can set it.
MUST HOLD:
- The caller's role comes only from `$ASK_HOME/config.toml` (default `~/.config/ask/`), written by `ask rbac <role>`. It never comes from the question, a flag on `ask "<question>"`, or an agent tool argument. If no role is set, the caller is `guest`.
- Roles: `employee` sees everything. `guest` sees only repos set to guest.
- No runtime dependencies beyond the standard library.
- Exit codes: 0 answered, 1 not found, 2 refused, 3 usage or input error.
- No inline comments in code. Docblocks of three sentences or fewer.
OUT OF SCOPE: indexing, search, owners.
DONE WHEN: `uv run pytest tests/test_access.py -q` passes with these rows: unset role is guest; `rbac employee` then `rbac` prints `employee`; `rbac admin` exits 3 with a one-line error; `config.toml` is written to `$ASK_HOME`; `can_see("guest","employee")` is False and the other three pairs are as expected. broken-twin: make `get_role` default to `employee` and confirm the unset-role row goes red, then restore.

- [ ] Write the failing tests, run them and confirm they fail.
- [ ] Implement. Write `config.toml` as `role = "<role>"` by hand. Read it with `tomllib`.
- [ ] Run the tests and confirm they pass. Run the broken twin.
- [ ] Commit `feat: scaffold ask with rbac role in config`.

### Task 2: file listing and redaction

**Files:** Create `src/ask/files.py`, `src/ask/redact.py`. Test: `tests/test_files.py`, `tests/test_redact.py`.

**Interfaces:**
- Produces: `list_files(root: Path) -> list[Path]` (relative paths, sorted). `read_text_lines(path: Path) -> list[str] | None` (None for a symlink, over 1 MB, a NUL byte in the first 8 KB, or not UTF-8. Lines split per Shared interfaces). `redact_lines(lines: list[str]) -> list[str]` (same length as the input). `redact(line: str) -> str` (one line).

GOAL: Given any folder, return exactly the files to index and their lines with secrets replaced by `[redacted]`.
MUST HOLD:
- A git repo indexes every `git ls-files` file, code and `.github/` included. A non-git folder indexes every text file, skipping `.git` and binaries.
- Secrets are redacted before text goes into the index: API keys, passwords in URLs, and signed tokens (JWTs). `.env*` files are skipped.
- Git repos: only tracked files count. A tracked file listed in .gitignore is still indexed, because `git ls-files` lists it.
- `.env*` means any file whose basename starts with `.env`, at any depth, in both git and non-git folders.
- No inline comments in code. Docblocks of three sentences or fewer.
OUT OF SCOPE: SQLite, CLI output.

`redact` patterns, each replaced with `[redacted]`:
- AWS key ids `AKIA[0-9A-Z]{16}`.
- Prefixed tokens: `ghp_`, `gho_`, `github_pat_`, `sk-`, `xox[abpr]-`, followed by 16 or more `[A-Za-z0-9_-]`. A prefix must not follow a letter, digit, `_` or `-`, so `risk-management-plan-v2` is left alone.
- PEM blocks: in `redact_lines`, every line from `-----BEGIN [A-Z ]*PRIVATE KEY-----` through the matching END line becomes `[redacted]`. The line count doesn't change.
- Password in a URL: `scheme://user:pass@` becomes `scheme://[redacted]@`.
- JWT: `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`.
- Assignment: `(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['"]?` followed by 8 or more non-space, non-quote characters. Only the value is replaced.

DONE WHEN: `uv run pytest tests/test_files.py tests/test_redact.py -q` passes with these rows:
- a git fixture with a gitignored file and an untracked file lists neither, and lists `.github/workflows/ci.yml`;
- a non-git fixture skips `.git/`, a PNG, `.env` and `.env.local`, and keeps `.github/CODEOWNERS`;
- a CRLF file and a 5,000-character line give the right line count;
- one row per secret pattern, each built from parts at run time so no literal secret is committed;
- `https://example.com/path`, the word `token` in prose, and `risk-management-plan-v2-final-draft` are left alone;
- a 3-line PEM block becomes 3 `[redacted]` lines;
- a symlink is skipped.

broken-twin: drop the URL-password pattern and confirm its row goes red, then restore.

- [ ] Write the failing tests, run them and confirm they fail.
- [ ] Implement. A folder is a git repo when `git -C <root> rev-parse --show-toplevel`, resolved, equals the resolved root.
- [ ] Run the tests and confirm they pass. Run the broken twin.
- [ ] Commit `feat: list indexable files and redact secrets`.

### Task 3: store and repo commands

**Files:** Create `src/ask/store.py`. Modify `src/ask/cli.py`. Test: `tests/test_store.py`.

**Interfaces:**
- Consumes: `ask_home`, `get_role`, `can_see`, `list_files`, `read_text_lines`, `redact`.
- Produces: `connect() -> sqlite3.Connection` (opens `$ASK_HOME/index.db` and creates the schema). `add_repo(con, path: Path, name: str | None = None) -> Repo`. `remove_repo(con, name) -> None`. `set_repo_role(con, name, role) -> None`. `list_repos(con) -> list[Repo]`. `Repo(name, path, role, file_count)`.
- Schema: `repos(name TEXT PRIMARY KEY, path TEXT, role TEXT DEFAULT 'employee', file_count INTEGER)`. `file_count` counts files that were read as text.
- The default name is the basename of the resolved path, so `.` and a trailing slash both work. Re-adding the same path replaces its chunks and keeps its role. Adding a different path under a name already in use is an `AskError` that says to pass `--name`. `chunks` is an FTS5 table with `tokenize='porter unicode61'`, columns `text`, plus UNINDEXED `repo`, `path`, `start_line`. A chunk is a run of non-blank lines split at blank lines, at most 20 lines. `text` holds the redacted lines joined with `\n`.
- CLI: `ask add-repo <path> [--name N]`, `ask list-repos`, `ask remove-repo <name>`, `ask update-repo <name> <employee|guest>`.

GOAL: The user can add, list, re-add, retag and remove repos. The index holds only redacted text.
MUST HOLD:
- New repos default to `employee`.
- `add-repo`, `remove-repo` and `update-repo` need the employee role. A guest gets exactly `Refused: needs employee access`, exit 2.
- `list-repos` run by a guest shows only guest repos.
- A path that can't be read gives a one-line error that says how to fix it.
- Secrets are redacted before text goes into the index.
- No inline comments in code. Docblocks of three sentences or fewer.
OUT OF SCOPE: search ranking and answers.
DONE WHEN: `uv run pytest tests/test_store.py -q` passes with these rows:
- add then list shows the name, `employee` and the file count;
- the default name is the folder's basename;
- re-adding the same name replaces its chunks, with no duplicate rows;
- `update-repo x guest` changes the role;
- remove deletes the repo's chunks;
- a guest running add, remove or update gets the refusal, exit 2;
- a guest's `list-repos` hides employee repos;
- a missing path, a file path, a folder with mode 000, and an unknown repo name each print one line to stderr, exit 3;
- a second folder with the same basename gives the `--name` error;
- a fixture secret never appears in `SELECT text FROM chunks`.

broken-twin: skip `redact` in `add_repo` and confirm the last row goes red, then restore.

- [ ] Write the failing tests, run them and confirm they fail.
- [ ] Implement.
- [ ] Run the tests and confirm they pass. Run the broken twin.
- [ ] Commit `feat: repo registry and FTS5 index`.

### Task 4: search, answer and the question CLI

**Files:** Create `src/ask/search.py`, `src/ask/answer.py`. Modify `src/ask/cli.py`. Test: `tests/test_search.py`, `tests/test_answer.py`.

**Interfaces:**
- Consumes: Task 3's `connect` and schema, `get_role`, `can_see`.
- Produces: `content_words(q: str) -> list[str]` (lowercase, split on anything not a letter or digit, drop stopwords, keep order, dedupe). `fts_search(con, words: list[str], repos: list[str], limit: int = 3) -> list[Citation]`. `answer(con, question: str, role: str, repo: str | None = None) -> dict` (the JSON result). `kind` is null for not_found and refused. `--repo` takes a repo name or an absolute path, and a path resolves to the repo whose path it is or is inside.
- CLI: `ask "<question>" [--json] [--repo NAME]`. Text output is the message, then one `repo:path:line  quote` per citation. `--json` prints the result dict.

`STOPWORDS` is a fixed set in search.py: a an and are as at be can do does for from get have how i in is it me my of on or our should so the there this to was what when where which who whose why will with you your now just s.

Search algorithm:
1. Resolve visible repos. If `--repo` names a repo the caller can't see, return refused. If it names an unknown repo, return not found.
2. Strict pass: an FTS MATCH where every word is a quoted phrase joined by AND. This is what keeps syntax characters safe.
3. If there are no rows and there are 3 or more words, run one fallback pass: an OR of the AND-groups that each leave out one word. With 1 or 2 words there is no fallback.
4. Rank by `bm25(chunks)`. For each of the top `limit` chunks, the cited line is the line inside the chunk that holds the most content words. A line token counts as a content word when the two share their first 5 characters, or are equal when either is shorter than 5. Ties go to the first such line. The quote is that line, trimmed. Text output for an answered search is `Found in:` followed by the citations.
5. No rows means not found.

GOAL: A question returns cited lines from visible repos, or the exact not-found or refused text.
MUST HOLD:
- A guest with no visible match gets exactly `Not found in added repos.`
- A guest who names an employee repo with `--repo` gets exactly `Refused: needs employee access`, with no file names or hints.
- Not found: a free-text hit has to contain every content word, with stopwords removed. If nothing does, retry once allowing one missing word. Anything looser is `Not found in added repos.` There is no BM25 score cutoff. The retry runs only with 3 or more content words.
- Every citation is `repo:path:line`. The quoted text equals the redacted text of that exact line, with whitespace trimmed.
- The caller's role comes only from `config.toml`. `answer()` takes it as a parameter, and only cli.py calls `get_role()`.
- Repos are filtered by role before any chunk is read.
- Exit codes: 0 answered, 1 not found, 2 refused, 3 usage or input error.
- No inline comments in code. Docblocks of three sentences or fewer.
OUT OF SCOPE: owner questions (Task 7 adds that path to `answer`).
DONE WHEN: `uv run pytest tests/test_search.py tests/test_answer.py -q` passes with these rows:
- the quote check runs on every hit in every test: `redact(file_lines[line-1]).strip() == quote`;
- an employee fixture repo holding `zorbquill` plus a guest fixture repo: a guest asking `zorbquill` gets exactly `Not found in added repos.`; a guest with `--repo <employee repo>` gets exactly the refusal, and the output contains neither `zorbquill` nor the employee repo's file names; an employee gets the hit;
- a secret fixture row in each pattern: no `ask` output (text or JSON) contains the raw secret;
- `atlas-api "quoted" OR *:` does not raise;
- an empty question and `who is the` both give exit 1;
- three words where only two co-occur hits on the fallback; three words where only one occurs gives not found; two words where only one occurs gives not found; a single word that doesn't occur gives not found;
- a fixture holding only a copy of `services-overview.md` gives not found for `aperture`.

broken-twin, each restored after: (a) drop the role filter and confirm the zorbquill row goes red; (b) let the fallback leave out two words and confirm the three-words-one-occurs row goes red; (c) cite `start_line` instead of the best line and confirm the quote check goes red.

- [ ] Write the failing tests, run them and confirm they fail.
- [ ] Implement.
- [ ] Run the tests and confirm they pass. Run the three broken twins.
- [ ] Commit `feat: cited search with role filter and not-found rule`.

### Task 5: CODEOWNERS

**Files:** Create `src/ask/owners.py`. Test: `tests/test_codeowners.py`.

**Interfaces:**
- Produces: `find_codeowners(root: Path) -> Path | None`. `parse_codeowners(text: str) -> list[Rule]`, where `Rule(pattern: str, owners: list[str], line: int)`. `owners_for_path(rules, path: str) -> Rule | None` (the winning rule, which may have empty owners).

Matching rules, from GitHub's "About code owners" docs:
- Look in `.github/CODEOWNERS`, then `CODEOWNERS`, then `docs/CODEOWNERS`. Use the first one found. Read it from disk at the repo's path.
- Skip blank lines and lines starting with `#`. Strip a trailing ` #` comment. `\#` is a literal `#`.
- A line is a pattern and then owners separated by whitespace (`@user`, `@org/team`, or an email).
- The last matching rule wins. A matching rule with no owners clears ownership.
- A pattern starting with `/`, or with a `/` anywhere except the end, is anchored to the root. Otherwise it matches at any depth.
- A trailing `/` matches a directory and everything under it. A pattern naming a directory without a trailing `/` also matches everything under it.
- A pattern ending in `/*` matches files directly in that directory only, not nested ones (`docs/*` matches `docs/a.md`, not `docs/x/a.md`).
- `*` matches within one path segment, `**` matches across zero or more segments, `?` matches one character other than `/`.
- `!` negation and `[ ]` ranges are not supported. Such a line is skipped.

GOAL: "who owns <path>" names the owners GitHub would request for that path.
MUST HOLD:
- CODEOWNERS matching follows GitHub's rules above, word for word.
- Owner names come only from CODEOWNERS and services.json lines, never from doc text.
- No inline comments in code. Docblocks of three sentences or fewer.
OUT OF SCOPE: services.json, routing questions, git log.
DONE WHEN: `uv run pytest tests/test_codeowners.py -q` passes with rows for: last match beats first; `/docs/` anchored versus `docs/` at any depth; `apps/web` (with no trailing slash) matching `apps/web/x.ts`; `*.js` at any depth; `/build/**/logs` matching both `build/logs` and `build/a/b/logs`; `docs/*` not matching `docs/x/a.md`; a trailing `# comment`; a rule with no owners clearing ownership; `.github/CODEOWNERS` chosen over a root one; a `docs/CODEOWNERS` file used when it's the only one. broken-twin: use first-match-wins and confirm the last-match row goes red, then restore.

- [ ] Write the failing tests, run them and confirm they fail.
- [ ] Implement.
- [ ] Run the tests and confirm they pass. Run the broken twin.
- [ ] Commit `feat: CODEOWNERS lookup per GitHub rules`.

### Task 6: eval runner, seen rows, scoreboard

**Files:** Create `src/ask/eval.py`, `eval/repos.json`, `eval/seen.jsonl`, `notes/SCOREBOARD.md`, `notes/AI-LOG.md`. Test: `tests/test_eval.py`.

**Interfaces:**
- Produces: `uv run python -m ask.eval eval/<rows>.jsonl [--detail]`. It builds a temp `ASK_HOME`, adds the repos named in `eval/repos.json` with their roles, sets each row's role, calls `answer()`, and prints `passed/total`. It prints per-row failures only with `--detail`.
- `eval/repos.json` shape: `{"seen": [{"path": str, "role": str, "name": str}], "heldout": [{"path": str, "role": str, "name": str, "pin": str}]}`. Paths are relative to the repo root (the parent of `eval/`). A rows file whose name starts with `heldout` uses the `heldout` list. Any other rows file uses `seen`.
- Row: `{"q": str, "role": "employee"|"guest", "repo": str|null, "status": str, "owners_include": [str], "path_endswith": str|null, "must_not_contain": [str]}`. Every field except `q`, `role` and `status` is optional. `path_endswith` passes when any hit or owner citation path ends with it. `must_not_contain` is a case-insensitive substring check against the full JSON text.
- The `ask` repo tracks its own eval rows, plan and tests, so an employee search can match the row's own text. Every not-found row is therefore a guest row or sets `repo` to a repo other than `ask`. No row targets a file in `ask` other than `pyproject.toml`.
- `eval/repos.json`: seen repos `context-bundle` (guest), `ask` (employee), `../edens.zac` (employee), `../edens.zac.backend` (guest). Held-out entry `../mempalace` (employee), pinned at `a938e3c`. The runner refuses to score held-out rows if `git -C ../mempalace rev-parse --short HEAD` is not `a938e3c`.

GOAL: Each step can be scored on seen and held-out rows in separate columns, and the held-out repo stays unread.
MUST HOLD:
- Someone other than the builder writes the test rows. A separate golden subagent writes `eval/seen.jsonl`. The user writes `eval/heldout.jsonl`. The user checks seen rows by hand before step 2.
- No builder or reviewer agent reads ../mempalace, searches its mempalace wing, or runs the held-out eval. The main session runs it and passes only the score on.
- The scoreboard gets one row per step, with seen and held-out scores in separate columns.
OUT OF SCOPE: owner rows (step 2 adds them).
DONE WHEN: `uv run pytest tests/test_eval.py -q` passes, with a row where a wrong `status` counts as a fail and a row where a tmp fixture repo with a wrong `pin` is refused. `uv run python -m ask.eval eval/seen.jsonl` prints a score. The main session runs `eval/heldout.jsonl` and writes both scores to SCOREBOARD.md row "step 1". broken-twin: make the runner treat every row as passed and confirm the wrong-status row goes red, then restore.

- [ ] The golden subagent writes about 10 seen search rows (bundle, ask, edens.zac, edens.zac.backend), including 3 not-found and 2 guest rows, plus 3 CODEOWNERS path rows built against a tmp fixture repo it describes in `eval/fixtures/codeowners/` (a CODEOWNERS file and empty files at the named paths). It reads only those repos.
- [ ] The builder writes the runner test, the runner and `eval/repos.json`.
- [ ] The user checks `eval/seen.jsonl` and writes `eval/heldout.jsonl`.
- [ ] The main session runs both and fills the scoreboard, the AI log, and the matching sections of `notes/WRITEUP.md`.
- [ ] Commit. Open the step 1 PR. The user approves the merge.

---

## Step 2: owners and the bundle (~20 min, cut line at minute 65)

Branch `step-2-owners`, one PR. Tasks 7 and 8. If the clock passes minute 65 during step 2, ship what is merged.

### Task 7: services.json, owner routing, recent committers

**Files:** Modify `src/ask/owners.py`, `src/ask/answer.py`. Test: `tests/test_owners_answer.py`.

**Interfaces:**
- Consumes: Task 5, `answer()`, the store.
- Produces: `load_services(root: Path) -> list[Service]`, where `Service(name, description, team, owner, owner_slack, repo, doc, slack_channel, owner_line: int)` uses the file's own keys. It reads `services.json` from disk at a repo root. `owner_line` is the 1-based line of the first `"owner":` line after that service's `"name":` line, found by scanning the text. `resolve_service(question, services) -> Service | None`. `recent_committers(root: Path, path: str | None, n: int = 3) -> list[dict]` from `git log -n 200 --format=%an [-- path]`.

Routing in `answer()`:
1. A question is an owner question if `content_words` would include any of: own, owns, owner, owners, owned, review, reviewer, reviewers. Remove those words before matching.
2. Service match: a word equal to a service name (case-insensitive, with hyphenated names matched as the consecutive tokens, so `atlas-api` matches `atlas` then `api`, and `atlas` alone matches nothing). If nothing matches, use a word that equals a lowercase description token of exactly one service across all visible repos. All name matches are returned.
3. Path match: a whitespace-split question token containing `/` or `.`, with trailing `?.,:;!` stripped, that equals an indexed file path or a directory prefix of one in a visible repo with a CODEOWNERS file. Return at most 5 matches. A service match and a path match are both returned.
4. An owner question with no service and no path match is not found. It never falls back to text search.
5. Services and CODEOWNERS are read only from repos the caller can see.
6. A CODEOWNERS owner is `{"name": "<owner string>", "team": null}`. A path whose winning rule has no owners is not found.
7. Answered owner results carry `recent_committers` only for a path match in a git repo, and the message labels them "recent committers, not owners".

GOAL: Owner questions answer from services.json or CODEOWNERS with a citation, or say not found.
MUST HOLD:
- Owners come only from services.json or CODEOWNERS, never doc text, a model, or git log. Git log committers may appear, labelled "recent committers, not owners".
- services.json: match on the exact service name, case-insensitive. A word in a service's description counts as a match only when it names exactly one service.
- A guest with no visible match gets exactly `Not found in added repos.`
- Every citation is `repo:path:line`. The quoted text equals the redacted text of that exact line, with whitespace trimmed.
- No inline comments in code. Docblocks of three sentences or fewer.
OUT OF SCOPE: the search path, CLI formatting beyond the message.
DONE WHEN: `uv run pytest tests/test_owners_answer.py -q` passes with these rows:
- "who owns ledger?" gives Sofia Reyes, citing the services.json owner line;
- "who owns billing now?" gives Sofia Reyes;
- "who owns kubernetes?" gives not found;
- "who should review my PR for forge?" gives Priya Nadkarni;
- a CODEOWNERS fixture path question gives the last-match owner, cited to the CODEOWNERS line, with recent committers labelled;
- a guest asking about an owner in an employee-only services.json gives exactly `Not found in added repos.`;
- an owner question never contains a name taken from a markdown file: a fixture doc saying "owned by Zed Quill" gives not found.

broken-twin: (a) let owner questions fall back to text search and confirm the Zed Quill row goes red; (b) let a description word match two services and confirm a row goes red. Restore both.

- [ ] Write the failing tests, run them and confirm they fail.
- [ ] Implement.
- [ ] Run the tests and confirm they pass. Run both broken twins.
- [ ] Commit `feat: owner answers from services.json and CODEOWNERS`.

### Task 8: bundle rows and scoring

**Files:** Modify `eval/seen.jsonl`, `notes/SCOREBOARD.md`, `notes/AI-LOG.md`.

GOAL: The 12 questions from last week and the not-found rows are scored on seen and held-out data.
MUST HOLD:
- Someone other than the builder writes the test rows. The user checks them by hand.
- The held-out eval is run only by the main session.
- A step fails on any of: a wrong answer from a source, a leaked secret, a quote not in the source, restricted content shown to a guest, or an answer where it should say not found.
OUT OF SCOPE: tuning code to the held-out rows.
DONE WHEN: the golden subagent has added 12 rows from `context-bundle/questions-last-week.md` plus 4 not-found rows. The user has checked them. Both evals have run and SCOREBOARD.md has a "step 2" row. Wrong answers found here become a failing test in the same session, then a fix.

- [ ] The golden subagent writes the rows.
- [ ] The user checks them.
- [ ] The main session runs both evals, fixes real-data failures with a test first, and updates WRITEUP.md.
- [ ] Commit. Open the step 2 PR. The user approves the merge.

---

## Step 3: ship (~15 min)

Branch `step-3-ship`, one PR.

### Task 9: README, fresh clone, write-up, public

**Files:** Create `README.md`, `notes/WRITEUP.md`. Modify `notes/AI-LOG.md`.

GOAL: A grader runs it from one documented command on a clean machine.
MUST HOLD:
- The README lists prerequisites (uv, git) and one run command: `uvx --from git+https://github.com/themancalledzac/ask ask`. It also shows the clone route: `git clone`, then `uv run ask ...`.
- A fresh clone in a temp folder is tested.
- Data that can't be read gives a one-line error with the fix.
- The write-up has these five headings, in order: "What I built and why", "How I'd attack the real problem", "What I'd measure", "Safety and exposure", "How I used AI tooling". It follows BRIEF:19-23 and claims only what a test or the scoreboard proves.
- The write-up's safety section says `ask rbac` is self-asserted and stands in for SSO login.
- The repo becomes public only after the user says yes.
OUT OF SCOPE: new features.
DONE WHEN: in a temp folder, `git clone` then `uv run ask rbac employee`, `uv run ask add-repo context-bundle`, `uv run ask "who owns ledger?"` work with a fresh `ASK_HOME`. After the user makes the repo public, the same three commands work through the `uvx` line. WRITEUP.md has the five headings. The held-out eval is run and SCOREBOARD.md has a "step 3" row. The submission is tagged `submission`. Anything after that goes on a branch.

- [ ] Write the README and WRITEUP.md.
- [ ] Run the fresh-clone test.
- [ ] The user approves going public, then merges. Tag the commit.

---

## Step 4: MCP (stretch)

Branch `step-4-mcp`.

### Task 10: MCP server

**Files:** Create `src/ask/mcp_server.py`. Modify `pyproject.toml` (optional extra `mcp`, script `ask-mcp`). Test: `tests/test_mcp.py`.

GOAL: An agent can call one `ask` tool that returns the same JSON as `ask --json`.
MUST HOLD:
- The MCP stretch exposes only an `ask` tool. No tool for `rbac`, `add-repo` or `update-repo`.
- The tool's parameters are `question` and optional `repo` (a repo name or an absolute path). The role is read with `get_role()` on each call and is never a parameter. The tool returns the result dict.
- MCP is the one dependency exception, as an optional extra.
OUT OF SCOPE: any other tool.
DONE WHEN: `uv run --extra mcp pytest tests/test_mcp.py -q` passes. It checks that the tool list is exactly `["ask"]`, that the schema has no role field, and that a guest call with `repo` naming an employee repo returns the refusal. The main session runs the held-out eval and adds a "step 4" row. broken-twin: add a `role` parameter and confirm the schema row goes red, then restore.

---

## Spec coverage

| Spec section | Plan task |
| --- | --- |
| Risk 1: add-repo, list, remove | 3 |
| Risk 1: git and non-git indexing, `.github/` | 2 |
| Risk 1: one-line error | 3 |
| Risk 1: citation is the exact line | 4, 7 |
| Risk 1: held-out column, CODEOWNERS fixture (step 1) | 5, 6 |
| Risk 2: roles, update-repo, default employee | 1, 3 |
| Risk 2: rbac in config, never from the question or an agent | 1, 4, 10 |
| Risk 2: exact not-found and refusal text | 3, 4, 7 |
| Risk 2: secret redaction, `.env*` | 2, 3, 4 |
| Risk 2: zorbquill and secret fixtures | 4 |
| Risk 3: owners only from services.json and CODEOWNERS, committers labelled | 7 |
| Risk 3: 12 questions and not-found rows | 8 |
| Answers: not-found rule | 4 |
| Decided: `--json`, exit codes | 4 |
| Decided: MCP exposes only `ask` | 10 |
| Decided: state in `$ASK_HOME` | 1, 3 |
| Data sources: CODEOWNERS rules | 5 |
| Data sources: services.json rules | 7 |
| Data sources: Devanagari row | 4 |
| Data sources: test repos, mempalace pin | 6 |
| Steps 1 to 4, cut line | Steps 1 to 4 |
| Brief trace: fresh clone (BRIEF:3, 17) | 9 |
| Brief trace: time log (BRIEF:4) | each step's SCOREBOARD row |
| Brief trace: write-up sections (BRIEF:19-23), updated each step | 6, 8, 9 |
| Held-out scored every step | 6, 8, 9, 10 |
| Build rules: one PR per step, AI log, broken twins | every step |

Not in the spec, added by this plan:
- Step 0 (a base commit, because main has none).
- The caller defaults to `guest` when no role is set.
- Admin commands need the employee role.
- The porter tokenizer wraps unicode61.
- The one-missing-word retry runs only with 3 or more content words. With 2 words it would accept a single-word match, which is the weak match the spec says is not found.

The user should confirm these five. No dead code: the repo has no source files yet.
