import { describe, it, expect } from "vitest";
import { sollAutoLookup } from "./KlageSection.jsx";

describe("sollAutoLookup", () => {
  const firma = { id: 3, versicherung: "HUK", rolle_klage: "beklagter" };
  it("Firma ohne Vertreter und ohne Cache-Eintrag: ja", () => {
    expect(sollAutoLookup(firma, {})).toBe(true);
  });
  it("abgeschlossener Lookup (laden:false, ergebnis vorhanden) verhindert Wiederholung", () => {
    expect(sollAutoLookup(firma, { 3: { laden: false, ergebnis: { name: "X" } } })).toBe(false);
  });
  it("laufender Lookup verhindert Wiederholung", () => {
    expect(sollAutoLookup(firma, { 3: { laden: true } })).toBe(false);
  });
  it("Klaeger, Privatperson, vorhandener Vertreter: nein", () => {
    expect(sollAutoLookup({ ...firma, rolle_klage: "klaeger" }, {})).toBe(false);
    expect(sollAutoLookup({ id: 4, vorname: "Max", name: "Muster", rolle: "gegner" }, {})).toBe(false);
    expect(sollAutoLookup({ ...firma, vertreter_name: "Dr. A" }, {})).toBe(false);
  });
});
