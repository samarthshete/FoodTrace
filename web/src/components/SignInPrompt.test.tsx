import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  social: vi.fn(),
  email: vi.fn<(request: unknown) => Promise<{ error: null | { status: number; message: string } }>>(),
  signUp: vi.fn<(request: unknown) => Promise<{ error: null | { status: number; message: string } }>>(),
}));
vi.mock("better-auth/react", () => ({
  createAuthClient: () => ({
    signIn: { social: auth.social, email: auth.email },
    signUp: { email: auth.signUp },
    useSession: vi.fn(),
    signOut: vi.fn(),
  }),
}));

import { SignInForm } from "./SignInForm";
import { SignInPrompt } from "./SignInPrompt";

beforeEach(() => {
  auth.email.mockReset().mockResolvedValue({ error: null });
  auth.signUp.mockReset().mockResolvedValue({ error: null });
});

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

describe("[ACC-1] signing in", () => {
  it("signs in with Google and returns to the account page", () => {
    render(<SignInPrompt />);
    expect(screen.getByText(/Everything else works without an account/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sign in with Google" }));
    expect(auth.social).toHaveBeenCalledWith({ provider: "google", callbackURL: "/account" });
  });
});

describe("[ACC-19] email and password", () => {
  it("signs in and goes to the next page", async () => {
    const onDone = vi.fn();
    render(<SignInForm next="/p/0038000138416" onDone={onDone} />);
    fill("Email", " demo@example.com ");
    fill("Password", "demo-pass-123");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(onDone).toHaveBeenCalledWith("/p/0038000138416"));
    expect(auth.email).toHaveBeenCalledWith({ email: "demo@example.com", password: "demo-pass-123" });
  });

  it("says the details don't match, without saying which", async () => {
    auth.email.mockResolvedValue({ error: { status: 401, message: "Invalid email or password" } });
    const onDone = vi.fn();
    render(<SignInForm onDone={onDone} />);
    fill("Email", "demo@example.com");
    fill("Password", "wrong-password");
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That email and password don't match.");
    expect(onDone).not.toHaveBeenCalled();
  });

  it("creates an account with a name", async () => {
    const onDone = vi.fn();
    render(<SignInForm onDone={onDone} />);
    fireEvent.click(screen.getByRole("tab", { name: "Create account" }));
    expect(screen.getByText("At least 8 characters.")).toBeInTheDocument();
    fill("Name", "Demo");
    fill("Email", "new@example.com");
    fill("Password", "demo-pass-123");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(onDone).toHaveBeenCalledWith("/account"));
    expect(auth.signUp).toHaveBeenCalledWith({ name: "Demo", email: "new@example.com", password: "demo-pass-123" });
  });

  it("explains a taken email and other sign-up errors", async () => {
    auth.signUp.mockResolvedValue({ error: { status: 422, message: "User already exists" } });
    render(<SignInForm onDone={vi.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Create account" }));
    fill("Name", "Demo");
    fill("Email", "demo@example.com");
    fill("Password", "demo-pass-123");
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("There's already an account with that email.");
    auth.signUp.mockResolvedValue({ error: { status: 400, message: "Password too short" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Password too short"));
    fireEvent.click(screen.getByRole("tab", { name: "Sign in" }));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
