import Link from "next/link";
import { Suspense } from "react";

import { ProductCard, ProductCardSkeleton } from "@/components/ProductCard";
import { loadCategory } from "@/lib/explore";

export const metadata = { title: "Explore" };

// Params are request-time data under Cache Components, so they are read inside Suspense.
export default function CategoryPage({ params }: PageProps<"/explore/[category]">) {
  return (
    <Suspense fallback={<Skeleton />}>
      {params.then(({ category }) => (
        <Category id={category} />
      ))}
    </Suspense>
  );
}

async function Category({ id }: { id: string }) {
  const category = await loadCategory(id);
  if (!category) {
    return (
      <div className="card flex flex-col items-start gap-3 p-8">
        <h1 className="text-2xl font-semibold">We don&apos;t have that category</h1>
        <Link href="/explore" className="btn-secondary">
          Back to top foods
        </Link>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <header>
        <p className="eyebrow">Top {category.products.length}</p>
        <h1 className="page-title mt-2">{category.label}</h1>
        <p className="mt-2 text-zinc-600">{category.blurb} Ranked by score, best first.</p>
      </header>
      <ul className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
        {category.products.map((p, i) => (
          <li key={p.gtin} className="flex">
            <ProductCard item={p} rank={i + 1} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function Skeleton() {
  return (
    <div role="status" aria-label="Loading products" className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
      {Array.from({ length: 8 }, (_, i) => (
        <ProductCardSkeleton key={i} />
      ))}
    </div>
  );
}
