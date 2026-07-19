// Parteianzeige Klage: Personen (mit Vornamen) haben Vorrang vor Firmen-/
// Versicherungsnamen — RA-MICRO traegt bei Versicherern den Firmennamen im
// Namensfeld, bei Personen ist der Vorname der verlaessliche Marker.

export function istPersonPartei(b) {
  return !!(b?.vorname || "").trim();
}

export function istFirmenPartei(b) {
  if (!b || istPersonPartei(b)) return false;
  return !!(
    b.versicherung ||
    b.firma ||
    ((b.name || "").trim() && b.rolle !== "mandant")
  );
}

export function parteiAnzeigeName(b) {
  if (!b) return "Unbekannt";
  if (istPersonPartei(b)) return `${b.vorname} ${b.name || ""}`.trim();
  return (
    (b.name || "").trim() ||
    (b.firma || "").trim() ||
    (b.versicherung || "").trim() ||
    "Unbekannt"
  );
}

export function organBezeichnung(firmenname) {
  const n = (firmenname || "").toUpperCase();
  if (/(GMBH|GBR|\bKG\b|OHG)/.test(n)) return "den/die Geschäftsführer";
  if (/(\bAG\b|\bSE\b|KGAA)/.test(n)) return "den Vorstand";
  return "den gesetzlichen Vertreter";
}
