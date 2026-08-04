import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const api = vi.hoisted(() => ({
  apiIntake: {
    queue: vi.fn(() => Promise.resolve({ eintraege: [
      { id: 461, klasse: "abrechnungsschreiben",
        queue_status: "bereit_zur_review", konfidenz: 0.9, erstellt_am: "2026-08-04 06:19:47" },
    ] })),
    detail: vi.fn(() => Promise.resolve({ id: 461, klasse: "abrechnungsschreiben",
      queue_status: "bereit_zur_review", felder: {}, parse: {},
      akten_kandidaten: [], zustellungen: [] })),
    ereignistypen: vi.fn(() => Promise.resolve({ typen: [] })),
    klassen: vi.fn(() => Promise.resolve({ klassen: [] })),
  },
  apiAktenanlage: { offen: vi.fn(() => Promise.resolve({ vorgaenge: [], ramicro_verfuegbar: true })) },
  tokenStore: { getAccess: vi.fn(() => "test-token") },
  API_BASE: "http://localhost:5000",
}));
vi.mock("../api", () => api);

import ReviewQueueView from "./ReviewQueueView.jsx";

describe("ReviewQueueView initialIntakeId", () => {
  it("öffnet das Detail des per initialIntakeId übergebenen Dokuments", async () => {
    const onGeoffnet = vi.fn();
    render(<ReviewQueueView onOpenAkte={() => {}} initialIntakeId={461}
             onDokumentGeoffnet={onGeoffnet} />);
    await waitFor(() => expect(api.apiIntake.detail).toHaveBeenCalledWith(461));
    expect(onGeoffnet).toHaveBeenCalled();
  });
});
