"use client";

import { useRouter } from "next/navigation";

import { ManualEntry } from "./ManualEntry";
import { Scanner } from "./Scanner";
import { SearchBox } from "./SearchBox";

function useGo() {
  const router = useRouter();
  return (gtin: string) => router.push(`/p/${gtin}`);
}

/** Scan tab: the camera, with typing as the fallback. */
export function ScanPanel() {
  const go = useGo();
  return (
    <div className="flex flex-col gap-6">
      <Scanner onDetected={go} />
      <div className="border-t border-zinc-100 pt-6">
        <ManualEntry onSubmit={go} />
      </div>
    </div>
  );
}

/** Lookup tab and the landing page: search by name, or type a barcode. */
export function LookupPanel() {
  const go = useGo();
  return (
    <div className="flex flex-col gap-6">
      <SearchBox onSelect={go} />
      <ManualEntry onSubmit={go} />
    </div>
  );
}

export function ScanHome() {
  const go = useGo();
  return (
    <div className="flex flex-col gap-6">
      <Scanner onDetected={go} />
      <ManualEntry onSubmit={go} />
      <SearchBox onSelect={go} />
    </div>
  );
}
