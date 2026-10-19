// The signed-in user's API token, server-side (ACC-3). Null when signed out.
import { headers } from "next/headers";

import { apiUrl } from "./api";
import { auth } from "./auth";

export async function apiToken(requestHeaders?: Headers): Promise<string | null> {
  try {
    const { token } = await auth.api.getToken({ headers: requestHeaders ?? (await headers()) });
    return token ?? null;
  } catch {
    return null; // no session
  }
}

/** Call the API's /me routes as the signed-in user. */
export async function fetchAsUser(path: string, token: string, init: RequestInit = {}) {
  return fetch(`${apiUrl()}${path}`, {
    ...init,
    headers: { ...init.headers, Accept: "application/json", Authorization: `Bearer ${token}` },
  });
}
