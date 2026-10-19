import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { UserMenu } from "./UserMenu";

const mocks = vi.hoisted(() => ({
  session: null as null | { user: { name: string; image: string | null } },
  signIn: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock("@/lib/auth-client", () => ({
  useSession: () => ({ data: mocks.session, isPending: false }),
  signInWithGoogle: mocks.signIn,
  signOut: mocks.signOut,
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/p/0036000291452" }));

describe("[ACC-4] [ACC-20] header account menu", () => {
  it("links to Sign in when signed out, returning to the current page", () => {
    mocks.session = null;
    render(<UserMenu />);
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/sign-in?next=%2Fp%2F0036000291452");
  });

  it("shows the account link and signs out when signed in", () => {
    mocks.session = { user: { name: "Alice", image: null } };
    render(<UserMenu />);
    expect(screen.getByRole("link", { name: "Account" })).toHaveAttribute("href", "/account");
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(mocks.signOut).toHaveBeenCalled();
  });
});
