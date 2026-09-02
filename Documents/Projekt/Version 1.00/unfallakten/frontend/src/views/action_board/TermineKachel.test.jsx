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

describe("TermineKachel – eindeutige Keys", () => {
  it("warnt nicht bei zwei Terminen derselben Akte zur selben Zeit", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    const doppelt = [
      { az: "312/26 AS", termin_art: "Gerichtstermin", termin_datum: "2026-07-30", uhrzeit: "09:00", tage_bis: 0, kurzbezeichnung: "Müller" },
      { az: "312/26 AS", termin_art: "Besprechung",    termin_datum: "2026-07-30", uhrzeit: "09:00", tage_bis: 0, kurzbezeichnung: "Müller" },
      { az: "218/26 PK", termin_art: "Ortstermin",     termin_datum: "2026-07-31", uhrzeit: "",      tage_bis: 1, kurzbezeichnung: "Weber" },
      { az: "218/26 PK", termin_art: "Rückruf",        termin_datum: "2026-07-31", uhrzeit: "",      tage_bis: 1, kurzbezeichnung: "Weber" },
    ];
    render(<TermineKachel status="ok" eintraege={doppelt} onOpenAkte={() => {}} onRetry={() => {}} />);
    const keyWarnungen = spy.mock.calls.filter((c) => String(c[0]).includes("same key"));
    spy.mockRestore();
    expect(keyWarnungen).toEqual([]);
  });
});

const KALENDER_SB = [
  { kuerzel: "AS", name: "Andreas Schatz", titel: "Rechtsanwalt" },
  { kuerzel: "CO", name: "Claudia Ostarek", titel: "Rechtsanwältin" },
];

function terminKachel(props = {}) {
  return render(
    <TermineKachel
      status="ok"
      eintraege={[]}
      onOpenAkte={() => {}}
      onRetry={() => {}}
      kalenderSbListe={KALENDER_SB}
      aktiveKalenderSb={new Set(["AS", "CO"])}
      onToggleKalenderSb={() => {}}
      {...props}
    />
  );
}

describe("TermineKachel – Termintext", () => {
  it("zeigt den Betreff eines Termins ohne Akte statt nur der Terminart", () => {
    terminKachel({ eintraege: [
      { az: "", sb: "AS", termin_art: "", betreff: "Herr Kirto Pektas",
        termin_datum: "2026-09-02", uhrzeit: "09:00", tage_bis: 0 },
    ] });
    expect(screen.getByText("Herr Kirto Pektas")).toBeInTheDocument();
  });

  it("verbindet Terminart und Betreff mit einem Gedankenstrich", () => {
    terminKachel({ eintraege: [
      { az: "192/25CO", sb: "CO", termin_art: "Verhandlungstermin", betreff: "Bhalla/Kangalli",
        termin_datum: "2026-09-02", uhrzeit: "13:30", tage_bis: 0 },
    ] });
    expect(screen.getByText("Verhandlungstermin — Bhalla/Kangalli")).toBeInTheDocument();
  });

  it("hängt keinen leeren Gedankenstrich an, wenn der Betreff fehlt", () => {
    terminKachel({ eintraege: [
      { az: "", sb: "AS", termin_art: "Mandantentermin", betreff: "",
        termin_datum: "2026-09-02", uhrzeit: "11:00", tage_bis: 0 },
    ] });
    expect(screen.getByText("Mandantentermin")).toBeInTheDocument();
    expect(screen.queryByText(/—\s*$/)).toBeNull();
  });

  it("zeigt Ort und Bemerkung des Termins", () => {
    terminKachel({ eintraege: [
      { az: "192/25CO", sb: "CO", termin_art: "Verhandlungstermin", betreff: "Bhalla/Kangalli",
        ort: "AG Dieburg, Raum 110", bemerkung: "Gütetermin",
        termin_datum: "2026-09-02", uhrzeit: "13:30", tage_bis: 0 },
    ] });
    expect(screen.getByText(/AG Dieburg, Raum 110/)).toBeInTheDocument();
    expect(screen.getByText("Gütetermin")).toBeInTheDocument();
  });

  it("öffnet keine Akte bei einem Termin ohne Aktenzeichen", () => {
    const oeffne = vi.fn();
    terminKachel({ onOpenAkte: oeffne, eintraege: [
      { az: "", sb: "AS", termin_art: "", betreff: "Fachanwaltslehrgang",
        termin_datum: "2026-09-02", uhrzeit: "09:00", tage_bis: 0 },
    ] });
    fireEvent.click(screen.getByRole("button", { name: /Fachanwaltslehrgang/ }));
    expect(oeffne).not.toHaveBeenCalled();
  });
});

describe("TermineKachel – eigener Kalenderfilter", () => {
  it("zeigt je einen Chip pro Anwaltskalender", () => {
    terminKachel();
    expect(screen.getByRole("button", { name: "Kalender AS" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kalender CO" })).toBeInTheDocument();
  });

  it("meldet einen Klick auf einen Kalender-Chip", () => {
    const toggle = vi.fn();
    terminKachel({ onToggleKalenderSb: toggle });
    fireEvent.click(screen.getByRole("button", { name: "Kalender CO" }));
    expect(toggle).toHaveBeenCalledWith("CO");
  });

  it("markiert abgewählte Kalender per aria-pressed", () => {
    terminKachel({ aktiveKalenderSb: new Set(["AS"]) });
    expect(screen.getByRole("button", { name: "Kalender AS" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Kalender CO" })).toHaveAttribute("aria-pressed", "false");
  });

  it("zeigt einen Hinweis statt des Leertexts, wenn kein Kalender gewählt ist", () => {
    terminKachel({ aktiveKalenderSb: new Set() });
    expect(screen.getByText("Kein Kalender ausgewählt")).toBeInTheDocument();
    expect(screen.queryByText("Heute keine Termine")).toBeNull();
  });
});
