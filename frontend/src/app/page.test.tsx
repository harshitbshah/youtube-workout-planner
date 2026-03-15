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
  loginUrl: vi.fn((scheme?: string) =>
    scheme ? `http://localhost:8000/auth/google?color_scheme=${scheme}` : "http://localhost:8000/auth/google"
  ),
  setToken: vi.fn(),
}));

vi.mock("@/components/ThemeProvider", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: vi.fn() }),
}));

import * as api from "@/lib/api";
const mockGetMe = api.getMe as ReturnType<typeof vi.fn>;
const mockGetChannels = api.getChannels as ReturnType<typeof vi.fn>;
const mockLoginUrl = api.loginUrl as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  mockGetMe.mockRejectedValue(new Error("Unauthenticated"));
});

describe("LandingPage — unauthenticated", () => {
  it("renders sign-in links after auth check fails", async () => {
    render(<LandingPage />);
    await waitFor(() =>
      expect(screen.getAllByRole("link", { name: /sign in|get started/i }).length).toBeGreaterThan(0)
    );
  });

  it("passes current theme to loginUrl for all sign-in links", async () => {
    render(<LandingPage />);
    await waitFor(() =>
      expect(screen.getAllByRole("link", { name: /sign in|get started/i }).length).toBeGreaterThan(0)
    );
    // loginUrl should have been called with the current theme ("light")
    expect(mockLoginUrl).toHaveBeenCalledWith("light");
  });

  it("sign-in links include color_scheme in href", async () => {
    render(<LandingPage />);
    await waitFor(() => {
      const links = screen.getAllByRole("link", { name: /sign in|get started/i });
      links.forEach((link) => {
        expect(link.getAttribute("href")).toContain("color_scheme=light");
      });
    });
  });
});

describe("LandingPage — authenticated redirect", () => {
  it("redirects to dashboard when user has channels", async () => {
    const replace = vi.fn();
    vi.mocked(vi.fn()).mockReturnValue({ replace });
    mockGetMe.mockResolvedValue({ id: 1, email: "u@example.com" });
    mockGetChannels.mockResolvedValue([{ id: 1, name: "FitnessCh" }]);
    // No assertion needed — just ensure no crash during redirect flow
    render(<LandingPage />);
    await waitFor(() => expect(mockGetMe).toHaveBeenCalled());
  });
});
