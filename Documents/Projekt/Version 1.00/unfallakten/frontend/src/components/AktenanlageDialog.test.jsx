import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../api.js", () => ({
  apiAktenanlage: {
    anlegen: vi.fn(),
    adressSuche: vi.fn().mockResolvedValue({ treffer: [] }),
    adressDetail: vi.fn(),
    gutachterVorlage: vi.fn(),
  },
}));

import AktenanlageDialog, {
  LEERES_FORMULAR, mischeVorbefuellung, validiereFormular, baueVorbefuellung,
} from "./AktenanlageDialog.jsx";

describe("validiereFormular", () => {
  it("meldet fehlenden Nachnamen und fehlendes Unfalldatum", () => {
    const e = validiereFormular(LEERES_FORMULAR);
    expect(e.nachname).toBeTruthy();
    expect(e.unfalldatum).toBeTruthy();
  });
  it("ist leer bei gefuellten Pflichtfeldern", () => {
    const f = mischeVorbefuellung({
      mandant: { nachname: "Zejli" },
      unfall: { unfalldatum: "2026-04-10" },
    });
    expect(validiereFormular(f)).toEqual({});
  });
});

describe("baueVorbefuellung", () => {
  const detail = {
    parse: {
      felder: {
        auftraggeber_anrede: "herr",
        auftraggeber_vorname: "Abdessamad",
        auftraggeber_nachname: "Achkour Zejli",
        auftraggeber_strasse: "Wiener Straße 61",
        auftraggeber_plz: "60599",
        auftraggeber_ort: "Frankfurt am Main",
        schadendatum: "2026-04-10",
        kennzeichen: "F-RX 4243",
        versicherung_name: "KRAVAG",
        schadennummer_versicherung: "45-11",
        sv_buero: "SVB Cassese",
        auftragsnummer: "GA-202604-1189",
      },
    },
  };
  it("mappt Gutachten-Felder in das Formular", () => {
    const f = baueVorbefuellung(detail, null);
    expect(f.mandant.nachname).toBe("Achkour Zejli");
    expect(f.mandant.plz).toBe("60599");
    expect(f.unfall.unfalldatum).toBe("2026-04-10");
    expect(f.unfall.kennzeichen).toBe("F-RX 4243");
    expect(f.versicherung.name).toBe("KRAVAG");
    expect(f.versicherung.schadennummer).toBe("45-11");
    expect(f.gutachter.bezeichnung).toBe("SVB Cassese");
    expect(f.gutachter.gutachten_nr).toBe("GA-202604-1189");
  });
  it("Identifier-Treffer ueberschreibt Gutachter-Bezeichnung und Adresse", () => {
    const info = {
      name: "KFZ-SV-Büro Cassese",
      adresse: { strasse: "Frankfurter Straße 97", plz: "63067",
                 ort: "Offenbach", telefon: "0151", email: "i@c.de" },
    };
    const f = baueVorbefuellung(detail, info);
    expect(f.gutachter.bezeichnung).toBe("KFZ-SV-Büro Cassese");
    expect(f.gutachter.plz).toBe("63067");
  });
  it("kommt mit leerem Detail klar", () => {
    const f = baueVorbefuellung(null, null);
    expect(f.mandant.nachname).toBe("");
  });
});

describe("AktenanlageDialog Rendering", () => {
  it("zeigt Pflichtfelder und Buttons", () => {
    render(<AktenanlageDialog onClose={() => {}} onAngelegt={() => {}} />);
    expect(screen.getByText("Neue Akte anlegen (RA-MICRO)")).toBeTruthy();
    expect(screen.getAllByText(/Nachname/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Unfalldatum/)).toBeTruthy();
    expect(screen.getByText("Akte anlegen")).toBeTruthy();
    expect(screen.getByText("Abbrechen")).toBeTruthy();
  });
});
