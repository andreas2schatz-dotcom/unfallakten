import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../api.js", () => ({
  API_BASE: "",
  ping: vi.fn(),
  ApiError: class ApiError extends Error {},
  tokenStore: { getAccess: () => "" },
  request: vi.fn(() => Promise.resolve({})),
  akten: { aktivitaeten: vi.fn(() => Promise.resolve({})), aktivitaetLoeschen: vi.fn(), aktualisieren: vi.fn(), pwaMessage: vi.fn() },
  forderungen: { nachSchreiben: vi.fn(() => Promise.resolve({ schreiben: [] })), klageFlagSetzen: vi.fn(), aktualisieren: vi.fn() },
  ramicroAkte: { laden: vi.fn(() => Promise.resolve(null)) },
  apiTodos: { liste: vi.fn(() => Promise.resolve({ todos: [] })), erstelle: vi.fn(), update: vi.fn(), loesche: vi.fn() },
  apiSta: { kontext: vi.fn(), generieren: vi.fn() },
}));

import UebersichtSection from "./UebersichtSection.jsx";

const PROPS = {
  akte: { id: "123/26", az: "123/26", az_roh: "123/26", hq: 100, status: "offen" },
  st: { schaden: { gesamt_brutto: 9600 }, abrechnungen: [], beteiligte: [], dokumente: [], aktivitaeten: [] },
  dispatch: () => {},
  onNavigate: () => {},
  posDaten: { positionen: { reparatur: { label: "Reparatur", gefordert: 8200, anerkannt: 6900, offen: 1300,
    zustand: "teilanerkannt", kategorie: "fahrzeugschaden", eskalationsstufe: 1,
    checkliste: { erledigt: [], offen: [] } } } },
  kpiSummen: { gefordert: 8200, reguliert: 6900, offen: 1300, quelle: "ereignismodell" },
  mandantChecks: { iban_vorhanden: true, vollmacht_vorhanden: true },
};

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, json: () => Promise.resolve({}) })));
});

describe("Übersicht-Redesign A — eine Wahrheit pro Information", () => {
  it("zeigt weder FinanzBand noch RegulierungsTabelle noch Forderungshistorie", () => {
    render(<UebersichtSection {...PROPS} />);
    expect(screen.queryByText(/Regulierungsfortschritt/)).toBeNull();
    expect(screen.queryByText(/Forderung vs\. Regulierung/)).toBeNull();
    expect(screen.queryByText(/Forderungshistorie/)).toBeNull();
    expect(screen.getByText("Reparatur")).toBeInTheDocument();
  });

  it("bietet nur noch drei Akkordeons an", () => {
    render(<UebersichtSection {...PROPS} />);
    expect(screen.getByText(/RA-Micro Beteiligte/)).toBeInTheDocument();
    expect(screen.getByText(/Chronik/)).toBeInTheDocument();
    expect(screen.getByText(/Notizen/)).toBeInTheDocument();
    expect(screen.queryByText(/Regulierungsdetails/)).toBeNull();
  });
});
