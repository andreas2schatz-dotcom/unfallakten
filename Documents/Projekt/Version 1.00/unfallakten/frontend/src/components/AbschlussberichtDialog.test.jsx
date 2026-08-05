import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../api.js", () => ({
  abschluss: {
    uebersicht: vi.fn(),
    statusSpeichern: vi.fn(),
  },
  word: {
    generieren: vi.fn(),
    vorschau: vi.fn(),
  },
}));

import AbschlussberichtDialog from "./AbschlussberichtDialog.jsx";
import { abschluss as apiAbschluss, word as apiWord } from "../api.js";

const UEBERSICHT = {
  modus: "sachstand",
  schluss: { typ: "offen", text: "", verjaehrung_datum: null, naechste_schritte_text: "" },
  summen: { gefordert: 6200, gezahlt: 3900, an_mandant: 3900, differenz: 2300 },
  positionen: [
    { key: "reparaturkosten", label: "Reparaturkosten", gefordert: 4200, gezahlt: 3900,
      differenz: 300, status: "offen", kuerzung_grund: "Stundenverrechnungssatz" },
    { key: "nutzungsausfall", label: "Nutzungsausfall", gefordert: 2000, gezahlt: 0,
      differenz: 2000, status: "offen", kuerzung_grund: null },
  ],
  plausi: { differenz_ok: true, zeilensumme: 3900, reguliert_gesamt: 3900 },
  anwaltskosten: {},
  bewertung_cta: null,
};

describe("AbschlussberichtDialog", () => {
  it("zeigt Lade-Zustand, dann Summen und Positionen nach dem Laden", async () => {
    apiAbschluss.uebersicht.mockResolvedValueOnce(UEBERSICHT);
    render(<AbschlussberichtDialog az="285/26" onClose={() => {}} />);

    expect(screen.getByText(/Lade Übersicht/)).toBeInTheDocument();

    await waitFor(() => expect(apiAbschluss.uebersicht).toHaveBeenCalledWith("285/26"));
    expect(await screen.findByText("Reparaturkosten")).toBeInTheDocument();
    expect(screen.getByText("Nutzungsausfall")).toBeInTheDocument();
    expect(screen.getByText("2.300,00 €")).toBeInTheDocument();
  });

  it("zeigt Badge 'Sachstandsbericht' bei typ=offen und wechselt zu 'Abschlussbericht'", async () => {
    apiAbschluss.uebersicht.mockResolvedValueOnce(UEBERSICHT);
    const user = userEvent.setup();
    render(<AbschlussberichtDialog az="285/26" onClose={() => {}} />);

    await screen.findByText("Reparaturkosten");
    expect(screen.getByText("Sachstandsbericht")).toBeInTheDocument();

    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "endgueltig");

    expect(screen.getByText("Abschlussbericht")).toBeInTheDocument();
  });

  it("zeigt Plausi-Warnung wenn differenz_ok === false", async () => {
    apiAbschluss.uebersicht.mockResolvedValueOnce({
      ...UEBERSICHT,
      plausi: { differenz_ok: false, zeilensumme: 4000, reguliert_gesamt: 3900 },
    });
    render(<AbschlussberichtDialog az="285/26" onClose={() => {}} />);

    expect(await screen.findByText(/weicht vom regulierten/)).toBeInTheDocument();
  });
});
