import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api.js", () => ({
  API_BASE: "",
  ping: vi.fn(),
  ApiError: class ApiError extends Error {},
  tokenStore: { getAccess: () => "" },
  request: vi.fn(() => Promise.resolve({})),
  akten: { aktivitaeten: vi.fn(() => Promise.resolve({})), aktualisieren: vi.fn() },
  forderungen: { nachSchreiben: vi.fn(() => Promise.resolve({ schreiben: [] })) },
  ramicroAkte: { laden: vi.fn(() => Promise.resolve(null)) },
  apiTodos: {
    liste: vi.fn(() => Promise.resolve({ todos: [] })),
    erstelle: vi.fn(), update: vi.fn(), loesche: vi.fn(),
  },
  apiAkteFristen: { liste: vi.fn(() => Promise.resolve({ fristen: [] })) },
  apiSta: { kontext: vi.fn(), generieren: vi.fn() },
}));

import { TodoSection } from "./UebersichtSection.jsx";
import { apiAkteFristen } from "../api.js";

const FRIST = {
  frist_datum: "2026-09-17", frist_beginn: "2026-09-03",
  frist_art: "Schriftsatzschluss", bemerkung: "", sb: "PK",
  gerichts_az: "AZ: 2-15 S 68/25", ist_vorfrist: false, tage_bis: -4,
};

const VORFRIST = {
  ...FRIST, frist_art: "Vorfrist Schriftsatzschluss",
  ist_vorfrist: true, tage_bis: -11,
};

beforeEach(() => {
  vi.clearAllMocks();
  apiAkteFristen.liste.mockResolvedValue({ fristen: [] });
});

describe("Fristen in der Akten-Übersicht", () => {
  it("zeigt die Fristen der Akte über den To-Dos", async () => {
    apiAkteFristen.liste.mockResolvedValue({ fristen: [FRIST] });
    render(<TodoSection az="322/26" />);
    await screen.findByText("Schriftsatzschluss");
    expect(screen.getByText(/aus RA-MICRO/)).toBeInTheDocument();
    expect(screen.getByText("Frist: 17.09.2026")).toBeInTheDocument();
  });

  it("markiert eine überfällige Frist auffällig", async () => {
    apiAkteFristen.liste.mockResolvedValue({ fristen: [FRIST] });
    render(<TodoSection az="322/26" />);
    expect(await screen.findByText("4 Tage überfällig")).toBeInTheDocument();
  });

  it("kennzeichnet Vorfristen und macht sie nicht dringlich", async () => {
    apiAkteFristen.liste.mockResolvedValue({ fristen: [VORFRIST] });
    render(<TodoSection az="322/26" />);
    expect(await screen.findByText("Vorfrist")).toBeInTheDocument();
    expect(screen.queryByText(/überfällig/)).toBeNull();
  });

  it("bietet keinen Erledigt-Haken — abgehakt wird in RA-MICRO", async () => {
    apiAkteFristen.liste.mockResolvedValue({ fristen: [FRIST] });
    render(<TodoSection az="322/26" />);
    await screen.findByText("Schriftsatzschluss");
    expect(screen.getByText(/wird dort abgehakt/)).toBeInTheDocument();
    expect(screen.queryByTitle("Als erledigt markieren")).toBeNull();
  });

  it("blendet den Block aus, wenn die Akte keine Fristen hat", async () => {
    render(<TodoSection az="322/26" />);
    await waitFor(() => expect(apiAkteFristen.liste).toHaveBeenCalled());
    expect(screen.queryByText(/aus RA-MICRO/)).toBeNull();
  });

  it("zeigt den fehlenden E-Akte-Mount statt stillschweigend nichts", async () => {
    apiAkteFristen.liste.mockRejectedValue(new Error("503"));
    render(<TodoSection az="322/26" />);
    expect(await screen.findByText("Fristenkalender nicht erreichbar (E-Akte-Mount)"))
      .toBeInTheDocument();
  });

  it("lädt nach einem Fehler per Knopf neu", async () => {
    apiAkteFristen.liste.mockRejectedValue(new Error("503"));
    render(<TodoSection az="322/26" />);
    await screen.findByText("Fristenkalender nicht erreichbar (E-Akte-Mount)");

    apiAkteFristen.liste.mockResolvedValue({ fristen: [FRIST] });
    fireEvent.click(screen.getByRole("button", { name: "Erneut laden" }));
    expect(await screen.findByText("Schriftsatzschluss")).toBeInTheDocument();
  });
});
