import { describe, it, expect } from "vitest";
import { dokumentAnzeige } from "./utils.js";

describe("dokumentAnzeige – nutzersichtbarer Dokumentname", () => {
  it("bevorzugt die Bezeichnung vor dem Dateinamen", () => {
    expect(dokumentAnzeige({
      id: 53279,
      dateiname: "f03d3379e8ddae9825e1dcba49f8dbf4948658a97329cf117584918cb6964503.pdf",
      bezeichnung: "Abrechnungsschreiben AXA vom 30.06.2026",
    })).toBe("Abrechnungsschreiben AXA vom 30.06.2026");
  });

  it("nutzt den Dateinamen, wenn keine Bezeichnung gesetzt ist", () => {
    expect(dokumentAnzeige({ id: 7, dateiname: "Gutachten_Mueller.pdf" }))
      .toBe("Gutachten_Mueller.pdf");
  });

  it("faellt bei Hash-Dateinamen ohne Bezeichnung auf die Dokumentenklasse zurueck", () => {
    expect(dokumentAnzeige({
      id: 42,
      dateiname: "15cd8ad3cb37fa0dedbd3d5a23dfb8173ada2aa673d706ac5f725617d7c94c2c.pdf",
      dokumentenklasse: "gutachten",
    })).toBe("Gutachten (Nr. 42)");
  });

  it("nutzt den Typ, wenn keine Dokumentenklasse gesetzt ist", () => {
    expect(dokumentAnzeige({
      id: 43,
      dateiname: "b19c1c507f9675b2f91fc9b1a25f0d56fc32f4ca0c91bb116003eba31a8c7cef.pdf",
      typ: "abrechnungsschreiben",
    })).toBe("Abrechnungsschreiben (Nr. 43)");
  });

  it("zeigt bei Hash ohne jede Klasse wenigstens die Dokumentnummer", () => {
    expect(dokumentAnzeige({
      id: 44,
      dateiname: "048afefc40088c77d5a2134600d5d9701827cca61e4951e0d87fe143d3839285.pdf",
      typ: "sonstiges",
    })).toBe("Dokument Nr. 44");
  });

  it("kennt die Beleg-Feldnamen dokument_id und dok_id", () => {
    expect(dokumentAnzeige({
      dok_id: 99,
      dateiname: "a9f4138f948a664e3c27673fb2c7db9f332f8f2605c08b96d71961854345459f.pdf",
      dokumentenklasse: "sv_rechnung",
    })).toBe("SV-/Gutachterrechnung (Nr. 99)");
  });

  it("leere Bezeichnung zaehlt nicht als Bezeichnung", () => {
    expect(dokumentAnzeige({ id: 5, dateiname: "Rechnung.pdf", bezeichnung: "   " }))
      .toBe("Rechnung.pdf");
  });

  it("liefert fuer null einen Platzhalter", () => {
    expect(dokumentAnzeige(null)).toBe("Dokument");
  });
});
