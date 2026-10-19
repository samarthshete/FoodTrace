"use client";

import { useEffect, useId, useRef, useState } from "react";

import { bandStyle } from "@/lib/present";
import { type SearchOutcome, type SearchResult, searchProducts } from "@/lib/search";

const DEBOUNCE_MS = 250; // SEARCH-7
const MIN_CHARS = 2;

type Status = "idle" | "loading" | "done" | "error";

// Search by name or brand, following the ARIA combobox pattern (spec 016, SEARCH-8).
export function SearchBox({
  onSelect,
  search = searchProducts,
}: {
  onSelect: (gtin: string) => void;
  search?: (q: string) => Promise<SearchOutcome>;
}) {
  const inputId = useId();
  const listId = useId();
  const [value, setValue] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [gtin, setGtin] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const latest = useRef(0);

  useEffect(() => {
    const q = value.trim();
    const request = ++latest.current; // also cancels any pending response
    if (q.length < MIN_CHARS) return;
    const timer = setTimeout(async () => {
      setStatus("loading");
      const outcome = await search(q);
      if (request !== latest.current) return; // SEARCH-10: a newer query superseded this one
      if (outcome.kind === "error") {
        setResults([]);
        setGtin(null);
        setStatus("error");
      } else {
        setResults(outcome.results);
        setGtin(outcome.gtin);
        setStatus("done");
      }
      setActive(-1);
      setOpen(true);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [value, search]);

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    const tooShortNow = value.trim().length < MIN_CHARS;
    const list = tooShortNow ? [] : results;
    if (event.key === "ArrowDown" && list.length) {
      event.preventDefault();
      setOpen(true);
      setActive((i) => (i + 1) % list.length);
    } else if (event.key === "ArrowUp" && list.length) {
      event.preventDefault();
      setActive((i) => (i <= 0 ? list.length - 1 : i - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (open && active >= 0 && list[active]) onSelect(list[active].gtin);
      else if (!tooShortNow && gtin) onSelect(gtin); // SEARCH-9: a typed barcode
    } else if (event.key === "Escape") {
      setOpen(false);
      setActive(-1);
    }
  }

  // Below the minimum, show nothing; derived here rather than reset inside the effect.
  const tooShort = value.trim().length < MIN_CHARS;
  const shown = tooShort ? [] : results;
  const typedGtin = tooShort ? null : gtin;
  const state: Status = tooShort ? "idle" : status;
  const expanded = open && shown.length > 0;
  const announcement =
    state === "error"
      ? "Search isn't available right now."
      : state === "done" && !typedGtin
        ? shown.length
          ? `${shown.length} ${shown.length === 1 ? "product" : "products"} found.`
          : "No products match."
        : "";

  return (
    <div className="relative flex flex-col gap-2">
      <label htmlFor={inputId} className="text-sm font-medium text-zinc-800">
        Search by name or brand
      </label>
      <input
        id={inputId}
        type="search"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={expanded}
        aria-controls={listId}
        aria-activedescendant={expanded && active >= 0 ? `${listId}-${active}` : undefined}
        autoComplete="off"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onFocus={() => results.length && setOpen(true)}
        placeholder="e.g. cheerios, oat milk"
        className="field"
      />
      <p role="status" className="min-h-5 text-sm text-zinc-600">
        {announcement}
      </p>
      <ul
        id={listId}
        role="listbox"
        aria-label="Search results"
        hidden={!expanded}
        className="absolute top-[5.25rem] z-20 w-full overflow-hidden rounded-xl bg-white shadow-xl ring-1 ring-zinc-200"
      >
        {shown.map((r, i) => (
          <li
            key={r.gtin}
            id={`${listId}-${i}`}
            role="option"
            aria-selected={i === active}
            onMouseDown={(e) => {
              e.preventDefault(); // keep focus so the click lands before blur closes the list
              onSelect(r.gtin);
            }}
            className={`flex cursor-pointer items-center justify-between gap-3 px-3 py-2 ${i === active ? "bg-zinc-100" : ""}`}
          >
            <span className="min-w-0">
              <span className="block truncate font-medium">{r.name ?? "Unnamed product"}</span>
              {r.brand && <span className="block truncate text-sm text-zinc-600">{r.brand}</span>}
            </span>
            {r.total !== null && (
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-sm font-medium ring-1 ${bandStyle(r.band?.id)}`}
              >
                {r.total}
                {r.band && <span className="sr-only"> out of 100, {r.band.label}</span>}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
