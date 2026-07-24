import { describe, it, expect } from "vitest";
import { beklagtenGrammatik, buildRwVorschau } from "./KlageWizard.jsx";

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
    const t = buildRwVorschau("", 100, 500, false, "gegnerisch", [VERS, MANN]);
    expect(t).toContain("Die Beklagten haben eine Teilregulierung");
    expect(t).not.toContain("zu 2)");
  });
  it("keine Regulierung bei maennlichem Beklagten", () => {
    const t = buildRwVorschau("", 100, 0, false, "gegnerisch", [MANN]);
    expect(t).toContain("Der Beklagte hat bislang keine Regulierung vorgenommen.");
  });
});
