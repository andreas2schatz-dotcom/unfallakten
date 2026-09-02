import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../api.js", () => ({
  apiKlage: {
    unfalldetails: vi.fn(),
    unfalldetailsSpeichern: vi.fn(),
    wdmLaden: vi.fn(),
  },
}));

import { apiKlage } from "../api.js";
import UnfalldetailsSection from "./UnfalldetailsSection.jsx";

describe("UnfalldetailsSection – Unfallort-Feld", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiKlage.unfalldetails.mockResolvedValue({
      unfalldetails: {
        unfalldatum: "15.01.2024", unfallort: "Heusenstamm",
        schilderung: "", haftungsquote: 100, vorsteuerabzug: false,
      },
    });
    apiKlage.unfalldetailsSpeichern.mockResolvedValue({ unfalldetails: {} });
  });

  it("zeigt den aus WDM vorbefuellten Unfallort an", async () => {
    render(<UnfalldetailsSection akteId="55/24" />);
    expect(await screen.findByDisplayValue("Heusenstamm")).toBeInTheDocument();
  });

  it("sendet den geaenderten Unfallort beim Speichern mit", async () => {
    render(<UnfalldetailsSection akteId="55/24" />);
    const input = await screen.findByDisplayValue("Heusenstamm");
    fireEvent.change(input, { target: { value: "Offenbach, Kaiserstr. 12" } });
    fireEvent.click(screen.getByRole("button", { name: /Unfalldetails speichern/i }));
    await waitFor(() => expect(apiKlage.unfalldetailsSpeichern).toHaveBeenCalled());
    const [, form] = apiKlage.unfalldetailsSpeichern.mock.calls[0];
    expect(form.unfallort).toBe("Offenbach, Kaiserstr. 12");
  });

  it("sendet auch einen geleerten Unfallort mit, damit er geloescht werden kann", async () => {
    render(<UnfalldetailsSection akteId="55/24" />);
    const input = await screen.findByDisplayValue("Heusenstamm");
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /Unfalldetails speichern/i }));
    await waitFor(() => expect(apiKlage.unfalldetailsSpeichern).toHaveBeenCalled());
    const [, form] = apiKlage.unfalldetailsSpeichern.mock.calls[0];
    expect(form).toHaveProperty("unfallort", "");
  });

  it("uebernimmt den Unfallort aus dem WDM-Import", async () => {
    apiKlage.unfalldetails.mockResolvedValue({
      unfalldetails: { unfalldatum: "", unfallort: "", schilderung: "",
        haftungsquote: 100, vorsteuerabzug: false },
    });
    apiKlage.wdmLaden.mockResolvedValue({
      unfalldetails: { unfalldatum: "20.07.2026", unfallort: "Heusenstamm",
        schilderung: "", haftungsquote: 100, vorsteuerabzug: false },
    });
    render(<UnfalldetailsSection akteId="55/24" />);
    await screen.findByRole("button", { name: /Unfalldetails speichern/i });
    fireEvent.click(screen.getByRole("button", { name: /WDM/i }));
    expect(await screen.findByDisplayValue("Heusenstamm")).toBeInTheDocument();
  });

  it("beschriftet das Feld als Unfallort", async () => {
    render(<UnfalldetailsSection akteId="55/24" />);
    await screen.findByDisplayValue("Heusenstamm");
    expect(screen.getByText("Unfallort")).toBeInTheDocument();
  });
});
