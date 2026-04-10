import React from "react";
import T from "../../config/theme.js";

export default function TerminEmailView() {
  return (
    <div style={{
      background: T.white,
      border: `1px solid ${T.border}`,
      borderRadius: 12,
      padding: "2.5rem",
      maxWidth: 560,
      margin: "2rem auto",
      textAlign: "center",
      boxShadow: "0 2px 8px rgba(0,0,0,0.04)",
    }}>
      <div style={{ color:"#1B2A4A", opacity:0.3, marginBottom:"0.75rem", display:"flex", justifyContent:"center" }}>
        <svg viewBox="0 0 24 24" fill="currentColor" style={{width:36,height:36}}><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>
      </div>
      <h2 style={{
        fontFamily: "'Bricolage Grotesque',sans-serif",
        fontSize: "1.35rem", fontWeight: 700,
        color: T.navy, margin: "0 0 0.5rem",
      }}>
        Terminanfragen-Workflow
      </h2>
      <p style={{
        fontFamily: "'Figtree',sans-serif",
        fontSize: "0.955rem", color: T.textMuted,
        margin: "0 0 1.25rem", lineHeight: 1.6,
      }}>
        Eingehende Terminanfragen an{" "}
        <span style={{ fontFamily: "ui-monospace,monospace", color: T.navy }}>
          termin@anwalt-offenbach.de
        </span>{" "}
        werden hier verwaltet und mit dem Kalender synchronisiert,
        sobald das Modul implementiert ist.
      </p>
      <div style={{
        background: T.offWhite,
        border: `1px solid ${T.border}`,
        borderRadius: 8,
        padding: "1rem 1.25rem",
        textAlign: "left",
      }}>
        <div style={{
          fontFamily: "'Figtree',sans-serif",
          fontSize: "0.8rem", fontWeight: 600,
          letterSpacing: "0.07em", textTransform: "uppercase",
          color: T.textMuted, marginBottom: "0.6rem",
        }}>
          Geplante Funktionen
        </div>
        {[
          "Automatische Bestätigung / Ablehnung von Terminanfragen",
          "Sync mit RA-MICRO Kalender",
          "Erinnerungs-E-Mail an Mandant",
          "Terminübersicht und Bearbeitungsstatus",
        ].map((f, i) => (
          <div key={i} style={{
            display: "flex", gap: 8, alignItems: "flex-start",
            fontFamily: "'Figtree',sans-serif",
            fontSize: "0.9rem", color: T.textMid,
            marginBottom: "0.4rem",
          }}>
            <span style={{ color: T.textFaint, flexShrink: 0 }}>·</span>
            {f}
          </div>
        ))}
      </div>
    </div>
  );
}
