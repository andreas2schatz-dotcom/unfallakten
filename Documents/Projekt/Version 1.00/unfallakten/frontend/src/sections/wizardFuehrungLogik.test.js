import { describe, it, expect } from "vitest";
import { wortDiff } from "./wizardFuehrungLogik.js";
import { schrittStatus, schrittWarnung, firmenOhneVertreter } from "./wizardFuehrungLogik.js";

describe("wortDiff", () => {
  it("identische Texte ergeben ein einziges gleich-Segment", () => {
    expect(wortDiff("Der Kläger fährt", "Der Kläger fährt")).toEqual([
      { typ: "gleich", text: "Der Kläger fährt" },
    ]);
  });

  it("Ergänzung am Ende wird als neu markiert", () => {
    expect(wortDiff("Der Kläger fährt", "Der Kläger fährt schnell")).toEqual([
      { typ: "gleich", text: "Der Kläger fährt" },
      { typ: "neu", text: "schnell" },
    ]);
  });

  it("Streichung wird als weg markiert", () => {
    expect(wortDiff("Der Kläger fährt schnell", "Der Kläger fährt")).toEqual([
      { typ: "gleich", text: "Der Kläger fährt" },
      { typ: "weg", text: "schnell" },
    ]);
  });

  it("Ersetzung liefert weg vor neu", () => {
    expect(wortDiff("Der Beklagte zahlt", "Die Beklagte zahlt")).toEqual([
      { typ: "weg", text: "Der" },
      { typ: "neu", text: "Die" },
      { typ: "gleich", text: "Beklagte zahlt" },
    ]);
  });

  it("leerer Auto-Text: alles neu; beide leer: leeres Ergebnis", () => {
    expect(wortDiff("", "Neuer Text")).toEqual([{ typ: "neu", text: "Neuer Text" }]);
    expect(wortDiff("", "")).toEqual([]);
    expect(wortDiff(null, undefined)).toEqual([]);
  });

  it("Umlaute bleiben unangetastet", () => {
    expect(wortDiff("Kürzung übernommen", "Kürzung geprüft und übernommen")).toEqual([
      { typ: "gleich", text: "Kürzung" },
      { typ: "neu", text: "geprüft und" },
      { typ: "gleich", text: "übernommen" },
    ]);
  });

  it("Zeilenumbrüche bleiben im Segmenttext erhalten", () => {
    const seg = wortDiff("Absatz eins.\n\nAbsatz zwei.", "Absatz eins.\n\nAbsatz zwei.");
    expect(seg).toEqual([{ typ: "gleich", text: "Absatz eins.\n\nAbsatz zwei." }]);
  });

  it("Änderung nach Zeilenumbruch wird erkannt", () => {
    const seg = wortDiff("Satz eins.\nSatz zwei.", "Satz eins.\nSatz drei.");
    expect(seg).toEqual([
      { typ: "gleich", text: "Satz eins.\nSatz" },
      { typ: "weg", text: "zwei." },
      { typ: "neu", text: "drei." },
    ]);
  });
});

const CTX_OK = {
  step: 3, maxStep: 6, gerichtBestaetigt: true,
  positionen: [{ checked: true }],
  beklagte: [
    { rolle_klage: "klaeger", name: "Muster" },
    { versicherung: "ADAC Autoversicherung AG", vertreter_name: "Stefan Daehne", checked: true },
  ],
  antraegeVeraltet: false, hatPlatzhalter: false,
};

describe("firmenOhneVertreter", () => {
  it("liefert kanonische Firmen-Beklagte ohne vertreter_name", () => {
    const beklagte = [
      { rolle_klage: "klaeger", firma: "Ignorier GmbH" },
      { versicherung: "HUK", vertreter_name: "", checked: true },
      { firma: "Abgewaehlt AG", checked: false },
      { name: "Privatperson", anrede: "1", checked: true },
    ];
    expect(firmenOhneVertreter(beklagte).map(b => b.versicherung || b.firma)).toEqual(["HUK"]);
  });

  it("schliesst natuerliche Personen mit versicherung aus (WDM-Anreicherung), Firmen bleiben drin", () => {
    const beklagte = [
      { vorname: "Max", name: "Mustermann", versicherung: "HUK", vertreter_name: "", checked: true },
      { firma: "ADAC AG", checked: true },
    ];
    expect(firmenOhneVertreter(beklagte).map(b => b.versicherung || b.firma)).toEqual(["ADAC AG"]);
  });
});

describe("schrittWarnung", () => {
  it("Schritt 1: Gericht nicht bestaetigt", () => {
    expect(schrittWarnung(1, { ...CTX_OK, gerichtBestaetigt: false }))
      .toBe("Gericht nicht bestätigt — in Schritt 1 bestätigen.");
    expect(schrittWarnung(1, CTX_OK)).toBeNull();
  });
  it("Schritt 2: Firma ohne Vertreter mit Namen", () => {
    const ctx = { ...CTX_OK, beklagte: [{ versicherung: "HUK", checked: true }] };
    expect(schrittWarnung(2, ctx)).toBe("Vertreter fehlt: HUK — Lookup in der Parteien-Karte.");
    expect(schrittWarnung(2, CTX_OK)).toBeNull();
  });
  it("Schritt 5: keine Position angehakt", () => {
    expect(schrittWarnung(5, { ...CTX_OK, positionen: [{ checked: false }] }))
      .toBe("Keine Schadenposition ausgewählt.");
    expect(schrittWarnung(5, CTX_OK)).toBeNull();
  });
  it("Schritt 6: veraltet und/oder Platzhalter", () => {
    expect(schrittWarnung(6, { ...CTX_OK, antraegeVeraltet: true }))
      .toBe("Antragstext veraltet — in Schritt 6 neu generieren.");
    expect(schrittWarnung(6, { ...CTX_OK, hatPlatzhalter: true }))
      .toBe("RVG-Platzhalter noch im Antragstext — Schritt 10 (Gebühren) aufrufen.");
    expect(schrittWarnung(6, { ...CTX_OK, antraegeVeraltet: true, hatPlatzhalter: true }))
      .toBe("Antragstext veraltet — in Schritt 6 neu generieren. RVG-Platzhalter noch im Antragstext — Schritt 10 (Gebühren) aufrufen.");
  });
  it("andere Schritte: nie Warnung", () => {
    [3, 4, 7, 8, 9, 10, 11].forEach(nr => expect(schrittWarnung(nr, CTX_OK)).toBeNull());
  });
});

describe("schrittStatus", () => {
  it("aktueller Schritt ist aktiv, auch mit Warnung", () => {
    expect(schrittStatus(3, CTX_OK).zustand).toBe("aktiv");
    const ctx = { ...CTX_OK, step: 1, gerichtBestaetigt: false };
    expect(schrittStatus(1, ctx)).toEqual({
      zustand: "aktiv", warnung: "Gericht nicht bestätigt — in Schritt 1 bestätigen.",
    });
  });
  it("nicht erreichte Schritte sind offen", () => {
    expect(schrittStatus(7, CTX_OK)).toEqual({ zustand: "offen", warnung: null });
    expect(schrittStatus(11, CTX_OK)).toEqual({ zustand: "offen", warnung: null });
  });
  it("besuchte Schritte ohne Warnung sind erledigt", () => {
    expect(schrittStatus(4, CTX_OK)).toEqual({ zustand: "erledigt", warnung: null });
  });
  it("Warnung ersetzt erledigt bei besuchten Schritten", () => {
    const ctx = { ...CTX_OK, step: 6, positionen: [{ checked: false }] };
    expect(schrittStatus(5, ctx)).toEqual({
      zustand: "warnung", warnung: "Keine Schadenposition ausgewählt.",
    });
  });
});
