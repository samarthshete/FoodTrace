"use client";

import { useId, useState, useSyncExternalStore } from "react";

import { signInWithEmail, signInWithGoogle, signUpWithEmail } from "@/lib/auth-client";

const noSubscribe = () => () => {};

/** ACC-19: sign in or create an account with an email and password, or use Google. */
export function SignInForm({ next = "/account", onDone }: { next?: string; onDone?: (next: string) => void }) {
  const ids = { name: useId(), email: useId(), password: useId(), error: useId() };
  const [mode, setMode] = useState<"in" | "up">("in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Until React has loaded, a click would submit the form as a plain page reload and lose it.
  const ready = useSyncExternalStore(noSubscribe, () => true, () => false);
  const done = onDone ?? ((to: string) => window.location.assign(to)); // full load: header and session refresh

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const problem =
      mode === "in" ? await signInWithEmail(email.trim(), password) : await signUpWithEmail(name.trim(), email.trim(), password);
    setBusy(false);
    if (problem) setError(problem);
    else done(next);
  }

  return (
    <div className="flex flex-col gap-5">
      <div role="tablist" aria-label="Account" className="grid grid-cols-2 rounded-xl bg-zinc-100 p-1 text-sm font-medium">
        {(["in", "up"] as const).map((m) => (
          <button
            key={m}
            type="button"
            role="tab"
            aria-selected={mode === m}
            onClick={() => {
              setMode(m);
              setError(null);
            }}
            className={`rounded-lg py-2 ${mode === m ? "bg-white text-zinc-900 shadow-sm ring-1 ring-zinc-200" : "text-zinc-600"}`}
          >
            {m === "in" ? "Sign in" : "Create account"}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="flex flex-col gap-4" aria-describedby={error ? ids.error : undefined}>
        {mode === "up" && (
          <div className="flex flex-col gap-1.5">
            <label htmlFor={ids.name} className="text-sm font-medium text-zinc-800">
              Name
            </label>
            <input id={ids.name} required autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} className="field" />
          </div>
        )}
        <div className="flex flex-col gap-1.5">
          <label htmlFor={ids.email} className="text-sm font-medium text-zinc-800">
            Email
          </label>
          <input
            id={ids.email}
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="field"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor={ids.password} className="text-sm font-medium text-zinc-800">
            Password
          </label>
          <input
            id={ids.password}
            type="password"
            required
            minLength={8}
            autoComplete={mode === "in" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="field"
          />
          {mode === "up" && <p className="text-xs text-zinc-600">At least 8 characters.</p>}
        </div>
        {error && (
          <p id={ids.error} role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-900">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy || !ready} className="btn-primary disabled:opacity-50">
          {busy ? "One moment…" : mode === "in" ? "Sign in" : "Create account"}
        </button>
      </form>
      <div className="flex items-center gap-3 text-xs text-zinc-500">
        <span className="h-px flex-1 bg-zinc-200" />
        or
        <span className="h-px flex-1 bg-zinc-200" />
      </div>
      <button type="button" onClick={() => signInWithGoogle(next)} className="btn-secondary">
        Sign in with Google
      </button>
    </div>
  );
}
