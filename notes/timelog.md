# Time log: Integrate take-home

Minutes are counted from the moment the clock started. "before clock" means before that.

| Step | Started | Finished | Minutes | Note |
|---|---|---|---|---|
| Run /pre-plan (skipped) |  | T+0 |  | done before clock (prompt approved); start marked it skipped |
| Write and approve PLAN.md (skipped) |  | T+0 |  | done before clock (PLAN.md approved) |
| Guess check (skipped) |  | T+0 |  | done before clock (fresh-agent guess pass, fixes applied) |
| Step 0: base commit on main | T+0 | T+0 | 0 | e7b21fc on main |
| Task 1: scaffold and rbac | T+0 | T+2 | 2 | 0704271, review clean, 9 tests |
| Task 2: file listing and redaction | T+2 | T+4 | 2 | 82ee883, review clean, 45 tests |
| Task 3: store and repo commands | T+4 | T+6 | 2 | 6176edc, review clean, 66 tests |
| Task 4: search, answer, question CLI | T+6 | T+11 | 5 | d101cc7, 1 fix round (quote check on mid-chunk hits), 110 tests |
| Task 5: CODEOWNERS | T+11 | T+14 | 3 | e3b94e8, 1 fix round (/* matched nested files), 138 tests |
| Task 6: eval runner and step 1 scores | T+14 |  |  | runner 3d926a4 + seen rows 8ea49bd done; still open: held-out score (eval/heldout.jsonl not written yet) and the step 1 PR |
| Task 4b: coverage match rule, echo-line skip | T+32 | T+32 | 0 | 8276d13..cfb30d5: 60% coverage + prefix match, echo-line skip; bundle questions 4/12 -> 8/12 search answers; 1 fix round; 178 tests |
