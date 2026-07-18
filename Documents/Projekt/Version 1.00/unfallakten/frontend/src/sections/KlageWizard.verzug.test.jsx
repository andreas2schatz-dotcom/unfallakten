import { describe, it, expect } from "vitest";
import { buildVerzugAutoText } from "./KlageWizard.jsx";
import { verzugEintrittDefault } from "../config/utils.js";

describe("buildVerzugAutoText (KW-10)", () => {
  it("nutzt Eintritt fuer den Eintrittssatz und Schreibdatum fuer den BEWEIS", () => {
    const t = buildVerzugAutoText("04.05.2026", "19.05.2026");
    expect(t).toContain("am 19.05.2026 eingetreten");
    expect(t).toContain("BEWEIS: Schreiben vom 04.05.2026");
  });
  it("ohne Eintritt -> Rechtshaengigkeit (Schreibdatum behauptet KEINEN Eintritt mehr)", () => {
    expect(buildVerzugAutoText("04.05.2026", "")).toBe("Verzug ist mit Rechtshängigkeit eingetreten.");
  });
  it("mit Eintritt, ohne Schreibdatum -> kein BEWEIS-Satz", () => {
    const t = buildVerzugAutoText("", "19.05.2026");
    expect(t).toContain("am 19.05.2026 eingetreten");
    expect(t).not.toContain("BEWEIS");
  });
});

describe("verzugEintrittDefault (KW-10)", () => {
  it("Schreibdatum + 14 Tage", () => expect(verzugEintrittDefault("04.05.2026")).toBe("18.05.2026"));
  it("ISO-Input wird verarbeitet", () => expect(verzugEintrittDefault("2026-05-04")).toBe("18.05.2026"));
  it("Monatsuebergang", () => expect(verzugEintrittDefault("20.12.2026")).toBe("03.01.2027"));
  it("leer -> leer", () => expect(verzugEintrittDefault("")).toBe(""));
});
