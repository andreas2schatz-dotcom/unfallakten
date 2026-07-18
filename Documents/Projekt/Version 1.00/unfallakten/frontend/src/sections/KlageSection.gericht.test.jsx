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
