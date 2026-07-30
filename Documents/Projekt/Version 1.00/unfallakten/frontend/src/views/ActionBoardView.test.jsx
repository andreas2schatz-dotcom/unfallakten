import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const api = vi.hoisted(() => ({
  termineHeute:   vi.fn(),
  fristen:        vi.fn(),
  wiedervorlagen: vi.fn(),
  nachrichtenNeu: vi.fn(),
}));
vi.mock("../api", () => ({ apiDashboard: api }));

import ActionBoardView from "./ActionBoardView.jsx";

const FRIST = { az: "312/26 AS", frist_art: "Stellungnahme", frist_datum: "2026-07-27", tage_bis: -3, kurzbezeichnung: "Müller ./. HUK" };

function mockOk({ fristen = [], termine = [], wv = [], ohne_wv = [] } = {}) {
  api.termineHeute.mockResolvedValue({ eintraege: termine });
  api.fristen.mockResolvedValue({ eintraege: fristen });
  api.wiedervorlagen.mockResolvedValue({ wv, ohne_wv });
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

  it("ruft nachrichtenNeu nicht mehr auf und zeigt keinen Posteingang", async () => {
    mockOk();
    render(<ActionBoardView onOpenAkte={() => {}} onOpenWiedervorlage={() => {}} />);
    await screen.findByText("Keine Fristen in den nächsten 14 Tagen");
    expect(api.nachrichtenNeu).not.toHaveBeenCalled();
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
    for (const sb of ["AS", "PK", "CO", "MM", "AH"]) {
      fireEvent.click(screen.getByRole("button", { name: sb }));
    }
    expect(screen.getByText("Kein Sachbearbeiter ausgewählt")).toBeInTheDocument();
    expect(screen.queryByText(/Keine Fristen in den nächsten/)).toBeNull();
  });
});
