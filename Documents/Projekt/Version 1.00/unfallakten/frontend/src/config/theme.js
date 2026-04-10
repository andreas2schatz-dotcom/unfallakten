const T = {
  // ─── Primärfarben ──────────────────────────────────────────────
  navy:     "#1B2A4A",
  navyDark: "#111d35",
  navyMid:  "#243660",
  navyLight:"#2e4270",

  // ─── Akzent: Sienna / Terrakotta (ersetzt Gold) ────────────────
  // oklch(55% 0.08 38) ≈ warme Sienna – augenschonend, menschennah
  accent:      "#A06B4A",                    // Primär – Rahmen, Icons, Spinner
  accentLight: "#C08F6C",                    // Hell – Hover, Text auf Dunkel (5:1 auf Navy)
  accentPale:  "#F3EAE2",                    // Sehr hell – Hintergründe, Highlights
  accentDark:  "#7D5038",                    // Dunkel – Text auf Weiß (6.5:1)
  accentTrim:  "rgba(160,107,74,0.18)",      // Transparent – dezente Rahmen
  // Gold behalten für Rückwärtskompatibilität (deprecated)
  gold:        "#C8A84B",
  goldLight:   "#dfc070",
  goldPale:    "#f8f1e0",
  goldTrim:    "rgba(200,168,75,0.18)",

  // ─── Oberflächen & Neutrale ────────────────────────────────────
  white:      "#FFFFFF",
  offWhite:   "#F6F4EF",  // Pergament – augenschonendes Hintergrundweiß
  surface:    "#FAFAF8",  // Kachel-Hintergrund
  border:     "#E2DDD3",
  borderSoft: "rgba(226,221,211,0.6)",

  // ─── Text ─────────────────────────────────────────────────────
  text:      "#1a1a2e",
  textMid:   "#3d4060",
  textMuted: "#6b7094",
  textFaint: "#9da3be",

  // ─── Semantische Status-Farben ─────────────────────────────────
  // Grün / Erfolg
  green:      "#10b981",
  greenBg:    "#ecfdf5",
  greenLight: "#86efac",  // Rahmen, helle Akzente
  greenText:  "#065f46",  // Text auf greenBg

  // Amber / Warnung
  amber:     "#f59e0b",
  amberBg:   "#fffbeb",   // Hintergrund
  amberMid:  "#fef3c7",   // Hintergrund (etwas dunkler)
  amberText: "#92400e",   // Text auf amberBg/amberMid

  // Rot / Fehler
  red:       "#ef4444",
  redBg:     "#fef2f2",
  redLight:  "#fca5a5",   // Rahmen, helle Akzente
  redText:   "#991b1b",   // Text auf redBg

  // Blau / Info
  blue:      "#3b82f6",
  blueBg:    "#eff6ff",
  blueText:  "#1e40af",   // Text auf blueBg

  // ─── Typographie-Tokens ────────────────────────────────────────
  fontDisplay: "'Bricolage Grotesque', system-ui, sans-serif",
  fontBody:    "'Figtree', system-ui, sans-serif",
  fontMono:    "ui-monospace, 'Cascadia Code', monospace",

  // Typscala
  textXs:   "0.75rem",
  textSm:   "0.8125rem",
  textBase: "0.875rem",
  textMd:   "1rem",
  textLg:   "1.125rem",
  textXl:   "1.25rem",
  text2Xl:  "1.5rem",
};

export default T;
