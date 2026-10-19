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
| Task 6: eval runner and step 1 scores | T+14 | T+36 | 22 | held-out dropped; seen 10/13 (3 owner rows wait for step 2); step 1 PR opened |
| Task 4b: coverage match rule, echo-line skip | T+32 | T+32 | 0 | 8276d13..cfb30d5: 60% coverage + prefix match, echo-line skip; bundle questions 4/12 -> 8/12 search answers; 1 fix round; 178 tests |
| Task 7: owner answers | T+36 | T+44 | 8 | 60fe94e..b03d7cf, 1 fix round (path words fed service match; suffix match removed); 197 tests; seen 13/13 |
| Task 8: bundle rows and step 2 scores | T+44 | T+49 | 5 | PR #1 merged to main; PR #2 merged into step-1 branch (stacked base), so step 2 not on main yet; replacement PR step-2-owners -> main opened |
| Task 9: ship | T+49 | T+53 | 4 | PR #4 merged; tag submission on 0c77451; 200 tests, eval 29/29; repo stays private until just before the interview, so the uvx line is untested |
| Task 10: MCP server | T+56 | T+62 | 6 | 1c0f591..d62e9ac: MCP server, one ask tool; injected role ignored (tested); 208 tests with extra; step 4 PR opened |
| Test README uvx one-liner on public repo | T+70 | T+70 | 0 | PUBLIC; fresh uv cache + ASK_HOME: help, rbac, add-repo, Sofia Reyes services.json:37, deploy-pipeline.md:11; @submission installs too |
| Owner question on a repo with no CODEOWNERS says so (org + recent committers) | T+70 | T+79 | 9 | 41b9c7b..f9f55a1: no-CODEOWNERS message + org + committers; --repo only when asking about the repo; 232 tests |
| Whole-repo review (separate agent) | T+70 | T+78 | 8 | 0 Critical, 5 Important (secret redaction gaps, owner-before-name, non-UTF-8 filename, size check, porter vs prefix), 12 Minor |
| Fix whole-repo review findings | T+79 | T+89 | 10 | PR #6 merged; 271 tests, eval 29/29; fix-wave re-review was never run |
| README: MCP setup order, no-clone install with MCP, claude mcp add -s user, /mcp + ledger check | T+88 | T+92 | 4 | 05e7335: install, rbac, add-repo, claude mcp add -s user, /mcp + ledger check; install and stdio verified, claude mcp add not run; PR opened |
| One hit per file; MCP up to 10 hits, CLI 3 (skipped) | T+92 | T+92 | 0 | stopped: timer over; briefed, not built |
| Move submission tag to final main | T+89 | T+89 | 0 | submission tag moved to d43c8eb (merge of #6), verified |
| Ship by the buzzer | T+56 |  |  | final: submission tag on d43c8eb; README MCP setup in PR #7 |
