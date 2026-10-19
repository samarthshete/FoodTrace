import type { Recalls } from "@/lib/api";
import { formatDate } from "@/lib/present";

// openFDA recall banner (spec 010). Says a recall is on record, never that the product is
// recalled: openFDA isn't a live feed and a brand-and-name match can't be certain.
export function RecallBanner({ data }: { data: Recalls | null | undefined }) {
  if (!data || data.as_of === null || data.recalls.length === 0) return null; // RECALL-14
  const [first, ...rest] = data.recalls;
  const byCode = first.match === "code";
  return (
    <section
      role="status"
      aria-labelledby="recall-heading"
      className="rounded-xl border-2 border-amber-700 bg-amber-50 p-4 text-sm text-amber-950"
    >
      <h2 id="recall-heading" className="flex items-start gap-2 text-base font-semibold">
        <span aria-hidden="true">⚠</span>
        {byCode ? "An FDA recall on record lists this barcode" : "A related FDA recall is on record"}
      </h2>
      <div className="mt-2 flex flex-col gap-1">
        {first.reason_for_recall && <p>Reason given by the FDA: {first.reason_for_recall}</p>}
        {first.recall_initiation_date && (
          <p>Recall started {formatDate(first.recall_initiation_date)}.</p>
        )}
        {!byCode && <p>This may be a different product from the same brand.</p>}
        {rest.length > 0 && <p>And {rest.length} more on record.</p>}
        <p>
          <a className="font-medium underline" href={first.url}>
            View the FDA record
          </a>
        </p>
        <p className="text-xs text-amber-900">FDA data as of {formatDate(data.as_of)}.</p>
      </div>
    </section>
  );
}
