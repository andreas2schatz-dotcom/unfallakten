import React from "react";
import T from "../config/theme.js";
import { Card, CardHead } from "../components/common.jsx";

export function intakeBadge(status) {
  switch (status) {
    case "bereit_zur_review":
      return { text: "Review ausstehend", color: T.amberText, bg: T.amberBg };
    case "pipeline_fehler":
      return { text: "Fehler – prüfen", color: T.redText, bg: T.redBg };
    default:
      return { text: "Wird verarbeitet", color: T.textMuted, bg: T.surface };
  }
}

function fmtDatum(iso) {
  if (!iso) return "";
  try {
    const dt = new Date(String(iso).replace(" ", "T"));
    if (isNaN(dt.getTime())) return "";
    return dt.toLocaleString("de-DE", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export default function IntakePendingListe({ eintraege = [], onOpenReview }) {
  if (!eintraege.length) return null;
  return (
    <Card>
      <CardHead title={`In Verarbeitung (${eintraege.length})`} />
      {eintraege.map((e, i) => {
        const b = intakeBadge(e.queue_status);
        return (
          <div key={e.intake_id}
            style={{ display: "flex", alignItems: "center", gap: 13,
              padding: "11px 1.4rem",
              borderBottom: i < eintraege.length - 1
                ? `1px solid ${T.borderSoft}` : "none" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: T.fontBody, fontSize: "0.975rem",
                fontWeight: 600, color: T.text, overflow: "hidden",
                textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {e.bezeichnung}
              </div>
              <div style={{ fontFamily: T.fontBody, fontSize: "0.815rem",
                color: T.textFaint, marginTop: 3 }}>
                {e.klasse || "—"} · {fmtDatum(e.erstellt_am)}
              </div>
            </div>
            <span style={{ background: b.bg, color: b.color,
              borderRadius: 10, padding: "2px 8px", fontSize: "0.825rem",
              fontWeight: 600, flexShrink: 0 }}>
              {b.text}
            </span>
            <button
              onClick={() => onOpenReview?.(e.intake_id)}
              style={{ background: "none", border: "none", color: T.accent,
                cursor: "pointer", fontFamily: T.fontBody,
                fontSize: "0.875rem", fontWeight: 600, flexShrink: 0 }}>
              Zur Review →
            </button>
          </div>
        );
      })}
    </Card>
  );
}
