import Link from "next/link";

export const metadata = { title: "Privacy" };

// ACC-16: exactly what is stored, why, and how to delete it.
export default function PrivacyPage() {
  return (
    <article className="flex flex-col gap-4 text-sm leading-6">
      <h1 className="text-2xl font-bold">Privacy</h1>
      <p>You can use the scanner, search and product pages without an account. Then we store nothing about you.</p>
      <h2 className="text-lg font-semibold">If you sign in</h2>
      <ul className="list-disc space-y-1 pl-5">
        <li>Your name and email (and, with Google, your picture), to show who is signed in.</li>
        <li>
          A sign-in session, kept in a secure cookie. With email sign-in we keep only a salted hash of your password,
          never the password itself. With Google we never keep your Google tokens.
        </li>
        <li>Your allergens, diets, and whether history is paused, to tailor product pages.</li>
        <li>Scan history: which products you opened, when, and their score then. Newest 1,000 only.</li>
        <li>Saved products, and the products you added from a label photo.</li>
      </ul>
      <h2 className="text-lg font-semibold">What we don&apos;t do</h2>
      <ul className="list-disc space-y-1 pl-5">
        <li>No analytics, advertising or tracking scripts.</li>
        <li>No label photos are uploaded: they&apos;re read on your device.</li>
        <li>Nobody else&apos;s account can read your data; the database enforces it per user.</li>
      </ul>
      <h2 className="text-lg font-semibold">Deleting your data</h2>
      <p>
        On <Link href="/account" className="underline">your account page</Link> you can remove one scan,
        delete all history, pause history, or delete your account and everything in it in one step.
      </p>
    </article>
  );
}
