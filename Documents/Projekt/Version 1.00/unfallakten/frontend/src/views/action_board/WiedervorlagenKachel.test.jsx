import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import WiedervorlagenKachel from "./WiedervorlagenKachel";

const WV = [
  { az: "145/26 AS", datum: "2026-07-28", tage_bis: -2, grund: "Zahlungseingang prüfen", kurzbezeichnung: "Schneider ./. DEVK" },
  { az: "287/26 AH", datum: "2026-07-30", tage_bis: 0, grund: "SV-Gutachten nachfassen", kurzbezeichnung: "Becker ./. Gothaer" },
];
const OHNE = Array.from({ length: 8 }, (_, i) => ({ az: `90${i}/26 AS`, kurzbezeichnung: `Akte ${i}` }));

describe("WiedervorlagenKachel", () => {
  it("zeigt Überfällig- und Heute-Abschnitte mit Badges", () => {
    render(<WiedervorlagenKachel status="ok" wv={WV} ohne_wv={[]} onOpenAkte={() => {}} onRetry={() => {}} onAlleOeffnen={() => {}} />);
    expect(screen.getByText("Überfällig")).toBeInTheDocument();
    expect(screen.getByText("Heute fällig")).toBeInTheDocument();
    expect(screen.getByText("−2 T")).toBeInTheDocument();
  });

  it("deckelt die Liste ohne WV auf 5 und bietet den Sprung in die Vollansicht", () => {
    const alle = vi.fn();
    render(<WiedervorlagenKachel status="ok" wv={[]} ohne_wv={OHNE} onOpenAkte={() => {}} onRetry={() => {}} onAlleOeffnen={alle} />);
    expect(screen.getByText("Keine Wiedervorlage gesetzt")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /\/26 AS/ })).toHaveLength(5);
    const mehr = screen.getByRole("button", { name: /\+ 3 weitere/ });
    fireEvent.click(mehr);
    expect(alle).toHaveBeenCalledTimes(1);
  });

  it("Fehlerzustand ersetzt den Leertext", () => {
    render(<WiedervorlagenKachel status="fehler" wv={[]} ohne_wv={[]} onOpenAkte={() => {}} onRetry={() => {}} onAlleOeffnen={() => {}} />);
    expect(screen.getByText("Wiedervorlagen konnten nicht geladen werden")).toBeInTheDocument();
    expect(screen.queryByText("Alle Wiedervorlagen erledigt")).toBeNull();
  });

  it("Leerzustand nur bei ok", () => {
    render(<WiedervorlagenKachel status="ok" wv={[]} ohne_wv={[]} onOpenAkte={() => {}} onRetry={() => {}} onAlleOeffnen={() => {}} />);
    expect(screen.getByText("Alle Wiedervorlagen erledigt")).toBeInTheDocument();
  });
});

describe("WiedervorlagenKachel – eindeutige Keys", () => {
  it("warnt nicht bei zwei Wiedervorlagen derselben Akte am selben Tag", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const wv = [
      { az: "312/26 AS", datum: "2026-07-27", tage_bis: -2, grund: "Sachstand",   kurzbezeichnung: "Müller" },
      { az: "312/26 AS", datum: "2026-07-27", tage_bis: -2, grund: "Zahlung",     kurzbezeichnung: "Müller" },
      { az: "218/26 PK", datum: "2026-07-30", tage_bis:  0, grund: "Rückruf",     kurzbezeichnung: "Weber" },
      { az: "218/26 PK", datum: "2026-07-30", tage_bis:  0, grund: "Unterlagen",  kurzbezeichnung: "Weber" },
    ];
    render(<WiedervorlagenKachel status="ok" wv={wv} ohne_wv={[]} onOpenAkte={() => {}} onRetry={() => {}} onAlleOeffnen={() => {}} />);
    const keyWarnungen = spy.mock.calls.filter((c) => String(c[0]).includes("same key"));
    spy.mockRestore();
    expect(keyWarnungen).toEqual([]);
  });
});
