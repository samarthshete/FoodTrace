"use client";

import { useEffect, useState } from "react";

import { type LabelData, type Preferences, personalNotes } from "@/lib/allergens";
import { useSession } from "@/lib/auth-client";

// The signed-in user's part of the product page: allergen and diet notes (ACC-7, ACC-8), the
// Save toggle (ACC-12), and saving the view to history (ACC-9). Signed out: nothing.
export function ProductAccount({
  gtin,
  label,
  fetcher = fetch,
}: {
  gtin: string;
  label: LabelData;
  fetcher?: typeof fetch;
}) {
  const { data: session } = useSession();
  const signedIn = Boolean(session);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!signedIn) return;
    const post = { method: "POST", headers: { "Content-Type": "application/json" } };
    fetcher("/api/me/history", { ...post, body: JSON.stringify({ gtin }) }).catch(() => {});
    fetcher("/api/me")
      .then((r) => (r.ok ? r.json() : null))
      .then((me) => setPrefs(me?.preferences ?? null))
      .catch(() => {});
    fetcher("/api/me/favorites")
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((f: { items: { gtin: string }[] }) => setSaved(f.items.some((i) => i.gtin === gtin)))
      .catch(() => {});
  }, [signedIn, gtin, fetcher]);

  if (!signedIn) return null;

  async function toggle() {
    const next = !saved;
    setSaved(next);
    const res = await fetcher(`/api/me/favorites/${gtin}`, { method: next ? "PUT" : "DELETE" }).catch(
      () => null,
    );
    if (!res?.ok) setSaved(!next);
  }

  const notes = prefs ? personalNotes(label, prefs) : null;
  const hasNotes =
    notes && (notes.unknown || notes.contains.length || notes.mayContain.length || notes.diets.length);
  return (
    <div className="flex flex-col gap-3">
      {hasNotes ? (
        <section
          aria-labelledby="personal-heading"
          className="rounded-xl border-2 border-rose-700 bg-rose-50 p-4 text-sm text-rose-950"
        >
          <h2 id="personal-heading" className="flex gap-2 text-base font-semibold">
            <span aria-hidden="true">⚠</span> For your allergens and diet
          </h2>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {notes.unknown && (
              <li>Allergen information isn&apos;t available for this product. Check the label.</li>
            )}
            {notes.contains.length > 0 && <li>Contains: {notes.contains.join(", ")}</li>}
            {notes.mayContain.length > 0 && <li>May contain: {notes.mayContain.join(", ")}</li>}
            {notes.diets.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
          <p className="mt-2">
            From the label data.{" "}
            <a href="#ingredients-heading" className="underline">
              Read the ingredients
            </a>
            .
          </p>
        </section>
      ) : null}
      <button
        type="button"
        aria-pressed={saved}
        onClick={toggle}
        className="self-start rounded-lg px-3 py-1.5 text-sm font-medium ring-1 ring-zinc-300 hover:bg-zinc-100"
      >
        {saved ? "★ Saved" : "☆ Save"}
      </button>
    </div>
  );
}
