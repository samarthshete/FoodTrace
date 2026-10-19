import { apiToken, fetchAsUser } from "@/lib/session";

// Forwards the browser's /api/me/... calls to the API's /me/... with the user's token, so
// the token never reaches client code (spec 018, ACC-3).
async function forward(request: Request, { params }: { params: Promise<{ path?: string[] }> }) {
  const token = await apiToken(request.headers);
  if (!token) return Response.json({ detail: "Sign in to use your account." }, { status: 401 });
  const { path = [] } = await params;
  const search = new URL(request.url).search;
  const hasBody = request.method === "POST" || request.method === "PUT";
  try {
    const res = await fetchAsUser(`/me${path.map((p) => `/${encodeURIComponent(p)}`).join("")}${search}`, token, {
      method: request.method,
      headers: hasBody ? { "Content-Type": "application/json" } : {},
      body: hasBody ? await request.text() : undefined,
    });
    return new Response(res.status === 204 ? null : res.body, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
    });
  } catch {
    return Response.json({ detail: "Your account isn't available right now." }, { status: 503 });
  }
}

export { forward as GET, forward as POST, forward as PUT, forward as DELETE };
