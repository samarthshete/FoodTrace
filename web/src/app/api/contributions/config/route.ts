import { apiUrl } from "@/lib/api";

export async function GET() {
  try {
    const res = await fetch(`${apiUrl()}/contributions/config`);
    return Response.json(res.ok ? await res.json() : { can_share_with_off: false });
  } catch {
    return Response.json({ can_share_with_off: false });
  }
}
