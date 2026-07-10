import { describe, test, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EmailKontextBox, TextVorschau } from '../ReviewQueueView.jsx';

describe('EmailKontextBox', () => {
  test('zeigt Absender, Betreff und AZ', () => {
    render(<EmailKontextBox eltern={{
      absender: 'sv@x.de', betreff: 'Ihr Brief', empfangen_am: '2026-07-10',
      text: 'Body mit 285/26', akte_az: '285/26',
    }} />);
    expect(screen.getByText(/sv@x\.de/)).toBeInTheDocument();
    expect(screen.getByText('285/26')).toBeInTheDocument();
    expect(screen.getByText(/Kam mit E-Mail/i)).toBeInTheDocument();
  });

  test('rendert nichts ohne eltern', () => {
    const { container } = render(<EmailKontextBox eltern={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('TextVorschau', () => {
  test('rendert den E-Mail-Text', () => {
    render(<TextVorschau text={'Zeile A\nZeile B'} />);
    expect(screen.getByText(/Zeile A/)).toBeInTheDocument();
  });
});
