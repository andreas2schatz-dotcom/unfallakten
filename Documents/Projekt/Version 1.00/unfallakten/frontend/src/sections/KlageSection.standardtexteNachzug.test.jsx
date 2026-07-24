import { describe, it, expect } from "vitest";
import { berechneNachgezogeneStandardtexte } from "./KlageSection.jsx";
import { STANDARDTEXTE_FIXTURE as TEXTE } from "../test/standardtexteFixture.js";

const GRUND = {
  standardtexte: TEXTE,
  wizardRwText: "",
  wizardVerzugText: "",
  wizardVerzugManuell: false,
  wizardHb: "",
  wizardHq: 100,
  wizardHqTyp: "gegnerisch",
  beklagte: [],
  daten: null,
  wizardVerzugDokDatum: "",
  wizardVerzugDatum: "",
};

describe("berechneNachgezogeneStandardtexte (V11 Seed-Race-Fix)", () => {
  it("liefert nichts, solange standardtexte noch nicht geladen ist", () => {
    const r = berechneNachgezogeneStandardtexte({ ...GRUND, standardtexte: null });
    expect(r).toEqual({});
  });

  it("zieht wizardRwText nach, wenn er noch leer-geseedet ist", () => {
    const r = berechneNachgezogeneStandardtexte(GRUND);
    expect(r.wizardRwText).toContain("Die alleinige Haftung");
  });

  it("zieht wizardVerzugText nach (Rechtshaengigkeits-Baustein ohne Verzugsdatum)", () => {
    const r = berechneNachgezogeneStandardtexte(GRUND);
    expect(r.wizardVerzugText).toBe("Verzug ist mit Rechtshängigkeit eingetreten.");
  });

  it("zieht wizardVerzugText mit Datum nach", () => {
    const r = berechneNachgezogeneStandardtexte({
      ...GRUND, wizardVerzugDatum: "2026-05-19", wizardVerzugDokDatum: "2026-05-04",
    });
    expect(r.wizardVerzugText).toContain("am 19.05.2026 eingetreten");
    expect(r.wizardVerzugText).toContain("BEWEIS: Schreiben vom 04.05.2026");
  });

  it("ueberschreibt wizardRwText NICHT, wenn bereits ein (auch nur manuell geaenderter) Text steht", () => {
    const r = berechneNachgezogeneStandardtexte({ ...GRUND, wizardRwText: "Vom Anwalt bereits bearbeitet." });
    expect(r.wizardRwText).toBeUndefined();
  });

  it("ueberschreibt wizardVerzugText NICHT, wenn bereits ein Text steht", () => {
    const r = berechneNachgezogeneStandardtexte({ ...GRUND, wizardVerzugText: "Vom Anwalt bereits bearbeitet." });
    expect(r.wizardVerzugText).toBeUndefined();
  });

  it("ueberschreibt wizardVerzugText NICHT, wenn der Anwender bereits manuell bearbeitet (auch bei leer)", () => {
    const r = berechneNachgezogeneStandardtexte({ ...GRUND, wizardVerzugManuell: true });
    expect(r.wizardVerzugText).toBeUndefined();
  });

  it("berechnet die Haftungsquote/-begruendung + gesamtReguliert aus daten.abrechnungen", () => {
    const r = berechneNachgezogeneStandardtexte({
      ...GRUND,
      wizardHb: "grobe Vorfahrtsverletzung", wizardHq: 70,
      daten: { abrechnungen: [{ gesamt_reguliert: "500" }] },
    });
    expect(r.wizardRwText).toContain("durch grobe Vorfahrtsverletzung. Die Haftungsquote beträgt 70 %.");
    expect(r.wizardRwText).toContain("Teilregulierung");
  });
});
