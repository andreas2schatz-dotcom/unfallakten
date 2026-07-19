import { describe, it, expect } from "vitest";
import {
  ENTWURF_FORMAT_VERSION,
  serialisiereEntwurf,
  parseEntwurf,
  reconcilePositionen,
  formatGespeichertAm,
} from "./klageEntwurfLogik.js";

const beispielState = {
  wizardStep: 7, wizardMaxStep: 8,
  aktLegTyp: "eigentum", aktLegFreigabe: "freigabe", aktLegDatum: "2026-03-01",
  auslandsunfall: false,
  wizardSachverhaltText: "SV", wizardSachverhaltManuell: true,
  wizardUnfallText: "U", wizardRwText: "RW",
  wizardVerzugText: "V", wizardVerzugManuell: false,
  wizardVerzugDatum: "2026-04-01", wizardVerzugDokDatum: "2026-03-15",
  wizardAntraegeText: "A", wizardAntraegeManuell: false, wizardAntraegeBasis: null,
  wizardGebuehrenText: "G", wizardGebuehrenManuell: false,
  wizardPos: [
    { key: "reparatur", label: "Reparaturkosten", betrag: 1200.5, betragOriginal: 1500, checked: true },
    { key: "unkostenpauschale", label: "Unkostenpauschale", betrag: 25, checked: false },
  ],
  wizardMitSG: true, wizardSGMind: 500,
  wizardHq: 100, wizardHqTyp: "gegnerisch", wizardHb: "Auffahrunfall",
  wizardMitFestSg: false, wizardMitFestSach: false,
  wizardRvgAussergOv: "", wizardRvgBereitsGezahlt: "",
  wizardGerichtBest: true,
};

describe("serialisiereEntwurf", () => {
  it("uebernimmt Zustaende unter den State-Namen und reduziert Positionen", () => {
    const e = serialisiereEntwurf(beispielState);
    expect(e.wizardStep).toBe(7);
    expect(e.wizardSachverhaltManuell).toBe(true);
    expect(e.wizardGerichtBest).toBe(true);
    expect(e.positionen).toEqual([
      { key: "reparatur", checked: true, betrag: 1200.5, label: "Reparaturkosten" },
      { key: "unkostenpauschale", checked: false, betrag: 25, label: "Unkostenpauschale" },
    ]);
    expect(e).not.toHaveProperty("wizardPos");
    expect(e).not.toHaveProperty("rvgData");
    expect(e).not.toHaveProperty("wizardRvgAussergData");
  });

  it("ist deterministisch (Fingerprint-Grundlage)", () => {
    expect(JSON.stringify(serialisiereEntwurf(beispielState)))
      .toBe(JSON.stringify(serialisiereEntwurf({ ...beispielState })));
  });
});

describe("parseEntwurf", () => {
  const gueltig = {
    entwurf_json: JSON.stringify(serialisiereEntwurf(beispielState)),
    format_version: ENTWURF_FORMAT_VERSION,
    gespeichert_am: "2026-07-19 14:32:05",
  };

  it("akzeptiert gueltigen Entwurf", () => {
    const p = parseEntwurf(gueltig);
    expect(p.ok).toBe(true);
    expect(p.entwurf.wizardStep).toBe(7);
  });

  it("lehnt fremde format_version ab", () => {
    expect(parseEntwurf({ ...gueltig, format_version: 99 }).ok).toBe(false);
  });

  it("lehnt korruptes JSON ab ohne zu werfen", () => {
    expect(parseEntwurf({ ...gueltig, entwurf_json: "{kaputt" }).ok).toBe(false);
    expect(parseEntwurf({ ...gueltig, entwurf_json: '"nur-string"' }).ok).toBe(false);
    expect(parseEntwurf(null).ok).toBe(false);
  });
});

describe("reconcilePositionen", () => {
  const entwurfPos = [
    { key: "reparatur", checked: true, betrag: 1200.5, label: "Reparaturkosten" },
    { key: "abschleppkosten", checked: true, betrag: 300, label: "Abschleppkosten" },
    { key: "unkostenpauschale", checked: false, betrag: 25, label: "Unkostenpauschale" },
  ];

  it("uebernimmt checked aus dem Entwurf, Betraege aus der frischen Akte", () => {
    const frisch = [
      { key: "reparatur", label: "Reparaturkosten", betrag: 1200.5, checked: true },
      { key: "unkostenpauschale", label: "Unkostenpauschale", betrag: 25, checked: true },
    ];
    const r = reconcilePositionen(entwurfPos, frisch);
    const rep = r.positionen.find(p => p.key === "reparatur");
    const unk = r.positionen.find(p => p.key === "unkostenpauschale");
    expect(rep.checked).toBe(true);
    expect(unk.checked).toBe(false);
  });

  it("neue Position erscheint mit checked=false und Meldung", () => {
    const frisch = [
      { key: "reparatur", label: "Reparaturkosten", betrag: 1200.5 },
      { key: "abschleppkosten", label: "Abschleppkosten", betrag: 300 },
      { key: "unkostenpauschale", label: "Unkostenpauschale", betrag: 25 },
      { key: "standkosten", label: "Standkosten", betrag: 90 },
    ];
    const r = reconcilePositionen(entwurfPos, frisch);
    expect(r.positionen.find(p => p.key === "standkosten").checked).toBe(false);
    expect(r.aenderungen.some(a => a.includes("Neue Position") && a.includes("Standkosten"))).toBe(true);
  });

  it("weggefallene Position wird entfernt und gemeldet", () => {
    const frisch = [
      { key: "reparatur", label: "Reparaturkosten", betrag: 1200.5 },
      { key: "unkostenpauschale", label: "Unkostenpauschale", betrag: 25 },
    ];
    const r = reconcilePositionen(entwurfPos, frisch);
    expect(r.positionen.some(p => p.key === "abschleppkosten")).toBe(false);
    expect(r.aenderungen.some(a => a.includes("entfallen") && a.includes("Abschleppkosten"))).toBe(true);
  });

  it("geaenderter Betrag: frischer Betrag gilt, Meldung mit alt und neu", () => {
    const frisch = [
      { key: "reparatur", label: "Reparaturkosten", betrag: 900 },
      { key: "abschleppkosten", label: "Abschleppkosten", betrag: 300 },
      { key: "unkostenpauschale", label: "Unkostenpauschale", betrag: 25 },
    ];
    const r = reconcilePositionen(entwurfPos, frisch);
    expect(r.positionen.find(p => p.key === "reparatur").betrag).toBe(900);
    const meldung = r.aenderungen.find(a => a.includes("Betrag"));
    expect(meldung).toContain("Reparaturkosten");
    expect(meldung).toContain("1200,50");
    expect(meldung).toContain("900,00");
  });

  it("unveraendert: leere Aenderungsliste", () => {
    const frisch = [
      { key: "reparatur", label: "Reparaturkosten", betrag: 1200.5 },
      { key: "abschleppkosten", label: "Abschleppkosten", betrag: 300 },
      { key: "unkostenpauschale", label: "Unkostenpauschale", betrag: 25 },
    ];
    expect(reconcilePositionen(entwurfPos, frisch).aenderungen).toEqual([]);
  });

  it("vertraegt leere/fehlende Eingaben", () => {
    expect(reconcilePositionen(null, []).positionen).toEqual([]);
    expect(reconcilePositionen(null, []).aenderungen).toEqual([]);
  });
});

describe("formatGespeichertAm", () => {
  it("formatiert SQLite-localtime", () => {
    expect(formatGespeichertAm("2026-07-19 14:32:05")).toBe("19.07., 14:32");
  });
  it("vertraegt leere/kaputte Werte", () => {
    expect(formatGespeichertAm("")).toBe("");
    expect(formatGespeichertAm(null)).toBe("");
    expect(formatGespeichertAm("unfug")).toBe("unfug");
  });
});
