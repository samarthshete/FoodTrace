"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ALLERGENS, type Allergen, DIETS, type Diet, type Preferences } from "@/lib/allergens";
import { signOut } from "@/lib/auth-client";
import { formatDate } from "@/lib/present";

export interface HistoryItem {
  id: number;
  gtin: string;
  scanned_at: string;
  name: string | null;
  brand: string | null;
  total: number | null;
  band: { id: string; label: string } | null;
}
export interface Favorite {
  gtin: string;
  name: string | null;
  brand: string | null;
  total: number | null;
}
export interface AccountData {
  me: { name: string; email: string; image: string | null; preferences: Preferences };
  history: HistoryItem[];
  favorites: Favorite[];
  contributions: { gtin: string; name: string | null; created_at: string }[];
}

/** History rows grouped by calendar day, newest day first (ACC-10). */
export function groupByDay(items: HistoryItem[]): [string, HistoryItem[]][] {
  const days = new Map<string, HistoryItem[]>();
  for (const item of items) {
    const day = formatDate(item.scanned_at);
    days.set(day, [...(days.get(day) ?? []), item]);
  }
  return [...days.entries()];
}

export function AccountView({ data, fetcher = fetch }: { data: AccountData; fetcher?: typeof fetch }) {
  const [prefs, setPrefs] = useState(data.me.preferences);
  const [history, setHistory] = useState(data.history);
  const [status, setStatus] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const router = useRouter();

  async function savePrefs(next: Preferences) {
    setPrefs(next);
    const res = await fetcher("/api/me/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(next),
    }).catch(() => null);
    setStatus(res?.ok ? "Saved." : "Couldn't save. Try again.");
  }

  function toggle<T extends string>(list: T[], value: T): T[] {
    return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
  }

  async function removeScan(id: number) {
    const res = await fetcher(`/api/me/history/${id}`, { method: "DELETE" }).catch(() => null);
    if (res?.ok) setHistory((h) => h.filter((i) => i.id !== id));
  }

  async function clearHistory() {
    const res = await fetcher("/api/me/history", { method: "DELETE" }).catch(() => null);
    if (res?.ok) setHistory([]);
    setStatus(res?.ok ? "History deleted." : "Couldn't delete. Try again.");
  }

  async function deleteAccount() {
    const res = await fetcher("/api/me", { method: "DELETE" }).catch(() => null);
    if (res?.ok) {
      await signOut().catch(() => {});
      router.push("/");
      router.refresh();
    } else setStatus("Couldn't delete your account. Try again.");
  }

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-bold">Your account</h1>
        <p className="text-zinc-700">
          {data.me.name} · {data.me.email}
        </p>
        <p role="status" className="min-h-5 text-sm text-zinc-600">
          {status}
        </p>
      </header>

      <section aria-labelledby="prefs-heading" className="flex flex-col gap-3">
        <h2 id="prefs-heading" className="text-lg font-semibold">
          Allergens and diets
        </h2>
        <fieldset className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
          <legend className="mb-1 font-medium">Warn me about</legend>
          {(Object.keys(ALLERGENS) as Allergen[]).map((a) => (
            <label key={a} className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={prefs.allergens.includes(a)}
                onChange={() => savePrefs({ ...prefs, allergens: toggle(prefs.allergens, a) })}
              />
              {ALLERGENS[a].label}
            </label>
          ))}
        </fieldset>
        <fieldset className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
          <legend className="mb-1 font-medium">My diet</legend>
          {(Object.keys(DIETS) as Diet[]).map((d) => (
            <label key={d} className="flex items-center gap-1.5">
              <input
                type="checkbox"
                checked={prefs.diets.includes(d)}
                onChange={() => savePrefs({ ...prefs, diets: toggle(prefs.diets, d) })}
              />
              {DIETS[d]}
            </label>
          ))}
        </fieldset>
      </section>

      <section aria-labelledby="history-heading" className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 id="history-heading" className="text-lg font-semibold">
            Scan history
          </h2>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={!prefs.save_history}
              onChange={() => savePrefs({ ...prefs, save_history: !prefs.save_history })}
            />
            Pause history
          </label>
        </div>
        {history.length === 0 ? (
          <p className="text-sm text-zinc-600">No scans saved.</p>
        ) : (
          <>
            {groupByDay(history).map(([day, items]) => (
              <div key={day}>
                <h3 className="text-sm font-medium text-zinc-600">{day}</h3>
                <ul className="divide-y divide-zinc-200">
                  {items.map((item) => (
                    <li key={item.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                      <Link href={`/p/${item.gtin}`} className="min-w-0 truncate underline">
                        {item.name ?? item.gtin}
                      </Link>
                      <span className="flex shrink-0 items-center gap-3">
                        {item.total !== null && (
                          <span>
                            {item.total}/100{item.band && ` · ${item.band.label}`}
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => removeScan(item.id)}
                          aria-label={`Remove ${item.name ?? item.gtin} from history`}
                          className="text-zinc-600 underline"
                        >
                          Remove
                        </button>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            <button type="button" onClick={clearHistory} className="self-start text-sm underline">
              Delete all history
            </button>
          </>
        )}
      </section>

      <section aria-labelledby="favorites-heading">
        <h2 id="favorites-heading" className="text-lg font-semibold">
          Saved products
        </h2>
        {data.favorites.length === 0 ? (
          <p className="text-sm text-zinc-600">Nothing saved yet. Use ☆ Save on a product.</p>
        ) : (
          <ul className="mt-2 divide-y divide-zinc-200 text-sm">
            {data.favorites.map((f) => (
              <li key={f.gtin} className="flex justify-between py-2">
                <Link href={`/p/${f.gtin}`} className="underline">
                  {f.name ?? f.gtin}
                </Link>
                {f.total !== null && <span>{f.total}/100</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      {data.contributions.length > 0 && (
        <section aria-labelledby="contrib-heading">
          <h2 id="contrib-heading" className="text-lg font-semibold">
            Products you added
          </h2>
          <ul className="mt-2 list-disc pl-5 text-sm">
            {data.contributions.map((c) => (
              <li key={c.gtin}>
                <Link href={`/p/${c.gtin}`} className="underline">
                  {c.name ?? c.gtin}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="delete-heading" className="flex flex-col gap-2 border-t border-zinc-200 pt-4">
        <h2 id="delete-heading" className="text-lg font-semibold">
          Delete your account
        </h2>
        <p className="text-sm text-zinc-700">
          Removes your account, preferences, history and saved products. Products you added stay,
          without your name.
        </p>
        {confirmDelete ? (
          <div className="flex gap-3">
            <button
              type="button"
              onClick={deleteAccount}
              className="rounded-lg bg-rose-800 px-4 py-2 font-medium text-white"
            >
              Yes, delete everything
            </button>
            <button type="button" onClick={() => setConfirmDelete(false)} className="underline">
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirmDelete(true)}
            className="self-start rounded-lg px-4 py-2 font-medium text-rose-800 ring-1 ring-rose-800"
          >
            Delete account
          </button>
        )}
      </section>
    </div>
  );
}
