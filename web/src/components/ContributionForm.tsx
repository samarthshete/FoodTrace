"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { type Per100g, parseLabel } from "@/lib/nutritionLabel";
import { readLabelText } from "@/lib/ocr";

type NutrientKey = keyof Per100g;

// CONTRIB-3: the four fields needed to score are required; the rest are optional.
const FIELDS: { key: NutrientKey; label: string; unit: string; required: boolean }[] = [
  { key: "energy_kj", label: "Energy", unit: "kJ", required: true },
  { key: "sugars_g", label: "Sugars", unit: "g", required: true },
  { key: "saturated_fat_g", label: "Saturated fat", unit: "g", required: true },
  { key: "salt_g", label: "Salt", unit: "g", required: true },
  { key: "fat_g", label: "Total fat", unit: "g", required: false },
  { key: "fiber_g", label: "Fibre", unit: "g", required: false },
  { key: "proteins_g", label: "Protein", unit: "g", required: false },
];

const KINDS = [
  { value: "food", label: "Food" },
  { value: "drink", label: "Drink" },
  { value: "cheese", label: "Cheese" },
  { value: "fat_oil_nut_seed", label: "Fat, oil, nut or seed" },
];

type Status = { kind: "idle" | "reading" | "saving" } | { kind: "error"; message: string };

export function ContributionForm({
  gtin,
  readText = readLabelText,
  fetcher = fetch,
}: {
  gtin: string;
  readText?: (file: Blob) => Promise<string>;
  fetcher?: typeof fetch;
}) {
  const router = useRouter();
  const id = useId();
  const [name, setName] = useState("");
  const [brand, setBrand] = useState("");
  const [kind, setKind] = useState("food");
  const [ingredients, setIngredients] = useState("");
  const [values, setValues] = useState<Record<NutrientKey, string>>(
    Object.fromEntries(FIELDS.map((f) => [f.key, ""])) as Record<NutrientKey, string>,
  );
  const [canShare, setCanShare] = useState(false);
  const [share, setShare] = useState(false);
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [readNote, setReadNote] = useState("");

  useEffect(() => {
    fetcher("/api/contributions/config")
      .then((r) => r.json())
      .then((c: { can_share_with_off?: boolean }) => setCanShare(Boolean(c.can_share_with_off)))
      .catch(() => setCanShare(false)); // CONTRIB-9
  }, [fetcher]);

  async function onPhoto(file: File | undefined) {
    if (!file) return;
    setStatus({ kind: "reading" });
    try {
      const { per100g } = parseLabel(await readText(file)); // CONTRIB-1, CONTRIB-2
      const found = FIELDS.filter((f) => per100g[f.key] !== undefined);
      setValues((v) => ({
        ...v,
        ...Object.fromEntries(found.map((f) => [f.key, String(per100g[f.key])])),
      }));
      setReadNote(
        found.length
          ? `Read ${found.length} of ${FIELDS.length} values. Check each one against the label.`
          : "We couldn't read the values. Type them in from the label.",
      );
      setStatus({ kind: "idle" });
    } catch {
      setStatus({ kind: "error", message: "We couldn't read that photo. Type the values in." });
    }
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setStatus({ kind: "saving" });
    const nutrition = Object.fromEntries(
      FIELDS.filter((f) => values[f.key] !== "").map((f) => [f.key, Number(values[f.key])]),
    );
    const body = {
      gtin, name, kind, nutrition, share_with_off: canShare && share,
      ...(brand ? { brand } : {}),
      ...(ingredients ? { ingredients_text: ingredients } : {}),
    };
    try {
      const res = await fetcher("/api/contributions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.status === 201) return router.push(`/p/${gtin}`);
      const problem = (await res.json().catch(() => ({}))) as { detail?: string };
      const message =
        res.status === 409
          ? "Someone has already added this product."
          : res.status === 429
            ? "Too many products added from here. Try again in an hour."
            : (problem.detail ?? "We couldn't save it. Try again.");
      setStatus({ kind: "error", message });
    } catch {
      setStatus({ kind: "error", message: "We couldn't save it. Check your connection." });
    }
  }

  const input = "rounded-lg border border-zinc-400 bg-white px-3 py-2 text-base text-zinc-900";
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5">
      <section className="flex flex-col gap-2">
        <label htmlFor={`${id}-photo`} className="font-medium">
          Photo of the Nutrition Facts panel
        </label>
        <input
          id={`${id}-photo`}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={(e) => onPhoto(e.target.files?.[0])}
        />
        <p className="text-sm text-zinc-600">The photo is read on your phone and never uploaded.</p>
        <p role="status" className="text-sm">
          {status.kind === "reading" ? "Reading the label…" : readNote}
        </p>
      </section>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 font-medium">About the product</legend>
        <label className="flex flex-col gap-1 text-sm">
          Product name
          <input required value={name} onChange={(e) => setName(e.target.value)} className={input} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Brand (optional)
          <input value={brand} onChange={(e) => setBrand(e.target.value)} className={input} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          What is it?
          <select value={kind} onChange={(e) => setKind(e.target.value)} className={input}>
            {KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Ingredients (optional)
          <textarea
            value={ingredients}
            onChange={(e) => setIngredients(e.target.value)}
            rows={3}
            className={input}
          />
        </label>
      </fieldset>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 font-medium">Per 100 g (or 100 ml)</legend>
        {FIELDS.map((f) => (
          <label key={f.key} className="flex items-center justify-between gap-3 text-sm">
            <span>
              {f.label} ({f.unit}){f.required ? "" : ", optional"}
            </span>
            <input
              type="number"
              inputMode="decimal"
              step="any"
              min="0"
              required={f.required}
              value={values[f.key]}
              onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
              className={`${input} w-28`}
            />
          </label>
        ))}
      </fieldset>

      {canShare && (
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} />
          Also add it to Open Food Facts (ODbL), so others can find it too.
        </label>
      )}

      {status.kind === "error" && (
        <p role="alert" className="text-sm text-rose-800">
          {status.message}
        </p>
      )}
      <button
        type="submit"
        disabled={status.kind === "saving" || status.kind === "reading"}
        className="self-start rounded-lg bg-zinc-900 px-4 py-2 font-medium text-white hover:bg-zinc-700 disabled:opacity-50"
      >
        {status.kind === "saving" ? "Saving…" : "Save and score"}
      </button>
    </form>
  );
}
