import { Assistant } from "@/components/Assistant";

export const metadata = { title: "Assistant" };

export default function AssistantPage() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10 sm:px-6">
      <header className="text-center">
        <p className="eyebrow">Assistant</p>
        <h1 className="page-title mt-2">Ask the assistant</h1>
        <p className="mx-auto mt-2 max-w-xl text-zinc-600">
          Tap the microphone and ask about any product, for example &ldquo;I&apos;m diabetic. Can I eat
          Pringles?&rdquo;
        </p>
      </header>
      <div className="card p-6">
        <Assistant />
      </div>
    </div>
  );
}
