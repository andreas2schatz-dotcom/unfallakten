import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EinwaendeAuswahl, StepEinwaende } from "./KlageWizard.jsx";

const KUERZUNGSARTEN = [
  { id: 1, bezeichnung: "Stundenverrechnungssatz", kategorie: "reparatur", varianten: [] },
  { id: 2, bezeichnung: "Verbringungskosten", kategorie: "reparatur", varianten: [] },
];
const ABRECHNUNGEN = [{
  gesamt_reguliert: "1000",
  positionen: [{ kuerzungsart_id: 1, betrag_gefordert: "500", betrag_reguliert: "300" }],
}];

describe("EinwaendeAuswahl", () => {
  it("erfasste Kuerzungsarten sind vorausgewaehlt", () => {
    render(<EinwaendeAuswahl abrechnungen={ABRECHNUNGEN} kuerzungsarten={KUERZUNGSARTEN}
      beklagte={[]} onUebernehmen={() => {}} />);
    expect(screen.getByText(/1 ausgewählt/)).toBeTruthy();
  });

  it("Text uebernehmen liefert Block mit Bezeichnung und Kuerzungsbetrag", () => {
    const onUebernehmen = vi.fn();
    render(<EinwaendeAuswahl abrechnungen={ABRECHNUNGEN} kuerzungsarten={KUERZUNGSARTEN}
      beklagte={[]} onUebernehmen={onUebernehmen} />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    const text = onUebernehmen.mock.calls[0][0];
    expect(text).toContain("Stundenverrechnungssatz");
    expect(text).toContain("200,00");
  });

  it("leere Auswahl liefert leeren String", () => {
    const onUebernehmen = vi.fn();
    render(<EinwaendeAuswahl abrechnungen={[]} kuerzungsarten={KUERZUNGSARTEN}
      beklagte={[]} onUebernehmen={onUebernehmen} />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    expect(onUebernehmen).toHaveBeenCalledWith("");
  });
});

describe("StepEinwaende", () => {
  it("ohne erfasste Kuerzungen: Hinweis statt Auswahlliste, Textkarte bleibt", () => {
    render(<StepEinwaende abrechnungen={[]} kuerzungsarten={KUERZUNGSARTEN} beklagte={[]}
      rwText="Grundtext" onRwText={() => {}} einwaendeBlock="" onEinwaendeBlock={() => {}}
      grundhaftungsText="Grundtext" />);
    expect(screen.getByText(/Keine Kürzungen der Versicherung erfasst/)).toBeTruthy();
    expect(screen.queryByText(/Text übernehmen/)).toBeNull();
    expect(screen.getByDisplayValue("Grundtext")).toBeTruthy();
  });

  it("Uebernehmen haengt Block an rwText an und meldet ihn als einwaendeBlock", () => {
    const onRwText = vi.fn(), onEinwaendeBlock = vi.fn();
    render(<StepEinwaende abrechnungen={ABRECHNUNGEN} kuerzungsarten={KUERZUNGSARTEN} beklagte={[]}
      rwText="Grundtext" onRwText={onRwText} einwaendeBlock="" onEinwaendeBlock={onEinwaendeBlock}
      grundhaftungsText="Grundtext" />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    const block = onEinwaendeBlock.mock.calls[0][0];
    expect(block).toContain("Stundenverrechnungssatz");
    expect(onRwText).toHaveBeenCalledWith(`Grundtext\n\n${block}`);
  });

  it("erneutes Uebernehmen ersetzt den alten Block statt anzuhaengen", () => {
    const onRwText = vi.fn();
    render(<StepEinwaende abrechnungen={ABRECHNUNGEN} kuerzungsarten={KUERZUNGSARTEN} beklagte={[]}
      rwText={"Grundtext\n\nALTER BLOCK"} onRwText={onRwText}
      einwaendeBlock="ALTER BLOCK" onEinwaendeBlock={() => {}}
      grundhaftungsText="Grundtext" />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    const neuerText = onRwText.mock.calls[0][0];
    expect(neuerText.startsWith("Grundtext\n\n")).toBe(true);
    expect(neuerText).not.toContain("ALTER BLOCK");
    expect(neuerText).toContain("Stundenverrechnungssatz");
  });

  it("haengt an, wenn der einwaendeBlock nicht mehr im rwText enthalten ist (Nutzer-Edit)", () => {
    const onRwText = vi.fn();
    render(<StepEinwaende abrechnungen={ABRECHNUNGEN} kuerzungsarten={KUERZUNGSARTEN} beklagte={[]}
      rwText={"Individuell bearbeiteter Text"} onRwText={onRwText}
      einwaendeBlock="ALTER BLOCK" onEinwaendeBlock={() => {}}
      grundhaftungsText="Grundtext" />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    const neuerText = onRwText.mock.calls[0][0];
    expect(neuerText.startsWith("Individuell bearbeiteter Text\n\n")).toBe(true);
    expect(neuerText).toContain("Stundenverrechnungssatz");
  });
});
