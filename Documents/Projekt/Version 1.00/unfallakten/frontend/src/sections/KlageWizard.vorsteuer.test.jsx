/**
 * Vorsteuerabzugsberechtigte Kläger: die vorgerichtlichen RVG-Kosten sind nur
 * netto erstattungsfähig — die Umsatzsteuer zieht der Kläger als Vorsteuer ab
 * (RA Schatz, 2026-08-27).
 *
 * Der Wizard muss dieselbe Regel anzeigen wie klage_service.py sie in die
 * Klageschrift schreibt, sonst zeigt der Bildschirm brutto und das Dokument
 * fordert netto.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StepGebuehren } from "./KlageWizard.jsx";

vi.mock("../api.js", () => ({
  apiGebuehren: { analysieren: vi.fn(), speichern: vi.fn() },
}));

const RVG = {
  faktor: 1.3,
  gebuehr_netto: 1000,
  post_pauschale: 20,
  zwischen_netto: 1020,
  ust: 193.8,
  gesamt: 1213.8,
  rvg_version: "2025",
};

const BEKLAGTE = [{ id: 1, name: "Muster", rolle_klage: "beklagter", checked: true }];

function zeige(vorsteuer) {
  render(
    <StepGebuehren
      akteId="44/22"
      swAusserg={10000}
      vorsteuer={vorsteuer}
      rvgAussergData={RVG}
      onRvgAussergData={() => {}}
      rvgAussergOv=""
      onRvgAussergOv={() => {}}
      rvgBereitsGezahlt=""
      onRvgBereitsGezahlt={() => {}}
      gebuehrenText=""
      onGebuehrenText={() => {}}
      beklagte={BEKLAGTE}
      weiblich={false}
      zinsenAb="rechtshaengigkeit"
      verzug=""
      antraegeText=""
      onAntraegeText={() => {}}
      gespeichertGb={null}
      onGespeichertGb={() => {}}
    />
  );
}

describe("StepGebuehren – Umsatzsteuer bei Vorsteuerabzug", () => {
  it("zeigt ohne Vorsteuerabzug die Umsatzsteuer und den Bruttobetrag", () => {
    zeige(false);
    expect(screen.getByText("19 % Umsatzsteuer")).toBeInTheDocument();
    expect(screen.getByText("Zwischensumme netto")).toBeInTheDocument();
    expect(screen.getAllByText(/1\.213,80/).length).toBeGreaterThan(0);
  });

  it("blendet bei Vorsteuerabzug die Umsatzsteuerzeile aus", () => {
    zeige(true);
    expect(screen.queryByText("19 % Umsatzsteuer")).toBeNull();
    expect(screen.queryByText("Zwischensumme netto")).toBeNull();
  });

  it("weist bei Vorsteuerabzug den Nettobetrag als Gesamtbetrag aus", () => {
    zeige(true);
    expect(screen.getByText("Gesamtbetrag")).toBeInTheDocument();
    expect(screen.getAllByText(/1\.020,00/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/1\.213,80/)).toBeNull();
  });
});
