import Link from "next/link";

import type { Alternatives } from "@/lib/api";
import { bandStyle, categoryWords } from "@/lib/present";

// Better-scored products from the same category (spec 009). Hidden when there are none.
export function AlternativesStrip({ data }: { data: Alternatives | null | undefined }) {
  if (!data || data.alternatives.length === 0) return null; // ALT-11
  return (
    <section aria-labelledby="alternatives-heading" className="card p-6">
      <h2 id="alternatives-heading" className="text-base font-semibold">
        Better-scored alternatives
      </h2>
      {data.category && <p className="text-sm text-zinc-600">{categoryWords(data.category)}</p>}
      <ul className="mt-3 flex snap-x gap-3 overflow-x-auto pb-2">
        {data.alternatives.map((alt) => (
          <li key={alt.gtin} className="w-40 shrink-0 snap-start">
            <Link
              href={`/p/${alt.gtin}`}
              className="flex h-full flex-col gap-2 rounded-xl bg-white p-3 ring-1 ring-zinc-200 transition hover:-translate-y-0.5 hover:shadow-md"
            >
              {alt.image_url ? (
                // Product photos come from Open Food Facts; next/image would need a remote allowlist.
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={alt.image_url}
                  alt=""
                  className="h-20 w-full rounded-lg bg-zinc-50 object-contain p-1"
                />
              ) : (
                <div className="h-20 w-full rounded-lg bg-zinc-100" aria-hidden="true" />
              )}
              <span className="line-clamp-2 font-medium">{alt.name ?? "Unnamed product"}</span>
              {alt.brand && <span className="text-sm text-zinc-700">{alt.brand}</span>}
              <span
                className={`mt-auto self-start rounded-full px-2 py-0.5 text-sm font-medium ring-1 ${bandStyle(alt.band?.id)}`}
              >
                {alt.total} / 100{alt.band && ` · ${alt.band.label}`}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
