"use client";

import { createAuthClient } from "better-auth/react";

export const authClient = createAuthClient();
export const { useSession, signOut } = authClient;

export function signInWithGoogle(callbackURL = "/account") {
  return authClient.signIn.social({ provider: "google", callbackURL });
}

/** ACC-19: an error message for the form, or null on success. */
export async function signInWithEmail(email: string, password: string): Promise<string | null> {
  const { error } = await authClient.signIn.email({ email, password });
  return error ? "That email and password don't match." : null;
}

export async function signUpWithEmail(name: string, email: string, password: string): Promise<string | null> {
  const { error } = await authClient.signUp.email({ name, email, password });
  if (!error) return null;
  if (error.status === 422 || /exist/i.test(error.message ?? "")) return "There's already an account with that email. Sign in instead.";
  return error.message || "Couldn't create the account. Try again.";
}
