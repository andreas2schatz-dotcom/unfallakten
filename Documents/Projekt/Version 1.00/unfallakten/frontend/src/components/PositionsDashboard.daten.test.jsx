import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../api.js", () => ({
  API_BASE: "",
  tokenStore: { getAccess: () => "" },
}));

import PositionsDashboard from "./PositionsDashboard.jsx";

const DATEN = {
  positionen: {
    reparatur: { label: "Reparatur", gefordert: 8200, anerkannt: 6900, offen: 1300,
      zustand: "teilanerkannt", kategorie: "fahrzeugschaden", eskalationsstufe: 1,
      checkliste: { erledigt: [], offen: [] } },
  },
  registry_version: "abc12345",
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) })));
});

describe("PositionsDashboard mit daten-Prop", () => {
  it("rendert aus der Prop ohne eigenen Fetch", () => {
    render(<PositionsDashboard az="123/26" daten={DATEN} />);
    expect(screen.getByText("Reparatur")).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("zeigt bei ladeStatus=fehler die Fehlermeldung ohne eigenen Fetch", () => {
    render(<PositionsDashboard az="123/26" ladeStatus="fehler" />);
    expect(screen.getByText(/Positionsstatus nicht geladen: Verbindung fehlgeschlagen/)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("zeigt bei ladeStatus=laedt den Ladehinweis ohne eigenen Fetch", () => {
    render(<PositionsDashboard az="123/26" ladeStatus="laedt" />);
    expect(screen.getByText(/Lade Positionsstatus/)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
});
