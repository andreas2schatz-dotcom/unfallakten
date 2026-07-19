import { describe, it, expect, vi } from "vitest";

vi.mock("../api.js", () => ({
  akten: {},
  apiKlage: { entwurfSpeichern: vi.fn() },
  apiGebuehren: {},
  apiFirmen: {},
  beteiligte: {},
}));

import { apiKlage } from "../api.js";
import { entwurfSpeichernRemote } from "./KlageSection.jsx";
import { ENTWURF_FORMAT_VERSION } from "./klageEntwurfLogik.js";

describe("entwurfSpeichernRemote", () => {
  it("sendet entwurf + format_version und liefert gespeichert_am zurueck", async () => {
    apiKlage.entwurfSpeichern.mockResolvedValueOnce({
      ok: true, gespeichert_am: "2026-07-19 14:32:05",
    });
    const r = await entwurfSpeichernRemote("61/26", { wizardStep: 3 });
    expect(apiKlage.entwurfSpeichern).toHaveBeenCalledWith("61/26", {
      entwurf: { wizardStep: 3 },
      format_version: ENTWURF_FORMAT_VERSION,
    });
    expect(r).toEqual({ ok: true, gespeichertAm: "2026-07-19 14:32:05" });
  });

  it("liefert bei Fehlern eine lesbare Warnung statt zu werfen", async () => {
    apiKlage.entwurfSpeichern.mockRejectedValueOnce({ status: 500, message: "kaputt" });
    const r = await entwurfSpeichernRemote("61/26", { wizardStep: 3 });
    expect(r.ok).toBe(false);
    expect(r.fehler).toMatch(/nicht gespeichert/i);
  });
});
