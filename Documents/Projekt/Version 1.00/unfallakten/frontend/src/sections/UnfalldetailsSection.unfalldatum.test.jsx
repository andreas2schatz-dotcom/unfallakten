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

describe("UnfalldetailsSection – Unfalldatum-Feld", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiKlage.unfalldetails.mockResolvedValue({
      unfalldetails: {
        unfalldatum: "15.01.2024", schilderung: "",
        haftungsquote: 100, vorsteuerabzug: false,
      },
    });
    apiKlage.unfalldetailsSpeichern.mockResolvedValue({ unfalldetails: {} });
  });

  it("zeigt das aus WDM vorbefuellte Unfalldatum an", async () => {
    render(<UnfalldetailsSection akteId="55/24" />);
    expect(await screen.findByDisplayValue("15.01.2024")).toBeInTheDocument();
  });

  it("sendet das geaenderte Unfalldatum beim Speichern mit", async () => {
    render(<UnfalldetailsSection akteId="55/24" />);
    const input = await screen.findByDisplayValue("15.01.2024");
    fireEvent.change(input, { target: { value: "16.01.2024" } });
    fireEvent.click(screen.getByRole("button", { name: /Unfalldetails speichern/i }));
    await waitFor(() => expect(apiKlage.unfalldetailsSpeichern).toHaveBeenCalled());
    const [, form] = apiKlage.unfalldetailsSpeichern.mock.calls[0];
    expect(form.unfalldatum).toBe("16.01.2024");
  });

  it("normalisiert lockere Eingabe beim Verlassen des Feldes", async () => {
    render(<UnfalldetailsSection akteId="55/24" />);
    const input = await screen.findByDisplayValue("15.01.2024");
    fireEvent.change(input, { target: { value: "5.3.24" } });
    fireEvent.blur(input);
    expect(await screen.findByDisplayValue("05.03.2024")).toBeInTheDocument();
  });

  it("warnt bei einem ungueltigen Kalenderdatum, blockiert aber nicht", async () => {
    render(<UnfalldetailsSection akteId="55/24" />);
    const input = await screen.findByDisplayValue("15.01.2024");
    fireEvent.change(input, { target: { value: "31.02.2024" } });
    fireEvent.blur(input);
    expect(await screen.findByText(/kein g.ltiges datum/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Unfalldetails speichern/i }));
    await waitFor(() => expect(apiKlage.unfalldetailsSpeichern).toHaveBeenCalled());
  });

  it("warnt bei einem Datum in der Zukunft", async () => {
    render(<UnfalldetailsSection akteId="55/24" />);
    const input = await screen.findByDisplayValue("15.01.2024");
    fireEvent.change(input, { target: { value: "01.01.2099" } });
    fireEvent.blur(input);
    expect(await screen.findByText(/zukunft/i)).toBeInTheDocument();
  });

  it("uebernimmt eine Kalenderauswahl als TT.MM.JJJJ", async () => {
    const { container } = render(<UnfalldetailsSection akteId="55/24" />);
    await screen.findByDisplayValue("15.01.2024");
    const picker = container.querySelector('input[type="date"]');
    expect(picker).toBeTruthy();
    fireEvent.change(picker, { target: { value: "2024-05-06" } });
    expect(await screen.findByDisplayValue("06.05.2024")).toBeInTheDocument();
  });

  it("bietet einen Kalender-Button", async () => {
    render(<UnfalldetailsSection akteId="55/24" />);
    await screen.findByDisplayValue("15.01.2024");
    expect(screen.getByRole("button", { name: /Kalender/i })).toBeInTheDocument();
  });
});
