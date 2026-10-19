// Better Auth: optional sign-in with Google or email and password (spec 018). Server-only.
import { betterAuth } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { jwt } from "better-auth/plugins";
import { Pool } from "pg";

const TOKEN_FIELDS = ["accessToken", "refreshToken", "idToken"] as const;

/** ACC-2: keep the Google account link, never its tokens. */
export function withoutProviderTokens<T extends Record<string, unknown>>(account: T): T {
  const copy: Record<string, unknown> = { ...account };
  for (const field of TOKEN_FIELDS) copy[field] = null;
  copy.accessTokenExpiresAt = null;
  copy.refreshTokenExpiresAt = null;
  return copy as T;
}

export const authOptions = {
  baseURL: process.env.BETTER_AUTH_URL ?? "http://localhost:3000",
  // Tables come from the API's Alembic migration 0006, not Better Auth's migrator.
  // Keep each serverless instance from exhausting the managed Postgres connection limit.
  database: new Pool({
    connectionString: process.env.AUTH_DATABASE_URL,
    max: 2,
    idleTimeoutMillis: 10_000,
    connectionTimeoutMillis: 10_000,
    allowExitOnIdle: true,
  }),
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    },
  },
  // ACC-19: email and password; Better Auth stores only a salted scrypt hash (ACC-1).
  emailAndPassword: { enabled: true, minPasswordLength: 8, autoSignIn: true },
  databaseHooks: {
    account: {
      create: { before: async (account: Record<string, unknown>) => ({ data: withoutProviderTokens(account) }) },
      update: { before: async (account: Record<string, unknown>) => ({ data: withoutProviderTokens(account) }) },
    },
  },
  plugins: [
    // ACC-3: 15-minute tokens for the API, carrying only the user id (sub).
    jwt({ jwt: { expirationTime: "15m", definePayload: () => ({}) } }),
    nextCookies(),
  ],
} satisfies Parameters<typeof betterAuth>[0];

export const auth = betterAuth(authOptions);
