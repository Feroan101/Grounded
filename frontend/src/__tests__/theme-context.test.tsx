import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ThemeProvider, useTheme } from "@/lib/theme-context";

const THEME_KEY = "grounded_theme";

function stubMatchMedia(matches: boolean) {
  const mq = {
    matches,
    media: "(prefers-color-scheme: dark)",
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  };
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue(mq));
  return mq;
}

function Probe() {
  const { theme, toggleTheme } = useTheme();
  return (
    <button type="button" onClick={toggleTheme}>
      {theme}
    </button>
  );
}

function renderApp() {
  return render(
    <ThemeProvider>
      <Probe />
    </ThemeProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ThemeProvider", () => {
  it("defaults to light when nothing is stored and the system prefers light", async () => {
    stubMatchMedia(false);
    renderApp();
    expect(screen.getByRole("button")).toHaveTextContent("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("follows the dark system preference when the user has not chosen", async () => {
    stubMatchMedia(true);
    renderApp();
    expect(screen.getByRole("button")).toHaveTextContent("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("respects a persisted dark preference over the system", async () => {
    stubMatchMedia(false);
    localStorage.setItem(THEME_KEY, "dark");
    renderApp();
    expect(screen.getByRole("button")).toHaveTextContent("dark");
  });

  it("toggling switches theme and persists it", async () => {
    stubMatchMedia(false);
    renderApp();
    expect(screen.getByRole("button")).toHaveTextContent("light");

    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("button")).toHaveTextContent("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");

    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("button")).toHaveTextContent("light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
  });

  it("a stored choice stops the theme from following the system", async () => {
    stubMatchMedia(true);
    localStorage.setItem(THEME_KEY, "light");
    renderApp();
    expect(screen.getByRole("button")).toHaveTextContent("light");
  });
});