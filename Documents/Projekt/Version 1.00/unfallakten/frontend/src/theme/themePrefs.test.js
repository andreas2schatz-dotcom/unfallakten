import { describe, it, expect, beforeEach } from "vitest";
import { getThemePrefs, setThemePrefs, THEME_STORAGE_KEY } from "./themePrefs.js";

describe("themePrefs", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-scheme");
    document.documentElement.removeAttribute("data-theme");
  });

  it("liefert Default classic/light, wenn nichts gespeichert ist", () => {
    expect(getThemePrefs()).toEqual({ scheme: "classic", mode: "light" });
  });

  it("liefert Default, wenn localStorage kaputten JSON enthält", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "{nicht valides json");
    expect(getThemePrefs()).toEqual({ scheme: "classic", mode: "light" });
  });

  it("speichert und liest eine gesetzte Präferenz zurück", () => {
    setThemePrefs({ scheme: "clio", mode: "dark" });
    expect(getThemePrefs()).toEqual({ scheme: "clio", mode: "dark" });
  });

  it("setzt data-scheme und data-theme auf documentElement", () => {
    setThemePrefs({ scheme: "clio", mode: "dark" });
    expect(document.documentElement.dataset.scheme).toBe("clio");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("erzwingt mode=light, wenn scheme=classic gesetzt wird (kein Dark fuer Classic)", () => {
    setThemePrefs({ scheme: "classic", mode: "dark" });
    expect(getThemePrefs()).toEqual({ scheme: "classic", mode: "light" });
  });
});
