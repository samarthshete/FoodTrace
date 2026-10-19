import { apiUrl } from "./api";

// Top foods per category (spec 024).
export interface ExploreItem {
  gtin: string;
  name: string;
  brand: string | null;
  image_url: string | null;
  total: number;
  band: { id: string; label: string };
  nutriscore_grade: string | null;
  nova_group: number | null;
}
export interface ExploreCategory {
  id: string;
  label: string;
  blurb: string;
  products: ExploreItem[];
}

async function get<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${apiUrl()}${path}`, { headers: { Accept: "application/json" } });
    return res.ok ? ((await res.json()) as T) : null;
  } catch {
    return null;
  }
}

export async function loadExplore(perCategory = 6): Promise<ExploreCategory[] | null> {
  const body = await get<{ categories: ExploreCategory[] }>(`/explore?per_category=${perCategory}`);
  return body?.categories ?? null;
}

export function loadCategory(id: string, limit = 48): Promise<ExploreCategory | null> {
  return get<ExploreCategory>(`/explore/${encodeURIComponent(id)}?limit=${limit}`);
}

/** The sidebar's list; static so it renders before the data arrives. */
export const CATEGORIES: { id: string; label: string; emoji: string }[] = [
  { id: "breakfast", label: "Breakfast cereals", emoji: "🥣" },
  { id: "yogurts", label: "Yogurts", emoji: "🥛" },
  { id: "breads", label: "Breads", emoji: "🍞" },
  { id: "snacks", label: "Chips & salty snacks", emoji: "🥨" },
  { id: "bars", label: "Snack & protein bars", emoji: "🍫" },
  { id: "sweets", label: "Cookies & sweets", emoji: "🍪" },
  { id: "drinks", label: "Drinks", emoji: "🧃" },
  { id: "cheese", label: "Cheese", emoji: "🧀" },
  { id: "meals", label: "Pasta, soups & meals", emoji: "🍝" },
  { id: "spreads", label: "Spreads & pantry", emoji: "🥜" },
];
