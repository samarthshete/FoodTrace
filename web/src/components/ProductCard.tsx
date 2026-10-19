import Link from "next/link";

import type { ExploreItem } from "@/lib/explore";

const SCORE_STYLES: Record<string, string> = {
  excellent: "bg-emerald-700 text-white",
  good: "bg-lime-700 text-white",
  mediocre: "bg-amber-500 text-zinc-950",
  poor: "bg-rose-600 text-white",
};
const NUTRI_STYLES: Record<string, string> = {
  a: "bg-emerald-700 text-white",
  b: "bg-lime-700 text-white",
  c: "bg-amber-400 text-zinc-950",
  d: "bg-orange-500 text-zinc-950",
  e: "bg-rose-600 text-white",
};

export function ProductCard({ item, rank }: { item: ExploreItem; rank?: number }) {
  return (
    <Link
      href={`/p/${item.gtin}`}
      className="group card flex w-full flex-col overflow-hidden transition hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-2 focus-visible:outline-emerald-600"
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-zinc-50">
        {item.image_url ? (
          // Open Food Facts photos; next/image would need a remote allowlist.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={item.image_url}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            className="absolute inset-0 h-full w-full object-contain p-4 transition group-hover:scale-[1.03]"
          />
        ) : (
          <div aria-hidden="true" className="grid h-full place-items-center text-3xl text-zinc-300">
            ◎
          </div>
        )}
        {rank !== undefined && (
          <span className="absolute top-3 left-3 rounded-full bg-white/90 px-2 py-0.5 text-xs font-semibold text-zinc-700 ring-1 ring-zinc-200">
            #{rank}
          </span>
        )}
        <span
          className={`absolute top-3 right-3 rounded-full px-2.5 py-1 text-sm font-semibold tabular-nums shadow-sm ${
            SCORE_STYLES[item.band.id] ?? "bg-zinc-700 text-white"
          }`}
        >
          {item.total}
          <span className="sr-only"> out of 100</span>
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2 border-t border-zinc-100 p-4">
        <div className="min-w-0">
          {item.brand && <p className="truncate text-xs font-medium text-zinc-500">{item.brand}</p>}
          <p className="line-clamp-2 font-medium text-zinc-900">{item.name}</p>
        </div>
        <div className="mt-auto flex flex-wrap items-center gap-1.5 text-xs">
          <span className="rounded-full bg-zinc-100 px-2 py-0.5 font-medium text-zinc-700">{item.band.label}</span>
          {item.nutriscore_grade && (
            <span
              className={`rounded-full px-2 py-0.5 font-semibold ${NUTRI_STYLES[item.nutriscore_grade] ?? "bg-zinc-200"}`}
            >
              Nutri-Score {item.nutriscore_grade.toUpperCase()}
            </span>
          )}
          {item.nova_group && (
            <span className="rounded-full bg-zinc-100 px-2 py-0.5 font-medium text-zinc-700">NOVA {item.nova_group}</span>
          )}
        </div>
      </div>
    </Link>
  );
}

export function ProductCardSkeleton() {
  return (
    <div aria-hidden="true" className="card overflow-hidden">
      <div className="aspect-[4/3] animate-pulse bg-zinc-100" />
      <div className="flex flex-col gap-2 p-4">
        <div className="h-3 w-1/3 animate-pulse rounded bg-zinc-100" />
        <div className="h-4 w-3/4 animate-pulse rounded bg-zinc-100" />
      </div>
    </div>
  );
}
