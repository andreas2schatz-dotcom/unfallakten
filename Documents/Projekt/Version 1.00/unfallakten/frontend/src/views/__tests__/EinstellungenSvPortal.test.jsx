import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import EinstellungenView from "../EinstellungenView";
import { apiSvPortal } from "../../api";

vi.mock("../../api", async () => {
  const echt = await vi.importActual("../../api");
  return {
    ...echt,
    apiSvPortal: {
      liste: vi.fn(),
      akten: vi.fn(),
      suche: vi.fn().mockResolvedValue([]),
    },
  };
});

function renderSvPortal() {
  render(<EinstellungenView />);
  fireEvent.click(screen.getByText("🔗 SV-Portal"));
}

describe("SV-Portal-Reiter", () => {
  beforeEach(() => vi.clearAllMocks());

  it("meldet eine abgelaufene Sitzung statt einer leeren Liste", async () => {
    const fehler = new Error("Sitzung abgelaufen. Bitte erneut anmelden.");
    fehler.status = 401;
    apiSvPortal.liste.mockRejectedValue(fehler);

    renderSvPortal();

    await waitFor(() => {
      expect(screen.getByText(/Sitzung abgelaufen/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Noch keine SV-Zugänge/i)).not.toBeInTheDocument();
  });

  it("zeigt laufende und gesamte Aktenzahl", async () => {
    apiSvPortal.liste.mockResolvedValue([{
      adressnr: 25982, name: "Ninnivaggi", vorname: "KFZ-SV",
      email: "info@gn-gutachter.de", portal_aktiv: 1,
      einladung_gesendet_am: null, angelegt_am: "2026-08-20",
      akten_anzahl: 578, akten_laufend: 111,
    }]);

    renderSvPortal();

    await waitFor(() => {
      expect(screen.getByText(/111 laufend/)).toBeInTheDocument();
      expect(screen.getByText(/578 gesamt/)).toBeInTheDocument();
    });
  });
});
