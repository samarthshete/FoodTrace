# 020: Scheduled data jobs

Status: implemented

GitHub Actions keeps the hosted database fresh at no cost. The jobs do nothing until the
repository has a `DATABASE_URL` secret pointing at the hosted Postgres, in SQLAlchemy's
asyncpg form (`postgresql+asyncpg://user:password@host:5432/db`). Until then, forks and the
current setup stay inert.

- **OPS-1** `.github/workflows/data-refresh.yml` runs the recall sync (`pipeline.recalls`)
  **daily** at 07:17 UTC, and the full refresh **weekly** on Mondays at 06:23 UTC: migrations,
  `pipeline.reference --refresh`, `pipeline.off_bulk --refresh` with the USDA gap-fill, then
  `pipeline.recalls`. The non-zero minutes avoid GitHub Actions' busiest scheduling boundary.
  Both jobs can also be started by hand (`workflow_dispatch`).
- **OPS-2** Each job checks for the `DATABASE_URL` secret first. Without it, the job logs
  "skipped: no DATABASE_URL secret" and succeeds, so missing setup is never a red build.
- **OPS-3** The weekly job downloads the USDA Branded Foods zip from the URL in the
  `USDA_BRANDED_ZIP_URL` repository variable. Without the variable, it imports Open Food
  Facts alone and logs that it did so.
- **OPS-4** The jobs never overlap (one `concurrency` group), have a timeout (20 minutes
  daily, 90 minutes weekly), and read only the secrets they need. `OFF_CONTACT` comes from
  a repository variable, for the User-Agent.
- **OPS-5** The daily database work reduces idle time, but does not guarantee that Supabase
  Free will keep a low-activity project active; operators must monitor pausing notices and can
  restore a paused project manually.
- **OPS-6** A failed run fails the workflow, so GitHub notifies the repository owner. Nothing
  else alerts.
