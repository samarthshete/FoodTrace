import { defineConfig, devices } from "@playwright/test";

import { E2E_DATABASE_URL } from "./e2e/global-setup";

const API_PORT = 8001;
const WEB_PORT = 3100;
const WEB_URL = `http://127.0.0.1:${WEB_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: WEB_URL,
    ...devices["Pixel 7"],
    launchOptions: {
      args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"],
    },
  },
  webServer: [
    {
      // OFF and USDA point at a closed port: e2e never calls a real outside service.
      command: `uv run uvicorn app.main:app --port ${API_PORT}`,
      cwd: "..",
      url: `http://127.0.0.1:${API_PORT}/health`,
      env: {
        DATABASE_URL: E2E_DATABASE_URL,
        OFF_BASE_URL: "http://127.0.0.1:9",
        USDA_BASE_URL: "http://127.0.0.1:9",
        OFF_CONTACT: "e2e",
        AUTH_JWKS_URL: `${WEB_URL}/api/auth/jwks`,
        AUTH_ISSUER: WEB_URL,
        AUTH_AUDIENCE: WEB_URL,
      },
      reuseExistingServer: false,
    },
    {
      // Production build: the service worker only registers in production.
      command: `pnpm build && pnpm start -p ${WEB_PORT}`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: {
        API_URL: `http://127.0.0.1:${API_PORT}`,
        BETTER_AUTH_URL: WEB_URL,
        BETTER_AUTH_SECRET: "e2e-only-secret-not-used-anywhere-else-0123456789",
        // Better Auth talks to Postgres directly (node-postgres URL, no SQLAlchemy driver).
        AUTH_DATABASE_URL: E2E_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"),
        GOOGLE_CLIENT_ID: "e2e",
        GOOGLE_CLIENT_SECRET: "e2e",
      },
      timeout: 180_000,
      reuseExistingServer: false,
    },
  ],
});
