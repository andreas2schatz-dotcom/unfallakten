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
});
