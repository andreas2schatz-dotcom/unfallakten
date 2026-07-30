import React, { useEffect, useRef, useState } from 'react';
import ReactDOM from 'react-dom';
import T from '../config/theme.js';
import { API_BASE, tokenStore } from '../api.js';

const MENU_BREITE = 340;

/**
 * P1.7 — Dokument-Scope-Aktionsmenü.
 *
 * Kebab-Button in der Dokumentzeile; öffnet Popover mit den vom
 * Backend vorgeschlagenen Aktionen (GET /akten/<az>/aktionen?dokument_id=…).
 * Parallel zum bestehenden handleInlineAnnehmen (Plan §6.3 — Alt-Weg
 * bleibt zunächst erhalten).
 *
 * Popover wird per Portal in document.body gerendert (position:fixed,
 * Koordinaten aus getBoundingClientRect des Kebab-Buttons) — sonst wird
 * es von umliegenden Karten mit overflow:hidden am Rand abgeschnitten.
 */
export default function DokumentAktionsmenue({ az, dokumentId, onAktion = () => {} }) {
  const [offen, setOffen] = useState(false);
  const [daten, setDaten] = useState(null);
  const [fehler, setFehler] = useState(null);
  const [pos, setPos] = useState(null);
  const btnRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!offen || daten || !az || dokumentId == null) return;
    let abgebrochen = false;
    const token = tokenStore.getAccess();
    fetch(
      `${API_BASE}/akten/${encodeURIComponent(az)}/aktionen?dokument_id=${encodeURIComponent(dokumentId)}`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} }
    )
      .then(res => res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`)))
      .then(d => { if (!abgebrochen) setDaten(d); })
      .catch(e => { if (!abgebrochen) setFehler(e.message || String(e)); });
    return () => { abgebrochen = true; };
  }, [offen, az, dokumentId, daten]);

  useEffect(() => {
    if (!offen) return;
    const klick = (ev) => {
      if (btnRef.current?.contains(ev.target) || menuRef.current?.contains(ev.target)) return;
      setOffen(false);
    };
    const schliessen = () => setOffen(false);
    document.addEventListener('mousedown', klick);
    window.addEventListener('scroll', schliessen, true);
    window.addEventListener('resize', schliessen);
    return () => {
      document.removeEventListener('mousedown', klick);
      window.removeEventListener('scroll', schliessen, true);
      window.removeEventListener('resize', schliessen);
    };
  }, [offen]);

  const toggleOffen = () => {
    if (!offen && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect();
      setPos({ top: r.bottom + 4, right: window.innerWidth - r.right });
    }
    setOffen(o => !o);
  };

  return (
    <span style={{ display: 'inline-block' }}>
      <button
        ref={btnRef}
        aria-label="Aktionen"
        title="Vorgeschlagene Aktionen"
        onClick={(e) => { e.stopPropagation(); toggleOffen(); }}
        style={{
          background: offen ? T.accentPale : 'transparent',
          border: `1px solid ${offen ? T.accent : 'transparent'}`,
          borderRadius: 6, cursor: 'pointer',
          color: offen ? T.accent : T.textMuted,
          padding: '4px 8px', fontSize: '1.05rem', lineHeight: 1,
        }}
      >⋮</button>

      {offen && pos && ReactDOM.createPortal(
        <div ref={menuRef} style={{
          position: 'fixed', top: pos.top, right: pos.right, width: MENU_BREITE,
          background: T.cardBg, border: `1px solid ${T.border}`,
          borderRadius: 10,
          boxShadow: '0 8px 24px rgba(27,42,74,0.14), 0 2px 6px rgba(27,42,74,0.06)',
          padding: 8, zIndex: 1000,
          fontFamily: T.fontBody,
        }}>
          <div style={{
            padding: '6px 10px 4px', fontSize: '0.66rem',
            textTransform: 'uppercase', letterSpacing: '0.1em',
            color: T.textFaint, fontWeight: 700,
          }}>
            Vorgeschlagene Aktionen
          </div>

          {fehler && (
            <div style={{ padding: '8px 10px', color: T.redText, fontSize: '0.8rem' }}>
              Aktionen nicht geladen: {fehler}
            </div>
          )}
          {!daten && !fehler && (
            <div style={{ padding: '8px 10px', color: T.textMuted, fontSize: '0.8rem' }}>
              Lade Vorschläge…
            </div>
          )}
          {daten && daten.aktionen.length === 0 && (
            <div style={{ padding: '10px', color: T.textMuted, fontSize: '0.8rem' }}>
              Keine Vorschläge — Aktenlage bietet aktuell keine Anschlussaktionen.
            </div>
          )}
          {daten && daten.aktionen.map((a, idx) => (
            <button
              key={a.aktion}
              onClick={() => { setOffen(false); onAktion(a); }}
              style={{
                display: 'grid',
                gridTemplateColumns: '22px 1fr auto',
                gap: 10, alignItems: 'center',
                padding: '10px', borderRadius: 8,
                border: 0, width: '100%', textAlign: 'left',
                background: idx === 0 ? T.navy : 'transparent',
                color: idx === 0 ? T.white : T.text,
                cursor: 'pointer',
                fontFamily: T.fontBody,
                marginTop: idx === 0 ? 2 : 0,
              }}
              onMouseEnter={e => { if (idx !== 0) e.currentTarget.style.background = T.accentPale; }}
              onMouseLeave={e => { if (idx !== 0) e.currentTarget.style.background = 'transparent'; }}
            >
              <span style={{ color: idx === 0 ? T.accentLight : T.accent, fontSize: '1rem', textAlign: 'center' }}>
                {idx === 0 ? '✎' : '▸'}
              </span>
              <span>
                <span style={{
                  display: 'block', fontSize: '0.85rem', fontWeight: 600,
                  color: idx === 0 ? T.white : T.navy,
                }}>{a.label}</span>
                {a.vorbedingung && (
                  <span style={{
                    display: 'block', fontSize: '0.7rem', marginTop: 2,
                    color: idx === 0 ? 'rgba(255,255,255,0.75)' : T.textMuted,
                  }}>{a.vorbedingung}</span>
                )}
              </span>
              <span style={{
                fontFamily: T.fontMono, fontSize: '0.68rem',
                color: idx === 0 ? T.accentLight : T.textFaint,
                fontWeight: 500,
              }}>{a.positions_scope ? 'position' : 'dokument'}</span>
            </button>
          ))}
        </div>,
        document.body
      )}
    </span>
  );
}
