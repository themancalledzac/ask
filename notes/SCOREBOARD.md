# Scoreboard

One row per step. Seen rows are in `eval/seen.jsonl`, written by a separate agent and checked by me. Held-out rows are in `eval/heldout.jsonl`, written by me against `../mempalace` at `a938e3c`, which no agent reads.

| Step | Time | Seen | Held-out | Notes |
| --- | --- | --- | --- | --- |
| 1: repos, index, access, search, CODEOWNERS parser | T+14 at review | 10/13 | pending | The 3 seen fails are CODEOWNERS owner rows. Owner routing lands in step 2. |
