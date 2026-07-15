import { describe, it, expect } from "vitest";
import { effektiveBezeichnung, naechsterFormState, bezeichnungGeaendert } from "./ReviewQueueView.jsx";

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

describe("bezeichnungGeaendert", () => {
  it("unveraenderter Vorschlag (nichts gespeichert) -> false", () => {
    const detail = { bezeichnung: null, bezeichnung_vorschlag: "Rechnung X" };
    expect(bezeichnungGeaendert(detail, "Rechnung X")).toBe(false);
  });
  it("Text abweichend vom Vorschlag -> true", () => {
    const detail = { bezeichnung: null, bezeichnung_vorschlag: "Rechnung X" };
    expect(bezeichnungGeaendert(detail, "Rechnung Y")).toBe(true);
  });
  it("gespeicherter Wert vorhanden, wert gleich -> false", () => {
    const detail = { bezeichnung: "Mein Titel", bezeichnung_vorschlag: "Vorschlag" };
    expect(bezeichnungGeaendert(detail, "Mein Titel")).toBe(false);
  });
  it("gespeicherter Wert vorhanden, wert geaendert -> true", () => {
    const detail = { bezeichnung: "Mein Titel", bezeichnung_vorschlag: "Vorschlag" };
    expect(bezeichnungGeaendert(detail, "Neuer Titel")).toBe(true);
  });
  it("Leeren erlaubt Rueckkehr zum Vorschlag -> true", () => {
    const detail = { bezeichnung: null, bezeichnung_vorschlag: "Rechnung X" };
    expect(bezeichnungGeaendert(detail, "")).toBe(true);
  });
  it("nur Whitespace-Unterschied -> false (beide getrimmt)", () => {
    const detail = { bezeichnung: null, bezeichnung_vorschlag: "Rechnung X" };
    expect(bezeichnungGeaendert(detail, "Rechnung X   ")).toBe(false);
  });
});
