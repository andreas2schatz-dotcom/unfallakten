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

import {
  RegulierungsTabelle,
  AktenTimeline,
  StatusBand,
  RechtsschutzKlappkachel,
} from "./UebersichtSection.jsx";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, json: () => Promise.resolve({}) })));
});

describe("B1 – RegulierungsTabelle ohne Abrechnungsart", () => {
  it("rendert Totalschaden-Zeilen ohne Crash, wenn keine abrechnungsart gesetzt ist", () => {
    render(
      <RegulierungsTabelle
        schaden={{ wiederbeschaffung: 10000, restwert: 2000 }}
        abrechnungen={[]}
      />
    );
    expect(screen.getByText(/Wiederbeschaffung/i)).toBeInTheDocument();
  });
});

describe("B6 – Akten-Chronik Sortierung", () => {
  it("sortiert Einträge chronologisch absteigend, auch mit Uhrzeiten", () => {
    const { container } = render(
      <AktenTimeline
        akteId="1/26"
        abrechnungen={[{ id: 1, datum: "2026-05-01", versicherung: "HUK-COBURG", gesamt_reguliert: 1000, gesamt_kuerzung: 0 }]}
        aktivitaeten={[
          { id: 1, aktion: "akte_erstellt", beschreibung: "Akte angelegt", zeitstempel: "2026-03-15 18:25:19" },
          { id: 2, aktion: "dokument_hochgeladen", beschreibung: "PDF hochgeladen", zeitstempel: "2026-04-02 09:00:00" },
        ]}
      />
    );
    const text = container.textContent;
    const posMai = text.indexOf("HUK-COBURG");
    const posApril = text.indexOf("Dokument hochgeladen");
    const posMaerz = text.indexOf("Akte angelegt");
    expect(posMai).toBeGreaterThan(-1);
    expect(posApril).toBeGreaterThan(-1);
    expect(posMaerz).toBeGreaterThan(-1);
    expect(posMai).toBeLessThan(posApril);
    expect(posApril).toBeLessThan(posMaerz);
  });
});

describe("B7 – StatusBand Fristtyp", () => {
  it("zeigt die §3a-Frist-Pill für To-Dos mit frist_typ 'gericht'", () => {
    render(
      <StatusBand
        ibanCheck={{}}
        hq={100}
        todos={[{ id: 1, erledigt: false, frist_typ: "gericht", faellig_am: "2099-01-01" }]}
      />
    );
    expect(screen.getByText(/§3a-Frist/)).toBeInTheDocument();
  });
});

describe("B8 – Rechtsschutz-Kachel", () => {
  it("zeigt das RSV-Aktenzeichen nur einmal an", () => {
    render(
      <RechtsschutzKlappkachel
        beteiligte={[{ name: "ARAG SE", betreff1: "RS-2026-99" }]}
      />
    );
    fireEvent.click(screen.getByText(/Rechtsschutzversicherung/i));
    expect(screen.getAllByText("RS-2026-99")).toHaveLength(1);
  });
});
