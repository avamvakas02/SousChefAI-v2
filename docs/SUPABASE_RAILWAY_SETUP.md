# Supabase Postgres + Railway Setup (Django)

This guide configures your app to:
- Keep Django app/business logic exactly as-is.
- Use Supabase for the production Postgres database.
- Deploy the Django app on Railway.

## 1) Supabase Project Setup

1. Create a new Supabase project.
2. Open `Project Settings -> Database`.
3. Copy the **connection string** URI (Postgres URI format).
   - Use the connection string that works for external apps.
4. Keep the DB password safe (you will add it to Railway env vars).

## 2) Django Environment Variables

Set these in Railway (and local `.env` if you want local testing against Supabase):

```env
DEBUG=False
SECRET_KEY=replace-with-a-strong-secret

# Railway domain(s) and any custom domain(s)
ALLOWED_HOSTS=.railway.app,your-app.up.railway.app,yourdomain.com
CSRF_TRUSTED_ORIGINS=https://your-app.up.railway.app,https://yourdomain.com

# Supabase Postgres URL
DATABASE_URL=postgresql://postgres:<password>@<host>:5432/postgres

# Optional tuning (defaults already set in settings.py)
DB_CONN_MAX_AGE=600
DB_SSL_REQUIRE=True
```

Notes:
- `DB_SSL_REQUIRE=True` is recommended for Supabase.
- On Railway, keep `DEBUG=False`.

## 3) Railway Service Setup

1. Connect your GitHub repo to Railway.
2. Add all required env vars in Railway.
3. Ensure start command runs your app (example):

```bash
gunicorn core.wsgi --log-file -
```

4. Add a release/migration step (important):

```bash
python manage.py migrate
```

If Railway does not support a dedicated release phase in your current setup, run migrations manually after each schema change:

```bash
python manage.py migrate
```

## 4) Local Verification (Before/After Deploy)

From your local venv:

```bash
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then confirm:
- Register/login works.
- Admin panel loads.
- Existing pages that read/write DB data work.

## 5) Data Migration Strategy (If Moving From Existing DB)

If your current data is in SQLite and you need to move it:

1. Keep old DB file as backup.
2. Point `DATABASE_URL` to Supabase.
3. Run migrations on Supabase:

```bash
python manage.py migrate
```

4. Load old data carefully (optional):
   - `python manage.py dumpdata > data.json` from old DB.
   - `python manage.py loaddata data.json` into Supabase-backed env.

Prefer loading only app models (not system tables) if there are auth/site/env differences.

## 6) Recommended Security/Operations

- Rotate secrets if any test/live keys were ever committed.
- Keep `SECRET_KEY`, DB credentials, Stripe keys only in env vars.
- Enable backups in Supabase.
- Keep Railway and Supabase in nearby regions for lower latency.

## 7) Troubleshooting

- **OperationalError / SSL errors**:
  - Verify `DATABASE_URL` is valid.
  - Ensure SSL is enabled (`DB_SSL_REQUIRE=True`).
- **CSRF errors in production**:
  - Add exact HTTPS domains to `CSRF_TRUSTED_ORIGINS`.
- **DisallowedHost**:
  - Add your domain to `ALLOWED_HOSTS`.
- **Slow first query**:
  - Keep `DB_CONN_MAX_AGE` non-zero (e.g., 600).

