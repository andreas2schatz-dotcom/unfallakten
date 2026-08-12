import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const api = vi.hoisted(() => ({
  sachbearbeiter:          vi.fn(),
  sachbearbeiterAnlegen:   vi.fn(),
  sachbearbeiterSpeichern: vi.fn(),
  sachbearbeiterLoeschen:  vi.fn(),
  sachbearbeiterAbgleich:  vi.fn(),
}));
vi.mock("../../api.js", () => ({ apiEinstellungen: api }));

import SachbearbeiterTab from "./SachbearbeiterTab.jsx";

const EINTRAEGE = [
  { kuerzel: "AS", name: "Andreas Schatz", titel: "Rechtsanwalt", anrede: "herr",
    rolle: "anwalt", aktiv: 1, ignoriert: 0, dashboard_vorauswahl: 1,
    kalender_name: "RA.Schatz", sortierung: 10 },
  { kuerzel: "JH", name: "Jochen Hofmann", titel: "Rechtsanwalt", anrede: "herr",
    rolle: "anwalt", aktiv: 0, ignoriert: 0, dashboard_vorauswahl: 0,
    kalender_name: null, sortierung: 110 },
];

describe("SachbearbeiterTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.sachbearbeiter.mockResolvedValue({ eintraege: EINTRAEGE });
    api.sachbearbeiterAbgleich.mockResolvedValue({ verfuegbar: false, kuerzel: {}, unbekannt: [] });
  });

  it("zeigt alle Sachbearbeiter und kennzeichnet ausgeschiedene", async () => {
    render(<SachbearbeiterTab />);
    expect(await screen.findByDisplayValue("Andreas Schatz")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Jochen Hofmann")).toBeInTheDocument();
    expect(screen.getByText("ausgeschieden")).toBeInTheDocument();
  });

  it("speichert eine geänderte Zeile", async () => {
    api.sachbearbeiterSpeichern.mockResolvedValue({ ok: true });
    render(<SachbearbeiterTab />);
    const feld = await screen.findByDisplayValue("Andreas Schatz");
    fireEvent.change(feld, { target: { value: "Andreas Schatz jun." } });
    fireEvent.click(screen.getAllByRole("button", { name: "Speichern" })[0]);
    await waitFor(() => expect(api.sachbearbeiterSpeichern).toHaveBeenCalledWith(
      "AS", expect.objectContaining({ name: "Andreas Schatz jun." })));
  });

  it("zeigt die Fehlermeldung des Servers", async () => {
    api.sachbearbeiterSpeichern.mockRejectedValue(
      new Error("Kalendername 'RA.Schatz' ist bereits AS zugeordnet."));
    render(<SachbearbeiterTab />);
    const feld = await screen.findByDisplayValue("Andreas Schatz");
    fireEvent.change(feld, { target: { value: "X" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Speichern" })[0]);
    expect(await screen.findByText(/bereits AS zugeordnet/)).toBeInTheDocument();
  });

  it("bewahrt ungespeicherte Änderungen anderer Zeilen beim Speichern und übernimmt den Server-Wert der gespeicherten Zeile", async () => {
    const eintraegeNachSpeichern = [
      { ...EINTRAEGE[0], name: "Andreas Schatz (Server)" },
      EINTRAEGE[1],
    ];
    api.sachbearbeiter
      .mockResolvedValueOnce({ eintraege: EINTRAEGE })
      .mockResolvedValueOnce({ eintraege: eintraegeNachSpeichern });
    api.sachbearbeiterSpeichern.mockResolvedValue({ ok: true, eintrag: eintraegeNachSpeichern[0] });

    render(<SachbearbeiterTab />);
    const feldAS = await screen.findByDisplayValue("Andreas Schatz");
    const feldJH = await screen.findByDisplayValue("Jochen Hofmann");

    fireEvent.change(feldAS, { target: { value: "Andreas Schatz jun." } });
    fireEvent.change(feldJH, { target: { value: "Jochen Hofmann (Entwurf)" } });

    fireEvent.click(screen.getAllByRole("button", { name: "Speichern" })[0]);

    await waitFor(() => expect(api.sachbearbeiter).toHaveBeenCalledTimes(2));

    expect(await screen.findByDisplayValue("Andreas Schatz (Server)")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Jochen Hofmann (Entwurf)")).toBeInTheDocument();
  });
});
