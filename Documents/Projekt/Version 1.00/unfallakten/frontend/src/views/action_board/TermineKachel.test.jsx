import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TermineKachel from "./TermineKachel";

const EINTRAEGE = [
  { az: "264/26 AS", termin_art: "Gerichtstermin", termin_datum: "2026-07-30", uhrzeit: "09:30", tage_bis: 0, kurzbezeichnung: "Klein ./. Provinzial" },
  { az: "198/26 CO", termin_art: "Gerichtstermin", termin_datum: "2026-07-31", uhrzeit: "10:00", tage_bis: 1, kurzbezeichnung: "Krause ./. VHV" },
];

describe("TermineKachel", () => {
  it("gruppiert nach Heute und Morgen mit Uhrzeit", () => {
    render(<TermineKachel status="ok" eintraege={EINTRAEGE} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Heute")).toBeInTheDocument();
    expect(screen.getByText("Morgen")).toBeInTheDocument();
    expect(screen.getByText("09:30")).toBeInTheDocument();
  });

  it("Eintrag ist Button und öffnet Akte", () => {
    const oeffne = vi.fn();
    render(<TermineKachel status="ok" eintraege={EINTRAEGE} onOpenAkte={oeffne} onRetry={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /264\/26 AS/ }));
    expect(oeffne).toHaveBeenCalledWith("264/26 AS");
  });

  it("Fehler- und Leerzustand sind getrennt", () => {
    const { rerender } = render(<TermineKachel status="fehler" eintraege={[]} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Termine konnten nicht geladen werden")).toBeInTheDocument();
    rerender(<TermineKachel status="ok" eintraege={[]} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Heute keine Termine")).toBeInTheDocument();
  });
});
