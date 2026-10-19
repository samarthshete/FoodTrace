// A per-client, per-minute limit for the assistant's Groq routes (spec 023). In memory: one
// process, reset on restart. Enough to protect the free tier from a stuck client.
export function createLimiter(perMinute: number) {
  const recent = new Map<string, number[]>();
  return function limited(client: string, now: number = Date.now()): boolean {
    const times = (recent.get(client) ?? []).filter((t) => now - t < 60_000);
    if (times.length >= perMinute) return true;
    times.push(now);
    recent.set(client, times);
    if (recent.size > 5_000) recent.clear(); // bounded memory
    return false;
  };
}

export function clientOf(request: Request): string {
  return request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "local";
}
