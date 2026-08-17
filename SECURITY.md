# Security Runbook

## Immediate Owner Actions

These actions require repository, PythonAnywhere, GitHub, Gmail, and Render account access. They are intentionally not automated by the application code.

1. Disable GitHub Pages for the old static frontend.
2. Stop the old PythonAnywhere application.
3. Make the repository private before cleanup.
4. Treat `users.json`, `admins.json`, `carts.json`, `TEST_ACCOUNTS.txt`, Gmail app passwords, deploy tokens, and every legacy session as compromised.
5. Rotate admin credentials, Gmail app passwords, deployment tokens, and any secret found by history scanning.
6. Do not migrate users, password hashes, carts, sessions, or legacy admins.
7. Import only `seed/products.json` after validating prices, stock, and image references.

## Git History Cleanup

Install `git-filter-repo`, then run the guarded helper:

```powershell
.\scripts\purge-history.ps1 -IUnderstandThisRewritesHistory
```

Review the resulting history locally, run Gitleaks, and only then force-push with lease:

```powershell
gitleaks detect --source .
git push --force-with-lease origin main
```

## Production Acceptance

Release is acceptable only after:

- The leaked JSON/test files are absent from the repository and Git history.
- All credentials and app passwords are rotated.
- CI passes: tests, lint, typecheck, Alembic, Gitleaks, dependency audit, Bandit, CodeQL, Docker build.
- `GET` and `HEAD` traversal probes return `404`.
- Concurrent checkout cannot create negative stock/balance and cannot double-charge one idempotency key.
- OWASP ZAP staging scan has no open Critical or High findings.
- Production monitoring is watched for at least 24 hours after launch.

## Operational Checks

Monitor:

- login failures and `429` rate limits
- checkout failures and idempotency conflicts
- RQ queue depth
- PostgreSQL connection and transaction errors
- Redis health
- 5xx response rate
