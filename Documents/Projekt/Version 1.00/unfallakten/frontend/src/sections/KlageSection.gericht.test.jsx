import { describe, it, expect, vi } from "vitest";

vi.mock("../api.js", () => ({
  akten: {},
  apiKlage: { gerichtSpeichern: vi.fn() },
  apiGebuehren: {},
  apiFirmen: {},
  beteiligte: {},
}));

import { apiKlage } from "../api.js";
import { gerichtSpeichernOderWarnen } from "./KlageSection.jsx";

describe("gerichtSpeichernOderWarnen (KW-27 Nachtrag)", () => {
  it("liefert eine lesbare Warnung, wenn die Persistenz fehlschlaegt (z.B. IntegrityError/HTTP 500 bei alter rolle-CHECK-Constraint ohne 'gericht')", async () => {
    apiKlage.gerichtSpeichern.mockRejectedValueOnce({ status: 500, message: "Internal Server Error" });
    const warnung = await gerichtSpeichernOderWarnen(42, { name: "AG Offenbach" });
    expect(warnung).toMatch(/nicht in der Akte gespeichert/i);
    expect(warnung).toMatch(/nur für diese Sitzung/i);
  });

  it("liefert keine Warnung, wenn die Persistenz erfolgreich ist", async () => {
    apiKlage.gerichtSpeichern.mockResolvedValueOnce({ ok: true });
    const warnung = await gerichtSpeichernOderWarnen(42, { name: "AG Offenbach" });
    expect(warnung).toBeNull();
  });
});

import { gerichtQuelleText } from "./KlageSection.jsx";

describe("gerichtQuelleText – Herkunft des Gerichtsvorschlags", () => {
  it("weist ein in der Akte gespeichertes Gericht aus", () => {
    expect(gerichtQuelleText("akte", "Offenbach").text).toMatch(/in akte gespeichert/i);
  });

  it("nennt die gepflegte Ortsliste als sichere Quelle", () => {
    const q = gerichtQuelleText("ortsliste", "Heusenstamm");
    expect(q.text).toMatch(/ortsliste/i);
    expect(q.text).toMatch(/Heusenstamm/);
    expect(q.text).not.toMatch(/bitte prüfen/i);
  });

  it("kennzeichnet den Namensabgleich als pruefbeduerftig", () => {
    const q = gerichtQuelleText("unfallort_match", "Offenbach");
    expect(q.text).toMatch(/bitte prüfen/i);
    expect(q.text).toMatch(/Offenbach/);
  });

  it("kommt ohne Unfallort aus", () => {
    expect(gerichtQuelleText("unfallort_match", "").text).toMatch(/bitte prüfen/i);
    expect(gerichtQuelleText("ortsliste", null).text).toMatch(/ortsliste/i);
  });

  it("faellt bei unbekannter Quelle auf die manuelle Wahl zurueck", () => {
    expect(gerichtQuelleText("irgendwas", "").text).toMatch(/manuell/i);
  });
});
