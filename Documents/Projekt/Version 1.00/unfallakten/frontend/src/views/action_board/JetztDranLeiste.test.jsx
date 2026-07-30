import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import JetztDranLeiste, { jetztDranEintraege } from "./JetztDranLeiste";

const FRISTEN = [
  { az: "312/26 AS", frist_art: "Stellungnahme", frist_datum: "2026-07-27", tage_bis: -3, kurzbezeichnung: "Müller ./. HUK" },
  { az: "218/26 PK", frist_art: "Klageerwiderung", frist_datum: "2026-07-30", tage_bis: 0, kurzbezeichnung: "Weber ./. Allianz" },
  { az: "402/26 AS", frist_art: "Nachbesserung", frist_datum: "2026-08-01", tage_bis: 2, kurzbezeichnung: "Öztürk ./. R+V" },
];
const WV = [
  { az: "145/26 AS", datum: "2026-07-28", tage_bis: -2, grund: "Zahlungseingang prüfen", kurzbezeichnung: "Schneider ./. DEVK" },
  { az: "287/26 AH", datum: "2026-07-30", tage_bis: 0, grund: "nachfassen", kurzbezeichnung: "Becker ./. Gothaer" },
];

describe("jetztDranEintraege", () => {
  it("nimmt nur Fälliges (<= 0), sortiert überfälligste zuerst, Frist vor WV, max 3", () => {
    const erg = jetztDranEintraege(FRISTEN, WV);
    expect(erg).toHaveLength(3);
    expect(erg[0].az).toBe("312/26 AS");
    expect(erg[1].az).toBe("145/26 AS");
    expect(erg[2].az).toBe("218/26 PK");
  });

  it("Frist gewinnt bei Gleichstand", () => {
    const erg = jetztDranEintraege(
      [{ az: "F", frist_art: "x", frist_datum: "d", tage_bis: 0, kurzbezeichnung: "f" }],
      [{ az: "W", datum: "d", tage_bis: 0, grund: "y", kurzbezeichnung: "w" }]
    );
    expect(erg.map((e) => e.az)).toEqual(["F", "W"]);
  });
});

describe("JetztDranLeiste", () => {
  it("rendert nichts, solange eine Quelle nicht ok ist", () => {
    const { container } = render(
      <JetztDranLeiste fristenStatus="laedt" wvStatus="ok" fristen={[]} wv={[]} onOpenAkte={() => {}} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("zeigt die dringendsten Vorgänge als klickbare Buttons", () => {
    const oeffne = vi.fn();
    render(<JetztDranLeiste fristenStatus="ok" wvStatus="ok" fristen={FRISTEN} wv={WV} onOpenAkte={oeffne} />);
    expect(screen.getByText("Jetzt dran")).toBeInTheDocument();
    expect(screen.getByText("3 Tage überfällig")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /312\/26 AS/ }));
    expect(oeffne).toHaveBeenCalledWith("312/26 AS");
  });

  it("zeigt bei leerer Lage die ruhige Entwarnung", () => {
    render(<JetztDranLeiste fristenStatus="ok" wvStatus="ok" fristen={[]} wv={[]} onOpenAkte={() => {}} />);
    expect(screen.getByText("Keine überfälligen Vorgänge")).toBeInTheDocument();
  });
});
