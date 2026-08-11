import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api.js", () => ({
  apiSta: {
    kontext: vi.fn(),
    generieren: vi.fn(() => Promise.resolve({ ok: true })),
  },
}));

import { apiSta } from "../api.js";
import StaDialog from "./StaDialog.jsx";

const KONTEXT = {
  az: "44/22",
  stufe: 2,
  brieftext: "Testbrief",
  letztes_schreiben: null,
  tage_ohne_antwort: 0,
  sta_anzahl: 0,
  versicherer_name: null,
  frist_tage: 10,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("G-2 – Fristanzeige aus konfigurierten frist_tage", () => {
  it("zeigt die konfigurierte Frist des Backends statt des Hardcodes", async () => {
    apiSta.kontext.mockResolvedValue(KONTEXT);
    render(<StaDialog az="44/22" onClose={vi.fn()} />);

    await waitFor(() =>
      expect(screen.getByText("Stufe 2 – Mahnung")).toBeInTheDocument()
    );
    expect(screen.getByText("10 Tage")).toBeInTheDocument();
    expect(screen.queryByText("7 Tage")).toBeNull();
  });

  it("aktualisiert die Frist beim Stufenwechsel", async () => {
    apiSta.kontext
      .mockResolvedValueOnce(KONTEXT)
      .mockResolvedValueOnce({ ...KONTEXT, stufe: 3, frist_tage: 4 });
    render(<StaDialog az="44/22" onClose={vi.fn()} />);

    await waitFor(() =>
      expect(screen.getByText("Stufe 2 – Mahnung")).toBeInTheDocument()
    );
    fireEvent.click(screen.getByText("+"));

    await waitFor(() =>
      expect(screen.getByText("Stufe 3 – Klage-Ankündigung")).toBeInTheDocument()
    );
    expect(apiSta.kontext).toHaveBeenLastCalledWith("44/22", 3);
    expect(screen.getByText("4 Tage")).toBeInTheDocument();
  });
});
