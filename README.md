# NovaTech Store

Production-hardened FastAPI rebuild of NovaTech Store. The legacy JSON-backed PythonAnywhere/GitHub Pages design has been removed from the application surface.

## Architecture

- `backend/app`: FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis sessions, RQ email worker.
- `frontend`: same-origin static frontend served by FastAPI from an allow-listed static directory.
- `seed/products.json`: catalog import source. Do not import legacy users, admins, carts, or sessions.
- `tests`: security, unit, and integration coverage.

## Local Run

```powershell
Copy-Item .env.example .env
docker compose up -d
pip install -e ".[dev]"
alembic upgrade head
novatech-import-products seed/products.json
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## Admin Bootstrap

After migrations are applied, create a fresh production admin. Do not reuse any leaked admin data.

```powershell
novatech create-admin --email admin@example.com --username admin
```

Store the generated TOTP URI in an authenticator app before first login.

## Security Changes

- Argon2id password hashing. No SHA-256/plaintext compatibility path.
- Redis-backed opaque sessions in `HttpOnly` cookies.
- CSRF token endpoint plus Origin enforcement on unsafe API methods.
- Checkout uses one database transaction and a per-user `Idempotency-Key`.
- Decimal/NUMERIC money handling and non-finite numeric rejection.
- Object storage for admin image uploads. No persistent runtime writes inside the container.
- Strict same-origin deployment. CORS is not enabled for production.
- Static files are served only from `frontend/`; unknown direct paths return `404`.

## Deploy

Use `render.yaml` as the Render Blueprint. Render's current Blueprint spec defines Render Key Value as a service with `type: keyvalue`; this repository follows that structure.

Set the `sync: false` values in Render before first deployment:

- `APP_ORIGIN`
- `ALLOWED_HOSTS`
- `MFA_ENCRYPTION_KEY`
- SMTP values
- S3-compatible object storage values
- `ASSET_ORIGIN`

Run the incident cleanup in `SECURITY.md` before reconnecting the repository to production.
