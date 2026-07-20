import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiFirmen } from "./api.js";

describe("apiFirmen.vertreterSpeichern", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({ ok: true }),
    });
    globalThis.localStorage = { getItem: () => null, setItem: () => {} };
  });

  it("sendet firma im Body mit", async () => {
    await apiFirmen.vertreterSpeichern(
      -1, "Stefan Daehne", "Vorstand", "ADAC Autoversicherung AG");
    const [, opts] = globalThis.fetch.mock.calls[0];
    const body = JSON.parse(opts.body);
    expect(body).toEqual({
      beteiligter_id: -1,
      vertreter_name: "Stefan Daehne",
      vertreter_funktion: "Vorstand",
      firma: "ADAC Autoversicherung AG",
    });
  });
});
