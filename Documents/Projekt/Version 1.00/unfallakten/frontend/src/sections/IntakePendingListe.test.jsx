import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import IntakePendingListe, { intakeBadge } from "./IntakePendingListe.jsx";

describe("intakeBadge", () => {
  it("mappt queue_status auf Badge-Texte", () => {
    expect(intakeBadge("neu").text).toBe("Wird verarbeitet");
    expect(intakeBadge("laeuft").text).toBe("Wird verarbeitet");
    expect(intakeBadge("bereit_zur_review").text).toBe("Review ausstehend");
    expect(intakeBadge("pipeline_fehler").text).toBe("Fehler – prüfen");
  });
});

describe("IntakePendingListe", () => {
  const EINTRAEGE = [
    { intake_id: 1, bezeichnung: "Abrechnung", klasse: "abrechnungsschreiben",
      queue_status: "bereit_zur_review", erstellt_am: "2026-08-04 06:19:47" },
    { intake_id: 2, bezeichnung: "Foto", klasse: "sonstiges",
      queue_status: "pipeline_fehler", erstellt_am: "2026-08-04 07:00:00" },
  ];

  it("rendert die drei Badge-Texte je Status", () => {
    render(<IntakePendingListe eintraege={EINTRAEGE} onOpenReview={() => {}} />);
    expect(screen.getByText("Review ausstehend")).toBeInTheDocument();
    expect(screen.getByText("Fehler – prüfen")).toBeInTheDocument();
  });

  it("löst onOpenReview mit der intake_id aus", () => {
    const onOpen = vi.fn();
    render(<IntakePendingListe eintraege={EINTRAEGE} onOpenReview={onOpen} />);
    fireEvent.click(screen.getAllByText("Zur Review →")[0]);
    expect(onOpen).toHaveBeenCalledWith(1);
  });

  it("rendert nichts bei leerer Liste", () => {
    const { container } = render(
      <IntakePendingListe eintraege={[]} onOpenReview={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
});
