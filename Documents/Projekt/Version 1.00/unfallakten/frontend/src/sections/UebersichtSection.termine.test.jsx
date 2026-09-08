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
  apiAkteTermine: { liste: vi.fn(() => Promise.resolve({ termine: [] })) },
  apiSta: { kontext: vi.fn(), generieren: vi.fn() },
}));

import { TodoSection } from "./UebersichtSection.jsx";
import { apiAkteTermine } from "../api.js";

const TERMIN = {
  termin_art: "Gütetermin",
  betreff: "Karic/DA Deutsche Allg.",
  termin_datum: "2026-10-02",
  uhrzeit: "09:00",
  tage_bis: 25,
  sb: "SK",
  ort: "LG Darmstadt, Steubenplatz 12, Saal 218",
  bemerkung: "Mdt. lädt selbst · Tel. 069 123456",
  ist_gerichtstermin: true,
};

beforeEach(() => {
  vi.clearAllMocks();
  apiAkteTermine.liste.mockResolvedValue({ termine: [] });
});

describe("Termine in der Akten-Übersicht", () => {
  it("zeigt die Termine der Akte bei den To-Dos", async () => {
    apiAkteTermine.liste.mockResolvedValue({ termine: [TERMIN] });
    render(<TodoSection az="322/26" />);
    await screen.findByText("Gütetermin");
    expect(screen.getByText(/02\.10\.2026/)).toBeInTheDocument();
    expect(screen.getByText(/09:00/)).toBeInTheDocument();
    expect(screen.getByText(/aus RA-MICRO/)).toBeInTheDocument();
  });

  it("nennt zugeklappt nur das Gericht, nicht die ganze Anschrift", async () => {
    apiAkteTermine.liste.mockResolvedValue({ termine: [TERMIN] });
    render(<TodoSection az="322/26" />);
    await screen.findByText("Gütetermin");
    expect(screen.getByText(/LG Darmstadt/)).toBeInTheDocument();
    expect(screen.queryByText(/Steubenplatz/)).toBeNull();
  });

  it("klappt Ort, Sachbearbeiter und Notiz beim Klick auf", async () => {
    apiAkteTermine.liste.mockResolvedValue({ termine: [TERMIN] });
    render(<TodoSection az="322/26" />);
    const zeile = await screen.findByRole("button", { name: /Gütetermin/ });
    expect(zeile).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(zeile);

    expect(zeile).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("LG Darmstadt, Steubenplatz 12, Saal 218")).toBeInTheDocument();
    expect(screen.getByText("Mdt. lädt selbst · Tel. 069 123456")).toBeInTheDocument();
    expect(screen.getByText("SK")).toBeInTheDocument();
  });

  it("klappt beim zweiten Klick wieder zu", async () => {
    apiAkteTermine.liste.mockResolvedValue({ termine: [TERMIN] });
    render(<TodoSection az="322/26" />);
    const zeile = await screen.findByRole("button", { name: /Gütetermin/ });
    fireEvent.click(zeile);
    fireEvent.click(zeile);
    expect(zeile).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Mdt. lädt selbst · Tel. 069 123456")).toBeNull();
  });

  it("sagt, wie weit der Termin weg ist", async () => {
    apiAkteTermine.liste.mockResolvedValue({
      termine: [
        { ...TERMIN, termin_art: "Ortstermin", tage_bis: 0 },
        { ...TERMIN, termin_art: "Anhörung", tage_bis: 1 },
        { ...TERMIN, termin_art: "Verhandlung", tage_bis: 25 },
        { ...TERMIN, termin_art: "Beweisaufnahme", tage_bis: -12 },
      ],
    });
    render(<TodoSection az="322/26" />);
    await screen.findByText("Ortstermin");
    expect(screen.getByText("heute")).toBeInTheDocument();
    expect(screen.getByText("morgen")).toBeInTheDocument();
    expect(screen.getByText("in 25 Tagen")).toBeInTheDocument();
    expect(screen.getByText("vor 12 Tagen")).toBeInTheDocument();
  });

  it("bietet keinen Erledigt-Haken — gepflegt wird in RA-MICRO", async () => {
    apiAkteTermine.liste.mockResolvedValue({ termine: [TERMIN] });
    render(<TodoSection az="322/26" />);
    await screen.findByText("Gütetermin");
    expect(screen.getByText(/wird dort gepflegt/)).toBeInTheDocument();
    expect(screen.queryByTitle("Als erledigt markieren")).toBeNull();
  });

  it("blendet den Block aus, wenn die Akte keine Termine hat", async () => {
    render(<TodoSection az="322/26" />);
    await waitFor(() => expect(apiAkteTermine.liste).toHaveBeenCalled());
    expect(screen.queryByText(/wird dort gepflegt/)).toBeNull();
  });

  it("zeigt einen RA-MICRO-Ausfall statt stillschweigend nichts", async () => {
    apiAkteTermine.liste.mockRejectedValue(new Error("503"));
    render(<TodoSection az="322/26" />);
    expect(await screen.findByText("RA-MICRO nicht erreichbar")).toBeInTheDocument();
  });

  it("lädt nach einem Fehler per Knopf neu", async () => {
    apiAkteTermine.liste.mockRejectedValue(new Error("503"));
    render(<TodoSection az="322/26" />);
    await screen.findByText("RA-MICRO nicht erreichbar");

    apiAkteTermine.liste.mockResolvedValue({ termine: [TERMIN] });
    fireEvent.click(screen.getByRole("button", { name: "Termine erneut laden" }));
    expect(await screen.findByText("Gütetermin")).toBeInTheDocument();
  });
});
