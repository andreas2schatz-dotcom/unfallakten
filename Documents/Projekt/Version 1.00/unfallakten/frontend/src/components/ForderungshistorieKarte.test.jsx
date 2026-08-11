import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("../api.js", () => ({
  forderungen: {
    nachSchreiben: vi.fn(),
    klageFlagSetzen: vi.fn(),
    aktualisieren: vi.fn(),
  },
}));

import { forderungen } from "../api.js";
import ForderungshistorieKarte from "./ForderungshistorieKarte.jsx";

const schreiben = (nr) => ({
  schreiben_nr: nr,
  datum: "2026-08-01",
  dokument_id: null,
  gesamt_gefordert: 300,
  gesamt_reguliert: 0,
  positionen_offen: 0,
  positionen: [],
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe("I-9 – Race + Fehlerzustand ForderungshistorieKarte", () => {
  it("verwirft die verspätete Antwort der vorherigen Akte", async () => {
    let resolveA;
    forderungen.nachSchreiben
      .mockImplementationOnce(() => new Promise((res) => { resolveA = res; }))
      .mockImplementationOnce(() =>
        Promise.resolve({ schreiben: [schreiben(1)] }));

    const { rerender } = render(<ForderungshistorieKarte akteId="1/26" />);
    rerender(<ForderungshistorieKarte akteId="2/26" />);

    await screen.findByText(/Forderungsschreiben Nr. 1/);

    resolveA({ schreiben: [schreiben(9)] });
    await waitFor(() =>
      expect(screen.queryByText(/Forderungsschreiben Nr. 9/)).toBeNull());
    expect(screen.getByText(/Forderungsschreiben Nr. 1/)).toBeInTheDocument();
  });

  it("zeigt beim Aktenwechsel wieder den Ladezustand", async () => {
    forderungen.nachSchreiben
      .mockImplementationOnce(() =>
        Promise.resolve({ schreiben: [schreiben(1)] }))
      .mockImplementationOnce(() => new Promise(() => {}));

    const { rerender } = render(<ForderungshistorieKarte akteId="1/26" />);
    await screen.findByText(/Forderungsschreiben Nr. 1/);

    rerender(<ForderungshistorieKarte akteId="2/26" />);
    expect(
      await screen.findByText(/Forderungshistorie wird geladen/)
    ).toBeInTheDocument();
  });

  it("zeigt einen Fehlerzustand statt 'noch kein Schreiben'", async () => {
    forderungen.nachSchreiben.mockImplementationOnce(() =>
      Promise.reject(new Error("kaputt")));

    render(<ForderungshistorieKarte akteId="1/26" />);
    expect(
      await screen.findByText(/konnte nicht geladen werden/)
    ).toBeInTheDocument();
    expect(screen.queryByText(/Noch kein Forderungsschreiben/)).toBeNull();
  });
});
