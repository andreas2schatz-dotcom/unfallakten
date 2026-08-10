import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

vi.mock("../api.js", () => ({
  API_BASE: "",
  ping: vi.fn(),
  ApiError: class ApiError extends Error {},
  tokenStore: { getAccess: () => "" },
  request: vi.fn(() => Promise.resolve({})),
  akten: { aktivitaeten: vi.fn(() => Promise.resolve({})), aktivitaetLoeschen: vi.fn(), aktualisieren: vi.fn(), pwaMessage: vi.fn() },
  beteiligte: { liste: vi.fn(() => Promise.resolve({ beteiligte: [] })) },
  schaden: { holen: vi.fn(() => Promise.resolve({})), speichern: vi.fn() },
  apiTodos: { liste: vi.fn(() => Promise.resolve({ todos: [] })), erstelle: vi.fn(), update: vi.fn(), loesche: vi.fn() },
  ramicroWdm: { schaden: vi.fn(() => Promise.resolve({})) },
  belege: { kandidaten: vi.fn(() => Promise.resolve({ kandidaten: [] })) },
  portalAkteAktivieren: vi.fn(() => Promise.resolve({})),
  forderungen: { nachSchreiben: vi.fn(() => Promise.resolve({ schreiben: [] })), klageFlagSetzen: vi.fn(), aktualisieren: vi.fn() },
  ramicroAkte: { laden: vi.fn(() => Promise.resolve(null)) },
  apiSta: { kontext: vi.fn(), generieren: vi.fn() },
  wiedervorlage: { suchen: vi.fn(() => Promise.resolve({})) },
  emailImport: { aktionErledigt: vi.fn() },
}));

import AkteDetailView from "./AkteDetailView.jsx";

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: false, json: () => Promise.resolve({}) })));
});

describe("B4 – '+ Todo' im Akten-Header", () => {
  it("öffnet beim Klick ein To-Do-Eingabeformular", async () => {
    render(
      <AkteDetailView
        akte={{ id: "1/26", az: "1/26", az_roh: "1/26", hq: 100, status: "offen" }}
        st={{}}
        dispatch={vi.fn()}
      />
    );
    fireEvent.click(screen.getByText("+ Todo"));
    expect(await screen.findByPlaceholderText(/To-Do Text/)).toBeInTheDocument();
  });
});
