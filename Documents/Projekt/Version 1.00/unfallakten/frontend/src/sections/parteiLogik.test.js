import { describe, it, expect } from "vitest";
import {
  istPersonPartei,
  istFirmenPartei,
  parteiAnzeigeName,
  organBezeichnung,
} from "./parteiLogik.js";

const FAHRER = { vorname: "Kadir", name: "Kuzaytepe", versicherung: "ADAC" };
const VERS_NAMENSFELD = { vorname: "", name: "ADAC Autoversicherung AG", versicherung: "ADAC Autoversicherung AG" };
const VERS_NUR_FELD = { versicherung: "Test-Versicherung AG" };
const FIRMA = { firma: "Autohaus Müller GmbH" };

describe("istPersonPartei", () => {
  it("Person nur bei vorhandenem Vornamen", () => {
    expect(istPersonPartei(FAHRER)).toBe(true);
    expect(istPersonPartei(VERS_NAMENSFELD)).toBe(false);
    expect(istPersonPartei(VERS_NUR_FELD)).toBe(false);
    expect(istPersonPartei(FIRMA)).toBe(false);
    expect(istPersonPartei({ vorname: "   " })).toBe(false);
    expect(istPersonPartei(null)).toBe(false);
  });
});

describe("istFirmenPartei", () => {
  it("Versicherer mit Firmenname im Namensfeld ist Firma (Lookup-Button-Fall 828/24)", () => {
    expect(istFirmenPartei({ ...VERS_NAMENSFELD, rolle: "gegner" })).toBe(true);
  });
  it("Person mit Vornamen ist keine Firma, auch mit Versicherungsfeld", () => {
    expect(istFirmenPartei({ ...FAHRER, rolle: "gegner" })).toBe(false);
  });
  it("firma-/versicherung-Feld reicht", () => {
    expect(istFirmenPartei({ ...FIRMA, rolle: "gegner" })).toBe(true);
    expect(istFirmenPartei({ ...VERS_NUR_FELD, rolle: "gegner" })).toBe(true);
  });
  it("Mandant mit blossem Nachnamen ist keine Firma", () => {
    expect(istFirmenPartei({ name: "Caporiccio", rolle: "mandant" })).toBe(false);
  });
});

describe("parteiAnzeigeName", () => {
  it("Person hat Vorrang vor Versicherungs-/Firmenname", () => {
    expect(parteiAnzeigeName(FAHRER)).toBe("Kadir Kuzaytepe");
  });
  it("Versicherung mit Firmenname im Namensfeld", () => {
    expect(parteiAnzeigeName(VERS_NAMENSFELD)).toBe("ADAC Autoversicherung AG");
  });
  it("Fallback-Kette name -> firma -> versicherung", () => {
    expect(parteiAnzeigeName(VERS_NUR_FELD)).toBe("Test-Versicherung AG");
    expect(parteiAnzeigeName(FIRMA)).toBe("Autohaus Müller GmbH");
    expect(parteiAnzeigeName({})).toBe("Unbekannt");
    expect(parteiAnzeigeName(null)).toBe("Unbekannt");
  });
});

describe("organBezeichnung", () => {
  it("GmbH/GbR/KG/OHG -> Geschäftsführer", () => {
    expect(organBezeichnung("Autohaus Müller GmbH")).toBe("den/die Geschäftsführer");
    expect(organBezeichnung("Praxis GbR")).toBe("den/die Geschäftsführer");
  });
  it("AG/SE/KGaA -> Vorstand", () => {
    expect(organBezeichnung("ADAC Autoversicherung AG")).toBe("den Vorstand");
    expect(organBezeichnung("Muster SE")).toBe("den Vorstand");
  });
  it("sonst gesetzlicher Vertreter; AG nicht als Substring", () => {
    expect(organBezeichnung("ADAC")).toBe("den gesetzlichen Vertreter");
    expect(organBezeichnung("")).toBe("den gesetzlichen Vertreter");
  });
});
