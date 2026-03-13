import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ThemeToggle from "./ThemeToggle";
import * as ThemeProviderModule from "./ThemeProvider";

describe("ThemeToggle", () => {
  it("shows sun icon when theme is dark", () => {
    vi.spyOn(ThemeProviderModule, "useTheme").mockReturnValue({ theme: "dark", toggleTheme: vi.fn() });
    render(<ThemeToggle />);
    expect(screen.getByRole("button").getAttribute("aria-label")).toBe("Switch to light mode");
  });

  it("shows moon icon when theme is light", () => {
    vi.spyOn(ThemeProviderModule, "useTheme").mockReturnValue({ theme: "light", toggleTheme: vi.fn() });
    render(<ThemeToggle />);
    expect(screen.getByRole("button").getAttribute("aria-label")).toBe("Switch to dark mode");
  });

  it("calls toggleTheme when clicked", () => {
    const toggleTheme = vi.fn();
    vi.spyOn(ThemeProviderModule, "useTheme").mockReturnValue({ theme: "light", toggleTheme });
    render(<ThemeToggle />);
    screen.getByRole("button").click();
    expect(toggleTheme).toHaveBeenCalledOnce();
  });
});
