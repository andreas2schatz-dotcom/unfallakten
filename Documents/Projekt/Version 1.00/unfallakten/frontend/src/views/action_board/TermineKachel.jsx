import React from "react";

const S = {
  kachel: {
    background: "#1e1b4b",
    border: "1px solid #4c1d95",
    borderRadius: 6,
    padding: 12,
    display: "flex",
    flexDirection: "column",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 10,
  },
  titel: {
    color: "#a78bfa",
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
  },
  badge: {
    background: "#7c3aed",
    color: "white",
    borderRadius: 10,
    padding: "2px 8px",
    fontSize: 10,
    fontWeight: 600,
  },
  sectionLabel: {
    color: "#6b7280",
    fontSize: 9,
    fontWeight: 700,
    letterSpacing: "0.1em",
    textTransform: "uppercase",
    marginBottom: 4,
    marginTop: 8,
    paddingLeft: 2,
  },
  eintrag: (gedimmt) => ({
    background: gedimmt ? "#201d3a" : "#2d2463",
    borderRadius: 4,
    padding: "8px 10px",
    marginBottom: 6,
    cursor: "pointer",
    borderLeft: `3px solid ${gedimmt ? "#4c1d95" : "#7c3aed"}`,
    opacity: gedimmt ? 0.85 : 1,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
  }),
  art: { color: "#c4b5fd", fontSize: 10, fontWeight: 600, marginBottom: 2 },
  bezeichnung: { color: "#e2e8f0", fontSize: 12, fontWeight: 500 },
  az: { color: "#94a3b8", fontSize: 11 },
  uhrzeit: { color: "#a78bfa", fontSize: 14, fontWeight: 700, whiteSpace: "nowrap" },
  leer: { color: "#4ade80", fontSize: 12, padding: "12px 0", textAlign: "center" },
};

export default function TermineKachel({ eintraege, onOpenAkte }) {
  const heute = eintraege.filter((e) => e.tage_bis === 0);
  const morgen = eintraege.filter((e) => e.tage_bis === 1);
  const anzahl = eintraege.length;

  function handleClick(e) {
    if (onOpenAkte) onOpenAkte(e.az);
  }

  if (anzahl === 0) {
    return (
      <div style={S.kachel}>
        <div style={S.header}>
          <span style={S.titel}>📅 Termine</span>
        </div>
        <div style={S.leer}>Heute keine Termine</div>
      </div>
    );
  }

  return (
    <div style={S.kachel}>
      <div style={S.header}>
        <span style={S.titel}>📅 Termine</span>
        <span style={S.badge}>{anzahl}</span>
      </div>

      {heute.length > 0 && (
        <>
          <div style={S.sectionLabel}>Heute</div>
          {heute.map((e) => (
            <div key={e.az + e.termin_datum} style={S.eintrag(false)} onClick={() => handleClick(e)}>
              <div>
                <div style={S.art}>{(e.termin_art || "Termin").toUpperCase()}</div>
                <div style={S.bezeichnung}>{e.kurzbezeichnung || e.mandant}</div>
                <div style={S.az}>{e.az}</div>
              </div>
              <div style={S.uhrzeit}>{e.uhrzeit || ""}</div>
            </div>
          ))}
        </>
      )}

      {morgen.length > 0 && (
        <>
          <div style={{ ...S.sectionLabel, marginTop: heute.length > 0 ? 8 : 0 }}>Morgen</div>
          {morgen.map((e) => (
            <div key={e.az + e.termin_datum} style={S.eintrag(true)} onClick={() => handleClick(e)}>
              <div>
                <div style={{ ...S.art, color: "#9ca3af" }}>{(e.termin_art || "Termin").toUpperCase()}</div>
                <div style={{ ...S.bezeichnung, color: "#cbd5e1" }}>{e.kurzbezeichnung || e.mandant}</div>
                <div style={{ ...S.az, color: "#6b7280" }}>{e.az}</div>
              </div>
              <div style={{ ...S.uhrzeit, color: "#9ca3af" }}>{e.uhrzeit || ""}</div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
