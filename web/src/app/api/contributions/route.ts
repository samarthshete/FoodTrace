import { apiUrl } from "@/lib/api";

// Proxies a confirmed contribution to the API (spec 017), passing on the client address for
// the per-client rate limit (CONTRIB-8).
export async function POST(request: Request) {
  const forwarded = request.headers.get("x-forwarded-for");
  try {
    const res = await fetch(`${apiUrl()}/contributions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(forwarded ? { "X-Forwarded-For": forwarded } : {}),
      },
      body: await request.text(),
    });
    return new Response(res.body, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
    return Response.json({ detail: "We couldn't save it right now." }, { status: 503 });
  }
}
