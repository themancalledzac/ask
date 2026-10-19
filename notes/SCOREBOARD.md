# Scoreboard

One row per step. Seen rows are in `eval/seen.jsonl`, written by a separate agent and checked by me. Held-out rows are in `eval/heldout.jsonl`, written by me against `../mempalace` at `a938e3c`, which no agent reads.

| Step | Time | Seen | Held-out | Notes |
| --- | --- | --- | --- | --- |
| 1: repos, index, access, search, CODEOWNERS parser | T+32 | 10/13 | pending | The 3 seen fails are CODEOWNERS owner rows. Owner routing lands in step 2. Bundle questions: 8 of 12 answered from the right doc after the match-rule fix (was 4 of 12). The 3 owner questions wait for step 2, and "what does lookout pull from" is honestly not found. |
