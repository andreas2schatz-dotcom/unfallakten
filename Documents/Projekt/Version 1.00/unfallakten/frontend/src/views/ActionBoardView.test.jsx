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
    dashboard_vorauswahl: 1, sortierung: 10 },
  { kuerzel: "TB", name: "Tanja Brunner", titel: "Rechtsanwalts- und Notarfachangestellte",
    aktiv: 1, ignoriert: 0, dashboard_vorauswahl: 0, sortierung: 70 },
  { kuerzel: "JH", name: "Jochen Hofmann", titel: "Rechtsanwalt", aktiv: 0, ignoriert: 0,
    dashboard_vorauswahl: 0, sortierung: 110 },
];

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
    await screen.findByText("Fristen konnten nicht geladen werden");
    expect(screen.queryByText(/Keine Fristen in den nächsten/)).toBeNull();
    api.fristen.mockResolvedValue({ eintraege: [] });
    fireEvent.click(screen.getByRole("button", { name: "Erneut laden" }));
    await screen.findByText("Keine Fristen in den nächsten 14 Tagen");
    expect(api.fristen).toHaveBeenCalledTimes(2);
  });

  it("zeigt keinen Posteingang mehr", async () => {
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Keine Fristen in den nächsten 14 Tagen");
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
    await screen.findByText("Keine Fristen in den nächsten 14 Tagen");
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
    await screen.findByText("Keine Fristen in den nächsten 14 Tagen");
    fireEvent.click(screen.getByRole("button", { name: "AS" }));
    expect(screen.getByText("Kein Sachbearbeiter ausgewählt")).toBeInTheDocument();
    expect(screen.queryByText(/Keine Fristen in den nächsten/)).toBeNull();
  });

  it("markiert aktive SB-Chips per aria-pressed", async () => {
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Keine Fristen in den nächsten 14 Tagen");
    expect(screen.getByRole("button", { name: "AS" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByRole("button", { name: "TB" }));
    expect(screen.getByRole("button", { name: "TB" })).toHaveAttribute("aria-pressed", "true");
  });

  it("sperrt den Retry-Knopf, solange die Kacheln neu laden", async () => {
    mockOk();
    api.fristen.mockRejectedValue(new Error("kaputt"));
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Fristen konnten nicht geladen werden");
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
});
