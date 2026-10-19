# FoodTrace Deployment Guide

This guide deploys FoodTrace as a non-commercial, strict-$0 portfolio/demo:

- Next.js web app and Better Auth on Vercel Hobby
- Dockerized FastAPI API on Render Free
- PostgreSQL on Supabase Free
- CI and scheduled data refreshes on GitHub Actions

The repository is `samarthshete/FoodTrace`, and production deploys come from `main`.
Never commit a real environment file, password, token, private key, or connection string.

## 1. Architecture and limitations

```mermaid
flowchart LR
    User[Browser PWA] --> Vercel[Next.js on Vercel]
    Vercel --> Render[FastAPI on Render]
    Vercel --> Supabase[PostgreSQL on Supabase]
    Render --> Supabase
    Render --> OFF[Open Food Facts]
    Render --> USDA[USDA FoodData Central]
    GitHub[GitHub Actions] --> Supabase
    GitHub --> Render
    GitHub --> Vercel
```

The browser talks to same-origin Next.js route handlers. Next.js calls FastAPI through the
server-only `API_URL`, so the API does not enable browser CORS. Both Better Auth and FastAPI use
the same PostgreSQL database. FastAPI validates short-lived Better Auth JWTs through the web
app's JWKS endpoint.

This is a demo deployment, not an availability-sensitive production service:

- Vercel Hobby is limited to non-commercial personal use.
- Render Free sleeps after 15 minutes without inbound traffic and can take about one minute
  to wake. Render describes free instances as unsuitable for production.
- Supabase Free can pause low-activity projects, has a 500 MB database-data limit, and provides
  no automatic database backups.
- GitHub scheduled workflows can be delayed or dropped.
- None of these free services provides an application SLA.

Current official references, checked 2026-10-19:

- [Vercel Hobby](https://vercel.com/docs/plans/hobby)
- [Vercel limits](https://vercel.com/docs/limits)
- [Render free services](https://render.com/docs/free)
- [Render Blueprint specification](https://render.com/docs/blueprint-spec)
- [Supabase pricing](https://supabase.com/pricing)
- [Supabase project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)
- [Supabase backups](https://supabase.com/docs/guides/platform/backups)
- [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)

Expected recurring platform cost: **$0**, provided all usage remains within free allowances and
no paid plan or usage-billed feature is enabled.

## 2. Prerequisites

Create or sign in to:

1. GitHub account with admin access to `samarthshete/FoodTrace`
2. Supabase account with one available Free project
3. Render account connected to the GitHub account
4. Vercel account connected to the GitHub account
5. Google Cloud project for optional Google OAuth
6. A free USDA API key from [api.data.gov](https://api.data.gov/signup)
7. Optionally, a Groq free-tier key for intent parsing and Whisper transcription

Local tools for validation and backups:

```bash
git
docker
uv
corepack
node 24
pg_dump
```

Before provisioning, confirm CI is green on `main` and the working tree is clean:

```bash
git status --short
gh run list --repo samarthshete/FoodTrace --limit 10
```

## 3. Database: Supabase

### 3.1 Create the project

1. Create a Supabase Free project in a US region close to the expected users.
2. Generate a strong database password and store it in a password manager.
3. Do not place the password or connection strings in this repository.
4. In **Project Settings → Database**, copy the shared **Session pooler** URL on port `5432`.

The API uses asyncpg and session-scoped PostgreSQL behavior. Do not use the transaction pooler
on port `6543` for `DATABASE_URL` unless the application is explicitly changed to disable
prepared statements.

Create two URLs from the same session-pooler connection:

```text
# Render API and GitHub Actions
postgresql+asyncpg://USER:PASSWORD@HOST:5432/postgres

# Vercel Better Auth and pg_dump
postgresql://USER:PASSWORD@HOST:5432/postgres
```

Retain the SSL settings provided by Supabase. Percent-encode special characters in the password.

### 3.2 Schema and migrations

The Render container runs this command before starting the API:

```bash
uv run --no-sync alembic upgrade head
```

The migrations create the product, scoring, recall, contribution, Better Auth, and account
tables; enable `pg_trgm`; and configure the `ofs_app` row-level-security role. Do not run Better
Auth's schema migrator separately.

After the first API deploy, verify the latest migration from a trusted machine:

```bash
DATABASE_URL='postgresql+asyncpg://...' uv run alembic current
```

### 3.3 Backups

Supabase Free has **no automatic database backups**. Before schema changes and periodically
after launch, create an encrypted logical backup from a trusted machine:

```bash
pg_dump "$AUTH_DATABASE_URL" --format=custom --file "foodtrace-$(date +%F).dump"
```

The dump contains account and health-adjacent user data. Store it outside the repository in
encrypted storage with restricted access. Never upload an unencrypted dump as a GitHub artifact.
Test restoration into a separate local database:

```bash
createdb foodtrace_restore_test
pg_restore --clean --if-exists --no-owner \
  --dbname postgresql://localhost/foodtrace_restore_test foodtrace-YYYY-MM-DD.dump
```

## 4. API: Render

### 4.1 Create the service

1. In Render, choose **New → Blueprint**.
2. Select `samarthshete/FoodTrace`, branch `main`, and the root `render.yaml`.
3. Confirm the service is named `foodtrace-api`, uses Docker, and uses the Free plan.
4. Keep the generated `onrender.com` domain and HTTPS enabled.
5. Render waits for GitHub checks because `autoDeployTrigger` is `checksPass`.

Do not override the Docker build or start command. The image applies migrations and starts:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 4.2 Render environment variables

Enter these in the Render dashboard:

- `DATABASE_URL` — Supabase session-pooler URL using `postgresql+asyncpg://`
- `OFF_CONTACT` — `https://github.com/samarthshete/FoodTrace`
- `USDA_API_KEY` — free api.data.gov key; do not rely on `DEMO_KEY`
- `AUTH_JWKS_URL` — `https://WEB_DOMAIN/api/auth/jwks`
- `AUTH_ISSUER` — `https://WEB_DOMAIN`
- `AUTH_AUDIENCE` — `https://WEB_DOMAIN`
- `OFF_USER` — optional Open Food Facts account
- `OFF_PASSWORD` — optional Open Food Facts password

The three `AUTH_*` values must use the exact canonical Vercel production origin, including
`https://` and without a trailing slash. Preview deployment URLs are not valid issuers.

### 4.3 API verification

```bash
curl -fsS https://API_DOMAIN/health
curl -fsS https://API_DOMAIN/ready
curl -fsS https://API_DOMAIN/methodology
```

`/health` proves the process is alive. `/ready` performs `SELECT 1` and returns HTTP 503 when
PostgreSQL is unavailable. Render uses `/ready` for deployment health.

## 5. Web: Vercel

### 5.1 Import the project

1. Import `samarthshete/FoodTrace` into Vercel.
2. Set **Root Directory** to `web`.
3. Select the Next.js framework preset.
4. Use Node.js 24, as pinned in `web/package.json`.
5. Keep the production branch as `main`.
6. Do not enable a paid plan or usage-billed add-on.

The committed Vercel configuration installs with:

```bash
corepack enable && pnpm install --frozen-lockfile
```

The production build is:

```bash
pnpm build
```

Install and prebuild hooks copy ZXing WASM and Tesseract assets into `public/`. A deployment
must contain `/zxing/zxing_reader.wasm` and the `/tesseract/` worker, core, and language files.

### 5.2 Vercel environment variables

Set these for the Production environment:

- `API_URL` — canonical Render origin, such as `https://foodtrace-api.onrender.com`
- `BETTER_AUTH_URL` — canonical Vercel origin
- `BETTER_AUTH_SECRET` — output of `openssl rand -base64 32`
- `AUTH_DATABASE_URL` — Supabase session-pooler URL using plain `postgresql://`
- `GOOGLE_CLIENT_ID` — optional until Google OAuth is configured
- `GOOGLE_CLIENT_SECRET` — optional until Google OAuth is configured
- `GROQ_API_KEY` — optional; without it the assistant uses keyword rules
- `GROQ_MODEL` — optional, default `openai/gpt-oss-20b`
- `GROQ_STT_MODEL` — optional, default `whisper-large-v3-turbo`

All values are server-only. The project intentionally uses no `NEXT_PUBLIC_*` API or secret
variables. The Better Auth PostgreSQL pool is bounded to two connections per serverless instance.

After setting the final `BETTER_AUTH_URL`, redeploy Vercel. Then make the Render `AUTH_*` values
match it exactly and redeploy Render.

## 6. Authentication and Google OAuth

Email/password authentication works without Google credentials. To enable Google:

1. Open Google Cloud Console → **APIs & Services → Credentials**.
2. Create an OAuth client ID of type **Web application**.
3. Add the canonical Vercel origin as an authorized JavaScript origin.
4. Add this exact authorized redirect URI:

```text
https://WEB_DOMAIN/api/auth/callback/google
```

5. Store the client ID and secret in Vercel only.
6. Redeploy Vercel.

Do not register ephemeral preview URLs as production issuers. FastAPI downloads public signing
keys from `AUTH_JWKS_URL` and checks issuer, audience, expiration, and subject.

## 7. GitHub Actions and initial data

In **GitHub → Settings → Secrets and variables → Actions**, add:

- Secret `DATABASE_URL` — the Supabase asyncpg session-pooler URL
- Variable `OFF_CONTACT` — `https://github.com/samarthshete/FoodTrace`
- Variable `USDA_BRANDED_ZIP_URL` — optional current Branded Foods CSV zip URL

The workflow is inert when `DATABASE_URL` is absent. After adding it:

1. Open **Actions → Data refresh → Run workflow**.
2. Select `full`.
3. Confirm migrations, additives, bulk products, scores, and recalls complete.
4. Check Supabase database usage remains below 450 MB.

Scheduled jobs run at:

- Daily recalls: 07:17 UTC
- Weekly full refresh: Monday 06:23 UTC

The daily activity reduces idle time but does not guarantee Supabase will keep the project
unpaused. Monitor Supabase email notices. Scheduled GitHub jobs may run late.

CI/CD is:

```text
commit → pull request → CI/CodeQL → merge to main
       → Render deploy after checks pass
       → Vercel production deployment
```

Provider-native Git integration performs deployment. Do not add duplicate GitHub deployment
workflows.

## 8. Verification

### 8.1 Platform checks

- GitHub CI, CodeQL, e2e, and Docker checks are green.
- Render deployment is healthy and `/ready` returns HTTP 200.
- Vercel deployment uses the production domain and HTTPS.
- Supabase is active, migrations are current, and database usage is below 450 MB.
- Render and Vercel logs contain no repeated authentication, connection, or asset errors.

### 8.2 User workflows

1. Open the home page over HTTPS.
2. Search for a known product and open its product page.
3. Confirm score, breakdown source links, alternatives, and Open Food Facts attribution.
4. Confirm scanner and OCR assets load from the Vercel origin, not a CDN.
5. Ask an assistant question; verify keyword fallback when Groq is unset.
6. Create an email/password account, sign out, and sign in again.
7. Save a product, update preferences, view history, and delete account data.
8. If Google credentials are configured, complete Google sign-in and callback.
9. Verify `/api/me/*` returns 401 without a session and succeeds with one.
10. Confirm the educational-not-medical-advice footer is visible.

### 8.3 Cold-start check

After the API has been idle for more than 15 minutes, load a product page and record the Render
wake-up delay. A slow first request is expected on the Free plan; subsequent requests should be
substantially faster.

## 9. Rollback and recovery

### Application rollback

- Vercel: open **Deployments**, select the last known-good production deployment, and promote it.
- Render: open **Deploys**, choose the last known-good image, and redeploy it.
- GitHub: revert the faulty change through a pull request. Do not rewrite `main`.

### Database recovery

- Alembic migrations run before the API starts. Review every migration for backward compatibility.
- Do not run destructive downgrade or production reset commands.
- For data loss, create a separate Supabase project or local PostgreSQL database and test
  `pg_restore` there before replacing production data.
- Restore account/auth data only from an encrypted, access-controlled backup.

### Free-tier suspension

- If Render is suspended, inspect monthly hours/bandwidth and redeploy only after the allowance
  resets or usage is reduced.
- If Supabase is paused, restore it from the dashboard and rerun `/ready`.
- If Vercel limits are reached, wait for the allowance window to reset; do not enable paid
  overages for this strict-$0 deployment.

## Alternative platform

If Render or Supabase Free becomes unsuitable, the closest strict-$0 fallback is Vercel Hobby,
Koyeb Free for the API, and Neon Free for PostgreSQL. It still sleeps and is not reliable
production infrastructure. Railway is operationally simpler but has only a small monthly credit
and generally requires its $5 Hobby plan, so it is outside this project's zero-cost rule.
