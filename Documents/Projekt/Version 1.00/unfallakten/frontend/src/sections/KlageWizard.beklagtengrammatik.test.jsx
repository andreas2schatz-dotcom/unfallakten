import { describe, it, expect } from "vitest";
import { beklagtenGrammatik, buildRwVorschau, buildVerzugAutoText } from "./KlageWizard.jsx";
import { STANDARDTEXTE_FIXTURE as TEXTE } from "../test/standardtexteFixture.js";

const VERS = { versicherung: "Test-Versicherung AG" };
const MANN = { anrede: "1", name: "Huber" };

describe("beklagtenGrammatik nomGross/hat (V11 Nebenbefund)", () => {
  it("mehrere Beklagte", () => {
    const g = beklagtenGrammatik([VERS, MANN]);
    expect(g.nomGross).toBe("Die Beklagten");
    expect(g.hat).toBe("haben");
  });
  it("maennlicher Einzel-Beklagter", () => {
    const g = beklagtenGrammatik([MANN]);
    expect(g.nomGross).toBe("Der Beklagte");
    expect(g.hat).toBe("hat");
  });
  it("Default feminin", () => {
    const g = beklagtenGrammatik([VERS]);
    expect(g.nomGross).toBe("Die Beklagte");
    expect(g.hat).toBe("hat");
  });
});

describe("buildRwVorschau nutzt Beklagten-Grammatik (V11 Nebenbefund)", () => {
  it("Teilregulierung bei mehreren Beklagten", () => {
    const t = buildRwVorschau("", 100, 500, false, "gegnerisch", [VERS, MANN], TEXTE);
    expect(t).toContain("Die Beklagten haben eine Teilregulierung");
    expect(t).not.toContain("zu 2)");
  });
  it("keine Regulierung bei maennlichem Beklagten", () => {
    const t = buildRwVorschau("", 100, 0, false, "gegnerisch", [MANN], TEXTE);
    expect(t).toContain("Der Beklagte hat bislang keine Regulierung vorgenommen.");
  });
});

describe("Generatoren beziehen Standardtexte aus der Registry-Map (V11)", () => {
  it("buildVerzugAutoText nutzt Registry-Text mit Platzhaltern", () => {
    const t = buildVerzugAutoText("2026-04-20", "2026-05-04", TEXTE);
    expect(t).toContain("am 04.05.2026 eingetreten.");
    expect(t).toContain("BEWEIS: Schreiben vom 20.04.2026");
  });
  it("buildVerzugAutoText ohne Datum nutzt Rechtshaengigkeits-Baustein", () => {
    expect(buildVerzugAutoText(null, null, TEXTE))
      .toBe("Verzug ist mit Rechtshängigkeit eingetreten.");
  });
  it("buildRwVorschau nutzt Registry-Texte", () => {
    const t = buildRwVorschau("grobe Vorfahrtsverletzung", 70, 500, false,
                              "gegnerisch", [VERS, MANN], TEXTE);
    expect(t).toContain("durch grobe Vorfahrtsverletzung. Die Haftungsquote beträgt 70 %.");
    expect(t).toContain("Die Beklagten haben eine Teilregulierung in Höhe von 500,00 € vorgenommen.");
    expect(t).toContain("Mithaftungsquote von 30 % auf Klägerseite");
  });
});
