import { Suspense } from "react";

import { SignInPrompt } from "@/components/SignInPrompt";
import { safeNext } from "@/lib/next-path";

export const metadata = { title: "Sign in" };

// ?next= is request-time data, so it's read inside Suspense.
export default function SignInPage({ searchParams }: PageProps<"/sign-in">) {
  return (
    <div className="px-4 py-12 sm:px-6">
      <Suspense fallback={<SignInPrompt />}>
        {searchParams.then((p) => (
          <SignInPrompt next={safeNext(typeof p.next === "string" ? p.next : null)} />
        ))}
      </Suspense>
    </div>
  );
}
