import { describe, it, expect } from "vitest";
import { loginUrl } from "./api";

// NEXT_PUBLIC_API_URL is not set in tests - falls back to localhost:8000
describe("loginUrl", () => {
  it("returns the auth/google URL", () => {
    expect(loginUrl()).toBe("http://localhost:8000/auth/google");
  });
});
