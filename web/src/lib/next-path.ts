/** ACC-19: only a path on this site, so ?next= can't send people elsewhere. */
export function safeNext(next: string | null | undefined): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : "/account";
}
