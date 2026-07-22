export const THEME_STORAGE_KEY = "unfallakten.theme";

const DEFAULT_PREFS = { scheme: "classic", mode: "light" };

function normalize(prefs) {
  const scheme = prefs?.scheme === "clio" ? "clio" : "classic";
  const mode = scheme === "clio" && prefs?.mode === "dark" ? "dark" : "light";
  return { scheme, mode };
}

export function getThemePrefs() {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PREFS };
    return normalize(JSON.parse(raw));
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function setThemePrefs(prefs) {
  const normalized = normalize(prefs);
  localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify(normalized));
  document.documentElement.dataset.scheme = normalized.scheme;
  document.documentElement.dataset.theme = normalized.mode;
  return normalized;
}
