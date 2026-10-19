# 021: Deployment

Status: implemented

Everything runs on free tiers ($0/month, hard rule 1): web on Vercel Hobby, API on Render's
free plan (as a container, so any container host works), and Postgres on Supabase Free (500 MB;
we stay under 450 MB). `docs/DEPLOYMENT_GUIDE.md` is the step-by-step guide.

- **DEPLOY-1** `Dockerfile` builds the API from `pyproject.toml` and `uv.lock` with no dev
  dependencies. It runs as a non-root user, uses `/health` for process liveness and a
  database-aware `/ready` endpoint for deployment health checks, applies migrations on start,
  then serves on `$PORT`. `.dockerignore` keeps data, the web app, tests and secrets out.
- **DEPLOY-2** CI builds the image and starts it against a fresh Postgres 16: migrations must
  apply and `/health`, `/ready` and `/methodology` must answer.
- **DEPLOY-3** `render.yaml` describes the API service: Docker runtime, free plan, `/ready`
  check, deploys from `main` only after its CI checks pass. Every secret is listed with
  `sync: false`, so values are only entered in the Render dashboard, never committed.
- **DEPLOY-4** `web/vercel.json` builds the web app with its pinned pnpm (`corepack`). Its
  supported Node runtime is pinned, its serverless Better Auth database pool is bounded, and
  its environment variables are listed in `web/.env.example`.
- **DEPLOY-5** `docs/DEPLOYMENT_GUIDE.md` is the complete production guide and
  `docs/DEPLOY.md` links to it. The guide covers, in order:
  1. Supabase: the session-pooler connection string in both forms (asyncpg for the API,
     plain for Better Auth), the free-tier pause risk, and the lack of automatic backups.
  2. Render, Vercel and Google sign-in, with the OAuth redirect URI.
  3. The GitHub `DATABASE_URL` secret for scheduled jobs (spec 020), and the first data load
     by running the "Data refresh" workflow by hand.
  4. Exact environment variables, rollback steps, and a checklist to confirm the deploy works.
