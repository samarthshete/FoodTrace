import Link from "next/link";

import { LookupPanel } from "@/components/ScanHome";
import { ArrowRightIcon } from "@/components/Icons";

export const metadata = { title: "Lookup" };

const EXAMPLES = [
  { gtin: "0076808008470", label: "Barilla red lentil rotini" },
  { gtin: "0016000275287", label: "Cheerios" },
  { gtin: "0038000138416", label: "Pringles Original" },
];

export default function LookupPage() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 py-10 sm:px-6">
      <header>
        <p className="eyebrow">Lookup</p>
        <h1 className="page-title mt-2">Find any product</h1>
        <p className="mt-2 text-zinc-600">Search by name or brand, or type the number under the barcode.</p>
      </header>
      <div className="card p-6">
        <LookupPanel />
      </div>
      <section aria-labelledby="try-heading">
        <h2 id="try-heading" className="text-sm font-semibold text-zinc-500">
          Try one
        </h2>
        <ul className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((e) => (
            <li key={e.gtin}>
              <Link
                href={`/p/${e.gtin}`}
                className="flex items-center gap-1.5 rounded-full bg-zinc-100 px-3.5 py-1.5 text-sm font-medium text-zinc-800 hover:bg-zinc-200"
              >
                {e.label}
                <ArrowRightIcon className="h-3.5 w-3.5" />
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
