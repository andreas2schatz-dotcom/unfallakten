import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api.js", () => ({
  akten: {},
  kuerzungsarten: {},
  abrechnungen: {
    typVorschlaege: vi.fn(),
    updatePos: vi.fn(),
  },
  pruefberichte: {},
  parsePdf: {},
  apiDistanz: {},
  apiStellungnahme: {},
  tokenStore: { get: () => null },
  request: vi.fn(),
}));

import { abrechnungen as apiAbrechnungen } from "../api.js";
import { PositionenTabelle } from "./RegulierungSection.jsx";

const KUERZUNGSARTEN = [
  { id: 2, bezeichnung: "Wertminderung" },
  { id: 4, bezeichnung: "Verbringungskosten" },
];

const POSITION = {
  id: 7, position_key: "wertminderung",
  betrag_gefordert: 100, betrag_reguliert: 40,
  kuerzungsart_id: null, kuerzung_freitext: "",
};

const VORSCHLAG = {
  typ_code: "A02", kuerzungsart_id: 4,
  snippet: "Die Verbringungskosten sind nicht erforderlich.",
  quelle: "regel", konfidenz: 0.9,
};

function renderTabelle() {
  return render(
    <PositionenTabelle
      positionen={[POSITION]}
      kuerzungsarten={KUERZUNGSARTEN}
      akteId="971/25"
      abid={3}
      onUpdate={() => {}}
      readOnly={false}
    />
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  apiAbrechnungen.typVorschlaege.mockResolvedValue({
    vorschlaege: [VORSCHLAG], quelle_dokument_id: 12,
  });
  apiAbrechnungen.updatePos.mockResolvedValue({ position: {} });
});

describe("PositionenTabelle Typ-Vorschlag", () => {
  it("zeigt Vorschlags-Chip bei Kuerzung ohne Kuerzungsart", async () => {
    renderTabelle();
    const chip = await screen.findByText(/Verbringungskosten \(A02\)/);
    expect(chip).toBeTruthy();
    expect(apiAbrechnungen.typVorschlaege).toHaveBeenCalledWith("971/25", 3);
  });

  it("Chip-Klick + Uebernehmen sendet EINEN updatePos mit Typ, Begruendung, Quelle", async () => {
    renderTabelle();
    fireEvent.click(await screen.findByText(/Verbringungskosten \(A02\)/));
    const ta = screen.getByLabelText("Begründung");
    expect(ta.value).toContain("Verbringungskosten");
    fireEvent.click(screen.getByText("Übernehmen"));
    await waitFor(() => expect(apiAbrechnungen.updatePos).toHaveBeenCalledTimes(1));
    const [, , posId, payload] = apiAbrechnungen.updatePos.mock.calls[0];
    expect(posId).toBe(7);
    expect(payload.kuerzungsart_id).toBe(4);
    expect(payload.kuerzung_freitext).toContain("Verbringungskosten");
    expect(payload.typ_quelle).toBe("regel");
  });

  it("manuelle Auswahl ohne Begruendung sendet keinen Request", async () => {
    renderTabelle();
    await screen.findByText(/Verbringungskosten \(A02\)/);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "2" } });
    expect(apiAbrechnungen.updatePos).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Begründung")).toBeTruthy();
    expect(screen.getByText("Übernehmen").closest("button").disabled).toBe(true);
  });

  it("manuelle Auswahl mit eingetippter Begruendung sendet typ_quelle manuell", async () => {
    renderTabelle();
    await screen.findByText(/Verbringungskosten \(A02\)/);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Begründung"),
      { target: { value: "Wertminderung nicht nachvollziehbar." } });
    fireEvent.click(screen.getByText("Übernehmen"));
    await waitFor(() => expect(apiAbrechnungen.updatePos).toHaveBeenCalledTimes(1));
    const payload = apiAbrechnungen.updatePos.mock.calls[0][3];
    expect(payload.kuerzungsart_id).toBe(2);
    expect(payload.typ_quelle).toBe("manuell");
  });
});
