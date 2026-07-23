import React, { useEffect, useRef, useState } from "react";
import T from "../config/theme.js";

export function pruefePlatzhalter(text, bekannteKeys) {
  const gefunden = [...(text || "").matchAll(/<([A-Z_]+)>/g)].map(m => m[1]);
  const unbekannte = [...new Set(gefunden.filter(k => !bekannteKeys.includes(k)))];
  return { ok: unbekannte.length === 0, unbekannte };
}

export default function TextbausteinEditor({
  wert, onChange, platzhalter = [], onVorschau = null,
  standardText = null, onReset = null,
}) {
  const taRef = useRef(null);
  const [vorschau, setVorschau] = useState("");

  const bekannteKeys = platzhalter.map(p => p.key);
  const pruefung = pruefePlatzhalter(wert, bekannteKeys);

  const lokaleVorschau = (text) => platzhalter.reduce(
    (t, p) => t.split(`<${p.key}>`).join(p.beispiel || ""), text || "");

  useEffect(() => {
    let aktiv = true;
    const timer = setTimeout(async () => {
      if (onVorschau) {
        try {
          const v = await onVorschau(wert || "");
          if (aktiv) setVorschau(v);
        } catch {
          if (aktiv) setVorschau(lokaleVorschau(wert));
        }
      } else {
        setVorschau(lokaleVorschau(wert));
      }
    }, 400);
    return () => { aktiv = false; clearTimeout(timer); };
  }, [wert, onVorschau, platzhalter]);

  const einfuegen = (key) => {
    const ta = taRef.current;
    const pos = ta ? ta.selectionStart : (wert || "").length;
    const neu = (wert || "").slice(0, pos) + `<${key}>` + (wert || "").slice(pos);
    onChange(neu);
    if (ta) {
      requestAnimationFrame(() => {
        ta.focus();
        ta.selectionStart = ta.selectionEnd = pos + key.length + 2;
      });
    }
  };

  return (
    <div style={{ display: "flex", gap: 14, alignItems: "stretch", flexWrap: "wrap" }}>
      <div style={{ flex: "1 1 320px", minWidth: 280, display: "flex",
        flexDirection: "column", gap: 6 }}>
        <textarea
          ref={taRef}
          value={wert || ""}
          onChange={e => onChange(e.target.value)}
          style={{ width: "100%", minHeight: 180, padding: "10px 12px",
            fontFamily: "ui-monospace,monospace", fontSize: "0.85rem",
            color: T.text, background: T.cardBg,
            border: `1.5px solid ${pruefung.ok ? T.border : T.redLight}`,
            borderRadius: 8, resize: "vertical", boxSizing: "border-box",
            outline: "none", lineHeight: 1.5 }}
        />
        {!pruefung.ok && (
          <div style={{ fontFamily: T.fontBody, fontSize: "0.8rem",
            color: T.redText, background: T.redBg, borderRadius: 6,
            padding: "5px 10px" }}>
            Unbekannte Platzhalter: {pruefung.unbekannte.map(k => `<${k}>`).join(", ")}
          </div>
        )}
        {standardText != null && onReset && (
          <button type="button" onClick={onReset}
            style={{ alignSelf: "flex-start", background: "none",
              border: `1px solid ${T.border}`, borderRadius: 6,
              padding: "4px 10px", cursor: "pointer", fontFamily: T.fontBody,
              fontSize: "0.8rem", color: T.textMid }}>
            ↺ Auf Standard zurücksetzen
          </button>
        )}
      </div>

      <div style={{ flex: "1 1 280px", minWidth: 240, display: "flex",
        flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {platzhalter.map(p => (
            <button key={p.key} type="button" onClick={() => einfuegen(p.key)}
              title={`${p.beschreibung || ""}${p.beispiel ? ` — z. B. „${p.beispiel}“` : ""}`}
              style={{ background: T.blueBg, color: T.blue, border: "none",
                borderRadius: 12, padding: "3px 10px", cursor: "pointer",
                fontFamily: "ui-monospace,monospace", fontSize: "0.75rem",
                fontWeight: 600 }}>
              {p.key}
            </button>
          ))}
        </div>
        <div style={{ flex: 1, padding: "10px 12px", background: T.surface,
          border: `1px solid ${T.border}`, borderRadius: 8,
          fontFamily: T.fontBody, fontSize: "0.85rem", color: T.textMid,
          whiteSpace: "pre-wrap", overflowY: "auto", minHeight: 120 }}>
          <div style={{ fontSize: "0.7rem", fontWeight: 600, color: T.textFaint,
            textTransform: "uppercase", letterSpacing: "0.06em",
            marginBottom: 6 }}>
            Vorschau
          </div>
          {vorschau || <span style={{ color: T.textFaint }}>— leer —</span>}
        </div>
      </div>
    </div>
  );
}
