import { describe, it, expect } from "vitest";
import {
  anredeNorm, kanonischeBeklagte, beklagtenGrammatik, versichererSuffix,
  buildSachverhaltText, buildRwVorschau, baueAntraegeText, ANTRAEGE_PLACEHOLDER,
} from "./KlageWizard.jsx";

const VERS = { rolle_klage: "beklagter", versicherung: "Test-Versicherung AG", checked: true };
const MANN = { rolle_klage: "beklagter", name: "Huber", vorname: "Hans", anrede: "Herr", checked: true };
const FRAU_HALTER = { rolle_klage: "beklagter", name: "Meier", vorname: "Eva", anrede: "2", ist_halter: 1, checked: true };
const KLAEGER = { rolle_klage: "klaeger", name: "Mustermann", checked: true };

describe("anredeNorm", () => {
  it("versteht numerisch und Klartext", () => {
    expect(anredeNorm("1")).toBe("herr");
    expect(anredeNorm("2")).toBe("frau");
    expect(anredeNorm("Herr")).toBe("herr");
    expect(anredeNorm("")).toBe("");
  });
});

describe("kanonischeBeklagte (KW-20)", () => {
  it("filtert Klaeger und abgewaehlte, behaelt Reihenfolge", () => {
    const liste = [KLAEGER, VERS, { ...MANN, checked: false }, FRAU_HALTER];
    expect(kanonischeBeklagte(liste)).toEqual([VERS, FRAU_HALTER]);
  });
  it("checked=null zaehlt als angehakt (Backend-Default)", () => {
    expect(kanonischeBeklagte([{ rolle_klage: "beklagter", name: "X" }])).toHaveLength(1);
  });
});

describe("beklagtenGrammatik (KW-06)", () => {
  it("mehrere -> Gesamtschuldner", () => {
    const g = beklagtenGrammatik([VERS, MANN]);
    expect(g.verurteilt).toBe("Die Beklagten werden als Gesamtschuldner verurteilt");
    expect(g.verpflichtet).toBe("die Beklagten als Gesamtschuldner verpflichtet sind");
    expect(g.kosten).toBe("Die Beklagten tragen die Kosten des Rechtsstreits.");
  });
  it("einzelner Mann -> maskulin", () => {
    expect(beklagtenGrammatik([MANN]).verurteilt).toBe("Der Beklagte wird verurteilt");
  });
  it("einzelne Versicherung -> wie bisher", () => {
    expect(beklagtenGrammatik([VERS]).verurteilt).toBe("Die Beklagte wird verurteilt");
  });
});

describe("versichererSuffix", () => {
  it("nennt die Nummer der Versicherung in der kanonischen Liste", () => {
    expect(versichererSuffix([MANN, VERS])).toBe(" zu 2)");
    expect(versichererSuffix([VERS, MANN])).toBe(" zu 1)");
  });
  it("leer bei nur einem Beklagten", () => {
    expect(versichererSuffix([VERS])).toBe("");
  });
});

describe("buildSachverhaltText (KW-20)", () => {
  const basis = {
    klaeger: "Der Kläger", vorsteuer: false,
    unfalldatum: "01.02.2026", unfallort: "Offenbach",
    aktLegTyp: "eigentum", aktLegFreigabe: "freigabe", aktLegDatum: "",
    mandantKz: "OF-AB 1", mandantIstFahrer: false, auslandsunfall: false,
  };
  it("Nummerierung folgt der kanonischen Reihenfolge (= Rubrum)", () => {
    const text = buildSachverhaltText({ ...basis, beklagte: [VERS, MANN] });
    expect(text).toContain("Die Beklagte zu 1) ist die gegnerische Haftpflichtversicherung");
    expect(text).toContain("Der Beklagte zu 2) war zum Unfallzeitpunkt der Fahrer");
  });
  it("Nicht-Halter-Privatperson fehlt nicht mehr; Versicherung mit ist_halter nicht doppelt", () => {
    const versHalter = { ...VERS, ist_halter: 1 };
    const text = buildSachverhaltText({ ...basis, beklagte: [versHalter, MANN] });
    const saetze = text.split("\n").filter(z => z.includes("Beklagte"));
    expect(saetze).toHaveLength(2);
    expect(text).toContain("zu 2) war zum Unfallzeitpunkt der Fahrer");
  });
  it("Halterin mit korrektem Genus", () => {
    const text = buildSachverhaltText({ ...basis, beklagte: [VERS, FRAU_HALTER] });
    expect(text).toContain("Die Beklagte zu 2) ist die Halterin des unfallverursachenden Fahrzeugs.");
  });
});

describe("Firmen-Halter-Klassifikation (Abschluss-Review-Fix)", () => {
  const FIRMA_HALTER = { rolle_klage: "beklagter", firma: "Spedition Krause GmbH", ist_halter: 1, checked: true };
  const basisFuerSachverhalt = {
    klaeger: "Der Kläger", vorsteuer: false,
    unfalldatum: "01.02.2026", unfallort: "Offenbach",
    aktLegTyp: "eigentum", aktLegFreigabe: "freigabe", aktLegDatum: "",
    mandantKz: "OF-AB 1", mandantIstFahrer: false, auslandsunfall: false,
  };
  it("buildSachverhaltText: Halter-GmbH bekommt Halter-Satz, nicht Versicherungssatz", () => {
    const text = buildSachverhaltText({ ...basisFuerSachverhalt, beklagte: [VERS, FIRMA_HALTER] });
    expect(text).toContain("Die Beklagte zu 2) ist die Halterin des unfallverursachenden Fahrzeugs.");
    expect(text).not.toContain("zu 2) ist die gegnerische Haftpflichtversicherung");
  });
  it("versichererSuffix überspringt den Firmen-Halter", () => {
    expect(versichererSuffix([FIRMA_HALTER, VERS])).toBe(" zu 2)");
  });
});

describe("buildRwVorschau hq=100 Referenzpartei (Fix-Wave)", () => {
  it("Nummer UND Genus zeigen auf die Versicherung, auch wenn sie nicht erste ist", () => {
    const text = buildRwVorschau("", 100, 0, false, "gegnerisch", [MANN, VERS]);
    expect(text).toContain("Die alleinige Haftung der Beklagten zu 2) steht außer Frage.");
    expect(text).toContain("bei der Beklagten zu 2) versicherten Fahrzeug");
    expect(text).not.toContain("des Beklagten zu 2)");
  });
});

describe("beklagtenGrammatik leere Liste", () => {
  it("wirft nicht und fällt auf feminine Singular-Form zurück", () => {
    expect(beklagtenGrammatik([]).verurteilt).toBe("Die Beklagte wird verurteilt");
  });
});

describe("baueAntraegeText (KW-06 FE)", () => {
  const POS = [{ key: "wertminderung", label: "WM", betrag: 400, betragOriginal: 400, checked: true }];
  const basis = { positionen: POS, mitSG: false, sgMind: 0, weiblich: false,
                  zinsenAb: "rechtshaengigkeit", verzug: "", unfalldatum: "01.02.2026",
                  mitFestSg: false, mitFestSach: false };

  it("mehrere Beklagte -> Gesamtschuldner, kein (zu 1)", () => {
    const text = baueAntraegeText({ ...basis, beklagte: [VERS, MANN] });
    expect(text).toContain("Die Beklagten werden als Gesamtschuldner verurteilt, an den Kläger 400,00 €");
    expect(text).toContain("Die Beklagten tragen die Kosten des Rechtsstreits.");
    expect(text).not.toContain("(zu 1)");
    expect(text).toContain(ANTRAEGE_PLACEHOLDER);
  });

  it("Feststellungsantrag plural", () => {
    const text = baueAntraegeText({ ...basis, beklagte: [VERS, MANN], mitFestSach: true });
    expect(text).toContain("dass die Beklagten als Gesamtschuldner verpflichtet sind,");
  });

  it("einzelner maennlicher Beklagter -> maskulin", () => {
    const text = baueAntraegeText({ ...basis, beklagte: [MANN] });
    expect(text).toContain("Der Beklagte wird verurteilt, an den Kläger 400,00 €");
    expect(text).toContain("Der Beklagte trägt die Kosten des Rechtsstreits.");
  });

  it("einzelne Versicherung -> unveraendert wie bisher", () => {
    const text = baueAntraegeText({ ...basis, beklagte: [VERS] });
    expect(text).toContain("Die Beklagte wird verurteilt, an den Kläger 400,00 €");
    expect(text).toContain("Die Beklagte trägt die Kosten des Rechtsstreits.");
  });
});
