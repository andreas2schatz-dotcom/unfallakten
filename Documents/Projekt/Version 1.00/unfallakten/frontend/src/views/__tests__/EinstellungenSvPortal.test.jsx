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
      togglePortalGesperrt: vi.fn(),
      zugriffeAbgleichen: vi.fn(),
    },
  };
});

function renderSvPortal() {
  render(<EinstellungenView />);
  fireEvent.click(screen.getByText("🔗 SV-Portal"));
}

const svEintrag = (overrides = {}) => ({
  adressnr: 111, name: "Muster", vorname: "SV",
  email: "sv@x.de", portal_aktiv: 1,
  einladung_gesendet_am: null, angelegt_am: "2026-08-20",
  akten_anzahl: 1, akten_laufend: 1,
  ...overrides,
});

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
    expect(screen.queryByText(/Noch keine SV-Accounts/i)).not.toBeInTheDocument();
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

  it("zeigt RA-MICRO-Störung in der Liste statt einer erfundenen Aktenzahl", async () => {
    apiSvPortal.liste.mockResolvedValue([svEintrag({
      akten_anzahl: null, akten_laufend: null, ra_micro_erreichbar: false,
    })]);

    renderSvPortal();

    expect(await screen.findByText("RA-MICRO nicht erreichbar")).toBeInTheDocument();
    expect(screen.queryByText(/laufend ·/)).not.toBeInTheDocument();
  });

  it("meldet eine gestörte RA-MICRO-Verbindung beim Laden der Akten statt einer leeren Liste", async () => {
    apiSvPortal.liste.mockResolvedValue([svEintrag()]);
    const fehler = new Error("RA-MICRO nicht erreichbar - Aktenliste kann nicht geladen werden.");
    fehler.status = 503;
    apiSvPortal.akten.mockRejectedValue(fehler);

    renderSvPortal();
    fireEvent.click(await screen.findByText("SV Muster"));

    expect(await screen.findByText(/RA-MICRO nicht erreichbar/)).toBeInTheDocument();
    expect(screen.queryByText(/Keine Akten in RA-MICRO gefunden/)).not.toBeInTheDocument();
  });

  it("sperrt eine freigegebene Akte über den Schalter", async () => {
    apiSvPortal.liste.mockResolvedValue([svEintrag()]);
    apiSvPortal.akten.mockResolvedValue([{
      az: "100/26", kurzbezeichnung: "Test-Akte", unfalldatum: "2026-01-01",
      portal_aktiv: 1, portal_gesperrt: 0, ramicro_abgelegt: 0, im_system: true,
    }]);
    apiSvPortal.togglePortalGesperrt.mockResolvedValue({ az: "100/26", portal_gesperrt: 1 });

    renderSvPortal();
    fireEvent.click(await screen.findByText("SV Muster"));
    await screen.findByText("100/26");

    const label = await screen.findByText("freigegeben");
    fireEvent.click(label.previousElementSibling);

    await waitFor(() => {
      expect(apiSvPortal.togglePortalGesperrt).toHaveBeenCalledWith("100/26", true);
    });
    expect(await screen.findByText("gesperrt")).toBeInTheDocument();
  });

  it("gibt eine gesperrte Akte über den Schalter wieder frei", async () => {
    apiSvPortal.liste.mockResolvedValue([svEintrag()]);
    apiSvPortal.akten.mockResolvedValue([{
      az: "100/26", kurzbezeichnung: "Test-Akte", unfalldatum: "2026-01-01",
      portal_aktiv: 0, portal_gesperrt: 1, ramicro_abgelegt: 0, im_system: true,
    }]);
    apiSvPortal.togglePortalGesperrt.mockResolvedValue({ az: "100/26", portal_gesperrt: 0 });

    renderSvPortal();
    fireEvent.click(await screen.findByText("SV Muster"));
    await screen.findByText("100/26");

    const label = await screen.findByText("gesperrt");
    fireEvent.click(label.previousElementSibling);

    await waitFor(() => {
      expect(apiSvPortal.togglePortalGesperrt).toHaveBeenCalledWith("100/26", false);
    });
    expect(await screen.findByText("freigegeben")).toBeInTheDocument();
  });

  it("meldet das Ergebnis des Zugriffs-Abgleichs", async () => {
    apiSvPortal.liste.mockResolvedValue([svEintrag()]);
    apiSvPortal.akten.mockResolvedValue([]);
    apiSvPortal.zugriffeAbgleichen.mockResolvedValue({
      gesamt: 578, gesperrt: 0, uebertragen: 578, gesendet: true, antwort: {}, unbekannt: [],
    });

    renderSvPortal();
    fireEvent.click(await screen.findByText("SV Muster"));
    fireEvent.click(await screen.findByText("⇄ Zugriffe abgleichen"));

    await waitFor(() => {
      expect(apiSvPortal.zugriffeAbgleichen).toHaveBeenCalledWith(111);
    });
    expect(await screen.findByText(/578 Akten, 0 gesperrt, 578 übertragen/)).toBeInTheDocument();
    expect(screen.queryByText(/unbekannt geblieben/)).not.toBeInTheDocument();
  });

  it("meldet unbekannt gebliebene Akten statt eines glatten Erfolgs", async () => {
    apiSvPortal.liste.mockResolvedValue([svEintrag()]);
    apiSvPortal.akten.mockResolvedValue([]);
    apiSvPortal.zugriffeAbgleichen.mockResolvedValue({
      gesamt: 2, gesperrt: 0, uebertragen: 2, gesendet: true, antwort: {},
      unbekannt: ["100/26"],
    });

    renderSvPortal();
    fireEvent.click(await screen.findByText("SV Muster"));
    fireEvent.click(await screen.findByText("⇄ Zugriffe abgleichen"));

    expect(await screen.findByText(/1 Akte\(n\) im Portal unbekannt geblieben/)).toBeInTheDocument();
  });
});
