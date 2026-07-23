import { describe, it, expect } from "vitest";
import { ersetzePlatzhalter, genusKontext } from "./platzhalterLogik.js";

describe("ersetzePlatzhalter (wortgleich zu backend ersetze_platzhalter)", () => {
  it("ersetzt bekannte Platzhalter", () => {
    expect(ersetzePlatzhalter("Hallo <MANDANT>!", { MANDANT: "Eva Muster" }))
      .toBe("Hallo Eva Muster!");
  });

  it("leere Werte werden zu leerem String", () => {
    expect(ersetzePlatzhalter("<ANREDE> Muster", { ANREDE: "" }))
      .toBe(" Muster");
  });

  it("unbekannte Platzhalter werden als FEHLT markiert", () => {
    expect(ersetzePlatzhalter("Betrag: <UNBEKANNT>", {}))
      .toBe("Betrag: [FEHLT: <UNBEKANNT>]");
  });

  it("leerer Text bleibt unangetastet", () => {
    expect(ersetzePlatzhalter("", { X: "y" })).toBe("");
    expect(ersetzePlatzhalter(null, { X: "y" })).toBe(null);
  });
});

describe("genusKontext", () => {
  it("maennlich als Default", () => {
    const k = genusKontext(false);
    expect(k.PRON).toBe("er");
    expect(k.POSS_EM).toBe("seinem");
    expect(k.ANREDE_DEKL).toBe("Herrn");
  });

  it("weiblich", () => {
    const k = genusKontext(true);
    expect(k.PRON).toBe("sie");
    expect(k.POSS_EM).toBe("ihrem");
    expect(k.PRON_DAT).toBe("ihr");
  });

  it("beide Genera tragen dieselben Schluessel", () => {
    expect(Object.keys(genusKontext(false)).sort())
      .toEqual(Object.keys(genusKontext(true)).sort());
    expect(Object.keys(genusKontext(false))).toHaveLength(18);
  });

  it("Mandant- und Artikel-Formen", () => {
    expect(genusKontext(false).MANDANT_NOM).toBe("Mandant");
    expect(genusKontext(true).MANDANT_NOM).toBe("Mandantin");
    expect(genusKontext(false).MANDANT_OBL).toBe("Mandanten");
    expect(genusKontext(true).UNSERES).toBe("unserer");
    expect(genusKontext(false).PRON_GROSS).toBe("Er");
  });
});
