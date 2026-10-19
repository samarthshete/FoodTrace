// Client-side search through the web app's /api/search route (spec 016).

export interface SearchResult {
  gtin: string;
  name: string | null;
  brand: string | null;
  image_url: string | null;
  total: number | null;
  band: { id: string; label: string } | null;
}

export type SearchOutcome =
  | { kind: "ok"; results: SearchResult[]; gtin: string | null }
  | { kind: "error" };

export async function searchProducts(
  q: string,
  fetcher: typeof fetch = fetch,
): Promise<SearchOutcome> {
  try {
    const res = await fetcher(`/api/search?q=${encodeURIComponent(q)}`);
    if (!res.ok) return { kind: "error" };
    const body = (await res.json()) as { results: SearchResult[]; gtin: string | null };
    return { kind: "ok", results: body.results, gtin: body.gtin };
  } catch {
    return { kind: "error" };
  }
}
