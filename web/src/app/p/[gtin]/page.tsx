import { Suspense } from "react";

import { ProductMessage, ProductView } from "@/components/ProductView";
import { loadAlternatives, loadProduct, loadRecalls } from "@/lib/api";

export const metadata = { title: "Product" };

// Params are request-time data under Cache Components, so they are read inside Suspense.
export default function ProductPage({ params }: PageProps<"/p/[gtin]">) {
  return (
    <>
      <Suspense fallback={<p role="status">Looking up this product…</p>}>
        {params.then(({ gtin }) => (
          <ProductContent gtin={gtin} />
        ))}
      </Suspense>
    </>
  );
}

async function ProductContent({ gtin }: { gtin: string }) {
  const result = await loadProduct(gtin);
  switch (result.kind) {
    case "ok": {
      // The product is stored by now, so these are cache hits; either may fail on its own.
      const [alternatives, recalls] = await Promise.all([
        loadAlternatives(result.product.gtin),
        loadRecalls(result.product.gtin),
      ]);
      return (
        <ProductView
          product={result.product}
          breakdown={result.breakdown}
          alternatives={alternatives}
          recalls={recalls}
        />
      );
    }
    case "not_found":
      return (
        <ProductMessage
          title="We couldn't find this product"
          body={`Barcode ${result.gtin} isn't in Open Food Facts or USDA yet.`}
          action={{ href: `/add/${result.gtin}`, label: "Add it from a label photo" }}
        />
      );
    case "invalid":
      return <ProductMessage title="That barcode isn't valid" body={result.detail} />;
    case "unavailable":
      return (
        <ProductMessage
          title="Try again in a moment"
          body="We couldn't reach the product database. Check your connection and try again."
        />
      );
  }
}
