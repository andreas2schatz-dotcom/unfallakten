import React from "react";
import T from "../../config/theme";
import Ic from "../../config/icons";

const STUFEN = {
  rot:  { zeileBg: T.redBg,   zeileBorder: T.redLight, meta: T.redText,   badgeBg: T.red,      badgeFg: "#FFFFFF",  badgeBorder: "transparent" },
  gelb: { zeileBg: T.amberBg, zeileBorder: T.amberMid, meta: T.amberText, badgeBg: T.amberBg,  badgeFg: T.amberText, badgeBorder: T.amberMid },
};

export function Kachel({ icon, titel, zusammenfassung, children }) {
  return (
    <section style={{ background: T.cardBg, border: `1px solid ${T.border}`, borderRadius: 10, padding: "13px 15px 14px", minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 11 }}>
        <span style={{ color: T.accent, display: "flex" }}>{icon}</span>
        <span style={{ fontFamily: T.fontDisplay, fontSize: T.textSm, fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase", color: T.textMid }}>{titel}</span>
        {zusammenfassung && (
          <span className="tabular-nums" style={{ marginLeft: "auto", fontSize: T.textXs, color: T.textMuted }}>{zusammenfassung}</span>
        )}
      </div>
      {children}
    </section>
  );
}

export function KachelInhalt({ status, fehlerText, onRetry, leer, leerText, children }) {
  if (status === "laedt") {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 9, padding: "4px 0" }}>
        {[88, 70, 79].map((breite) => (
          <div key={breite} style={{ height: 11, width: `${breite}%`, borderRadius: 5, background: `linear-gradient(90deg, ${T.surface} 25%, ${T.border} 50%, ${T.surface} 75%)`, backgroundSize: "200% 100%", animation: "shimmer 1.4s linear infinite" }} />
        ))}
      </div>
    );
  }
  if (status === "fehler") {
    return (
      <div style={{ background: T.redBg, border: `1px solid ${T.redLight}`, borderRadius: 7, padding: "10px 12px" }}>
        <div style={{ fontSize: T.textSm, fontWeight: 600, color: T.redText }}>{fehlerText}</div>
        <button onClick={onRetry} style={{ marginTop: 8, fontSize: T.textXs, fontWeight: 600, color: T.redText, border: `1px solid ${T.redLight}`, background: T.cardBg, borderRadius: 6, padding: "4px 10px", cursor: "pointer" }}>
          Erneut laden
        </button>
      </div>
    );
  }
  if (leer) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: T.textSm, color: T.textMuted, padding: "10px 2px" }}>
        <span style={{ color: T.green, display: "flex" }}>{Ic.check}</span>
        {leerText}
      </div>
    );
  }
  return children;
}

export function Zeile({ stufe, onClick, links, rechts }) {
  const s = STUFEN[stufe];
  return (
    <button
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 10, width: "100%", textAlign: "left",
        padding: "8px 12px", borderRadius: 7, cursor: "pointer", font: "inherit", color: "inherit",
        background: s ? s.zeileBg : T.surface,
        border: `1px solid ${s ? s.zeileBorder : T.border}`,
      }}
    >
      <span style={{ flex: 1, minWidth: 0 }}>{links}</span>
      {rechts}
      <span style={{ color: T.textFaint, display: "flex" }}>{Ic.chevR}</span>
    </button>
  );
}

export function ZeileText({ titel, meta, metaFarbe }) {
  return (
    <span style={{ display: "block", minWidth: 0 }}>
      <span style={{ display: "block", fontSize: T.textSm, fontWeight: 500, color: T.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{titel}</span>
      {meta && (
        <span style={{ display: "block", fontSize: T.textXs, color: metaFarbe || T.textMuted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginTop: 1 }}>{meta}</span>
      )}
    </span>
  );
}

export function StufenBadge({ stufe, children }) {
  const s = STUFEN[stufe] || STUFEN.gelb;
  return (
    <span className="tabular-nums" style={{ fontSize: "0.6875rem", fontWeight: 600, padding: "2px 8px", borderRadius: 999, whiteSpace: "nowrap", background: s.badgeBg, color: s.badgeFg, border: `1px solid ${s.badgeBorder}` }}>
      {children}
    </span>
  );
}

export function AbschnittLabel({ abstandOben, children }) {
  return (
    <div style={{ fontSize: "0.65625rem", fontWeight: 600, letterSpacing: "0.07em", textTransform: "uppercase", color: T.textMuted, margin: `${abstandOben ? 12 : 0}px 2px 6px` }}>
      {children}
    </div>
  );
}

export function MehrKnopf({ onClick, children }) {
  return (
    <button onClick={onClick} style={{ display: "block", marginTop: 9, fontSize: T.textXs, color: T.textMuted, cursor: "pointer", background: "none", border: "none", padding: "4px 2px" }}>
      {children} ›
    </button>
  );
}

export function ZeilenListe({ children }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>{children}</div>;
}
