# How We Deploy (forge)

> Status: mostly accurate as of last quarter. The Ops bits changed recently and
> may be wrong.

We deploy through **forge**, our GitHub Actions–based pipeline.

## The short version
1. Open a PR. CI runs lint + tests.
2. Merge to `main` → forge builds a container and pushes to the registry.
3. Staging deploy is automatic. **Production requires a manual approval** in the
   forge dashboard from a Platform on-call.

## Secrets
Secrets live in the forge secret store, injected at deploy time as env vars.
**Never** commit secrets to a repo — we've been burned before (see the incident
in `oncall.md`). If you need a new secret added, ping the Platform owner.

## Things that bite people
- Services that bind to `127.0.0.1` instead of `0.0.0.0` come up "healthy" in the
  container but are unreachable. This has caused two outages.
- Hardcoded ports break the staging/prod port mapping. Read `PORT` from env.
