import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  teileQueue, ampelText, FragebogenEintrag,
} from "./ReviewQueueView.jsx";

const bogen = (id, zuordnung) => ({
  eintrag: {
    id, klasse: "fragebogen", ist_fragebogen: true,
    erstellt_am: "2026-08-15 12:45",
    bogen_kopf: { mandant_name: "Paul Golovin", kennzeichen: "WÜ PG 777",
                  unfalltag: "2026-08-03" },
    zuordnung,
  },
  kinder: [],
});

const sonstiges = (id) => ({
  eintrag: { id, klasse: "gutachten", ist_fragebogen: false,
             erstellt_am: "2026-08-14 09:00" },
  kinder: [],
});

describe("teileQueue", () => {
  it("trennt Fragebögen von den übrigen Dokumenten", () => {
    const g = [sonstiges(1), bogen(2, { ampel: "gruen" }), sonstiges(3)];
    const { boegen, uebrige } = teileQueue(g);
    expect(boegen.map(x => x.eintrag.id)).toEqual([2]);
    expect(uebrige.map(x => x.eintrag.id)).toEqual([1, 3]);
  });

  it("leere Eingabe ergibt zwei leere Listen", () => {
    expect(teileQueue([])).toEqual({ boegen: [], uebrige: [] });
    expect(teileQueue(null)).toEqual({ boegen: [], uebrige: [] });
  });

  it("ein Fragebogen erscheint nicht doppelt", () => {
    const g = [bogen(2, { ampel: "neu" })];
    const { boegen, uebrige } = teileQueue(g);
    expect(boegen).toHaveLength(1);
    expect(uebrige).toHaveLength(0);
  });
});

describe("ampelText", () => {
  it("grün nennt Aktenzeichen und Kurzbezeichnung", () => {
    const a = ampelText({ ampel: "gruen", akte_az: "742/26",
                          kurzbezeichnung: "Golovin/Brochner",
                          begruendung: "Mandanten-E-Mail" });
    expect(a.text).toContain("742/26");
    expect(a.text).toContain("Golovin/Brochner");
  });

  it("grün ohne Kurzbezeichnung nennt nur das Aktenzeichen", () => {
    const a = ampelText({ ampel: "gruen", akte_az: "742/26" });
    expect(a.text).toBe("→ 742/26");
  });

  it("prüfen nennt die Anzahl der Kandidaten", () => {
    const a = ampelText({ ampel: "pruefen", kandidaten_anzahl: 2 });
    expect(a.text).toContain("PRÜFEN");
  });

  it("neu meldet die neue Akte", () => {
    expect(ampelText({ ampel: "neu" }).text).toContain("NEUE AKTE");
  });

  it("abgelegt nennt Aktenzeichen und Kurzbezeichnung", () => {
    const a = ampelText({ ampel: "abgelegt", akte_az: "749/26",
                          kurzbezeichnung: "Rügner/Unbekannt",
                          abgelegt_am: "2026-08-26" });
    expect(a.farbe).toBe("abgelegt");
    expect(a.text).toContain("ABGELEGT");
    expect(a.text).toContain("749/26");
    expect(a.text).toContain("Rügner/Unbekannt");
  });

  it("ohne Zuordnung kein Absturz", () => {
    expect(ampelText(null).text).toBe("");
  });
});

describe("FragebogenEintrag", () => {
  const basis = {
    id: 834, klasse: "fragebogen", ist_fragebogen: true,
    erstellt_am: "2026-08-15 12:45",
    bogen_kopf: { mandant_name: "Paul Golovin", kennzeichen: "WÜ PG 777",
                  unfalltag: "2026-08-03" },
  };

  it("zeigt Name, Kennzeichen und Unfalltag", () => {
    render(<FragebogenEintrag
      item={{ ...basis, zuordnung: { ampel: "gruen", akte_az: "742/26",
                                     begruendung: "Mandanten-E-Mail" } }}
      aktiv={false} onClick={() => {}} onVerwerfen={() => {}}
      onAktenanlage={() => {}} />);
    expect(screen.getByText(/Paul Golovin/)).toBeTruthy();
    expect(screen.getByText(/WÜ PG 777/)).toBeTruthy();
    expect(screen.getByText(/03\.08\.2026/)).toBeTruthy();
    expect(screen.getByText(/Mandanten-E-Mail/)).toBeTruthy();
  });

  it("Anlage-Knopf nur bei neuer Akte", () => {
    const { rerender } = render(<FragebogenEintrag
      item={{ ...basis, zuordnung: { ampel: "gruen", akte_az: "742/26" } }}
      aktiv={false} onClick={() => {}} onVerwerfen={() => {}}
      onAktenanlage={() => {}} />);
    expect(screen.queryByRole("button", { name: /Akte anlegen/ })).toBeNull();

    rerender(<FragebogenEintrag
      item={{ ...basis, zuordnung: { ampel: "abgelegt", akte_az: "749/26",
                                     abgelegt_am: "2026-08-26" } }}
      aktiv={false} onClick={() => {}} onVerwerfen={() => {}}
      onAktenanlage={() => {}} />);
    expect(screen.queryByRole("button", { name: /Akte anlegen/ })).toBeNull();
    expect(screen.getByText(/abgelegt 26\.08\.2026/)).toBeTruthy();

    rerender(<FragebogenEintrag
      item={{ ...basis, zuordnung: { ampel: "neu" } }}
      aktiv={false} onClick={() => {}} onVerwerfen={() => {}}
      onAktenanlage={() => {}} />);
    expect(screen.getByRole("button", { name: /Akte anlegen/ })).toBeTruthy();
  });

  it("Anlage-Knopf öffnet den Dialog ohne die Zeile zu aktivieren", async () => {
    const onAktenanlage = vi.fn();
    const onClick = vi.fn();
    render(<FragebogenEintrag
      item={{ ...basis, zuordnung: { ampel: "neu" } }}
      aktiv={false} onClick={onClick} onVerwerfen={() => {}}
      onAktenanlage={onAktenanlage} />);
    await userEvent.click(
      screen.getByRole("button", { name: /Akte anlegen/ }));
    expect(onAktenanlage).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });
});
