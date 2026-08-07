import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

const api = vi.hoisted(() => ({
  apiIntake: {
    queue: vi.fn(() => Promise.resolve({ eintraege: [
      { id: 516, klasse: "pruefbericht", queue_status: "bereit_zur_review",
        konfidenz: 0.9, erstellt_am: "2026-08-07 09:00:00" },
    ] })),
    detail: vi.fn(),
    entfernungPruefen: vi.fn(() => Promise.resolve({
      ok: true,
      werkstatt_name: "Möser Arno - Karosseriefachbetrieb",
      werkstatt_adresse: "Philipp-Reis-Straße 9, 63128 Dietzenbach",
      km_genannt: 16.0, km_echt: 24.3, minuten: 31, abweichung_km: 8.3,
      unzumutbar: true, textbaustein: "Den dortigen Verweis ...",
      referenzwerkstatt: {},
    })),
    ereignistypen: vi.fn(() => Promise.resolve({ typen: [] })),
    klassen: vi.fn(() => Promise.resolve({ klassen: [] })),
  },
  apiAktenanlage: { offen: vi.fn(() => Promise.resolve({ vorgaenge: [], ramicro_verfuegbar: true })) },
  tokenStore: { getAccess: vi.fn(() => "test-token") },
  API_BASE: "http://localhost:5000",
}));
vi.mock("../api", () => api);

import ReviewQueueView from "./ReviewQueueView.jsx";

const PRUEF_DETAIL = {
  id: 516, klasse: "pruefbericht", queue_status: "bereit_zur_review",
  payload_typ: "pdf",
  parse: {
    felder: { referenzwerkstatt: {
      name: "Möser Arno - Karosseriefachbetrieb",
      adresse: "Philipp-Reis-Straße 9", plz_ort: "63128 Dietzenbach",
      telefon: "", km_genannt: 16.0, quelle: "vhv_block",
    } },
    akten_kandidaten: [{ akte_az: "1280/25", score: 1.0, quelle: "az_exakt" }],
  },
  zustellungen: [],
};

function setDetail(fixture) {
  api.apiIntake.detail.mockImplementation(() => Promise.resolve(fixture));
}

beforeEach(() => {
  api.apiIntake.detail.mockReset();
  api.apiIntake.entfernungPruefen.mockClear();
  setDetail(PRUEF_DETAIL);
});

describe("ReviewQueueView Entfernungsprüfung", () => {
  it("prüft die Entfernung und zeigt das Ergebnis-Popup", async () => {
    render(<ReviewQueueView onOpenAkte={() => {}} initialIntakeId={516} />);
    const btn = await screen.findByRole("button", { name: /Entfernung prüfen/ });
    await waitFor(() => expect(btn.disabled).toBe(false));
    fireEvent.click(btn);
    await waitFor(() => expect(api.apiIntake.entfernungPruefen)
      .toHaveBeenCalledWith(516, "1280/25"));
    await screen.findByText(/Entfernungsprüfung Referenzwerkstatt/);
    expect(screen.getByText(/24,3 km/)).toBeTruthy();
    expect(screen.getByText(/Nicht zumutbar/)).toBeTruthy();
  });

  it("zeigt den Button nur bei Klasse pruefbericht", async () => {
    setDetail({ ...PRUEF_DETAIL, id: 517, klasse: "abrechnungsschreiben" });
    render(<ReviewQueueView onOpenAkte={() => {}} initialIntakeId={517} />);
    await waitFor(() => expect(api.apiIntake.detail).toHaveBeenCalled());
    await screen.findByText(/Extrahierte Felder/);
    expect(screen.queryByRole("button", { name: /Entfernung prüfen/ })).toBeNull();
  });

  it("deaktiviert den Button ohne gewählte Akte und zeigt einen Hinweis", async () => {
    setDetail({ ...PRUEF_DETAIL, id: 518,
      parse: { ...PRUEF_DETAIL.parse, akten_kandidaten: [] } });
    render(<ReviewQueueView onOpenAkte={() => {}} initialIntakeId={518} />);
    const btn = await screen.findByRole("button", { name: /Entfernung prüfen/ });
    expect(btn.disabled).toBe(true);
    expect(screen.getByText(/Erst Akte auswählen/)).toBeTruthy();
  });

  it("zeigt den Fehler im Popup, wenn der Endpoint einen Fehler liefert", async () => {
    api.apiIntake.entfernungPruefen.mockRejectedValueOnce(
      new Error("Mandanten-Adresse für Akte 1280/25 nicht gefunden"));
    render(<ReviewQueueView onOpenAkte={() => {}} initialIntakeId={516} />);
    const btn = await screen.findByRole("button", { name: /Entfernung prüfen/ });
    await waitFor(() => expect(btn.disabled).toBe(false));
    fireEvent.click(btn);
    await screen.findByText(/Mandanten-Adresse für Akte 1280\/25 nicht gefunden/);
  });
});
