"use client";

import { SignInForm } from "./SignInForm";

// The account page when signed out (ACC-20).
export function SignInPrompt({ next = "/account" }: { next?: string }) {
  return (
    <div className="card mx-auto flex w-full max-w-md flex-col gap-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Your account</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Sign in to keep a scan history, save products, and get warnings for your allergens and diet.
          Everything else works without an account.
        </p>
      </div>
      <SignInForm next={next} />
    </div>
  );
}
