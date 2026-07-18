import { describe, it, expect } from "vitest";
import { verzugDatenAusDok } from "./KlageSection.jsx";
import { verzugEintrittDefault } from "../config/utils.js";

describe("verzugDatenAusDok", () => {
  it("liefert Schreibdatum + Eintritt-Vorschlag (+14 Tage)", () => {
    const dok = { id: 7, hochgeladen_am: "2026-06-01 10:15:00" };
    expect(verzugDatenAusDok(dok)).toEqual({
      dokDatum: "2026-06-01",
      eintritt: verzugEintrittDefault("2026-06-01"),
    });
  });

  it("ohne Datum null (keine Wirkung)", () => {
    expect(verzugDatenAusDok({ id: 7 })).toBeNull();
    expect(verzugDatenAusDok(null)).toBeNull();
  });
});
