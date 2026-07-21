import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { KlageGesamtvorschau } from './KlageGesamtvorschau';

vi.mock('../api.js', () => ({
  apiKlage: {
    vorschau: vi.fn(() => Promise.resolve({ abschnitte: [
      { key: 'gericht', titel: 'Gericht', text: 'Amtsgericht Offenbach',
        editierbar: false, override_feld: null },
      { key: 'sachverhalt', titel: 'Sachverhalt', text: 'Der Beklagte fuhr auf.',
        editierbar: true, override_feld: 'sachverhalt_override' },
    ] })),
  },
}));

import { apiKlage } from '../api.js';

describe('KlageGesamtvorschau', () => {
  beforeEach(() => vi.clearAllMocks());

  it('laedt erst nach Klick (kein Auto-Load)', () => {
    render(<KlageGesamtvorschau akteId="55/26" cfg={{}} overrides={{}} onEditAbschnitt={() => {}} />);
    expect(apiKlage.vorschau).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /Vorschau erzeugen/i })).toBeInTheDocument();
  });

  it('rendert Abschnitte nach Klick', async () => {
    render(<KlageGesamtvorschau akteId="55/26" cfg={{ a: 1 }} overrides={{ b: 2 }} onEditAbschnitt={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Vorschau erzeugen/i }));
    await waitFor(() => expect(screen.getByText('Der Beklagte fuhr auf.')).toBeInTheDocument());
    expect(apiKlage.vorschau).toHaveBeenCalledWith('55/26', { a: 1 }, { b: 2 });
    expect(screen.getByText('Amtsgericht Offenbach')).toBeInTheDocument();
  });

  it('zeigt "Bearbeiten" nur bei editierbaren Abschnitten', async () => {
    render(<KlageGesamtvorschau akteId="55/26" cfg={{}} overrides={{}} onEditAbschnitt={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Vorschau erzeugen/i }));
    await waitFor(() => screen.getByText('Der Beklagte fuhr auf.'));
    // genau ein Bearbeiten-Button (fuer den editierbaren Sachverhalt)
    expect(screen.getAllByRole('button', { name: /Bearbeiten/i })).toHaveLength(1);
  });
});
