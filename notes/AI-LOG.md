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
