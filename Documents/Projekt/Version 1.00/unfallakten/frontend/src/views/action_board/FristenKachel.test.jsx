import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import FristenKachel from "./FristenKachel";

const EINTRAEGE = [
  { az: "312/26 AS", frist_art: "Stellungnahme", frist_datum: "2026-07-27", tage_bis: -3, kurzbezeichnung: "Müller ./. HUK-Coburg" },
  { az: "218/26 PK", frist_art: "Klageerwiderung", frist_datum: "2026-07-30", tage_bis: 0, kurzbezeichnung: "Weber ./. Allianz" },
  { az: "402/26 AS", frist_art: "Nachbesserung Gutachten", frist_datum: "2026-08-01", tage_bis: 2, kurzbezeichnung: "Öztürk ./. R+V" },
];

describe("FristenKachel", () => {
  it("teilt in Handlungsbedarf und Demnächst und zeigt Badges statt Text-Redundanz", () => {
    render(<FristenKachel status="ok" eintraege={EINTRAEGE} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Handlungsbedarf")).toBeInTheDocument();
    expect(screen.getByText("Demnächst")).toBeInTheDocument();
    expect(screen.getByText("−3 T")).toBeInTheDocument();
    expect(screen.getByText("heute")).toBeInTheDocument();
    expect(screen.queryByText(/ÜBERFÄLLIG/)).toBeNull();
  });

  it("jeder Eintrag ist ein Button und öffnet die Akte", () => {
    const oeffne = vi.fn();
    render(<FristenKachel status="ok" eintraege={EINTRAEGE} onOpenAkte={oeffne} onRetry={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /312\/26 AS/ }));
    expect(oeffne).toHaveBeenCalledWith("312/26 AS");
  });

  it("zeigt Fehlerzustand statt Leertext bei status=fehler", () => {
    render(<FristenKachel status="fehler" eintraege={[]} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Fristen konnten nicht geladen werden")).toBeInTheDocument();
    expect(screen.queryByText(/Keine Fristen/)).toBeNull();
  });

  it("zeigt Leertext nur bei status=ok", () => {
    render(<FristenKachel status="ok" eintraege={[]} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText("Keine Fristen in den nächsten 14 Tagen")).toBeInTheDocument();
  });

  it("Kopf-Zusammenfassung nennt die Lage", () => {
    render(<FristenKachel status="ok" eintraege={EINTRAEGE} onOpenAkte={() => {}} onRetry={() => {}} />);
    expect(screen.getByText(/1 überfällig/)).toBeInTheDocument();
    expect(screen.getByText(/1 heute · 1 demnächst/)).toBeInTheDocument();
  });

  it("zeigt die Bemerkung zur Frist", () => {
    render(
      <FristenKachel
        status="ok"
        eintraege={[{
          az: "403/26AH", kurzbezeichnung: "Reinhard/Susnjar", mandant: "",
          frist_art: "Fristablauf", frist_datum: "2026-09-02", tage_bis: 0,
          bemerkung: "Wenn nix mehr gekommen ist, ablegen",
        }]}
        onOpenAkte={() => {}}
        onRetry={() => {}}
        retryLaeuft={false}
      />
    );
    expect(screen.getByText("Wenn nix mehr gekommen ist, ablegen")).toBeInTheDocument();
  });
});

describe("FristenKachel – eindeutige Keys", () => {
  it("warnt nicht bei zwei Fristen derselben Akte am selben Tag", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const doppelt = [
      { az: "312/26 AS", frist_art: "Stellungnahme",   frist_datum: "2026-07-27", tage_bis: -3, kurzbezeichnung: "Müller ./. HUK" },
      { az: "312/26 AS", frist_art: "Klageerwiderung", frist_datum: "2026-07-27", tage_bis: -3, kurzbezeichnung: "Müller ./. HUK" },
      { az: "312/26 AS", frist_art: "Nachfrist",       frist_datum: "2026-08-05", tage_bis:  5, kurzbezeichnung: "Müller ./. HUK" },
      { az: "312/26 AS", frist_art: "Belegvorlage",    frist_datum: "2026-08-05", tage_bis:  5, kurzbezeichnung: "Müller ./. HUK" },
    ];
    render(<FristenKachel status="ok" eintraege={doppelt} onOpenAkte={() => {}} onRetry={() => {}} />);
    const keyWarnungen = spy.mock.calls.filter((c) => String(c[0]).includes("same key"));
    spy.mockRestore();
    expect(keyWarnungen).toEqual([]);
  });
});
