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

  it("bevorzugt das Schreibdatum (forderung_positionen) vor dem Upload-Zeitstempel", () => {
    const dok = { id: 7, datum: "2026-06-01", hochgeladen_am: "2026-06-20 09:30:00" };
    expect(verzugDatenAusDok(dok)).toEqual({
      dokDatum: "2026-06-01",
      eintritt: verzugEintrittDefault("2026-06-01"),
    });
  });

  it("faellt auf hochgeladen_am zurueck, wenn kein Schreibdatum vorhanden ist", () => {
    const dok = { id: 7, datum: null, hochgeladen_am: "2026-06-20 09:30:00" };
    expect(verzugDatenAusDok(dok)).toEqual({
      dokDatum: "2026-06-20",
      eintritt: verzugEintrittDefault("2026-06-20"),
    });
  });

  it("liefert null, wenn das Datum nicht parsebar ist (kein Clobber von wizardVerzugDatum)", () => {
    expect(verzugDatenAusDok({ id: 7, datum: "kein-datum" })).toBeNull();
  });
});
