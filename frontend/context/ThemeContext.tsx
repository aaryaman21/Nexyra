"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";

type Theme = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";
interface ThemeContextType {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}
const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("system");
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>("dark");
  const preference = useRef<Theme>("system");
  const transition = useRef<{ skipTransition: () => void } | null>(null);

  const applyTheme = useCallback((next: Theme, animate: boolean) => {
    const resolved = next === "system"
      ? (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : next;
    const root = document.documentElement;
    const changed = root.classList.contains("dark") !== (resolved === "dark");
    preference.current = next;
    try { localStorage.setItem("nexyra_theme", next); } catch { /* Keep working when storage is unavailable. */ }
    const commit = () => {
      root.classList.toggle("dark", resolved === "dark");
      setThemeState(next);
      setResolvedTheme(resolved);
    };
    transition.current?.skipTransition();
    if (animate && changed && document.startViewTransition && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      transition.current = document.startViewTransition(() => flushSync(commit));
    } else {
      commit();
    }
  }, []);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem("nexyra_theme");
      localStorage.removeItem("nexyra_light_style");
    } catch { /* System theme remains available without storage. */ }
    delete document.documentElement.dataset.lightStyle;
    // Restore the browser preference after hydration; the server cannot read it.
    applyTheme(stored === "light" || stored === "dark" ? stored : "system", false);
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => { if (preference.current === "system") applyTheme("system", true); };
    media.addEventListener("change", onChange);
    return () => { media.removeEventListener("change", onChange); transition.current?.skipTransition(); };
  }, [applyTheme]);

  const setTheme = (next: Theme) => applyTheme(next, true);
  const toggleTheme = () => setTheme(preference.current === "dark" ? "light" : preference.current === "light" ? "system" : "dark");
  return <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme, toggleTheme }}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within a ThemeProvider");
  return context;
}
