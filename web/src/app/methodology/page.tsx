import { Suspense } from "react";

import { MethodologyView } from "@/components/MethodologyView";
import { loadMethodology } from "@/lib/api";

export const metadata = { title: "How the score works" };

export default function MethodologyPage() {
  return (
    <article className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">How the score works</h1>
      <Suspense fallback={<p role="status">Loading…</p>}>
        <Methodology />
      </Suspense>
    </article>
  );
}

async function Methodology() {
  return <MethodologyView m={await loadMethodology()} />;
}
