import React, { useEffect, useState, useMemo } from 'react';
import T from '../config/theme.js';
import AbleitungBadge from './AbleitungBadge.jsx';
import { API_BASE, tokenStore } from '../api.js';

const ZUSTAND_CHIP = {
  offen:         { bg: T.surface,   fg: T.textMid,   bd: T.border },
  gefordert:     { bg: T.blueBg,    fg: T.blueText,  bd: T.blue },
  anerkannt:     { bg: T.greenBg,   fg: T.greenText, bd: T.greenLight },
  teilanerkannt: { bg: T.amberBg,   fg: T.amberText, bd: T.amber },
  bestritten:    { bg: T.amberMid,  fg: T.amberText, bd: T.amber },
  erledigt:      { bg: T.greenBg,   fg: T.greenText, bd: T.green },
};

const KAT_LABEL = {
  fahrzeugschaden:  'Fahrzeugschaden',
  nebenkosten:      'Nebenkosten',
  personenschaden:  'Personenschaden',
  sonstiges:        'Sonstiges',
};

function fmtEuro(v) {
  const n = Number(v || 0);
  return n.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
}

function fmtDatum(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : null;
}

function eskalationLabel(stufe) {
  if (stufe >= 3) return 'STA Stufe 3';
  if (stufe === 2) return 'STA Stufe 2';
  return 'STA Stufe 1';
}

function ZustandChip({ zustand }) {
  const cfg = ZUSTAND_CHIP[zustand] || ZUSTAND_CHIP.offen;
  return (
    <span style={{
      display: 'inline-block',
      padding: '3px 9px',
      borderRadius: 999,
      fontSize: '0.7rem',
      fontWeight: 600,
      background: cfg.bg,
      color: cfg.fg,
      border: `1px solid ${cfg.bd}`,
      whiteSpace: 'nowrap',
    }}>{zustand}</span>
  );
}

function PositionsZeile({ posKey, pos, onClick }) {
  const chk = pos.checkliste || { erledigt: [], offen: [] };
  const gesamtCheck = chk.erledigt.length + chk.offen.length;
  const cardStyle = {
    display: 'grid',
    gridTemplateColumns: '1.5fr 110px 110px 110px 160px 130px',
    alignItems: 'center',
    gap: 10,
    padding: '10px 12px',
    background: pos.has_unbestaetigt
      ? `repeating-linear-gradient(-45deg, ${T.cardBg} 0, ${T.cardBg} 12px, ${T.accentPale} 12px, ${T.accentPale} 13px)`
      : T.cardBg,
    border: `1px solid ${T.border}`,
    borderLeft: `4px ${pos.has_unbestaetigt ? 'dashed' : 'solid'} ${
      pos.has_unbestaetigt ? T.accent
        : pos.zustand === 'anerkannt' || pos.zustand === 'erledigt' ? T.green
        : pos.zustand === 'bestritten' ? T.amber
        : pos.zustand === 'teilanerkannt' ? T.amber
        : T.navyMid
    }`,
    borderRadius: 10,
    cursor: 'pointer',
    marginBottom: 6,
  };
  return (
    <div
      data-testid={`positionszeile-${posKey}`}
      onClick={() => onClick(posKey)}
      style={cardStyle}
    >
      <div>
        <div style={{ fontWeight: 600, color: T.text, fontSize: '0.92rem' }}>
          {pos.label || posKey}
          {pos.has_unbestaetigt && (
            <span style={{
              marginLeft: 8,
              padding: '2px 8px',
              borderRadius: 999,
              fontSize: '0.65rem',
              border: `1px dashed ${T.accent}`,
              color: T.accentDark,
              fontWeight: 700,
              letterSpacing: '0.04em',
            }}>WDM · unbestätigt</span>
          )}
        </div>
        <div style={{ marginTop: 3, display: 'flex', gap: 6, alignItems: 'center' }}>
          <ZustandChip zustand={pos.zustand} />
          <span style={{ color: T.textFaint, fontSize: '0.7rem' }}>
            · {KAT_LABEL[pos.kategorie] || pos.kategorie || '–'}
          </span>
        </div>
      </div>
      <div style={{ textAlign: 'right', fontFamily: T.fontMono, fontSize: '0.85rem' }}>
        <div style={{ fontSize: '0.62rem', color: T.textFaint, textTransform: 'uppercase', letterSpacing: '0.09em', fontFamily: T.fontBody, fontWeight: 600 }}>gefordert</div>
        {fmtEuro(pos.gefordert)}
      </div>
      <div style={{ textAlign: 'right', fontFamily: T.fontMono, fontSize: '0.85rem', color: T.greenText }}>
        <div style={{ fontSize: '0.62rem', color: T.textFaint, textTransform: 'uppercase', letterSpacing: '0.09em', fontFamily: T.fontBody, fontWeight: 600 }}>anerkannt</div>
        {fmtEuro(pos.anerkannt)}
      </div>
      <div style={{ textAlign: 'right', fontFamily: T.fontMono, fontSize: '0.85rem',
                     color: pos.offen > 0 ? T.redText : T.textFaint,
                     fontWeight: pos.offen > 0 ? 600 : 400 }}>
        <div style={{ fontSize: '0.62rem', color: T.textFaint, textTransform: 'uppercase', letterSpacing: '0.09em', fontFamily: T.fontBody, fontWeight: 600 }}>offen</div>
        {fmtEuro(pos.offen)}
      </div>
      <div>
        <span style={{
          display: 'inline-block', padding: '4px 10px', borderRadius: 999,
          fontSize: '0.7rem', fontWeight: 600,
          background: pos.zustand === 'anerkannt' || pos.zustand === 'erledigt' ? T.green : T.navy,
          color: T.white,
        }}>{pos.zustand === 'anerkannt' || pos.zustand === 'erledigt' ? 'erledigt' : eskalationLabel(pos.eskalationsstufe)}</span>
      </div>
      <div style={{ fontSize: '0.75rem', color: T.textMid }}>
        <div style={{ fontWeight: 600, color: T.text }}>
          {chk.erledigt.length}&nbsp;/&nbsp;{gesamtCheck || 0}&nbsp;Checkliste
        </div>
        {chk.offen.length > 0 && (
          <div style={{ color: T.amberText, fontSize: '0.7rem' }}>
            fehlt: {chk.offen[0].replaceAll('_', ' ')}
          </div>
        )}
        {chk.offen.length === 0 && gesamtCheck > 0 && (
          <div style={{ color: T.greenText, fontSize: '0.7rem' }}>alles erfüllt</div>
        )}
      </div>
    </div>
  );
}

function AggregationsZeile({ gruppe, positionen }) {
  const summen = positionen.reduce((acc, [, p]) => ({
    gefordert: acc.gefordert + Number(p.gefordert || 0),
    anerkannt: acc.anerkannt + Number(p.anerkannt || 0),
    offen:     acc.offen     + Number(p.offen     || 0),
  }), { gefordert: 0, anerkannt: 0, offen: 0 });
  return (
    <div
      data-testid={`aggregationszeile-${gruppe}`}
      style={{
        display: 'grid',
        gridTemplateColumns: '1.6fr 130px 130px 130px',
        gap: 12, alignItems: 'center',
        padding: '14px 16px',
        background: T.cardBg,
        border: `1px solid ${T.border}`,
        borderRadius: 10, marginBottom: 6,
      }}
    >
      <div>
        <div style={{ fontWeight: 600, color: T.text, fontSize: '0.95rem' }}>
          {KAT_LABEL[gruppe] || gruppe}
        </div>
        <div style={{ color: T.textMuted, fontSize: '0.72rem' }}>
          {positionen.map(([k]) => k).join(' + ')}
        </div>
      </div>
      <div style={{ textAlign: 'right', fontFamily: T.fontMono, fontSize: '0.92rem' }}>
        <div style={{ fontSize: '0.62rem', color: T.textFaint, textTransform: 'uppercase', letterSpacing: '0.09em', fontFamily: T.fontBody, fontWeight: 600 }}>gefordert</div>
        {fmtEuro(summen.gefordert)}
      </div>
      <div style={{ textAlign: 'right', fontFamily: T.fontMono, fontSize: '0.92rem', color: T.greenText }}>
        <div style={{ fontSize: '0.62rem', color: T.textFaint, textTransform: 'uppercase', letterSpacing: '0.09em', fontFamily: T.fontBody, fontWeight: 600 }}>anerkannt</div>
        {fmtEuro(summen.anerkannt)}
      </div>
      <div style={{ textAlign: 'right', fontFamily: T.fontMono, fontSize: '0.92rem',
                     color: summen.offen > 0 ? T.redText : T.textFaint,
                     fontWeight: summen.offen > 0 ? 600 : 400 }}>
        <div style={{ fontSize: '0.62rem', color: T.textFaint, textTransform: 'uppercase', letterSpacing: '0.09em', fontFamily: T.fontBody, fontWeight: 600 }}>offen</div>
        {fmtEuro(summen.offen)}
      </div>
    </div>
  );
}

export default function PositionsDashboard({ az, onOeffneEreignisse = () => {} }) {
  const [daten, setDaten] = useState(null);
  const [fehler, setFehler] = useState(null);
  const [view, setView] = useState('getrennt');

  useEffect(() => {
    if (!az) return;
    let abgebrochen = false;
    const token = tokenStore.getAccess();
    fetch(`${API_BASE}/akten/${encodeURIComponent(az)}/positionen/status`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(res => res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`)))
      .then(d => { if (!abgebrochen) setDaten(d); })
      .catch(e => { if (!abgebrochen) setFehler(e.message || String(e)); });
    return () => { abgebrochen = true; };
  }, [az]);

  const gruppen = useMemo(() => {
    if (!daten?.positionen) return {};
    const g = {};
    for (const [k, p] of Object.entries(daten.positionen)) {
      const key = p.aggregation || 'sonstiges';
      (g[key] = g[key] || []).push([k, p]);
    }
    return g;
  }, [daten]);

  if (fehler) {
    return (
      <div style={{ padding: 12, background: T.redBg, border: `1px solid ${T.red}`, borderRadius: 8, color: T.redText, fontSize: '0.85rem' }}>
        Positionsstatus nicht geladen: {fehler}
      </div>
    );
  }
  if (!daten) {
    return (
      <div style={{ padding: 12, color: T.textMuted, fontSize: '0.85rem' }}>
        Lade Positionsstatus…
      </div>
    );
  }

  const eintraege = Object.entries(daten.positionen || {});
  const juengsterStand = eintraege
    .map(([, p]) => p.stand)
    .filter(Boolean)
    .sort()
    .slice(-1)[0];

  const summen = eintraege.reduce((acc, [, p]) => ({
    gefordert: acc.gefordert + Number(p.gefordert || 0),
    anerkannt: acc.anerkannt + Number(p.anerkannt || 0),
    offen:     acc.offen     + Number(p.offen     || 0),
  }), { gefordert: 0, anerkannt: 0, offen: 0 });

  return (
    <div style={{
      background: T.cardBg,
      border: `1px solid ${T.border}`,
      borderRadius: 12,
      marginBottom: 18,
      boxShadow: '0 1px 2px rgba(27,42,74,0.03)',
      overflow: 'hidden',
    }}>
      <div style={{
        padding: '14px 18px',
        borderBottom: `1px solid ${T.borderSoft}`,
        background: T.surface,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12,
      }}>
        <div>
          <div style={{ fontFamily: T.fontDisplay, fontSize: '0.98rem', fontWeight: 600, color: T.navy }}>
            Forderungen · Positions-Übersicht
          </div>
          <div style={{ fontSize: '0.72rem', color: T.textMuted, marginTop: 2 }}>
            {eintraege.length} Positionen · gefordert{' '}
            <b style={{ color: T.text, fontFamily: T.fontMono }}>{fmtEuro(summen.gefordert)}</b>
            {' · anerkannt '}
            <b style={{ color: T.greenText, fontFamily: T.fontMono }}>{fmtEuro(summen.anerkannt)}</b>
            {' · offen '}
            <b style={{ color: T.redText, fontFamily: T.fontMono }}>{fmtEuro(summen.offen)}</b>
          </div>
        </div>
        <div style={{ display: 'inline-flex', background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: 3 }}>
          <button
            data-testid="toggle-getrennt"
            data-active={view === 'getrennt'}
            onClick={() => setView('getrennt')}
            style={{
              background: view === 'getrennt' ? T.navy : 'transparent',
              color: view === 'getrennt' ? T.white : T.textMuted,
              border: 0, padding: '6px 14px', borderRadius: 6,
              fontFamily: T.fontBody, fontSize: '0.78rem', fontWeight: 600,
              cursor: 'pointer',
            }}
          >getrennt</button>
          <button
            data-testid="toggle-aggregiert"
            data-active={view === 'aggregiert'}
            onClick={() => setView('aggregiert')}
            style={{
              background: view === 'aggregiert' ? T.navy : 'transparent',
              color: view === 'aggregiert' ? T.white : T.textMuted,
              border: 0, padding: '6px 14px', borderRadius: 6,
              fontFamily: T.fontBody, fontSize: '0.78rem', fontWeight: 600,
              cursor: 'pointer',
            }}
          >aggregiert</button>
        </div>
      </div>

      <div style={{ padding: 14 }}>
        {daten.historie_hinweis?.zeige && fmtDatum(daten.historie_hinweis.beginnt_am) && (
          <div
            data-testid="historie-hinweis"
            style={{
              display: 'flex', alignItems: 'flex-start', gap: 8,
              padding: '10px 12px', marginBottom: 12,
              background: T.surface,
              borderLeft: `3px solid ${T.accent}`,
              borderRadius: 6,
              fontSize: '0.78rem', color: T.textMid, lineHeight: 1.4,
            }}
          >
            <span aria-hidden="true" style={{ fontSize: '1rem', lineHeight: 1 }}>🕓</span>
            <span>
              <b style={{ color: T.text }}>Bestandsakte:</b>{' '}
              Ereignishistorie beginnt am{' '}
              <b>{fmtDatum(daten.historie_hinweis.beginnt_am)}</b>
              {' — ältere Vorgänge siehe Regulierung.'}
            </span>
          </div>
        )}

        {eintraege.length === 0 && (
          <div style={{ padding: 20, textAlign: 'center', color: T.textMuted, fontSize: '0.85rem' }}>
            Noch keine Positionen mit Ereignissen erfasst.
          </div>
        )}

        {view === 'getrennt' && eintraege.map(([k, p]) => (
          <PositionsZeile key={k} posKey={k} pos={p} onClick={onOeffneEreignisse} />
        ))}

        {view === 'aggregiert' && Object.entries(gruppen).map(([g, ps]) => (
          <AggregationsZeile key={g} gruppe={g} positionen={ps} />
        ))}

        {eintraege.length > 0 && (
          <div style={{
            marginTop: 14, paddingTop: 12,
            borderTop: `1px dashed ${T.border}`,
            display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap',
          }}>
            <AbleitungBadge
              aussage="Zustand und Eskalationsvorschläge aus Aktenlage abgeleitet"
              stand={juengsterStand}
            />
            {daten.registry_version && (
              <span style={{ fontSize: '0.7rem', color: T.textFaint, fontFamily: T.fontMono }}>
                registry {String(daten.registry_version).slice(0, 8)}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
