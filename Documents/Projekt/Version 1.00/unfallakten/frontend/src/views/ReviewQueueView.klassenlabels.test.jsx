import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const api = vi.hoisted(() => ({
  apiIntake: {
    queue: vi.fn(() => Promise.resolve({ eintraege: [
      { id: 461, klasse: "sv_rechnung",
        queue_status: "bereit_zur_review", konfidenz: 0.9,
        erstellt_am: "2026-08-04 06:19:47" },
    ] })),
    detail: vi.fn(() => Promise.resolve({ id: 461, klasse: "sv_rechnung",
      queue_status: "bereit_zur_review", felder: {}, parse: {},
      akten_kandidaten: [], zustellungen: [] })),
    ereignistypen: vi.fn(() => Promise.resolve({ typen: [] })),
    klassen: vi.fn(() => Promise.resolve({ klassen: [
      { wert: "sonstiges",   label: "Sonstiges" },
      { wert: "sv_rechnung", label: "SV-/Gutachterrechnung" },
    ] })),
  },
  apiAktenanlage: { offen: vi.fn(() => Promise.resolve({ vorgaenge: [], ramicro_verfuegbar: true })) },
  tokenStore: { getAccess: vi.fn(() => "test-token") },
  API_BASE: "http://localhost:5000",
}));
vi.mock("../api", () => api);

import ReviewQueueView from "./ReviewQueueView.jsx";

describe("ReviewQueueView Klassen-Labels", () => {
  it("zeigt im Dropdown das Label, nicht den technischen Schluessel", async () => {
    render(<ReviewQueueView onOpenAkte={() => {}} initialIntakeId={461} />);
    const option = await screen.findByRole("option", { name: "SV-/Gutachterrechnung" });
    expect(option).toHaveValue("sv_rechnung");
    expect(screen.queryByRole("option", { name: "sv_rechnung" })).toBeNull();
  });

  it("zeigt die Klasse der Trefferliste als Label", async () => {
    render(<ReviewQueueView onOpenAkte={() => {}} />);
    await waitFor(() => expect(api.apiIntake.queue).toHaveBeenCalled());
    expect(await screen.findByText("SV-/Gutachterrechnung")).toBeInTheDocument();
  });
});
