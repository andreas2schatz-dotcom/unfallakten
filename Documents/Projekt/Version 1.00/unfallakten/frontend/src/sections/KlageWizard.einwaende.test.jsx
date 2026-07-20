import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EinwaendeAuswahl } from "./KlageWizard.jsx";

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
