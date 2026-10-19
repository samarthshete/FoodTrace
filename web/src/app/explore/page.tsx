import Link from "next/link";
import { Suspense } from "react";

import { ArrowRightIcon } from "@/components/Icons";
import { ProductCard, ProductCardSkeleton } from "@/components/ProductCard";
import { loadExplore } from "@/lib/explore";

export const metadata = { title: "Explore" };

export default function ExplorePage() {
  return (
    <div className="flex flex-col gap-10">
      <header>
        <p className="eyebrow">Explore</p>
        <h1 className="page-title mt-2">Top foods in every aisle</h1>
        <p className="mt-2 max-w-2xl text-zinc-600">
          The best-scored products we know of in each category, ranked by our 0–100 score. Open any one to see
          every rule behind its number.
        </p>
      </header>
      <Suspense fallback={<Skeleton />}>
        <Sections />
      </Suspense>
    </div>
  );
}

async function Sections() {
  const categories = await loadExplore(4);
  if (!categories) {
    return (
      <p role="status" className="card p-6 text-zinc-700">
        Top foods are unavailable right now. Try again in a moment.
      </p>
    );
  }
  return (
    <>
      {categories
        .filter((c) => c.products.length > 0)
        .map((c) => (
          <section key={c.id} aria-labelledby={`cat-${c.id}`} className="flex flex-col gap-4">
            <div className="flex items-end justify-between gap-4">
              <div>
                <h2 id={`cat-${c.id}`} className="text-xl font-semibold tracking-tight">
                  {c.label}
                </h2>
                <p className="text-sm text-zinc-600">{c.blurb}</p>
              </div>
              <Link
                href={`/explore/${c.id}`}
                className="flex shrink-0 items-center gap-1 text-sm font-medium text-emerald-700 hover:text-emerald-800"
              >
                See all <span className="sr-only">{c.label}</span>
                <ArrowRightIcon className="h-4 w-4" />
              </Link>
            </div>
            <ul className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {c.products.map((p, i) => (
                <li key={p.gtin} className="flex">
                  <ProductCard item={p} rank={i + 1} />
                </li>
              ))}
            </ul>
          </section>
        ))}
    </>
  );
}

function Skeleton() {
  return (
    <div role="status" aria-label="Loading top foods" className="flex flex-col gap-10">
      {[0, 1].map((s) => (
        <div key={s} className="flex flex-col gap-4">
          <div className="h-6 w-48 animate-pulse rounded bg-zinc-100" />
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <ProductCardSkeleton key={i} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
