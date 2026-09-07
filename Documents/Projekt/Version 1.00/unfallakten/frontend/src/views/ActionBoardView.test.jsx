import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";

const api = vi.hoisted(() => ({
  termineHeute:   vi.fn(),
  fristen:        vi.fn(),
  wiedervorlagen: vi.fn(),
}));
const einst = vi.hoisted(() => ({ sachbearbeiter: vi.fn() }));
vi.mock("../api", () => ({ apiDashboard: api, apiEinstellungen: einst }));

import ActionBoardView from "./ActionBoardView.jsx";

const FRIST = { az: "312/26 AS", frist_art: "Stellungnahme", frist_datum: "2026-07-27", tage_bis: -3, kurzbezeichnung: "Müller ./. HUK" };

const SB_LISTE = [
  { kuerzel: "AS", name: "Andreas Schatz", titel: "Rechtsanwalt", aktiv: 1, ignoriert: 0,
    dashboard_vorauswahl: 1, sortierung: 10, kalender_name: "RA.Schatz" },
  { kuerzel: "CO", name: "Claudia Ostarek", titel: "Rechtsanwältin", aktiv: 1, ignoriert: 0,
    dashboard_vorauswahl: 0, sortierung: 30, kalender_name: "C. Ostarek" },
  { kuerzel: "TB", name: "Tanja Brunner", titel: "Rechtsanwalts- und Notarfachangestellte",
    aktiv: 1, ignoriert: 0, dashboard_vorauswahl: 0, sortierung: 70, kalender_name: null },
  { kuerzel: "JH", name: "Jochen Hofmann", titel: "Rechtsanwalt", aktiv: 0, ignoriert: 0,
    dashboard_vorauswahl: 0, sortierung: 110, kalender_name: null },
];

// Termin ohne Akte: genau der Fall, bei dem die AZ-Ableitung versagt.
const TERMIN_OHNE_AKTE = { az: "", sb: "CO", termin_art: "", betreff: "Sigkeris neue Sache",
  termin_datum: "2026-09-02", uhrzeit: "12:00", tage_bis: 0 };
const TERMIN_AS = { az: "", sb: "AS", termin_art: "", betreff: "Herr Kirto Pektas",
  termin_datum: "2026-09-02", uhrzeit: "09:00", tage_bis: 0 };

function mockOk({ fristen = [], termine = [], wv = [], ohne_wv = [] } = {}) {
  api.termineHeute.mockResolvedValue({ eintraege: termine });
  api.fristen.mockResolvedValue({ eintraege: fristen });
  api.wiedervorlagen.mockResolvedValue({ wv, ohne_wv });
  einst.sachbearbeiter.mockResolvedValue({ eintraege: SB_LISTE });
}

describe("ActionBoardView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("zeigt beim Laden keinen Leertext (kein falsches 'alles erledigt')", () => {
    api.termineHeute.mockReturnValue(new Promise(() => {}));
    api.fristen.mockReturnValue(new Promise(() => {}));
    api.wiedervorlagen.mockReturnValue(new Promise(() => {}));
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    expect(screen.queryByText(/Keine Fristen/)).toBeNull();
    expect(screen.queryByText(/Heute keine Termine/)).toBeNull();
  });

  it("zeigt bei Fristen-Fehler den Fehlerblock und lädt per Retry neu", async () => {
    mockOk();
    api.fristen.mockRejectedValue(new Error("kaputt"));
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Fristenkalender nicht erreichbar (E-Akte-Mount)");
    expect(screen.queryByText(/Keine Fristen in den nächsten/)).toBeNull();
    api.fristen.mockResolvedValue({ eintraege: [] });
    fireEvent.click(screen.getByRole("button", { name: "Erneut laden" }));
    await screen.findByText("Keine Fristen in den nächsten drei Werktagen");
    expect(api.fristen).toHaveBeenCalledTimes(2);
  });

  it("zeigt keinen Posteingang mehr", async () => {
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Alle Wiedervorlagen erledigt");
    expect(screen.queryByText(/Posteingang/i)).toBeNull();
  });

  it("öffnet Akten aus der Jetzt-dran-Leiste mit normalisiertem AZ", async () => {
    mockOk({ fristen: [FRIST] });
    const oeffne = vi.fn();
    render(<ActionBoardView onOpenAkte={oeffne} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Jetzt dran");
    fireEvent.click(screen.getAllByRole("button", { name: /312\/26 AS/ })[0]);
    expect(oeffne).toHaveBeenCalledWith({ az: "312/26", az_roh: "312/26 AS" });
  });

  it("persistiert den SB-Filter in localStorage und stellt ihn wieder her", async () => {
    mockOk();
    const { unmount } = render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Alle Wiedervorlagen erledigt");
    fireEvent.click(screen.getByRole("button", { name: "TB" }));
    expect(JSON.parse(localStorage.getItem("dashboard.aktiveSB"))).toContain("TB");
    unmount();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await waitFor(() => expect(api.fristen).toHaveBeenCalledTimes(2));
    expect(JSON.parse(localStorage.getItem("dashboard.aktiveSB"))).toContain("TB");
  });

  it("zeigt bei komplett abgewähltem SB-Filter einen Hinweis statt leerer Kacheln", async () => {
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Alle Wiedervorlagen erledigt");
    fireEvent.click(screen.getByRole("button", { name: "AS" }));
    expect(screen.getByText("Kein Sachbearbeiter ausgewählt")).toBeInTheDocument();
    expect(screen.queryByText(/Keine Fristen in den nächsten/)).toBeNull();
  });

  it("markiert aktive SB-Chips per aria-pressed", async () => {
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Alle Wiedervorlagen erledigt");
    expect(screen.getByRole("button", { name: "AS" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByRole("button", { name: "TB" }));
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "true");
  });

  it("sperrt den Retry-Knopf, solange die Kacheln neu laden", async () => {
    mockOk();
    api.fristen.mockRejectedValue(new Error("kaputt"));
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Fristenkalender nicht erreichbar (E-Akte-Mount)");
    api.fristen.mockReturnValue(new Promise(() => {}));
    fireEvent.click(screen.getByRole("button", { name: "Erneut laden" }));
    await waitFor(() => expect(within(screen.getByRole("alert")).getByRole("button")).toBeDisabled());
  });

  it("versteckt Fristen ohne oder mit unbekanntem SB-Kürzel nie", async () => {
    mockOk({ fristen: [
      { az: "999/26", frist_art: "Berufung", frist_datum: "2026-08-01", tage_bis: 2, kurzbezeichnung: "Ohne Kürzel" },
      { az: "888/26 XY", frist_art: "Stellungnahme", frist_datum: "2026-08-02", tage_bis: 3, kurzbezeichnung: "Unbekanntes Kürzel" },
    ] });
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    expect(await screen.findByRole("button", { name: /999\/26/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /888\/26 XY/ })).toBeInTheDocument();
  });

  it("baut die SB-Chips aus der Einstellungs-Liste, mit Klarnamen als Tooltip", async () => {
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    const as = await screen.findByRole("button", { name: "AS" });
    expect(as).toHaveAttribute("title", "Andreas Schatz · Rechtsanwalt");
    expect(as).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("button", { name: "JH" })).toBeNull();
  });

  it("stellt die gespeicherte Auswahl wieder her und verwirft unbekannte Kürzel", async () => {
    localStorage.setItem("dashboard.aktiveSB", JSON.stringify(["TB", "ZZ"]));
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    expect(await screen.findByRole("button", { name: "TB" }))
      .toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "AS" })).toHaveAttribute("aria-pressed", "false");
  });

  it("filtert nicht, solange die Sachbearbeiter-Liste nicht geladen ist", async () => {
    mockOk({ fristen: [FRIST] });
    einst.sachbearbeiter.mockReturnValue(new Promise(() => {}));
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    expect(await screen.findAllByRole("button", { name: /312\/26 AS/ })).not.toHaveLength(0);
  });

  it("aktiviert ein neu hinzugekommenes Kürzel automatisch, auch wenn die gespeicherte Auswahl es nicht enthält", async () => {
    localStorage.setItem("dashboard.aktiveSB", JSON.stringify(["AS"]));
    localStorage.setItem("dashboard.bekannteSB", JSON.stringify(["AS", "CO", "TB"]));
    mockOk();
    einst.sachbearbeiter.mockResolvedValue({ eintraege: [
      ...SB_LISTE,
      { kuerzel: "CS", name: "Carina Salvagnin", titel: "Rechtsanwältin", aktiv: 1,
        ignoriert: 0, dashboard_vorauswahl: 0, sortierung: 60 },
    ] });
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    expect(await screen.findByRole("button", { name: "CS" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "AS" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "false");
  });

  it("lässt ein bewusst abgewähltes Kürzel abgewählt, solange kein neues Kürzel hinzukommt", async () => {
    localStorage.setItem("dashboard.aktiveSB", JSON.stringify([]));
    localStorage.setItem("dashboard.bekannteSB", JSON.stringify(["AS", "CO", "TB"]));
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Kein Sachbearbeiter ausgewählt");
    expect(screen.getByRole("button", { name: "AS" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "false");
  });

  it("wählt beim allerersten Öffnen ohne gespeicherten Stand nur die Vorauswahl, nicht alle", async () => {
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Alle Wiedervorlagen erledigt");
    expect(screen.getByRole("button", { name: "AS" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "false");
  });

  it("übernimmt ein während der Sitzung neu hinzugekommenes Kürzel schon beim Aktualisieren-Klick, ohne ein abgewähltes wieder zu aktivieren", async () => {
    localStorage.setItem("dashboard.aktiveSB", JSON.stringify(["AS"]));
    localStorage.setItem("dashboard.bekannteSB", JSON.stringify(["AS", "CO", "TB"]));
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Alle Wiedervorlagen erledigt");
    expect(screen.getByRole("button", { name: "AS" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("button", { name: "CS" })).toBeNull();

    einst.sachbearbeiter.mockResolvedValue({ eintraege: [
      ...SB_LISTE,
      { kuerzel: "CS", name: "Carina Salvagnin", titel: "Rechtsanwältin", aktiv: 1,
        ignoriert: 0, dashboard_vorauswahl: 0, sortierung: 60 },
    ] });
    fireEvent.click(screen.getByRole("button", { name: /Aktualisieren/ }));

    expect(await screen.findByRole("button", { name: "CS" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "AS" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "false");
  });

  it("persistiert die um ein neues Kürzel erweiterte Auswahl schon beim ersten Laden (Mount-Pfad)", async () => {
    localStorage.setItem("dashboard.aktiveSB", JSON.stringify(["AS"]));
    localStorage.setItem("dashboard.bekannteSB", JSON.stringify(["AS", "CO", "TB"]));
    mockOk();
    einst.sachbearbeiter.mockResolvedValue({ eintraege: [
      ...SB_LISTE,
      { kuerzel: "CS", name: "Carina Salvagnin", titel: "Rechtsanwältin", aktiv: 1,
        ignoriert: 0, dashboard_vorauswahl: 0, sortierung: 60 },
    ] });

    const { unmount } = render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    expect(await screen.findByRole("button", { name: "CS" })).toHaveAttribute("aria-pressed", "true");
    const gespeichert = JSON.parse(localStorage.getItem("dashboard.aktiveSB"));
    expect(gespeichert).toEqual(["AS", "CS"]);

    unmount();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    expect(await screen.findByRole("button", { name: "CS" })).toHaveAttribute("aria-pressed", "true");
  });

  it("überschreibt den bekannten Bestand nicht mit einer leeren Antwort", async () => {
    localStorage.setItem("dashboard.bekannteSB", JSON.stringify(["AS", "CO", "TB"]));
    api.termineHeute.mockResolvedValue({ eintraege: [] });
    api.fristen.mockResolvedValue({ eintraege: [] });
    api.wiedervorlagen.mockResolvedValue({ wv: [], ohne_wv: [] });
    einst.sachbearbeiter.mockResolvedValue({ eintraege: [] });

    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Alle Wiedervorlagen erledigt");
    expect(JSON.parse(localStorage.getItem("dashboard.bekannteSB"))).toEqual(["AS", "CO", "TB"]);
  });

  it("fasst weder Auswahl noch Bestand an, wenn die Antwort keine Kürzel enthält (leere Liste, Tabelle leer o. ä.)", async () => {
    localStorage.setItem("dashboard.aktiveSB", JSON.stringify(["AS"]));
    localStorage.setItem("dashboard.bekannteSB", JSON.stringify(["AS", "CO", "TB"]));
    api.termineHeute.mockResolvedValue({ eintraege: [] });
    api.fristen.mockResolvedValue({ eintraege: [] });
    api.wiedervorlagen.mockResolvedValue({ wv: [], ohne_wv: [] });
    einst.sachbearbeiter.mockResolvedValue({ eintraege: [] });

    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Alle Wiedervorlagen erledigt");
    expect(JSON.parse(localStorage.getItem("dashboard.aktiveSB"))).toEqual(["AS"]);
    expect(JSON.parse(localStorage.getItem("dashboard.bekannteSB"))).toEqual(["AS", "CO", "TB"]);

    einst.sachbearbeiter.mockResolvedValue({ eintraege: SB_LISTE });
    fireEvent.click(screen.getByRole("button", { name: /Aktualisieren/ }));

    expect(await screen.findByRole("button", { name: "AS" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "false");
  });

  it("wählt ohne gespeicherte Auswahl und ohne jede Vorauswahl alle aktiven Kürzel (lieber zu viel zeigen als eine Frist verschlucken)", async () => {
    const listeOhneVorauswahl = [
      { kuerzel: "AS", name: "Andreas Schatz", titel: "Rechtsanwalt", aktiv: 1, ignoriert: 0,
        dashboard_vorauswahl: 0, sortierung: 10 },
      { kuerzel: "TB", name: "Tanja Brunner", titel: "Rechtsanwalts- und Notarfachangestellte",
        aktiv: 1, ignoriert: 0, dashboard_vorauswahl: 0, sortierung: 70 },
    ];
    mockOk({ fristen: [FRIST] });
    einst.sachbearbeiter.mockResolvedValue({ eintraege: listeOhneVorauswahl });

    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);

    expect(await screen.findByRole("button", { name: "AS" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText("Kein Sachbearbeiter ausgewählt")).toBeNull();
    expect(screen.getByText("Jetzt dran")).toBeInTheDocument();
  });
});

describe("ActionBoardView – Kalenderfilter der Termine-Kachel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("bietet nur Anwaltskalender als Kalender-Chips an", async () => {
    mockOk({ termine: [TERMIN_AS] });
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByRole("button", { name: "Kalender AS" });
    expect(screen.getByRole("button", { name: "Kalender CO" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kalender TB" })).toBeNull();
  });

  it("blendet einen Termin ohne Akte aus, wenn sein Kalender abgewählt wird", async () => {
    mockOk({ termine: [TERMIN_OHNE_AKTE, TERMIN_AS] });
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText(/Sigkeris neue Sache/);
    fireEvent.click(screen.getByRole("button", { name: "Kalender CO" }));
    expect(screen.queryByText(/Sigkeris neue Sache/)).toBeNull();
    expect(screen.getByText(/Herr Kirto Pektas/)).toBeInTheDocument();
  });

  it("lässt den SB-Filter der Fristen die Termine unberührt", async () => {
    mockOk({ termine: [TERMIN_AS] });
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText(/Herr Kirto Pektas/);
    fireEvent.click(screen.getByRole("button", { name: "AS" }));
    expect(screen.getByText("Kein Sachbearbeiter ausgewählt")).toBeInTheDocument();
    expect(screen.getByText(/Herr Kirto Pektas/)).toBeInTheDocument();
  });

  it("persistiert den Kalenderfilter unter einem eigenen Schlüssel", async () => {
    mockOk({ termine: [TERMIN_AS] });
    const { unmount } = render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByRole("button", { name: "Kalender CO" });
    fireEvent.click(screen.getByRole("button", { name: "Kalender CO" }));
    expect(JSON.parse(localStorage.getItem("dashboard.aktiveKalenderSB"))).toEqual(["AS"]);
    expect(JSON.parse(localStorage.getItem("dashboard.aktiveSB"))).toEqual(["AS"]);
    unmount();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await waitFor(() => expect(api.termineHeute).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Kalender CO" })).toHaveAttribute("aria-pressed", "false"));
  });

  it("zeigt Termine unbekannter Kürzel weiter an (kein stilles Verschlucken)", async () => {
    mockOk({ termine: [{ az: "500/26XY", sb: "XY", termin_art: "Verhandlungstermin",
      betreff: "Fremd/Unbekannt", termin_datum: "2026-09-02", uhrzeit: "08:00", tage_bis: 0 }] });
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText(/Fremd\/Unbekannt/);
    fireEvent.click(screen.getByRole("button", { name: "Kalender AS" }));
    fireEvent.click(screen.getByRole("button", { name: "Kalender CO" }));
    expect(screen.getByText("Kein Kalender ausgewählt")).toBeInTheDocument();
  });
});
