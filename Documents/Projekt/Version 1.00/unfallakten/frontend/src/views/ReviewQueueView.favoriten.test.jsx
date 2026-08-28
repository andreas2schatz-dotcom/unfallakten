import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReviewQueueView, {
  teileQueue, ampelText, FragebogenEintrag,
  bogenVorbefuellung, zeigeAktenanlageVorschlag, aktenanlageBannerText,
} from "./ReviewQueueView.jsx";

const api = vi.hoisted(() => ({
  apiIntake: {
    queue: vi.fn(() => Promise.resolve({ eintraege: [] })),
    klassen: vi.fn(() => Promise.resolve({ klassen: [] })),
    ereignistypen: vi.fn(() => Promise.resolve({ typen: [] })),
    papierkorb: vi.fn(() => Promise.resolve({ eintraege: [] })),
  },
  apiAktenanlage: { offen: vi.fn(() => Promise.resolve({ vorgaenge: [], ramicro_verfuegbar: true })) },
  tokenStore: { getAccess: vi.fn(() => "test-token") },
  API_BASE: "http://localhost:5000",
}));
vi.mock("../api", () => api);

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

  it("zeigt bei laufendem Anlage-Vorgang den Status statt des Knopfes", () => {
    render(<FragebogenEintrag
      item={{ ...basis, zuordnung: { ampel: "neu" } }}
      aktiv={false} onClick={() => {}} onVerwerfen={() => {}}
      onAktenanlage={() => {}}
      vorgang={{ status: "laeuft", warnung: false }} />);
    expect(screen.queryByRole("button", { name: /Akte anlegen/ })).toBeNull();
    expect(screen.getByText(/Aktenanlage läuft/)).toBeTruthy();
  });
});

describe("Kinder in der Liste (ReviewQueueView)", () => {
  const kopf = (name) => ({ mandant_name: name, kennzeichen: "OF-XX 1",
                            unfalltag: "2026-08-01" });

  it("Anhänge eines Fragebogens verschwinden nicht", async () => {
    api.apiIntake.queue.mockResolvedValueOnce({ eintraege: [
      { id: 1, klasse: "fragebogen", ist_fragebogen: true,
        queue_status: "bereit_zur_review", erstellt_am: "2026-08-15 09:00",
        zustellung_id: 100, parent_zustellung_id: null,
        bogen_kopf: kopf("Erika Mustermann"),
        zuordnung: { ampel: "gruen", akte_az: "100/26" } },
      { id: 2, klasse: "lichtbilder", ist_fragebogen: false,
        queue_status: "bereit_zur_review", erstellt_am: "2026-08-15 09:05",
        zustellung_id: 101, parent_zustellung_id: 100 },
    ] });
    render(<ReviewQueueView onOpenAkte={() => {}} />);
    await waitFor(() => expect(screen.getByText(/Erika Mustermann/)).toBeTruthy());
    expect(screen.getByText("lichtbilder")).toBeTruthy();
  });

  it("ein Fragebogen als Anhang bekommt Chip und Ampel statt der schlichten Zeile", async () => {
    api.apiIntake.queue.mockResolvedValueOnce({ eintraege: [
      { id: 3, klasse: "sonstiges", ist_fragebogen: false,
        queue_status: "bereit_zur_review", erstellt_am: "2026-08-14 09:00",
        zustellung_id: 200, parent_zustellung_id: null },
      { id: 4, klasse: "fragebogen", ist_fragebogen: true,
        queue_status: "bereit_zur_review", erstellt_am: "2026-08-14 09:10",
        zustellung_id: 201, parent_zustellung_id: 200,
        bogen_kopf: kopf("Tim Englert"),
        zuordnung: { ampel: "pruefen", kandidaten_anzahl: 2 } },
    ] });
    render(<ReviewQueueView onOpenAkte={() => {}} />);
    await waitFor(() => expect(screen.getByText(/Tim Englert/)).toBeTruthy());
    expect(screen.getByText(/PRÜFEN/)).toBeTruthy();
  });
});

describe("bogenVorbefuellung", () => {
  const roh = JSON.stringify({
    meta: { formular: "unfallbogen", version: "2.1" },
    mandant: { name: "Golovin", vorname: "Paul", strasse: "Bergstr. 1",
               plz: "63075", ort: "Offenbach am Main",
               telefon: "01785799951", email: "paulgolovin@web.de" },
    unfall: { datum: "2026-08-03", ort: "Mainhausen" },
    sachschaden: { eigenes_fahrzeug: { kennzeichen: "WÜ PG 777" } },
  });

  it("übernimmt Mandanten- und Unfalldaten", () => {
    const p = bogenVorbefuellung(roh);
    expect(p.mandant.nachname).toBe("Golovin");
    expect(p.mandant.vorname).toBe("Paul");
    expect(p.mandant.plz).toBe("63075");
    expect(p.mandant.email).toBe("paulgolovin@web.de");
    expect(p.unfall.unfalldatum).toBe("2026-08-03");
    expect(p.unfall.unfallort).toBe("Mainhausen");
    expect(p.unfall.kennzeichen).toBe("WÜ PG 777");
  });

  it("liefert null bei fremdem Inhalt", () => {
    expect(bogenVorbefuellung("Sehr geehrte Damen")).toBeNull();
    expect(bogenVorbefuellung('{"meta":{}}')).toBeNull();
    expect(bogenVorbefuellung(null)).toBeNull();
  });
});

describe("zeigeAktenanlageVorschlag", () => {
  it("gilt für Fragebögen ohne Treffer", () => {
    expect(zeigeAktenanlageVorschlag({
      klasse: "fragebogen", ist_fragebogen: true,
      zuordnung: { ampel: "neu" },
    })).toBe(true);
  });

  it("gilt nicht für Fragebögen mit Treffer", () => {
    expect(zeigeAktenanlageVorschlag({
      klasse: "fragebogen", ist_fragebogen: true,
      zuordnung: { ampel: "gruen", akte_az: "742/26" },
    })).toBe(false);
  });

  it("der Gutachten-Fall bleibt erhalten", () => {
    expect(zeigeAktenanlageVorschlag({
      klasse: "gutachten", absender_kategorie: "gutachter",
      akte_kandidat_top: null,
    })).toBe(true);
  });
});

describe("aktenanlageBannerText", () => {
  it("nennt beim Fragebogen den Mandanten, nicht das Postfach", () => {
    const text = aktenanlageBannerText({
      ist_fragebogen: true, absender: "unfall@anwalt-offenbach.de",
      bogen_kopf: { mandant_name: "Paul Golovin" },
    });
    expect(text).toContain("Paul Golovin");
    expect(text).not.toMatch(/Gutachten/);
    expect(text).not.toContain("unfall@anwalt-offenbach.de");
  });

  it("formuliert beim Fragebogen ohne Namen ohne leeren Platzhalter", () => {
    const text = aktenanlageBannerText({
      ist_fragebogen: true, absender: "unfall@anwalt-offenbach.de",
      bogen_kopf: {},
    });
    expect(text).not.toMatch(/Gutachten/);
    expect(text).not.toContain("undefined");
    expect(text).toContain("Unfallfragebogen");
  });

  it("bleibt beim Gutachten unveraendert", () => {
    const text = aktenanlageBannerText({
      klasse: "gutachten", absender: "Sachverständigenbüro Krause",
    });
    expect(text).toBe(
      "Vermutlich neue Akte: Gutachten von Sachverständigenbüro Krause, kein Treffer im Bestand.");
  });
});
