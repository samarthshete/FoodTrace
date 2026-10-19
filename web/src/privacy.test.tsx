import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PrivacyPage from "./app/privacy/page";

const TRACKERS = /googletagmanager|google-analytics|gtag\(|segment\.(io|com)|mixpanel|hotjar|plausible|posthog|facebook\.net|fbq\(/i;

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : /\.(tsx?|mjs)$/.test(name) ? [path] : [];
  });
}

describe("[ACC-15] no analytics or tracking", () => {
  it("no source file loads a tracker", () => {
    const self = join(import.meta.dirname, "privacy.test.tsx");
    const offenders = files(import.meta.dirname).filter((f) => f !== self && TRACKERS.test(readFileSync(f, "utf8")));
    expect(offenders).toEqual([]);
  });
});

describe("[ACC-16] privacy page", () => {
  it("lists what is stored and how to delete it", () => {
    render(<PrivacyPage />);
    expect(screen.getByRole("heading", { name: "If you sign in" })).toBeInTheDocument();
    expect(screen.getByText(/only a salted hash of your password/)).toBeInTheDocument();
    expect(screen.getByText(/never keep your Google tokens/)).toBeInTheDocument();
    expect(screen.getByText(/Newest 1,000 only/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "your account page" })).toHaveAttribute("href", "/account");
  });
});
