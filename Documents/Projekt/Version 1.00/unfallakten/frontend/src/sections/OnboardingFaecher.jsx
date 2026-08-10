import React from "react";
import T from "../config/theme.js";
import { vollmachtAnfrageMailto, vollmachtPdfLaden } from "./mandantAktionen.js";

const chip = {
  fontFamily: T.fontBody, fontSize: "0.72rem", fontWeight: 600, padding: "2px 9px",
  borderRadius: 6, border: `1px solid ${T.accentTrim}`, background: T.accentPale,
  color: T.accentDark, textDecoration: "none", cursor: "pointer", whiteSpace: "nowrap",
};

export default function OnboardingFaecher({ checks, onNavigate, akteId, mandantChecks, mandant, onFehler }) {
  return (
    <div style={{
      background: T.cardBg, borderTop: `1px solid ${T.border}`, padding: "10px 18px",
      display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(260px,1fr))", gap: "2px 20px",
    }}>
      {checks.kacheln.map(k => (
        <div key={k.key} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0",
          fontFamily: T.fontBody, fontSize: "0.85rem" }}>
          <span style={{ color: k.ok ? T.green : T.amber, fontWeight: 700, width: 16, textAlign: "center" }}>
            {k.ok ? "✓" : "○"}
          </span>
          <span style={{ color: k.ok ? T.textMuted : T.text, fontWeight: k.ok ? 400 : 600 }}>
            {k.label}
            {k.optional && !k.ok && (
              <span style={{ color: T.textFaint, fontSize: "0.7rem", marginLeft: 5 }}>optional</span>
            )}
          </span>
          {!k.ok && (
            <span style={{ marginLeft: "auto", display: "flex", gap: 5 }}>
              {k.key === "vollmacht" && (mandantChecks?.mandant_email || mandant?.email) && (
                <a href={vollmachtAnfrageMailto(mandantChecks, mandant)} style={chip}>✉ anfordern</a>
              )}
              {k.key === "vollmacht" && akteId && (
                <button style={chip}
                  onClick={() => vollmachtPdfLaden(akteId).catch(e => onFehler && onFehler(`Vollmacht-Fehler: ${e.message}`))}>
                  ↓ PDF
                </button>
              )}
              {onNavigate && (
                <button style={chip} onClick={() => onNavigate(k.tab)}>→ öffnen</button>
              )}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
