import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EinwaendeAuswahl } from "./KlageWizard.jsx";

const ABRECHNUNGEN = [{
  gesamt_reguliert: "1000",
  positionen: [{ kuerzungsart_id: 1, betrag_gefordert: "500", betrag_reguliert: "300" }],
}];

function kuerzungsart(extra = {}) {
  return { id: 1, bezeichnung: "Stundenverrechnungssatz", kategorie: "reparatur", varianten: [], ...extra };
}

describe("EinwaendeAuswahl ohne hinterlegten Text", () => {
  it("leerer textbaustein und standard_gegenargument erzeugen sichtbaren FEHLT-Marker", () => {
    const onUebernehmen = vi.fn();
    render(<EinwaendeAuswahl abrechnungen={ABRECHNUNGEN} kuerzungsarten={[kuerzungsart()]}
      beklagte={[]} onUebernehmen={onUebernehmen} />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    const text = onUebernehmen.mock.calls[0][0];
    expect(text).toContain("[FEHLT: Kein Textbaustein zur Kürzungsart „Stundenverrechnungssatz“ hinterlegt]");
  });

  it("vorhandener textbaustein erzeugt keinen FEHLT-Marker", () => {
    const onUebernehmen = vi.fn();
    render(<EinwaendeAuswahl abrechnungen={ABRECHNUNGEN}
      kuerzungsarten={[kuerzungsart({ textbaustein: "Nach der Rechtsprechung des BGH ist der Abzug unzulässig." })]}
      beklagte={[]} onUebernehmen={onUebernehmen} />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    const text = onUebernehmen.mock.calls[0][0];
    expect(text).not.toContain("[FEHLT");
    expect(text).toContain("Nach der Rechtsprechung des BGH");
  });

  it("standard_gegenargument greift als Fallback ohne FEHLT-Marker", () => {
    const onUebernehmen = vi.fn();
    render(<EinwaendeAuswahl abrechnungen={ABRECHNUNGEN}
      kuerzungsarten={[kuerzungsart({ standard_gegenargument: "Der Abzug ist unbegründet." })]}
      beklagte={[]} onUebernehmen={onUebernehmen} />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    const text = onUebernehmen.mock.calls[0][0];
    expect(text).not.toContain("[FEHLT");
    expect(text).toContain("Der Abzug ist unbegründet.");
  });
});
