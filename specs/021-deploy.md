# 021: Deployment

Status: implemented

Everything runs on free tiers ($0/month, hard rule 1): web on Vercel Hobby, API on Render's
free plan (as a container, so any container host works), and Postgres on Supabase Free (500 MB;
we stay under 450 MB). `docs/DEPLOY.md` is the step-by-step guide.

- **DEPLOY-1** `Dockerfile` builds the API from `pyproject.toml` and `uv.lock` with no dev
  dependencies. It runs as a non-root user, has a `/health` healthcheck, applies migrations on
  start, then serves on `$PORT`. `.dockerignore` keeps data, the web app, tests and secrets out.
- **DEPLOY-2** CI builds the image and starts it against a fresh Postgres 16: migrations must
  apply and `/health` and `/methodology` must answer.
- **DEPLOY-3** `render.yaml` describes the API service: Docker runtime, free plan, `/health`
  check, deploys from `main`. Every secret is listed with `sync: false`, so values are only
  entered in the Render dashboard, never committed.
- **DEPLOY-4** `web/vercel.json` builds the web app with its pinned pnpm (`corepack`). Its
  environment variables are listed in `web/.env.example`.
- **DEPLOY-5** `docs/DEPLOY.md` covers, in order:
  1. Supabase: the session-pooler connection string in both forms (asyncpg for the API,
     plain for Better Auth). Why session mode: asyncpg's prepared statements don't work through
     a transaction-mode pooler.
  2. Render, Vercel and Google sign-in, with the OAuth redirect URI.
  3. The GitHub `DATABASE_URL` secret for scheduled jobs (spec 020), and the first data load
     by running the "Data refresh" workflow by hand.
  4. A checklist to confirm the deploy works.
