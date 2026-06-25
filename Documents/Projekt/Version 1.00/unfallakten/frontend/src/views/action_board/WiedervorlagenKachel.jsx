import React from "react";

function WvEintrag({ e, onOpenAkte }) {
  const istUeberfaellig = e.hat_wv && e.tage_bis < 0;
  const istHeute        = e.hat_wv && e.tage_bis === 0;
  const ohneWv          = !e.hat_wv;

  let borderColor = "#f59e0b";
  if (istUeberfaellig) borderColor = "#dc2626";
  if (ohneWv)          borderColor = "#6366f1";

  let badgeContent = null;
  if (istUeberfaellig) badgeContent = (
    <span style={{ background: "#dc2626", color: "white", borderRadius: 4, padding: "1px 5px", fontSize: 10, fontWeight: 600 }}>
      {e.tage_bis}T
    </span>
  );
  if (istHeute) badgeContent = (
    <span style={{ background: "#f59e0b", color: "#1c1917", borderRadius: 4, padding: "1px 5px", fontSize: 10, fontWeight: 600 }}>
      HEUTE
    </span>
  );
  if (ohneWv) badgeContent = (
    <span style={{ color: "#818cf8", fontSize: 10, fontWeight: 600 }}>⚠ keine WV</span>
  );

  return (
    <div
      onClick={() => onOpenAkte && onOpenAkte(e.az)}
      style={{
        background: "#132237",
        borderRadius: 4,
        padding: "7px 10px",
        marginBottom: 5,
        cursor: "pointer",
        borderLeft: `3px solid ${borderColor}`,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}
    >
      <div>
        <div style={{ color: "#e2e8f0", fontSize: 12, fontWeight: 500 }}>
          {e.kurzbezeichnung || e.mandant || e.az}
        </div>
        <div style={{ color: "#94a3b8", fontSize: 10 }}>
          {e.grund ? `${e.grund} · ` : ""}{e.az}
        </div>
      </div>
      {badgeContent}
    </div>
  );
}

export default function WiedervorlagenKachel({ wv, ohne_wv, onOpenAkte }) {
  const ueberfaellig = (wv || []).filter((e) => e.tage_bis < 0);
  const heute        = (wv || []).filter((e) => e.tage_bis === 0);
  const gesamt       = (wv || []).length;
  const alleOhneWv   = ohne_wv || [];
  const hatInhalt    = gesamt > 0 || alleOhneWv.length > 0;

  const S = {
    kachel: { background: "#0c1929", border: "1px solid #1e3a5f", borderRadius: 6, padding: 12, display: "flex", flexDirection: "column", maxHeight: "calc(50vh - 90px)", overflow: "hidden" },
    header: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
    titel:  { color: "#60a5fa", fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" },
    badge:  { background: "#1d4ed8", color: "white", borderRadius: 10, padding: "2px 8px", fontSize: 10, fontWeight: 600 },
    label:  { color: "#6b7280", fontSize: 9, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4, paddingLeft: 2 },
    leer:   { color: "#4ade80", fontSize: 12, padding: "12px 0", textAlign: "center" },
  };

  if (!hatInhalt) {
    return (
      <div style={S.kachel}>
        <div style={S.header}><span style={S.titel}>🔁 Wiedervorlagen</span></div>
        <div style={S.leer}>Alle Wiedervorlagen erledigt</div>
      </div>
    );
  }

  return (
    <div style={S.kachel}>
      <div style={S.header}>
        <span style={S.titel}>🔁 Wiedervorlagen</span>
        {gesamt > 0 && <span style={S.badge}>{gesamt} offen</span>}
      </div>

      <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
        {ueberfaellig.length > 0 && (
          <>
            <div style={S.label}>Überfällig</div>
            {ueberfaellig.map((e) => <WvEintrag key={e.az + e.datum} e={e} onOpenAkte={onOpenAkte} />)}
          </>
        )}

        {heute.length > 0 && (
          <>
            <div style={{ ...S.label, marginTop: ueberfaellig.length > 0 ? 8 : 0 }}>Heute fällig</div>
            {heute.map((e) => <WvEintrag key={e.az + e.datum} e={e} onOpenAkte={onOpenAkte} />)}
          </>
        )}

        {alleOhneWv.length > 0 && (
          <>
            <div style={{ ...S.label, marginTop: gesamt > 0 ? 8 : 0 }}>Keine Wiedervorlage gesetzt</div>
            {alleOhneWv.map((e) => <WvEintrag key={e.az} e={e} onOpenAkte={onOpenAkte} />)}
          </>
        )}
      </div>
    </div>
  );
}
