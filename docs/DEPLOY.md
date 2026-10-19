# Deploying FoodTrace ($0/month)

| Part | Host (free tier) | Config |
| --- | --- | --- |
| Database | Supabase Free (500 MB; we stay under 450 MB) | Alembic migrations |
| API | Render free web service (Docker) | `Dockerfile`, `render.yaml` |
| Web | Vercel Hobby | `web/vercel.json`, `web/.env.example` |
| Data refresh | GitHub Actions | `.github/workflows/data-refresh.yml` |

The Render free service sleeps after 15 idle minutes, and the first request after that takes
about a minute. Any container host works the same way with the `Dockerfile`.

## 1. Database: Supabase

1. Create a project at supabase.com (Free plan). Pick the region closest to your users.
2. **Project Settings → Database → Connection string → Session pooler** (port **5432**). Use
   session mode, not the transaction pooler on 6543: the API's driver (asyncpg) uses prepared
   statements, which a transaction-mode pooler breaks.
3. You need the string in two forms:
   - **API** (`DATABASE_URL`): `postgresql+asyncpg://postgres.<ref>:<password>@<host>:5432/postgres`
   - **Web** (`AUTH_DATABASE_URL`): `postgresql://postgres.<ref>:<password>@<host>:5432/postgres`

The API applies migrations when it starts, including the row-level-security role `ofs_app`.

## 2. API: Render

1. render.com → **New → Blueprint** → pick this repository. Render reads `render.yaml`.
2. Enter the secrets it asks for:
   - `DATABASE_URL`: the asyncpg form from step 1.
   - `OFF_CONTACT`: your email (sent in the Open Food Facts User-Agent).
   - `USDA_API_KEY`: free at https://api.data.gov/signup.
   - `AUTH_JWKS_URL`, `AUTH_ISSUER`, `AUTH_AUDIENCE`: your web URL from step 3, e.g.
     `https://foodtrace.vercel.app/api/auth/jwks`, and the URL itself twice.
   - `OFF_USER`, `OFF_PASSWORD`: optional, to let users share contributions with Open Food Facts.
3. Deploy. Check `https://<api>.onrender.com/health` returns `{"status":"ok"}`.

## 3. Web: Vercel

1. vercel.com → **Add New → Project** → this repository. Set **Root Directory** to `web`.
2. Environment variables (see `web/.env.example`):
   - `API_URL`: `https://<api>.onrender.com`
   - `BETTER_AUTH_URL`: your Vercel URL, e.g. `https://foodtrace.vercel.app`
   - `BETTER_AUTH_SECRET`: `openssl rand -base64 32`
   - `AUTH_DATABASE_URL`: the plain `postgresql://` form from step 1
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: from step 4
3. Deploy, then set the Render `AUTH_*` values to this URL if you hadn't yet.

## 4. Google sign-in

Google Cloud Console → **APIs & Services → Credentials → Create OAuth client ID → Web
application**:
- Authorized JavaScript origin: your Vercel URL.
- Authorized redirect URI: `<your Vercel URL>/api/auth/callback/google`.

Put the client ID and secret into Vercel (step 3) and redeploy.

## 5. Data: GitHub Actions

1. Repository **Settings → Secrets and variables → Actions**:
   - Secret `DATABASE_URL`: the asyncpg form from step 1.
   - Variable `OFF_CONTACT`: your email.
   - Variable `USDA_BRANDED_ZIP_URL` (optional): the latest "Branded Foods CSV" zip from
     https://fdc.nal.usda.gov/download-datasets/.
2. **Actions → Data refresh → Run workflow → full** for the first load (about 15 minutes):
   additives, around 100,000 US products, and recalls. After that it runs on its own: recalls
   daily, everything weekly.

## 6. Check it works

- [ ] `<api>/health` is ok, and `<api>/methodology` shows the current `engine_version`.
- [ ] The web home page loads, and searching "cheerios" suggests products.
- [ ] A product page shows a score, its rules and sources, and alternatives.
- [ ] Sign in with Google works, and the account page loads.
- [ ] Supabase **Database → Usage** shows under 450 MB.
