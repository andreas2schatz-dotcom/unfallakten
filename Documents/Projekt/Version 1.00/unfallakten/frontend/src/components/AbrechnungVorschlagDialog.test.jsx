import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import AbrechnungVorschlagDialog, { vorschlagBackendKey } from "./AbrechnungVorschlagDialog.jsx";

const VORSCHLAG = {
  dokument_id: 53279,
  bezeichnung: "Abrechnungsschreiben AXA vom 30.06.2026",
  datum: "2026-06-30",
  versicherung: "AXA Versicherung AG",
  referenz_nr: "90000810441",
  gesamtbetrag: 3719.53,
  warnungen: [],
  positionen: [
    { position_key: "fahrzeugschaden", roh_label: "fiktive Abrechnung", betrag_reguliert: 2697.19 },
    { position_key: "sv_kosten", roh_label: "Sachverständigenkosten", betrag_reguliert: 992.34 },
    { position_key: "kostenpauschale", roh_label: "Auslagenpauschale", betrag_reguliert: 30.0 },
  ],
};

const OPTIONEN = [
  { value: "fahrzeugschaden_netto", label: "Fahrzeugschaden", gefordert: 4882.48 },
  { value: "sv_kosten", label: "SV-Kosten", gefordert: 992.34 },
  { value: "unkostenpauschale", label: "Unkostenpauschale", gefordert: 30.0 },
  { value: "sonstiges", label: "Sonstiges", gefordert: 29.75 },
  // Position, die in dieser Akte (noch) nicht gefordert ist – muss trotzdem
  // zuordenbar sein, sonst laesst sich eine Zahlung darauf nicht buchen.
  { value: "nutzungsausfall", label: "Nutzungsausfall", gefordert: 0 },
];

function zeile(rohLabel) {
  return screen.getByTestId(`vorschlagzeile-${rohLabel}`);
}

describe("vorschlagBackendKey", () => {
  it("uebersetzt die Sammelzeile auf den Backend-Key", () => {
    expect(vorschlagBackendKey("fahrzeugschaden_netto")).toBe("fahrzeugschaden");
  });
  it("uebersetzt WDM-Sonderschaeden zurueck", () => {
    expect(vorschlagBackendKey("extra_wdm_ss3")).toBe("sonstiges_wdm_3");
  });
  it("laesst normale Keys unveraendert", () => {
    expect(vorschlagBackendKey("sv_kosten")).toBe("sv_kosten");
  });
});

describe("AbrechnungVorschlagDialog", () => {
  it("zeigt Kopfdaten und jede geparste Zeile", () => {
    render(<AbrechnungVorschlagDialog vorschlag={VORSCHLAG} positionsOptionen={OPTIONEN}
      onUebernehmen={() => {}} onAbbrechen={() => {}} />);
    expect(screen.getByText(/Abrechnungsschreiben AXA vom 30.06.2026/)).toBeInTheDocument();
    expect(screen.getByText(/AXA Versicherung AG/)).toBeInTheDocument();
    expect(zeile("fiktive Abrechnung")).toBeInTheDocument();
    expect(zeile("Sachverständigenkosten")).toBeInTheDocument();
    expect(zeile("Auslagenpauschale")).toBeInTheDocument();
  });

  it("waehlt die Sammelzeile fuer fahrzeugschaden vor", () => {
    render(<AbrechnungVorschlagDialog vorschlag={VORSCHLAG} positionsOptionen={OPTIONEN}
      onUebernehmen={() => {}} onAbbrechen={() => {}} />);
    const select = within(zeile("fiktive Abrechnung")).getByRole("combobox");
    expect(select.value).toBe("fahrzeugschaden_netto");
  });

  it("uebergibt die bestaetigten Positionen mit Backend-Keys", () => {
    const onUeber = vi.fn();
    render(<AbrechnungVorschlagDialog vorschlag={VORSCHLAG} positionsOptionen={OPTIONEN}
      onUebernehmen={onUeber} onAbbrechen={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /übernehmen/i }));

    expect(onUeber).toHaveBeenCalledTimes(1);
    const payload = onUeber.mock.calls[0][0];
    expect(payload.dokument_id).toBe(53279);
    expect(payload.datum).toBe("2026-06-30");
    expect(payload.versicherung).toBe("AXA Versicherung AG");
    expect(payload.referenz_nr).toBe("90000810441");
    expect(payload.positionen).toEqual([
      { position_key: "fahrzeugschaden", betrag_gefordert: 4882.48, betrag_reguliert: 2697.19 },
      { position_key: "sv_kosten", betrag_gefordert: 992.34, betrag_reguliert: 992.34 },
      { position_key: "unkostenpauschale", betrag_gefordert: 30.0, betrag_reguliert: 30.0 },
    ]);
  });

  it("laesst abgewaehlte Zeilen weg", () => {
    const onUeber = vi.fn();
    render(<AbrechnungVorschlagDialog vorschlag={VORSCHLAG} positionsOptionen={OPTIONEN}
      onUebernehmen={onUeber} onAbbrechen={() => {}} />);
    fireEvent.click(within(zeile("Auslagenpauschale")).getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /übernehmen/i }));
    expect(onUeber.mock.calls[0][0].positionen).toHaveLength(2);
  });

  it("uebernimmt den korrigierten Betrag", () => {
    const onUeber = vi.fn();
    render(<AbrechnungVorschlagDialog vorschlag={VORSCHLAG} positionsOptionen={OPTIONEN}
      onUebernehmen={onUeber} onAbbrechen={() => {}} />);
    const feld = within(zeile("Auslagenpauschale")).getByLabelText("Gezahlt");
    fireEvent.change(feld, { target: { value: "25,50" } });
    fireEvent.click(screen.getByRole("button", { name: /übernehmen/i }));
    const pos = onUeber.mock.calls[0][0].positionen.find(p => p.position_key === "unkostenpauschale");
    expect(pos.betrag_reguliert).toBe(25.5);
  });

  describe("nicht zugeordnete Zeile", () => {
    const OFFEN = {
      ...VORSCHLAG,
      dokument_id: 53278,
      bezeichnung: "Abrechnungsschreiben AXA vom 28.07.2026",
      warnungen: ["Summe der Positionen weicht vom Gesamtbetrag ab"],
      positionen: [
        { position_key: "nutzungsausfall", roh_label: "Nutzungsausfallentschädigung", betrag_reguliert: 43 },
        { position_key: null, roh_label: "Kosten für die Reparaturbestätigung", betrag_reguliert: 29.75 },
      ],
    };

    it("startet unausgewaehlt und blockiert die Uebernahme nicht", () => {
      const onUeber = vi.fn();
      render(<AbrechnungVorschlagDialog vorschlag={OFFEN} positionsOptionen={OPTIONEN}
        onUebernehmen={onUeber} onAbbrechen={() => {}} />);
      const cb = within(zeile("Kosten für die Reparaturbestätigung")).getByRole("checkbox");
      expect(cb.checked).toBe(false);
      fireEvent.click(screen.getByRole("button", { name: /übernehmen/i }));
      expect(onUeber.mock.calls[0][0].positionen).toEqual([
        { position_key: "nutzungsausfall", betrag_gefordert: 0, betrag_reguliert: 43 },
      ]);
    });

    it("laesst sich nach Zuordnung mitnehmen", () => {
      const onUeber = vi.fn();
      render(<AbrechnungVorschlagDialog vorschlag={OFFEN} positionsOptionen={OPTIONEN}
        onUebernehmen={onUeber} onAbbrechen={() => {}} />);
      const row = zeile("Kosten für die Reparaturbestätigung");
      fireEvent.change(within(row).getByRole("combobox"), { target: { value: "sonstiges" } });
      fireEvent.click(within(row).getByRole("checkbox"));
      fireEvent.click(screen.getByRole("button", { name: /übernehmen/i }));
      expect(onUeber.mock.calls[0][0].positionen).toContainEqual(
        { position_key: "sonstiges", betrag_gefordert: 29.75, betrag_reguliert: 29.75 });
    });

    it("zeigt die Parser-Warnung an", () => {
      render(<AbrechnungVorschlagDialog vorschlag={OFFEN} positionsOptionen={OPTIONEN}
        onUebernehmen={() => {}} onAbbrechen={() => {}} />);
      expect(screen.getByText(/Summe der Positionen weicht vom Gesamtbetrag ab/))
        .toBeInTheDocument();
    });
  });

  it("sperrt Uebernehmen, wenn keine Zeile ausgewaehlt ist", () => {
    render(<AbrechnungVorschlagDialog vorschlag={VORSCHLAG} positionsOptionen={OPTIONEN}
      onUebernehmen={() => {}} onAbbrechen={() => {}} />);
    VORSCHLAG.positionen.forEach(p => {
      fireEvent.click(within(zeile(p.roh_label)).getByRole("checkbox"));
    });
    expect(screen.getByRole("button", { name: /übernehmen/i })).toBeDisabled();
  });
});
