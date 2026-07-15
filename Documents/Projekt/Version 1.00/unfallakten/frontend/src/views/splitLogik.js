// frontend/src/views/splitLogik.js
// Reine Logik fuer den Aufteilen-Dialog: Schnitte <-> Seitengruppen.
// "schnitt nach Seite p" bedeutet: zwischen Seite p und p+1 (1 <= p <= N-1).

export function gruppenAusSchnitten(seitenGesamt, schnitte) {
  const cuts = [...new Set(schnitte)]
    .filter((p) => p >= 1 && p < seitenGesamt)
    .sort((a, b) => a - b);
  const gruppen = [];
  let start = 1;
  for (const c of cuts) {
    const g = [];
    for (let p = start; p <= c; p++) g.push(p);
    gruppen.push(g);
    start = c + 1;
  }
  const rest = [];
  for (let p = start; p <= seitenGesamt; p++) rest.push(p);
  gruppen.push(rest);
  return gruppen;
}

export function schnittUmschalten(schnitte, pos) {
  return schnitte.includes(pos)
    ? schnitte.filter((p) => p !== pos)
    : [...schnitte, pos].sort((a, b) => a - b);
}

export function istAufteilbar(detail) {
  return !!detail && detail.payload_typ === "datei";
}
