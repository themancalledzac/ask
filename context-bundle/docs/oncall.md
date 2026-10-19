# On-Call Runbook (Platform)

On-call rotates weekly. The schedule lives in PagerDuty, not here.

## Common pages
- **atlas-api 5xx spike** — check the deploy that just went out; forge has a
  one-click rollback.
- **beacon backlog** — the notification queue is backing up; usually a downstream
  provider (courier) is throttling.
- **"billing looks wrong"** — escalate to Ops, owner of `ledger`. Do not touch
  ledger yourself.

## Past incident: leaked key (read this)
Last year an API key was committed to the `courier` repo and ended up in git
history. Rotating it was painful. Lesson: secrets come from the secret store,
always. Reviewers should flag any literal key in a diff.
