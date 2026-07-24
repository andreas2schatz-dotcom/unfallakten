import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

const api = vi.hoisted(() => {
  const BAUSTEIN = {
    key: "schaden_gesamtbetrag", abschnitt: "schaden", abschnitt_label: "Unfallschaden",
    beschreibung: "Ohne Zahlungen: der volle Gesamtbetrag wird eingeklagt",
    standard_text: "Der Gesamtbetrag in Höhe von <GESAMTSCHADEN> wird mit dem Klageantrag zu 1 geltend gemacht.",
    override_text: null, geaendert_am: null,
    platzhalter: [{ key: "GESAMTSCHADEN", beschreibung: "Gesamtschaden", beispiel: "5.000,00 €", pflicht: true }],
  };
  const GEAENDERT = { ...BAUSTEIN, key: "schluss_hinweis", abschnitt: "schluss",
    abschnitt_label: "Schluss", beschreibung: "Schlussformel", platzhalter: [],
    standard_text: "Standard.", override_text: "Eigener Text.", geaendert_am: "2026-07-24 10:00:00" };

  return {
    liste: vi.fn().mockResolvedValue({ bausteine: [BAUSTEIN, GEAENDERT] }),
    speichern: vi.fn().mockResolvedValue({ ok: true }),
    reset: vi.fn().mockResolvedValue({ ok: true, geloescht: true }),
    vorschau: vi.fn().mockResolvedValue({ vorschau: "Vorschau." }),
    aufgeloest: vi.fn().mockResolvedValue({ texte: {} }),
  };
});
vi.mock("../api.js", () => ({ apiStandardtexte: api }));

import StandardtexteTab from "./StandardtexteTab.jsx";

describe("StandardtexteTab", () => {
  beforeEach(() => vi.clearAllMocks());

  it("gruppiert nach Abschnitt und markiert geaenderte Bausteine", async () => {
    render(<StandardtexteTab />);
    await waitFor(() => expect(screen.getByText("Unfallschaden")).toBeInTheDocument());
    expect(screen.getByText("Schluss")).toBeInTheDocument();
    expect(screen.getAllByText("geändert").length).toBe(1);
  });

  it("Suche filtert die Liste", async () => {
    render(<StandardtexteTab />);
    await waitFor(() => screen.getByText("Schlussformel"));
    fireEvent.change(screen.getByPlaceholderText(/Suche/i), { target: { value: "Gesamtbetrag" } });
    expect(screen.queryByText("Schlussformel")).toBeNull();
    expect(screen.getByText(/Gesamtbetrag wird eingeklagt/)).toBeInTheDocument();
  });

  it("Speichern mit fehlendem Pflicht-Platzhalter fragt nach Bestaetigung", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<StandardtexteTab />);
    await waitFor(() => screen.getByText(/Gesamtbetrag wird eingeklagt/));
    fireEvent.click(screen.getByText(/Gesamtbetrag wird eingeklagt/));
    const ta = await screen.findByDisplayValue(/Der Gesamtbetrag in Höhe von/);
    fireEvent.change(ta, { target: { value: "Ohne Platzhalter." } });
    fireEvent.click(screen.getByRole("button", { name: /Speichern/ }));
    await waitFor(() => expect(api.speichern).toHaveBeenCalledWith(
      "schaden_gesamtbetrag", "Ohne Platzhalter.", true));
    expect(confirmSpy).toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it("Reset ruft api.reset", async () => {
    render(<StandardtexteTab />);
    await waitFor(() => screen.getByText("Schlussformel"));
    fireEvent.click(screen.getByText("Schlussformel"));
    fireEvent.click(await screen.findByText(/Auf Standard zurücksetzen/));
    await waitFor(() => expect(api.reset).toHaveBeenCalledWith("schluss_hinweis"));
  });
});
