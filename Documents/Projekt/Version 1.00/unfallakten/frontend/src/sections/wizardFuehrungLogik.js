// Klage-Wizard UI-Fuehrung (Paket 2): reine Logik ohne React/API.

import { kanonischeBeklagte, istPersonPartei } from "./parteiLogik.js";

function tokenisiere(text) {
  return String(text ?? "")
    .split(/(\n)/)
    .flatMap(teil => (teil === "\n" ? ["\n"] : teil.split(/[^\S\n]+/).filter(Boolean)));
}

function fasseZusammen(roh) {
  const segmente = [];
  roh.forEach(({ typ, token }) => {
    const letzt = segmente[segmente.length - 1];
    if (letzt && letzt.typ === typ) {
      const nahtlos = token === "\n" || letzt.text.endsWith("\n");
      letzt.text += nahtlos ? token : ` ${token}`;
    } else {
      segmente.push({ typ, text: token });
    }
  });
  return segmente;
}

export function wortDiff(autoText, aktuellerText) {
  const a = tokenisiere(autoText);
  const b = tokenisiere(aktuellerText);
  const n = a.length, m = b.length;
  const lcs = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j]
        ? lcs[i + 1][j + 1] + 1
        : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }
  const roh = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { roh.push({ typ: "gleich", token: a[i] }); i++; j++; }
    else if (lcs[i + 1][j] >= lcs[i][j + 1]) { roh.push({ typ: "weg", token: a[i] }); i++; }
    else { roh.push({ typ: "neu", token: b[j] }); j++; }
  }
  while (i < n) { roh.push({ typ: "weg", token: a[i] }); i++; }
  while (j < m) { roh.push({ typ: "neu", token: b[j] }); j++; }
  return fasseZusammen(roh);
}

export function firmenOhneVertreter(beklagte) {
  return kanonischeBeklagte(beklagte).filter(b => !istPersonPartei(b) && (b.versicherung || b.firma) && !b.vertreter_name);
}

export function schrittWarnung(nr, ctx) {
  if (nr === 1 && !ctx.gerichtBestaetigt) {
    return "Gericht nicht bestätigt — in Schritt 1 bestätigen.";
  }
  if (nr === 2) {
    const ohne = firmenOhneVertreter(ctx.beklagte);
    if (ohne.length > 0) {
      const namen = ohne.map(b => b.versicherung || b.firma).join(", ");
      return `Vertreter fehlt: ${namen} — Lookup in der Parteien-Karte.`;
    }
  }
  if (nr === 5 && !(ctx.positionen || []).some(p => p.checked)) {
    return "Keine Schadenposition ausgewählt.";
  }
  if (nr === 6) {
    const teile = [];
    if (ctx.antraegeVeraltet) teile.push("Antragstext veraltet — in Schritt 6 neu generieren.");
    if (ctx.hatPlatzhalter) teile.push("RVG-Platzhalter noch im Antragstext — Schritt 10 (Gebühren) aufrufen.");
    if (teile.length) return teile.join(" ");
  }
  return null;
}

export function schrittStatus(nr, ctx) {
  if (nr === ctx.step) return { zustand: "aktiv", warnung: schrittWarnung(nr, ctx) };
  if (nr > ctx.maxStep) return { zustand: "offen", warnung: null };
  const warnung = schrittWarnung(nr, ctx);
  return warnung ? { zustand: "warnung", warnung } : { zustand: "erledigt", warnung: null };
}
