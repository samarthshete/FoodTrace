"use client";

import { useId, useState } from "react";

import { InvalidGTIN, normalize } from "@/lib/gtin";

export const MANUAL_INPUT_ID = "barcode-input";

export function ManualEntry({ onSubmit }: { onSubmit: (gtin: string) => void }) {
  const errorId = useId();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    try {
      onSubmit(normalize(value));
    } catch (e) {
      setError(e instanceof InvalidGTIN ? e.message : "That barcode isn't valid.");
    }
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-2">
      <label htmlFor={MANUAL_INPUT_ID} className="text-sm font-medium text-zinc-800">
        Or type the barcode number
      </label>
      <div className="flex gap-2">
        <input
          id={MANUAL_INPUT_ID}
          inputMode="numeric"
          autoComplete="off"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setError(null);
          }}
          aria-invalid={error !== null}
          aria-describedby={error ? errorId : undefined}
          placeholder="e.g. 036000291452"
          className="field min-w-0 flex-1"
        />
        <button
          type="submit"
          className="btn-primary"
        >
          Look up
        </button>
      </div>
      {error && (
        <p id={errorId} role="alert" className="text-sm text-rose-800">
          {error}
        </p>
      )}
    </form>
  );
}
