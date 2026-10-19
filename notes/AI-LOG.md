# AI log

Tools: Claude Code (Opus as controller, Sonnet for builders and reviewers, Haiku for dashboard updates).

## Planning (before the clock)

- Delegated: a fresh agent read the plan and listed what it would have to guess. It found 30-odd gaps, including PEM keys spanning lines, `sk-` matching inside "risk-management", `docs/*` matching nested files, and services.json field names that didn't match the file.
- By hand: the ranking of risks, and the five access and correctness rules.
- Where the agent was wrong: the mempalace search pulled up notes from an unrelated project. I dropped them, and builders get no mempalace access.

## Step 1

- Delegated: Tasks 1 to 6, one builder agent each, each followed by a reviewer agent. A separate agent wrote the seen test rows, so the builder never wrote its own rows.
- By hand: the redaction ruling (index and the quote check both use the same line-preserving redaction), plus reading each review.
- Where agents got it wrong:
  - Task 4's quote check only ever saw hits on a chunk's first line, so it couldn't catch a wrong line number. The reviewer caught it, and one fix round added mid-chunk fixtures.
  - Task 5's `/*` matched nested files because the leading slash was stripped before the one-level check. The reviewer caught it, and one fix round fixed it.
  - Running the 12 bundle questions by hand found two things no agent had caught. First, the questions log quoted every question, so it "answered" all of them. Second, the strict all-words rule answered only 4 of 12. I prototyped a 60% coverage rule with prefix matching, the user approved it, and a builder applied it test-first (Task 4b). The builder changed the echo skip to drop the whole block. Its reviewer then caught that the skip counted raw words while my ruling said content words. I restated the ruling to match the code, which the courier question needs.

## Step 2

- Delegated: Task 7 (owner routing) to a builder on Opus, then a reviewer. A separate golden agent wrote the 12 bundle question rows and 4 owner not-found rows.
- By hand: ran the owner questions end to end as employee and as guest. Ruled that the suffix path match was out of scope, and ruled that the "where do secrets go" row accepts oncall.md instead of loosening the rule to fit one row.
- Where agents got it wrong: Task 7 let words inside a path ("billing" in `services/billing/api.py`) match a service. So a path that CODEOWNERS marks as unowned was answered with the ledger owner. The builder flagged it as a concern, and the reviewer reproduced it. One fix round took path tokens out of the service match, with tests that add the bundle and a CODEOWNERS repo together.

## Step 3

- Delegated: the README, the write-up draft and `ask --help` to one builder.
- By hand: the fresh-clone test, reading the write-up line by line, and cutting one claim. The draft said the tool "works on a repo it has never seen", which no test proves now that the held-out repo is dropped.
- Where things went wrong: PR #2 was stacked on the step 1 branch and merged into that branch, not main. I opened PR #3 to bring step 2 to main. A builder also left an empty `index.db` at the repo root during step 1. It was gitignored, so nothing shipped, but I deleted it.
