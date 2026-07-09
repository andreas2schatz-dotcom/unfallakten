import React from 'react';
import T from '../config/theme.js';

function formatStand(stand) {
  if (!stand || typeof stand !== 'string') return null;
  const iso = stand.slice(0, 10);
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return null;
  return `${m[3]}.${m[2]}.${m[1]}`;
}

/**
 * Wissensgrenze für abgeleitete Aussagen.
 *
 * Rendert `aussage` immer zusammen mit "nach Aktenlage, letztes Ereignis vom {stand}".
 * Ohne verwertbaren stand → Fehleranzeige statt Aussage
 * (POSITIONSMODELL-PLAN §6.2, freigabe.md K-Punkt 3d).
 */
export default function AbleitungBadge({ aussage, stand, inline = false }) {
  const standDe = formatStand(stand);

  if (!standDe) {
    return (
      <div
        role="alert"
        data-variant="error"
        style={{
          display: 'inline-flex',
          alignItems: 'flex-start',
          gap: 6,
          padding: '6px 10px',
          background: T.redBg,
          border: `1px solid ${T.red}`,
          borderRadius: 4,
          fontSize: '0.75rem',
          color: T.redText,
          fontWeight: 600,
        }}
      >
        <span aria-hidden="true" style={{ fontSize: '1rem', lineHeight: 1 }}>⚠</span>
        <span>
          Ableitung <b>nicht anzeigbar</b> — Endpoint hat kein <code>stand</code> geliefert.
        </span>
      </div>
    );
  }

  if (inline) {
    return (
      <span
        data-variant="inline"
        style={{
          padding: '3px 8px',
          fontSize: '0.7rem',
          color: T.textFaint,
          fontStyle: 'italic',
        }}
      >
        <span style={{ color: T.text, fontWeight: 500, fontStyle: 'normal' }}>{aussage}</span>
        {' — nach Aktenlage vom '}
        {standDe}
      </span>
    );
  }

  return (
    <div
      data-variant="prominent"
      style={{
        display: 'inline-flex',
        alignItems: 'flex-start',
        gap: 6,
        padding: '6px 10px',
        background: T.surface,
        borderLeft: `3px solid ${T.accent}`,
        borderRadius: 4,
        fontSize: '0.75rem',
        color: T.textMid,
        lineHeight: 1.35,
      }}
    >
      <span aria-hidden="true" style={{ fontSize: '1rem', lineHeight: 1 }}>📍</span>
      <span>
        <span style={{ color: T.text, fontWeight: 500 }}>{aussage}</span>
        {' — nach Aktenlage, letztes Ereignis vom '}
        <b>{standDe}</b>.
      </span>
    </div>
  );
}
