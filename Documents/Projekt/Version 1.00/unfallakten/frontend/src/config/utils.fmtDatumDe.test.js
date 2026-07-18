import { describe, it, expect } from "vitest";
import { fmtDatumDe } from "./utils.js";
import { baueAntraegeText } from "../sections/KlageWizard.jsx";

describe("fmtDatumDe (KW-09, wortgleich zu _fmt_datum)", () => {
  it("wandelt ISO in DD.MM.YYYY", () => expect(fmtDatumDe("2026-05-04")).toBe("04.05.2026"));
  it("laesst deutsches Datum unveraendert", () => expect(fmtDatumDe("04.05.2026")).toBe("04.05.2026"));
  it("leer -> leer", () => expect(fmtDatumDe("")).toBe(""));
  it("unbekanntes Format unveraendert", () => expect(fmtDatumDe("unbekannt")).toBe("unbekannt"));
});

describe("baueAntraegeText nutzt fmtDatumDe (KW-09)", () => {
  it("ISO-Verzugsdatum erscheint deutsch im Zinssatz", () => {
    const text = baueAntraegeText({
      positionen: [{ key: "wertminderung", label: "Wertminderung", betrag: 700, checked: true }],
      mitSG: false, sgMind: 0,
      beklagte: [{ rolle_klage: "beklagter", versicherung: "Test AG", checked: true }],
      weiblich: false, zinsenAb: "verzug", verzug: "2026-05-04",
      unfalldatum: "01.02.2026", mitFestSg: false, mitFestSach: false,
    });
    expect(text).toContain("seit dem 04.05.2026");
    expect(text).not.toContain("2026-05-04");
  });
});
