import { describe, it, expect } from "vitest";
import { initialeEreignisse, naechsterFormState } from "./ReviewQueueView.jsx";

describe("initialeEreignisse", () => {
  it("belegt mit dem Default vor", () => {
    expect(initialeEreignisse("rechnung_eingegangen")).toEqual([
      { typ: "rechnung_eingegangen" },
    ]);
  });
  it("liefert leere Liste ohne Default", () => {
    expect(initialeEreignisse(null)).toEqual([]);
    expect(initialeEreignisse(undefined)).toEqual([]);
  });
});

describe("naechsterFormState", () => {
  const detail = {
    default_ereignistyp: "rechnung_eingegangen",
    parse: { akten_kandidaten: [{ akte_az: "44/22" }] },
  };

  it("liefert Form-Defaults beim normalen Laden (Dokumentwechsel/Aktion)", () => {
    expect(naechsterFormState(detail)).toEqual({
      gewaehlteAkte: "44/22",
      ereignisse: [{ typ: "rechnung_eingegangen" }],
      bezeichnung: "",
      dirty: {},
    });
  });

  it("liefert null beim Poll-Refresh (skipFormReset) — offene Dialog-Eingaben bleiben erhalten", () => {
    expect(naechsterFormState(detail, { skipFormReset: true })).toBeNull();
  });

  it("ist robust gegen fehlende Kandidaten/Default", () => {
    expect(naechsterFormState({ parse: {} })).toEqual({
      gewaehlteAkte: "",
      ereignisse: [],
      bezeichnung: "",
      dirty: {},
    });
  });
});
