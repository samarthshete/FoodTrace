import { Suspense } from "react";

import { ContributionForm } from "@/components/ContributionForm";

export const metadata = { title: "Add a product" };

export default function AddProductPage({ params }: PageProps<"/add/[gtin]">) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Add this product</h1>
      <p className="text-zinc-700">
        Photograph the Nutrition Facts panel, then check every value against the label before
        saving.
      </p>
      <Suspense fallback={<p role="status">Loading…</p>}>
        {params.then(({ gtin }) => (
          <ContributionForm gtin={gtin} />
        ))}
      </Suspense>
    </div>
  );
}
