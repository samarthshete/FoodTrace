// Typed client for the FastAPI backend (specs 006, 009, 010). Server-side only: it reads API_URL.

export type Component = "nutrition" | "additives" | "processing";

export interface BreakdownLine {
  rule_id: string;
  component: Component;
  points: number;
  input_value: unknown;
  source_url: string;
  estimated: boolean;
  note?: string;
}

export interface Score {
  engine_version: string;
  status: "scored" | "not_scored";
  total: number | null;
  band: { id: string; label: string } | null;
  confidence: number;
  missing_inputs: string[];
  nutriscore: { class: string; score: number | null; grade: string | null };
  components: Record<Component, { weight: number; value: number | null; known: boolean }>;
  breakdown?: BreakdownLine[];
}

export interface ProductAdditive {
  code: string;
  name: string;
  us_status: string | null;
  fda_cfr_ref: string | null;
}

export interface Product {
  gtin: string;
  name: string | null;
  brand: string | null;
  image_url: string | null;
  ingredients_text: string | null;
  nova_group: number | null;
  is_organic: boolean;
  stale: boolean;
  score: Score;
  attribution: string;
  additives?: ProductAdditive[];
  source_by_field?: Record<string, string>;
  allergens?: string[];
  traces?: string[];
  ingredients_analysis?: string[];
  allergens_known?: boolean;
}

export interface Breakdown {
  gtin: string;
  score: Score & { breakdown: BreakdownLine[] };
  explanation: string[];
}

export interface Alternative {
  gtin: string;
  name: string | null;
  brand: string | null;
  image_url: string | null;
  total: number;
  band: { id: string; label: string } | null;
  confidence: number;
}

export interface Alternatives {
  gtin: string;
  category: string | null;
  alternatives: Alternative[];
}

export interface Recall {
  recall_number: string;
  match: "code" | "brand_name";
  classification: string | null;
  status: string | null;
  reason_for_recall: string | null;
  recall_initiation_date: string | null;
  product_description: string;
  url: string;
}

export interface Recalls {
  gtin: string;
  recalls: Recall[];
  as_of: string | null;
}

export type ProductResult =
  | { kind: "ok"; product: Product; breakdown: Breakdown }
  | { kind: "not_found"; gtin: string }
  | { kind: "invalid"; detail: string }
  | { kind: "unavailable" };

export function apiUrl(): string {
  return process.env.API_URL ?? "http://localhost:8000";
}

async function getJson(path: string, fetcher: typeof fetch): Promise<Response> {
  return fetcher(`${apiUrl()}${path}`, { headers: { Accept: "application/json" } });
}

/**
 * Product first, then breakdown. Sequential on purpose: the first call may fetch from
 * Open Food Facts and store the product; the second is then a cache hit.
 */
export async function loadProduct(
  gtin: string,
  fetcher: typeof fetch = fetch,
): Promise<ProductResult> {
  const path = `/products/${encodeURIComponent(gtin)}`;
  let res: Response;
  try {
    res = await getJson(path, fetcher);
  } catch {
    return { kind: "unavailable" };
  }
  if (res.status === 404) return { kind: "not_found", gtin };
  if (res.status === 422) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    return { kind: "invalid", detail: body.detail ?? "That barcode isn't valid." };
  }
  if (!res.ok) return { kind: "unavailable" };
  const product = (await res.json()) as Product;

  try {
    const bres = await getJson(`${path}/breakdown`, fetcher);
    if (!bres.ok) return { kind: "unavailable" };
    return { kind: "ok", product, breakdown: (await bres.json()) as Breakdown };
  } catch {
    return { kind: "unavailable" };
  }
}

/** Extras on the product page: any failure gives null, so the page still renders. */
async function optionalJson<T>(path: string, fetcher: typeof fetch): Promise<T | null> {
  try {
    const res = await getJson(path, fetcher);
    return res.ok ? ((await res.json()) as T) : null;
  } catch {
    return null;
  }
}

export function loadAlternatives(gtin: string, fetcher: typeof fetch = fetch) {
  return optionalJson<Alternatives>(`/products/${encodeURIComponent(gtin)}/alternatives`, fetcher);
}

export function loadRecalls(gtin: string, fetcher: typeof fetch = fetch) {
  return optionalJson<Recalls>(`/products/${encodeURIComponent(gtin)}/recalls`, fetcher);
}

export interface Methodology {
  engine_version: string;
  weights: Record<Component, number>;
  bands: { id: string; label: string; min: number }[];
  nova_values: Record<string, number>;
  additives: {
    risk_penalty: Record<string, number>;
    evidence_weight: Record<string, number>;
    cap_total: number;
  };
  sources: Record<"nutriscore_foods" | "nutriscore_beverages" | "efsa" | "nova", string>;
  changelog: { version: string; change: string }[];
}

export function loadMethodology(fetcher: typeof fetch = fetch) {
  return optionalJson<Methodology>("/methodology", fetcher);
}
