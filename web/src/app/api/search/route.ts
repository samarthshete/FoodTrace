import { apiUrl } from "@/lib/api";

const SUGGESTIONS = 8; // SEARCH-7

// Proxies search to the API so its address stays server-side (SEARCH-7).
export async function GET(request: Request) {
  const q = new URL(request.url).searchParams.get("q") ?? "";
  const url = `${apiUrl()}/search?q=${encodeURIComponent(q)}&limit=${SUGGESTIONS}`;
  try {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    return new Response(res.body, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("Content-Type") ?? "application/json",
        "Cache-Control": res.headers.get("Cache-Control") ?? "no-store",
      },
    });
  } catch {
    return Response.json({ detail: "Search is unavailable." }, { status: 503 });
  }
}
