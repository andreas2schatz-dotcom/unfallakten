import React from "react";

const ROT_BG      = "#3b1c0c";
const ROT_BORDER  = "#dc2626";
const GRAU_BG     = "#231f1d";
const GRAU_BORDER = "#475569";

function Badge({ tage }) {
  const istKritisch = tage <= 0;
  return (
    <span style={{
      background: istKritisch ? ROT_BORDER : "#374151",
      color: "white",
      borderRadius: 4,
      padding: "2px 6px",
      fontSize: 10,
      fontWeight: 700,
      whiteSpace: "nowrap",
    }}>
      {tage === 0 ? "HEUTE" : tage < 0 ? `${tage}T` : `+${tage}T`}
    </span>
  );
}

function FristEintrag({ e, onOpenAkte }) {
  const kritisch = e.tage_bis <= 0;
  return (
    <div
      onClick={() => onOpenAkte && onOpenAkte(e.az)}
      style={{
        background: kritisch ? ROT_BG : GRAU_BG,
        borderRadius: 4,
        padding: "8px 10px",
        marginBottom: 5,
        cursor: "pointer",
        borderLeft: `3px solid ${kritisch ? ROT_BORDER : GRAU_BORDER}`,
        opacity: kritisch ? 1 : 0.75,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
      }}
    >
      <div>
        <div style={{ color: kritisch ? "#fca5a5" : "#9ca3af", fontSize: 10, fontWeight: 600, marginBottom: 2 }}>
          {e.frist_art.toUpperCase()}
          {e.tage_bis < 0
            ? ` · ${Math.abs(e.tage_bis)} TAG${Math.abs(e.tage_bis) === 1 ? "" : "E"} ÜBERFÄLLIG`
            : e.tage_bis === 0 ? " · HEUTE FÄLLIG" : ""}
        </div>
        <div style={{ color: "#e2e8f0", fontSize: 12, fontWeight: 500 }}>{e.kurzbezeichnung || e.mandant}</div>
        <div style={{ color: "#94a3b8", fontSize: 11 }}>{e.az}</div>
      </div>
      <Badge tage={e.tage_bis} />
    </div>
  );
}

export default function FristenKachel({ eintraege, onOpenAkte }) {
  const kritisch  = eintraege.filter((e) => e.tage_bis <= 0);
  const demnächst = eintraege.filter((e) => e.tage_bis > 0);

  const S = {
    kachel: { background: "#1c1917", border: "1px solid #7c2d12", borderRadius: 6, padding: 12 },
    header: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
    titel:  { color: "#fb923c", fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" },
    badge:  { background: "#dc2626", color: "white", borderRadius: 10, padding: "2px 8px", fontSize: 10, fontWeight: 600 },
    label:  { color: "#6b7280", fontSize: 9, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4, paddingLeft: 2 },
    leer:   { color: "#4ade80", fontSize: 12, padding: "12px 0", textAlign: "center" },
  };

  if (eintraege.length === 0) {
    return (
      <div style={S.kachel}>
        <div style={S.header}><span style={S.titel}>⏰ Fristen</span></div>
        <div style={S.leer}>Keine Fristen in den nächsten 14 Tagen</div>
      </div>
    );
  }

  return (
    <div style={S.kachel}>
      <div style={S.header}>
        <span style={S.titel}>⏰ Fristen</span>
        {kritisch.length > 0 && (
          <span style={S.badge}>{kritisch.length} kritisch</span>
        )}
      </div>

      {kritisch.length > 0 && (
        <>
          <div style={{ ...S.label, color: "#fca5a5" }}>⚠ Handlungsbedarf</div>
          {kritisch.map((e) => <FristEintrag key={e.az + e.frist_datum} e={e} onOpenAkte={onOpenAkte} />)}
        </>
      )}

      {demnächst.length > 0 && (
        <>
          <div style={{ ...S.label, marginTop: kritisch.length > 0 ? 10 : 0 }}>Demnächst</div>
          {demnächst.map((e) => <FristEintrag key={e.az + e.frist_datum} e={e} onOpenAkte={onOpenAkte} />)}
        </>
      )}
    </div>
  );
}
