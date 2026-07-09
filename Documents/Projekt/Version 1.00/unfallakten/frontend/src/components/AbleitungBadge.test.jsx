import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import AbleitungBadge from './AbleitungBadge.jsx';

describe('AbleitungBadge', () => {
  it('rendert die Aussage mit Stand-Datum (deutsches Format)', () => {
    const { container } = render(
      <AbleitungBadge
        aussage="Klage-Checkliste 4/4 erfüllt"
        stand="2026-06-30"
      />
    );
    expect(screen.getByText(/Klage-Checkliste 4\/4 erfüllt/)).toBeInTheDocument();
    expect(container.textContent).toMatch(
      /nach Aktenlage, letztes Ereignis vom\s+30\.06\.2026/
    );
  });

  it('rendert ohne stand einen Fehler statt der Aussage', () => {
    render(
      <AbleitungBadge
        aussage="Klage-Checkliste 4/4 erfüllt"
        stand={null}
      />
    );
    expect(screen.queryByText(/Klage-Checkliste/)).not.toBeInTheDocument();
    const fehler = screen.getByRole('alert');
    expect(fehler).toHaveTextContent(/nicht anzeigbar/i);
    expect(fehler).toHaveTextContent(/stand/i);
  });

  it('rendert Fehler auch bei leerem stand-String', () => {
    render(<AbleitungBadge aussage="X" stand="" />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('rendert inline-Variante ohne Prominent-Icon', () => {
    const { container } = render(
      <AbleitungBadge aussage="bestritten" stand="2026-06-30" inline />
    );
    expect(container.querySelector('[data-variant="inline"]')).toBeInTheDocument();
    expect(container.querySelector('[data-variant="prominent"]')).not.toBeInTheDocument();
  });

  it('rendert Prominent-Variante als default', () => {
    const { container } = render(
      <AbleitungBadge aussage="X" stand="2026-06-30" />
    );
    expect(container.querySelector('[data-variant="prominent"]')).toBeInTheDocument();
  });

  it('behandelt ISO-Datum mit Zeitanteil korrekt', () => {
    render(<AbleitungBadge aussage="X" stand="2026-06-30T14:22:00" />);
    expect(screen.getByText(/30\.06\.2026/)).toBeInTheDocument();
  });
});
