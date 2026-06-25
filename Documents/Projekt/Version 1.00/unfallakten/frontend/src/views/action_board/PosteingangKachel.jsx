import React, { useState } from "react";

function kontoKuerzel(absender) {
  if (!absender) return "unfall";
  if (absender.includes("termin@"))   return "termin";
  if (absender.includes("bussgeld@")) return "bussgeld";
  return "unfall";
}

export default function PosteingangKachel({ eintraege, onOpenEmail, onAlleOeffnen }) {
  const [aktivesKonto, setAktivesKonto] = useState("unfall");

  const konten = ["unfall", "termin", "bussgeld"];
  const zaehler = {};
  konten.forEach((k) => {
    zaehler[k] = (eintraege || []).filter((e) => kontoKuerzel(e.absender) === k).length;
  });

  const gefiltert = (eintraege || []).filter(
    (e) => kontoKuerzel(e.absender) === aktivesKonto
  );
  const gesamt = (eintraege || []).length;

  const S = {
    kachel:  { background: "#0a1f1a", border: "1px solid #14532d", borderRadius: 6, padding: 12 },
    header:  { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
    titel:   { color: "#4ade80", fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" },
    badge:   { background: "#15803d", color: "white", borderRadius: 10, padding: "2px 8px", fontSize: 10, fontWeight: 600 },
    tabs:    { display: "flex", gap: 6, marginBottom: 8 },
    allLink: { textAlign: "center", paddingTop: 6, color: "#22c55e", fontSize: 11, cursor: "pointer", opacity: 0.7 },
    leer:    { color: "#6b7280", fontSize: 12, padding: "12px 0", textAlign: "center" },
  };

  function tabStyle(konto) {
    const aktiv = konto === aktivesKonto;
    return {
      background: aktiv ? "#14532d" : "#1a2e1a",
      color: aktiv ? "#4ade80" : "#6b7280",
      borderRadius: 3,
      padding: "3px 8px",
      fontSize: 10,
      fontWeight: aktiv ? 600 : 400,
      cursor: "pointer",
      display: "flex",
      alignItems: "center",
      gap: 4,
    };
  }

  return (
    <div style={S.kachel}>
      <div style={S.header}>
        <span style={S.titel}>✉ Posteingang</span>
        {gesamt > 0 && <span style={S.badge}>{gesamt} neu</span>}
      </div>

      <div style={S.tabs}>
        {konten.map((k) => (
          <div key={k} style={tabStyle(k)} onClick={() => setAktivesKonto(k)}>
            {k}@
            {zaehler[k] > 0 && (
              <span style={{
                background: k === aktivesKonto ? "#dc2626" : "#374151",
                color: "white",
                borderRadius: 8,
                padding: "0 4px",
                fontSize: 9,
              }}>
                {zaehler[k]}
              </span>
            )}
          </div>
        ))}
      </div>

      {gefiltert.length === 0 ? (
        <div style={S.leer}>Keine neuen E-Mails</div>
      ) : (
        gefiltert.slice(0, 5).map((e) => (
          <div
            key={e.log_id}
            onClick={() => onOpenEmail && onOpenEmail({ az: e.az, logId: e.log_id })}
            style={{
              background: "#0d2b1f",
              borderRadius: 4,
              padding: "8px 10px",
              marginBottom: 5,
              cursor: "pointer",
              borderLeft: "3px solid #16a34a",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ color: "#e2e8f0", fontSize: 12, fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {e.betreff || "(kein Betreff)"}
              </div>
              <div style={{ color: "#6b7280", fontSize: 10 }}>
                {e.absender}{e.az ? ` · ${e.az}` : ""}
              </div>
            </div>
            <div style={{ color: "#4b5563", fontSize: 10, whiteSpace: "nowrap", marginLeft: 8 }}>
              {e.datum
                ? new Date(e.datum).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })
                : ""}
            </div>
          </div>
        ))
      )}

      <div style={S.allLink} onClick={onAlleOeffnen}>→ Alle E-Mails öffnen</div>
    </div>
  );
}
