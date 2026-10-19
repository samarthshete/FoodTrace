import { execSync } from "node:child_process";
import { join } from "node:path";

const ROOT = join(__dirname, "..", "..");
export const E2E_DATABASE_URL =
  process.env.E2E_DATABASE_URL ?? "postgresql+asyncpg://ofs:ofs@localhost:5432/ofs_test";

// Migrate the test database, load real additives (from the cached OFF taxonomy), seed a product.
export default function globalSetup() {
  const env = { ...process.env, DATABASE_URL: E2E_DATABASE_URL };
  for (const cmd of [
    "uv run alembic upgrade head",
    "uv run python -m pipeline.reference",
    "uv run python web/e2e/seed.py",
  ]) {
    execSync(cmd, { cwd: ROOT, env, stdio: "inherit" });
  }
}
