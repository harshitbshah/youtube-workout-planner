import { describe, it, expect, beforeEach, vi } from "vitest";
import { loginUrl } from "./api";

// NEXT_PUBLIC_API_URL is not set in tests — falls back to localhost:8000
describe("loginUrl", () => {
  it("returns base auth URL with no color_scheme when called without args", () => {
    const url = loginUrl();
    expect(url).toBe("http://localhost:8000/auth/google");
  });

  it("appends color_scheme=light when theme is light", () => {
    const url = loginUrl("light");
    expect(url).toBe("http://localhost:8000/auth/google?color_scheme=light");
  });

  it("appends color_scheme=dark when theme is dark", () => {
    const url = loginUrl("dark");
    expect(url).toBe("http://localhost:8000/auth/google?color_scheme=dark");
  });
});
