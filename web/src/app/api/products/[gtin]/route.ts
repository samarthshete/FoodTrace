import { apiUrl } from "@/lib/api";

// Product data for the assistant (spec 023, ASSIST-4), proxied so the API stays server-side.
export async function GET(_request: Request, { params }: { params: Promise<{ gtin: string }> }) {
  const { gtin } = await params;
  try {
    const res = await fetch(`${apiUrl()}/products/${encodeURIComponent(gtin)}`, {
      headers: { Accept: "application/json" },
    });
    return new Response(res.body, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
    return Response.json({ detail: "Product data is unavailable." }, { status: 503 });
  }
}
