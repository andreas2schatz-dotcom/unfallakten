import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EinwaendeAuswahl } from "./KlageWizard.jsx";
import { genusKontext } from "./platzhalterLogik.js";

const ABRECHNUNGEN = [{
  gesamt_reguliert: "1000",
  positionen: [{ kuerzungsart_id: 1, betrag_gefordert: "500", betrag_reguliert: "300" }],
}];

function kuerzungsart(extra = {}) {
  return { id: 1, bezeichnung: "Wertminderung", kategorie: "fahrzeugschaden", varianten: [], ...extra };
}

describe("EinwaendeAuswahl mit Genus-Platzhaltern", () => {
  it("loest <PRON>/<POSS_EM> weiblich auf, wenn platzhalterKontext gesetzt", () => {
    const onUebernehmen = vi.fn();
    render(<EinwaendeAuswahl abrechnungen={ABRECHNUNGEN}
      kuerzungsarten={[kuerzungsart({
        textbaustein: "Das Fahrzeug wurde an <POSS_EM> Wohnort besichtigt, wo <PRON> es nutzt." })]}
      beklagte={[]} onUebernehmen={onUebernehmen}
      platzhalterKontext={genusKontext(true)} />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    const text = onUebernehmen.mock.calls[0][0];
    expect(text).toContain("an ihrem Wohnort");
    expect(text).toContain("wo sie es nutzt");
    expect(text).not.toContain("<PRON>");
  });

  it("unaufloesbare Platzhalter werden sichtbarer FEHLT-Marker", () => {
    const onUebernehmen = vi.fn();
    render(<EinwaendeAuswahl abrechnungen={ABRECHNUNGEN}
      kuerzungsarten={[kuerzungsart({ textbaustein: "Frist bis <RGGDAT>." })]}
      beklagte={[]} onUebernehmen={onUebernehmen}
      platzhalterKontext={genusKontext(false)} />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    expect(onUebernehmen.mock.calls[0][0]).toContain("[FEHLT: <RGGDAT>]");
  });

  it("ohne platzhalterKontext bleibt der Text unveraendert (Bestandsverhalten)", () => {
    const onUebernehmen = vi.fn();
    render(<EinwaendeAuswahl abrechnungen={ABRECHNUNGEN}
      kuerzungsarten={[kuerzungsart({ textbaustein: "Text mit <PRON>." })]}
      beklagte={[]} onUebernehmen={onUebernehmen} />);
    fireEvent.click(screen.getByText(/Text übernehmen/));
    expect(onUebernehmen.mock.calls[0][0]).toContain("Text mit <PRON>.");
  });
});
