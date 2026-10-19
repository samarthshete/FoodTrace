import { ScanPanel } from "@/components/ScanHome";
import { CheckIcon } from "@/components/Icons";

export const metadata = { title: "Scan" };

const TIPS = [
  "Hold the barcode flat, about a hand's width from the camera.",
  "Good light helps. Turn on a lamp rather than the flash.",
  "Works with UPC-A, UPC-E, EAN-8 and EAN-13 codes.",
  "Nothing leaves your phone: the barcode is read in the browser.",
];

export default function ScanPage() {
  return (
    <div className="mx-auto grid w-full max-w-5xl grid-cols-[minmax(0,1fr)] gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section className="flex flex-col gap-6">
        <header>
          <p className="eyebrow">Scan</p>
          <h1 className="page-title mt-2">Scan a barcode</h1>
          <p className="mt-2 text-zinc-600">Point your camera at any US grocery barcode to see its score.</p>
        </header>
        <div className="card p-6">
          <ScanPanel />
        </div>
      </section>
      <aside className="card h-fit p-6">
        <h2 className="font-semibold">Tips for a quick scan</h2>
        <ul className="mt-4 flex flex-col gap-3 text-sm text-zinc-700">
          {TIPS.map((t) => (
            <li key={t} className="flex gap-3">
              <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
              {t}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
