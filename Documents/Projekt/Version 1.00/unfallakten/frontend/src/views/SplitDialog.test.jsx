import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { apiIntake } from "../api.js";
import SplitDialog from "./SplitDialog.jsx";

vi.mock("../api.js", () => ({
  apiIntake: {
    seiten: vi.fn(),
    split: vi.fn(),
  },
}));

describe("SplitDialog — Backdrop-Guard waehrend busy (Abschluss-Review #1)", () => {
  it("Backdrop-Klick schliesst NICHT, solange der Split-Request laeuft", async () => {
    apiIntake.seiten.mockResolvedValue({ seiten: 3 });
    apiIntake.split.mockReturnValue(new Promise(() => {})); // haengt bewusst

    const onClose = vi.fn();
    const onDone = vi.fn();
    const thumbUrl = (n) => `about:blank#${n}`;

    const { container } = render(
      <SplitDialog docId={1} thumbUrl={thumbUrl} onClose={onClose} onDone={onDone} />,
    );

    await waitFor(() => expect(apiIntake.seiten).toHaveBeenCalledWith(1));
    await screen.findByText(/Dokument aufteilen/);

    // Mindestens einen Schnitt setzen, damit "aufteilen" aktivierbar ist.
    const schnittButtons = screen.getAllByTitle("Hier schneiden");
    fireEvent.click(schnittButtons[0]);

    const aufteilenButton = screen.getByText(/In \d+ Teile aufteilen/);
    fireEvent.click(aufteilenButton);

    await waitFor(() => expect(apiIntake.split).toHaveBeenCalled());

    // Backdrop ist das Wurzel-Overlay-Element (nicht die Box) -- direkter
    // Klick darauf (nicht ueber Bubbling von der Box) simuliert den
    // Backdrop-Dismiss waehrend busy. Darf onClose NICHT ausloesen.
    const overlay = container.firstChild;
    fireEvent.click(overlay);
    expect(onClose).not.toHaveBeenCalled();
  });
});
