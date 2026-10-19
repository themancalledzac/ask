# Write-up

## What I built and why

`ask` is a Python CLI that answers "where does X live / who owns X" from repos you add. Every answer cites `repo:path:line`, and a test checks that the quoted text is on that line. It indexes every git-tracked file (code included) into SQLite FTS5 and uses only the standard library, except the optional `mcp` extra for the MCP server. Two roles, employee and guest, decide which repos a question can see.

I scoped it to three things that had to be true. First, it should work on a repo it has never seen, because the interview pairs on their repo. So the bundle is added with `ask add-repo` like any other folder, and the CODEOWNERS rules are tested on a fixture built from GitHub's docs. I did not score a held-out repo, so this is designed for, not proven. Second, owner answers come only from `services.json` or CODEOWNERS (GitHub's rules, last match wins), never from doc text. Recent git committers can be shown, labelled as not owners. Third, a weak match says "Not found in added repos." instead of guessing.

The eval scores 29/29 on the seen rows, which include all 12 bundle questions (notes/SCOREBOARD.md). `uv run --extra mcp pytest -q` passes.

Left out on purpose: live `gh api` owner lookups, Slack and Notion connectors, a web UI, real SSO, a model writing answers, and a stale-docs report.

## How I'd attack the real problem

"People can't find context" is a routing problem more than a search problem. The leverage is in reading the systems that already hold the answer, and in putting the answer where people already ask.

- Owners from systems of record. CODEOWNERS and a service catalog (Backstage `catalog-info.yaml`, or `services.json` here) already say who owns what. CODEOWNERS names teams, so I'd expand teams into people through GitHub teams or the identity provider. Nobody maintains a second owner list.
- Meet people where they ask. The same answer function behind a Slack bot, an MCP tool for coding agents, and the CLI. One index, three front ends.
- Unanswered questions become doc tasks. A not-found question with a known owner opens a task for that owner: "people asked X, nothing answers it."
- Freshness. Flag docs that disagree with `services.json`. The bundle's `services-overview.md` says its own table "goes stale fast", and someone asked "who owns billing now? I thought it was someone who left".
- The question log is the demand signal. It shows which systems people ask about most, which tells you which docs to write first.

## What I'd measure

- Time to an answer, from question to cited reply.
- The not-found rate, and the actual not-found questions. Those are the doc backlog.
- How often someone still pings a person after asking. That is the real test of whether the answer was good enough.
- Wrong-owner reports, from a "this is wrong" button on each answer.
- The eval score, run in CI on every change, so a match-rule change that breaks real questions fails the build.

## Safety and exposure

The role is self-asserted today: anyone can run `ask rbac employee`. It stands in for SSO login, where the role would come from identity-provider groups. Some secret shapes are redacted at index time: AWS key ids, GitHub, Slack, OpenAI and Stripe key prefixes, values assigned to secret-named keys (`password`, `token`, `api_key`, `*_KEY`, including quoted JSON keys), bearer tokens, passwords in URLs, JWTs and private key blocks. `.env*` files are skipped. Anything else is indexed as written, so a real rollout needs secret scanning at the source. Internal and external repos map to the employee and guest roles. Anything an agent can run can change the role, so the MCP tool exposes only `ask`, not `rbac` or the repo commands, and a test (`tests/test_mcp.py`) proves its schema has no role field.

## How I used AI tooling

Tools: Claude Code, with Opus as the controller, Sonnet for builders and reviewers, and Haiku for dashboard updates. The full log is notes/AI-LOG.md.

- Delegated: each build task went to one builder agent, then a separate reviewer agent. A different agent wrote the eval rows, so no builder graded its own work. Before the build, a fresh agent read the plan and listed 30-odd things it would have to guess.
- Kept by hand: the risk ranking and the access and correctness rules, the redaction ruling, reading every review, and running the bundle questions end to end as employee and as guest.
- Where agents were wrong:
  - Task 4's quote check only saw hits on a chunk's first line, so it could not catch a wrong line number. The reviewer caught it.
  - Task 5's CODEOWNERS `/*` matched nested files. The reviewer caught it.
  - The strict all-words match rule answered only 4 of 12 bundle questions, and the questions log "answered" every question by quoting it. No agent caught either. I found both by running the real questions, and replaced the rule with a 60% content-word rule.
  - Task 7 let words inside a path ("billing" in `services/billing/api.py`) match a service, so a path CODEOWNERS marks as unowned was answered with the ledger owner. The builder flagged it, the reviewer reproduced it, and one fix round removed path words from the service match.
