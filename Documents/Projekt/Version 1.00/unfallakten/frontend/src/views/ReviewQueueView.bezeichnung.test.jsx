import { describe, it, expect } from "vitest";
import { effektiveBezeichnung, naechsterFormState } from "./ReviewQueueView.jsx";

describe("effektiveBezeichnung", () => {
  it("nimmt gespeicherten Wert, wenn gesetzt", () => {
    expect(effektiveBezeichnung({ bezeichnung: "Mein Titel",
      bezeichnung_vorschlag: "Vorschlag" })).toBe("Mein Titel");
  });
  it("faellt auf Vorschlag zurueck, wenn nicht gesetzt", () => {
    expect(effektiveBezeichnung({ bezeichnung: null,
      bezeichnung_vorschlag: "Rechnung X" })).toBe("Rechnung X");
  });
  it("leerer String bei fehlenden Werten", () => {
    expect(effektiveBezeichnung({})).toBe("");
  });
});

describe("naechsterFormState liefert bezeichnung", () => {
  it("aus effektiveBezeichnung", () => {
    const f = naechsterFormState({ bezeichnung: null,
      bezeichnung_vorschlag: "Gutachten vom 01.01.2026",
      parse: { akten_kandidaten: [] } }, {});
    expect(f.bezeichnung).toBe("Gutachten vom 01.01.2026");
  });
  it("null bei skipFormReset", () => {
    expect(naechsterFormState({}, { skipFormReset: true })).toBe(null);
  });
});
