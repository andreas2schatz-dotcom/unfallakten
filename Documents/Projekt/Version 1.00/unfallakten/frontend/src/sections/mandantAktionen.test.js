import { describe, it, expect, vi } from "vitest";

vi.mock("../api.js", () => ({
  tokenStore: { getAccess: () => "tok" },
}));

import { ibanAnfrageMailto, vollmachtAnfrageMailto } from "./mandantAktionen.js";

describe("mandantAktionen", () => {
  it("baut den IBAN-Anfrage-Link mit Anrede aus den Checks", () => {
    const link = ibanAnfrageMailto(
      { mandant_email: "max@example.com", mandant_name: "Max Müller" },
      { anrede: "Herr" }
    );
    expect(link).toMatch(/^mailto:max@example\.com\?subject=/);
    expect(decodeURIComponent(link)).toContain("Sehr geehrter Herr Müller,");
    expect(decodeURIComponent(link)).toContain("Bankverbindung");
  });

  it("nutzt die neutrale Anrede ohne Anredefeld", () => {
    const link = vollmachtAnfrageMailto({}, { email: "erika@example.com", name: "Erika Beispiel" });
    expect(link).toMatch(/^mailto:erika@example\.com/);
    expect(decodeURIComponent(link)).toContain("Sehr geehrte/r Erika Beispiel,");
    expect(decodeURIComponent(link)).toContain("Vollmacht");
  });
});
