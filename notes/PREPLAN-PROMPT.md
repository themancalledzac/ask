# Planning prompt: `ask`

## What to build

A Python CLI, `ask`, run with uv. It answers the questions in notes/BRIEF.md:7 from repos I add, and every answer cites a file and line (BRIEF:11, 13). The bundle is context-bundle/. Search uses SQLite FTS5 with BM25. There are no other dependencies, except MCP as a stretch.

## Ranked risks

### 1. It works on a repo it has never seen

The interview pairs on their own repo (BRIEF:27).

Pre-mortem: I asked who owns a path and got the wrong team, because I used the first matching CODEOWNERS rule and GitHub uses the last.

Rules:
- `ask add-repo <path>`, `ask list-repos`, `ask remove-repo <name>`. The bundle is added the same way as any other folder.
- A git repo indexes every `git ls-files` file, code and `.github/` included. A non-git folder indexes every text file, skipping `.git` and binaries.
- A path that can't be read gives a one-line error that says how to fix it.
- Every citation is `repo:path:line`. The quoted text appears on that exact line.

Test in step 1: the held-out mempalace column, using my rows, and a CODEOWNERS fixture repo. No seen repo has a CODEOWNERS file.

### 2. Access and exposure (BRIEF:22)

Pre-mortem: a guest searched "deploy" and the reply named an employee repo. Or: a snippet printed a key from a tracked config file.

Rules:
- `employee` sees everything. `guest` sees only guest repos. `ask update-repo <name> <role>` sets a repo's role, and new repos default to employee.
- `ask rbac <role>` writes the caller's role to `~/.config/ask/config.toml` (or `$ASK_HOME`). The role comes only from there, never from the question or an agent. The write-up says it stands in for SSO login.
- A guest with no visible match gets exactly "Not found in added repos." A guest who names an employee repo with `--repo` gets exactly "Refused: needs employee access", with no file names or hints.
- Secrets are redacted before text goes into the index: API keys, passwords in URLs, and signed tokens (JWTs). `.env*` files are skipped.

Test in step 1: `zorbquill` is planted in every employee fixture repo, and any guest output containing it fails. Fixture rows hold one of each secret kind, and any output containing one fails.

### 3. Answers on the bundle are true

Pre-mortem: "who owns billing now?" quoted oncall.md's "escalate to Ops" or a committer, not Sofia Reyes from services.json. Or "who owns kubernetes?" named someone.

Rules:
- Owners come only from services.json or CODEOWNERS, never doc text, a model, or git log. Git log committers may appear, labelled "recent committers, not owners".
- A weak match counts as not found.

Test in step 2: the 12 questions in context-bundle/questions-last-week.md, plus questions that should come back not found.

## My answers, as rules

All five were option A, and most are written into the risks above. Not found: a free-text hit has to contain every content word, with stopwords removed. If nothing does, retry once allowing one missing word. Anything looser is "Not found in added repos." There is no BM25 score cutoff.

Decided for you, change any:
- `--json` output is in step 1, with a stable schema and exit codes. The tests call `--json`.
- The MCP stretch exposes only an `ask` tool. No tool for `rbac`, `add-repo` or `update-repo`.
- Index state lives in `~/.config/ask/` (or `$ASK_HOME`). Tests use a temp `ASK_HOME`.

## Data sources and their rules

- CODEOWNERS. Reference: GitHub's "About code owners" docs.
  - Look in `.github/`, then the repo root, then `docs/`. Use the first file found.
  - The last matching pattern wins.
  - Patterns follow gitignore rules: `*`, `/dir/`, `dir/`, `**`, and a leading `/` anchors to the root.
  - A pattern with no owners clears ownership.
  - Fixture rows a naive version would fail: last match beats first, an anchored versus unanchored directory, a file in `docs/` versus `.github/`, and a rule with an empty owner list.
- services.json. Reference: the bundle README, which names it the owner source.
  - Match on the exact service name, case-insensitive.
  - A word in a service's description ("billing" → ledger) counts as a match only when it names exactly one service.
- Git repos. Reference: `git ls-files` docs. Ignored files are never indexed.
- Text. Reference: SQLite FTS5 docs (unicode61, bm25()). Test row: the Devanagari "Aperture" at services-overview.md:1 doesn't match "Aperture".
- Test repos. Seen: context-bundle, this repo, ../edens.zac (651372d5), ../edens.zac.backend (417e36f9). Held out: ../mempalace at a938e3c. No agent reads it or searches its mempalace wing. I write its rows, and it is scored in its own column at every step.

## Steps

1. Repos, index, access, search (~40m): `add-repo`, `list-repos`, `remove-repo`, `update-repo`, `rbac`, and `ask "<question>"` with `--json` and `--repo`. Also git and non-git indexing, redaction, the not-found rule, and the planted-word and secret fixtures. Score the seen repos and the mempalace column.
2. Owners and the bundle (~20m): services.json and CODEOWNERS lookup, recent committers, the 12 questions and the not-found rows. The cut line is at minute 65. If I'm behind, I ship what step 2 has.
3. Ship (~15m): README with prerequisites and one run command (`uvx --from git+https://github.com/themancalledzac/ask ask`), a fresh-clone test in a temp folder, make the repo public, write-up.
4. Stretch: an MCP server exposing `ask`, with the role read from config.

## Brief trace

| Brief | Test | Output that fails it |
| --- | --- | --- |
| 3, 17 actually runs | fresh clone in a temp folder, run the one documented command | any error, or an extra step that isn't in the README |
| 4 time cap | the time log for each step | a step over its time with no cut |
| 7 where / who / status | the 12 log questions | a wrong owner or wrong location |
| 11, 13 says where it found it | quote check on every answer | a citation whose line doesn't contain the quote |
| 15 taste in scoping | the write-up's "left out" list | a listed feature that got built, or a built one not listed |
| 19–23 write-up sections | a check that the write-up has these headings | a missing section |
| 22 safety / access | the planted-word and secret fixtures | `zorbquill` in guest output, or a secret in any output |
| 25 one thing genuinely end-to-end | the mempalace column | an owner or citation wrong on the held-out repo |
| 27 their own repo | `add-repo` on mempalace and the CODEOWNERS fixture | any held-out row failing, or a fixture's last-match row failing |

## Build rules that apply

- Build in steps. Each step leaves a working tool, never a half-built one.
- The clock starts when the build starts. Log each step's time.
- Tag the submission when time runs out. Anything after that goes on a branch.
- The cut line is the end of step 2. Steps after it are still planned. Once every planned step is done, fix what real data gets wrong. Don't add features.
- Keep the feature list small. Name what is left out. Future ideas are listed, not built.
- Someone other than the builder writes the test rows. I check them by hand before step 2.
- A step fails on any of: a wrong answer from a source, a leaked secret, a quote not in the source, restricted content shown to a guest, or an answer where it should say not found.
- Every fail rule gets a broken-twin check.
- The scoreboard gets one row per step, with seen and held-out scores in separate columns.
- A problem a review finds becomes a failing test in the same session, then a fix.
- Docs and docblocks only claim what a test proves.
- One branch and PR per step. I approve each merge. If I skip a check, the write-up doesn't claim it.
- Plan steps and subagent assignments use builder-handoff.
- Before the build, a fresh agent reads the plan and lists what it would have to guess.
- Keep an AI log at each step: what went to agents, what I did by hand, and where agents got it wrong.
- The README lists prerequisites, a fresh clone is tested, and data that can't be read gives a one-line error with the fix.
- The write-up follows the brief's sections and is updated at each step.

## Left out

- Live `gh api` owner lookups, Slack and Notion, a web UI, real SSO, a model writing answers, and a stale-docs report.

## Future ideas

- Expand CODEOWNERS teams into people through GitHub teams or the identity provider.
- Turn not-found questions into doc tasks.
- Read catalog-info.yaml files.
- Run the eval in CI.

## Output

PLAN.md via writing-plans, every step in builder-handoff form. Run it with subagent-driven-development, not orch. Track progress with task-dashboard.
