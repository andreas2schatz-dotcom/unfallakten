import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StepZusammenfassung, ANTRAEGE_PLACEHOLDER } from "./KlageWizard.jsx";

const BASIS_PROPS = {
  gericht: { name: "Amtsgericht Offenbach" },
  beklagte: [{ id: 1, name: "Muster", rolle_klage: "beklagter", checked: true }],
  positionen: [{ key: "fahrzeugschaden", label: "Fahrzeugschaden", betrag: 1000, checked: true }],
  mitSG: false,
  sgMind: 0,
  rvgAussergData: null,
  rvgAussergOv: null,
  aktLegTyp: "eigentum",
  aktLegFreigabe: "freigabe",
  zinsenAb: "verzug",
  wizardVerzugDatum: null,
  laedt: false,
  onGenerieren: vi.fn(),
  fehler: null,
  lgGrenzwert: 0,
  swAusserg: 0,
};

const ANTRAEGE_MIT_PLATZHALTER =
  `1. Die Beklagte wird verurteilt, an den Kläger 1.000,00 € zu zahlen.\n\n` +
  `2. ${ANTRAEGE_PLACEHOLDER}`;

const ANTRAEGE_OHNE_PLATZHALTER =
  `1. Die Beklagte wird verurteilt, an den Kläger 1.000,00 € zu zahlen.`;

describe("StepZusammenfassung – KW-23 Platzhalter-Guard", () => {
  it("sperrt Generieren-Button und zeigt Warnblock, wenn Anträge-Text den Platzhalter enthält", () => {
    render(<StepZusammenfassung {...BASIS_PROPS} antraegeText={ANTRAEGE_MIT_PLATZHALTER} />);

    const button = screen.getByRole("button", { name: /Als Word generieren/i });
    expect(button).toBeDisabled();
    expect(screen.getByText(/Platzhalter/i)).toBeInTheDocument();
    expect(screen.getByText(/Schritt 9/i)).toBeInTheDocument();
  });

  it("laesst den Button bei fertigem Anträge-Text (ohne Platzhalter) unangetastet", () => {
    render(<StepZusammenfassung {...BASIS_PROPS} antraegeText={ANTRAEGE_OHNE_PLATZHALTER} />);

    const button = screen.getByRole("button", { name: /Als Word generieren/i });
    expect(button).not.toBeDisabled();
    expect(screen.queryByText(/Platzhalter/i)).not.toBeInTheDocument();
  });

  it("Regression: ohne Gericht bleibt der Button weiterhin gesperrt", () => {
    render(<StepZusammenfassung {...BASIS_PROPS} gericht={null} antraegeText={ANTRAEGE_OHNE_PLATZHALTER} />);

    const button = screen.getByRole("button", { name: /Als Word generieren/i });
    expect(button).toBeDisabled();
  });
});

describe("StepZusammenfassung – KW-19 Generieren-Sperre bei 0 Beklagten", () => {
  it("sperrt Generieren-Button und zeigt Warnblock, wenn keine Beklagten angehakt sind", () => {
    const props = {
      ...BASIS_PROPS,
      beklagte: [
        { id: 1, name: "Mustermann", rolle_klage: "klaeger", checked: true },
        { id: 2, name: "Huber", rolle_klage: "beklagter", checked: false }
      ],
      antraegeText: ANTRAEGE_OHNE_PLATZHALTER
    };
    render(<StepZusammenfassung {...props} />);

    expect(screen.getByText(/Keine Beklagten ausgewählt/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Als Word generieren/i })).toBeDisabled();
  });
});

describe("StepZusammenfassung – KW-13 RVG-gerichtlich-Duplikat entfernt", () => {
  it("zeigt gerichtlichen Streitwert als Zahl statt 'RVG gerichtlich'", () => {
    render(<StepZusammenfassung {...BASIS_PROPS} />);
    expect(screen.queryByText(/RVG gerichtlich/)).toBeNull();
    expect(screen.getByText(/Gerichtlicher Streitwert/)).toBeTruthy();
    expect(screen.getByText(/RVG außergerichtlich/)).toBeTruthy();
  });
});
