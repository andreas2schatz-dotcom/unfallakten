import { describe, it, expect } from "vitest";
import { berechneOnboardingChecks } from "./onboardingChecks.js";

const voll = {
  akte: { unfalldatum: "2026-01-10", unfallort: "Offenbach" },
  beteiligte: [
    { rolle: "mandant", name: "Max Müller" },
    { rolle: "gegner", name: "Erika Beispiel" },
    { kuerzel: "GHPV", name: "HUK-COBURG" },
  ],
  schaden: { gesamt_brutto: 8200 },
  dokumente: [
    { dokumentenklasse: "vollmacht" },
    { dokumentenklasse: "forderungsschreiben" },
  ],
};

const kachel = (r, key) => r.kacheln.find(k => k.key === key);

describe("berechneOnboardingChecks", () => {
  it("meldet noetig=false, wenn alle Pflichtbereiche vollständig sind", () => {
    const r = berechneOnboardingChecks(voll);
    expect(r.noetig).toBe(false);
    expect(r.erledigt).toBe(r.pflichtAnzahl);
  });

  it("erkennt die GHPV über das großgeschriebene Kürzel", () => {
    const r = berechneOnboardingChecks({ beteiligte: [{ kuerzel: "GHPV" }] });
    expect(kachel(r, "ghpv").ok).toBe(true);
  });

  it("erkennt Schadenspositionen über gesamt_brutto", () => {
    const r = berechneOnboardingChecks({ schaden: { gesamt_brutto: 4500 } });
    expect(kachel(r, "schaden").ok).toBe(true);
  });

  it("erkennt Unfalldetails über die Akten-Felder", () => {
    const r = berechneOnboardingChecks({ akte: { unfalldatum: "2026-01-10", unfallort: "Offenbach" } });
    expect(kachel(r, "unfalldetails").ok).toBe(true);
  });

  it("erkennt Vollmacht und Erstforderung über die Dokumentenklasse", () => {
    const r = berechneOnboardingChecks({ dokumente: [
      { dokumentenklasse: "vollmacht" }, { dokumentenklasse: "forderungsschreiben" },
    ] });
    expect(kachel(r, "vollmacht").ok).toBe(true);
    expect(kachel(r, "erstforderung").ok).toBe(true);
  });

  it("zählt die Erstforderung nicht als Pflichtbereich", () => {
    const r = berechneOnboardingChecks(voll);
    expect(r.pflichtAnzahl).toBe(6);
    expect(kachel(r, "erstforderung").optional).toBe(true);
  });
});
