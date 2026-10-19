import { Suspense } from "react";

import { type AccountData, AccountView } from "@/components/AccountView";
import { SignInPrompt } from "@/components/SignInPrompt";
import { apiToken, fetchAsUser } from "@/lib/session";

export const metadata = { title: "Your account" };

export default function AccountPage() {
  return (
    <Suspense fallback={<p role="status">Loading your account…</p>}>
      <Account />
    </Suspense>
  );
}

async function Account() {
  const token = await apiToken();
  if (!token) return <SignInPrompt />;
  const get = async (path: string) => {
    const res = await fetchAsUser(path, token);
    if (!res.ok) throw new Error(`${path}: ${res.status}`);
    return res.json();
  };
  let data: AccountData | null = null;
  try {
    const [me, history, favorites, contributions] = await Promise.all([
      get("/me"), get("/me/history"), get("/me/favorites"), get("/me/contributions"),
    ]);
    data = { me, history: history.items, favorites: favorites.items, contributions: contributions.items };
  } catch {
    data = null;
  }
  if (!data) return <p>Your account isn&apos;t available right now. Try again in a moment.</p>;
  return <AccountView data={data} />;
}
