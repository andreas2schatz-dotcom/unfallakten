import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Kachel, KachelInhalt, Zeile, ZeileText, StufenBadge, MehrKnopf, tageBadgeText } from "./boardUi";

describe("boardUi", () => {
  it("KachelInhalt zeigt bei laedt weder Leertext noch Kinder", () => {
    render(
      <KachelInhalt status="laedt" leerText="Nichts da" leer={true}>
        <div>Inhalt</div>
      </KachelInhalt>
    );
    expect(screen.queryByText("Nichts da")).toBeNull();
    expect(screen.queryByText("Inhalt")).toBeNull();
  });

  it("KachelInhalt zeigt bei fehler den Fehlertext und ruft onRetry", () => {
    const retry = vi.fn();
    render(
      <KachelInhalt status="fehler" fehlerText="Fristen konnten nicht geladen werden" onRetry={retry}>
        <div>Inhalt</div>
      </KachelInhalt>
    );
    expect(screen.getByText("Fristen konnten nicht geladen werden")).toBeInTheDocument();
    expect(screen.queryByText("Inhalt")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Erneut laden" }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("KachelInhalt zeigt bei ok+leer den Leertext, sonst die Kinder", () => {
    const { rerender } = render(
      <KachelInhalt status="ok" leer={true} leerText="Keine Fristen">
        <div>Inhalt</div>
      </KachelInhalt>
    );
    expect(screen.getByText("Keine Fristen")).toBeInTheDocument();
    rerender(
      <KachelInhalt status="ok" leer={false} leerText="Keine Fristen">
        <div>Inhalt</div>
      </KachelInhalt>
    );
    expect(screen.getByText("Inhalt")).toBeInTheDocument();
    expect(screen.queryByText("Keine Fristen")).toBeNull();
  });

  it("Zeile ist ein Button und feuert onClick", () => {
    const klick = vi.fn();
    render(
      <Zeile stufe="rot" onClick={klick} links={<ZeileText titel="312/26 AS · Müller" meta="Stellungnahme" />} rechts={<StufenBadge stufe="rot">−3 T</StufenBadge>} />
    );
    const btn = screen.getByRole("button");
    fireEvent.click(btn);
    expect(klick).toHaveBeenCalledTimes(1);
    expect(btn.style.borderLeftWidth).not.toBe("3px");
  });

  it("Kachel rendert Titel und Zusammenfassung", () => {
    render(<Kachel icon={<svg />} titel="Fristen" zusammenfassung="2 überfällig"><div /></Kachel>);
    expect(screen.getByText("Fristen")).toBeInTheDocument();
    expect(screen.getByText("2 überfällig")).toBeInTheDocument();
  });
});

describe("boardUi – A11y und Button-Semantik", () => {
  it("meldet den Fehlerblock als role=alert", () => {
    render(<KachelInhalt status="fehler" fehlerText="Fristen konnten nicht geladen werden" onRetry={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Fristen konnten nicht geladen werden");
  });

  it("blendet die Lade-Platzhalter vor Screenreadern aus", () => {
    const { container } = render(<KachelInhalt status="laedt" leerText="Nichts da" />);
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });

  it("deaktiviert den Retry-Knopf, solange nachgeladen wird", () => {
    const retry = vi.fn();
    const { rerender } = render(<KachelInhalt status="fehler" fehlerText="Fehler" onRetry={retry} />);
    expect(screen.getByRole("button", { name: "Erneut laden" })).not.toBeDisabled();
    rerender(<KachelInhalt status="fehler" fehlerText="Fehler" onRetry={retry} retryLaeuft={true} />);
    const btn = screen.getByRole("button", { name: /Erneut laden|Lädt/ });
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(retry).not.toHaveBeenCalled();
  });

  it("gibt allen Knöpfen type=button (kein versehentliches Formular-Absenden)", () => {
    const { container: c1 } = render(<KachelInhalt status="fehler" fehlerText="Fehler" onRetry={() => {}} />);
    expect(c1.querySelector("button").getAttribute("type")).toBe("button");
    const { container: c2 } = render(<Zeile onClick={() => {}} links={<ZeileText titel="312/26 AS" />} />);
    expect(c2.querySelector("button").getAttribute("type")).toBe("button");
    const { container: c3 } = render(<MehrKnopf onClick={() => {}}>Alle öffnen</MehrKnopf>);
    expect(c3.querySelector("button").getAttribute("type")).toBe("button");
  });

  it("tageBadgeText ist die gemeinsame Quelle für Tages-Badges", () => {
    expect(tageBadgeText(0)).toBe("heute");
    expect(tageBadgeText(-3)).toBe("−3 T");
    expect(tageBadgeText(2)).toBe("+2 T");
  });
});
