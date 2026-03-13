import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ThemeProvider, useTheme } from "./ThemeProvider";

// Helper component to expose context values
function ThemeConsumer() {
  const { theme, toggleTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <button onClick={toggleTheme}>Toggle</button>
    </div>
  );
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
    vi.restoreAllMocks();
  });

  it("defaults to dark when system prefers dark", () => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
    });
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("defaults to light when system prefers light", () => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
    });
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    expect(screen.getByTestId("theme").textContent).toBe("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("reads saved dark preference from localStorage", () => {
    localStorage.setItem("theme", "dark");
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
    });
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    expect(screen.getByTestId("theme").textContent).toBe("dark");
  });

  it("reads saved light preference from localStorage", () => {
    localStorage.setItem("theme", "light");
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
    });
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    expect(screen.getByTestId("theme").textContent).toBe("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("toggleTheme switches from dark to light and saves to localStorage", async () => {
    localStorage.setItem("theme", "dark");
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
    });
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    act(() => { screen.getByRole("button").click(); });
    expect(screen.getByTestId("theme").textContent).toBe("light");
    expect(localStorage.getItem("theme")).toBe("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("toggleTheme switches from light to dark and saves to localStorage", async () => {
    localStorage.setItem("theme", "light");
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
    });
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    act(() => { screen.getByRole("button").click(); });
    expect(screen.getByTestId("theme").textContent).toBe("dark");
    expect(localStorage.getItem("theme")).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});
