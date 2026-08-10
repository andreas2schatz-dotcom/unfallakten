import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

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

import UebersichtSection, { StatusBand } from "./UebersichtSection.jsx";

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

describe("StatusBand-Aktions-Popover", () => {
  it("zeigt bei fehlender Vollmacht die Aktionen nach Klick auf die Pill", () => {
    render(<StatusBand ibanCheck={{ vollmacht_vorhanden: false, iban_vorhanden: true }}
      todos={[]} hq={100} akteId="123/26" mandant={{ email: "m@example.com", name: "Max Müller" }} />);
    fireEvent.click(screen.getByText(/Vollmacht fehlt/));
    expect(screen.getByText(/✉ anfordern/)).toBeInTheDocument();
    expect(screen.getByText(/PDF generieren/)).toBeInTheDocument();
  });
});

describe("Redesign B — Onboarding-Fächer", () => {
  const onboardingProps = {
    ...PROPS,
    akte: { ...PROPS.akte },
    st: { ...PROPS.st, schaden: {}, beteiligte: [{ rolle: "mandant", name: "Max Müller" }] },
    posDaten: { positionen: {} },
    kpiSummen: { gefordert: 0, reguliert: 0, offen: 0, quelle: "alt" },
    mandantChecks: { iban_vorhanden: false, vollmacht_vorhanden: false },
  };

  it("zeigt keinen OnboardingHub-Banner mehr", () => {
    render(<UebersichtSection {...onboardingProps} />);
    expect(screen.queryByText(/Bereichen vollständig/)).toBeNull();
  });

  it("öffnet den Fächer per Klick auf die Onboarding-Phase", () => {
    render(<UebersichtSection {...onboardingProps} />);
    fireEvent.click(screen.getByText(/1\/6/));
    expect(screen.getByText("Gegner / Schädiger")).toBeInTheDocument();
    expect(screen.getByText("Schadenspositionen")).toBeInTheDocument();
  });

  it("zeigt in Phase Regulierung keinen Onboarding-Chip", () => {
    render(<UebersichtSection {...PROPS}
      st={{ ...PROPS.st, abrechnungen: [{ id: 1, gesamt_reguliert: 6900, positionen: [] }] }} />);
    expect(screen.queryByText(/\/6/)).toBeNull();
  });
});
