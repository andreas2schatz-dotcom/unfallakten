const T = {
  // ─── Farben ────────────────────────────────────────────────────
  navy:"#1B2A4A", navyDark:"#111d35", navyMid:"#243660", navyLight:"#2e4270",
  // Gold: nicht mehr primärer Akzent – für Rückwärtskompatibilität behalten
  gold:"#C8A84B", goldLight:"#dfc070", goldPale:"#f8f1e0", goldTrim:"rgba(200,168,75,0.18)",
  white:"#FFFFFF", offWhite:"#F6F4EF", surface:"#FAFAF8",
  border:"#E2DDD3", borderSoft:"rgba(226,221,211,0.6)",
  text:"#1a1a2e", textMid:"#3d4060", textMuted:"#6b7094", textFaint:"#9da3be",
  green:"#10b981", greenBg:"#ecfdf5",
  amber:"#f59e0b", amberBg:"#fffbeb",
  red:"#ef4444",   redBg:"#fef2f2",
  blue:"#3b82f6",  blueBg:"#eff6ff",

  // ─── Typographie-Tokens ────────────────────────────────────────
  // Schriftfamilien (spiegeln die CSS-Variablen in globals.css)
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
