import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import OnboardingHub from "./OnboardingHub.jsx";

const voll = {
  az: "1/26",
  akte: { unfalldatum: "2026-01-10", unfallort: "Offenbach" },
  beteiligte: [
    { rolle: "mandant", name: "Max Müller" },
    { rolle: "gegner", name: "Erika Beispiel" },
    { kuerzel: "GHPV", name: "HUK-COBURG" },
  ],
  schaden: { gesamt_brutto: 8200 },
  dokumente: [
    { dokumentenklasse: "vollmacht" },
    { dokumentenklasse: "forderungsschreiben" },
  ],
};

beforeEach(() => localStorage.clear());

describe("B2 – OnboardingHub Datenquellen", () => {
  it("bleibt verborgen, wenn alle Pflichtbereiche vollständig sind", () => {
    const { container } = render(<OnboardingHub {...voll} />);
    expect(container.firstChild).toBeNull();
  });

  it("erkennt die GHPV über das großgeschriebene Kürzel", () => {
    render(<OnboardingHub az="1/26" beteiligte={[{ kuerzel: "GHPV" }]} />);
    expect(screen.getByText(/✓ GHPV/)).toBeInTheDocument();
  });

  it("erkennt Schadenspositionen über gesamt_brutto", () => {
    render(<OnboardingHub az="1/26" schaden={{ gesamt_brutto: 4500 }} />);
    expect(screen.getByText(/✓ Schadenspositionen/)).toBeInTheDocument();
  });

  it("erkennt Unfalldetails über die Akten-Felder", () => {
    render(<OnboardingHub az="1/26" akte={{ unfalldatum: "2026-01-10", unfallort: "Offenbach" }} />);
    expect(screen.getByText(/✓ Unfalldetails/)).toBeInTheDocument();
  });

  it("erkennt die Vollmacht über die Dokumentenklasse", () => {
    render(<OnboardingHub az="1/26" dokumente={[{ dokumentenklasse: "vollmacht" }]} />);
    expect(screen.getByText(/✓ Vollmacht/)).toBeInTheDocument();
  });

  it("erkennt die Erstforderung über die Dokumentenklasse", () => {
    render(<OnboardingHub az="1/26" dokumente={[{ dokumentenklasse: "forderungsschreiben" }]} />);
    expect(screen.getByText(/✓ Erstforderung/)).toBeInTheDocument();
  });
});
