# Write-up

## What I built and why

`ask` is a Python CLI that answers "where does X live / who owns X" from repos you add, with a `repo:path:line` citation on every answer. It indexes every git-tracked file (code included) into SQLite FTS5, and only the standard library is used. Two roles, employee and guest, decide which repos a question can see.

Left out on purpose: Slack and Notion connectors, a web UI, real login, a model writing answers, live GitHub lookups, and a stale-docs report.

## How I'd attack the real problem

To be written.

## What I'd measure

To be written.

## Safety and exposure

`ask rbac <role>` is self-asserted. Anyone at the keyboard can run `ask rbac employee`. It stands in for SSO login, where the role would come from identity-provider group membership. Secrets (API keys, passwords in URLs, JWTs, private keys) are redacted before text reaches the index, and `.env*` files are never read.

## How I used AI tooling

See `notes/AI-LOG.md`.
