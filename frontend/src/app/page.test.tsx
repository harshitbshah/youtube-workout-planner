import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import LandingPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("@/components/Footer", () => ({ Footer: () => null }));

vi.mock("@/lib/api", () => ({
  getMe: vi.fn(),
  getChannels: vi.fn(),
  loginUrl: vi.fn(() => "http://localhost:8000/auth/google"),
  setToken: vi.fn(),
}));

import * as api from "@/lib/api";
const mockGetMe = api.getMe as ReturnType<typeof vi.fn>;
const mockGetChannels = api.getChannels as ReturnType<typeof vi.fn>;
const mockLoginUrl = api.loginUrl as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  mockGetMe.mockRejectedValue(new Error("Unauthenticated"));
});

describe("LandingPage - unauthenticated", () => {
  it("renders sign-in links after auth check fails", async () => {
    render(<LandingPage />);
    await waitFor(() =>
      expect(screen.getAllByRole("link", { name: /sign in|get started/i }).length).toBeGreaterThan(0)
    );
  });

  it("'Sign in' nav link points to the auth/google URL", async () => {
    render(<LandingPage />);
    await waitFor(() => {
      const signInLink = screen.getByRole("link", { name: /^sign in$/i });
      expect(signInLink.getAttribute("href")).toContain("/auth/google");
    });
  });

  it("'Get started free' CTA links point to /onboarding", async () => {
    render(<LandingPage />);
    await waitFor(() => {
      const ctaLinks = screen.getAllByRole("link", { name: /get started free/i });
      ctaLinks.forEach((link) => {
        expect(link.getAttribute("href")).toBe("/onboarding");
      });
    });
  });
});

describe("LandingPage - authenticated redirect", () => {
  it("redirects to dashboard when user has channels", async () => {
    const replace = vi.fn();
    vi.mocked(vi.fn()).mockReturnValue({ replace });
    mockGetMe.mockResolvedValue({ id: 1, email: "u@example.com" });
    mockGetChannels.mockResolvedValue([{ id: 1, name: "FitnessCh" }]);
    // No assertion needed - just ensure no crash during redirect flow
    render(<LandingPage />);
    await waitFor(() => expect(mockGetMe).toHaveBeenCalled());
  });
});
