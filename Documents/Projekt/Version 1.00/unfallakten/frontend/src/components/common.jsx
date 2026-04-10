import React, { useState, useRef, useEffect, useCallback } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { STATUS_MAP, KLAGE_SECTION_COLORS } from "../config/constants.js";
import { fmtEuro, fmtSize } from "../config/utils.js";
import { ping, ApiError } from "../api.js";

function StatusBadge({ status, map = STATUS_MAP }) {
  const s = map[status] || { label: status, color: "#888", bg: "#f0f0f0" };
  const bg = s.bg || s.color + "18";
  return (
    <span style={{ display:"inline-flex", alignItems:"center", gap:5, background:bg, color:s.color, border:`1px solid ${s.color}33`, borderRadius:20, padding:"2px 9px", fontSize:"0.845rem", fontWeight:600, whiteSpace:"nowrap" }}>
      <span style={{ width:6, height:6, borderRadius:"50%", background:s.color, flexShrink:0 }} />
      {s.label}
    </span>
  );
}


function Card({ children, style = {} }) {
  return <div style={{ background:T.white, borderRadius:12, border:`1px solid ${T.border}`, boxShadow:"0 2px 8px rgba(0,0,0,0.04)", overflow:"hidden", ...style }}>{children}</div>;
}


function CardHead({ title, action }) {
  return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"1rem 1.4rem", borderBottom:`1px solid ${T.border}` }}>
      <h3 style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"1.05rem", fontWeight:700, color:T.navy, margin:0, letterSpacing:"-0.01em" }}>{title}</h3>
      {action}
    </div>
  );
}


// Klage-spezifischer CardHead: Farbige Hintergrundstreifen (Word-Vorlage: Arial 16pt)


function KlageCardHead({ nr, title, action }) {
  const col = KLAGE_SECTION_COLORS[(nr - 1) % KLAGE_SECTION_COLORS.length] || KLAGE_SECTION_COLORS[0];
  return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
      padding:"0.75rem 1.4rem",
      background: col.bg,
      borderBottom: `1px solid ${col.border}`,
      borderRadius:"8px 8px 0 0",
    }}>
      <h3 style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"1rem", fontWeight:700,
        color: col.text, margin:0, letterSpacing:"0.01em" }}>
        {nr ? `${nr}. ` : ""}{title}
      </h3>
      {action}
    </div>
  );
}


function Btn({ children, variant="primary", onClick, onMouseDown, disabled=false, size="md", style={} }) {
  const pad  = { sm:"5px 10px", md:"8px 14px", lg:"10px 18px" }[size];
  const fs   = { sm:"0.74rem",  md:"0.82rem",  lg:"0.88rem"  }[size];
  const vars = {
    primary:   { background:T.navy,    color:T.white,    border:"none" },
    secondary: { background:T.surface, color:T.textMid,  border:`1px solid ${T.border}` },
    gold:      { background:T.accent,    color:T.navy,     border:"none" },
    danger:    { background:T.redBg,   color:T.red,      border:`1px solid ${T.red}33` },
  };
  return (
    <button disabled={disabled} onClick={disabled ? null : onClick} onMouseDown={onMouseDown}
      style={{ display:"inline-flex", alignItems:"center", gap:6, borderRadius:7, fontFamily:"'Figtree',sans-serif", fontWeight:600, cursor:disabled?"default":"pointer", transition:"all 0.15s", opacity:disabled?0.55:1, padding:pad, fontSize:fs, ...vars[variant], ...style }}>
      {children}
    </button>
  );
}


function FieldInput({ label, value, onChange, type="text", placeholder="", required=false }) {
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
      {label && <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem", fontWeight:600, color:T.textMid, letterSpacing:"0.05em", textTransform:"uppercase" }}>{label}{required && <span style={{ color:T.red }}> *</span>}</label>}
      <input type={type} value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)}
        style={{ padding:"8px 10px", border:`1.5px solid ${T.border}`, borderRadius:7, fontFamily:"'Figtree',sans-serif", fontSize:"0.985rem", color:T.text, background:T.surface, outline:"none" }}
        onFocus={e => e.target.style.borderColor = T.accent}
        onBlur={e  => e.target.style.borderColor = T.border} />
    </div>
  );
}


function FieldSelect({ label, value, onChange, options }) {
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
      {label && <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem", fontWeight:600, color:T.textMid, letterSpacing:"0.05em", textTransform:"uppercase" }}>{label}</label>}
      <select value={value} onChange={e => onChange(e.target.value)}
        style={{ padding:"8px 10px", border:`1.5px solid ${T.border}`, borderRadius:7, fontFamily:"'Figtree',sans-serif", fontSize:"0.985rem", color:T.text, background:T.surface, outline:"none", cursor:"pointer" }}>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}


function Toast({ msg, onDone }) {
  useEffect(() => { const t = setTimeout(onDone, 2600); return () => clearTimeout(t); }, [onDone]);
  return (
    <div style={{ position:"fixed", bottom:24, right:24, zIndex:600, background:T.navy, color:T.white, padding:"10px 18px", borderRadius:10, fontFamily:"'Figtree',sans-serif", fontSize:"0.975rem", boxShadow:`0 8px 32px rgba(0,0,0,0.25), 0 0 0 1.5px ${T.accentTrim}`, display:"flex", alignItems:"center", gap:8, animation:"slideUp 0.3s ease-out" }}>
      <span style={{ color:T.accentLight, flexShrink:0 }}>{Ic.check}</span>{msg}
    </div>
  );
}


function SlidePanel({ open, onClose, title, children }) {
  return (
    <>
      {open && <div onClick={onClose} style={{ position:"fixed", inset:0, background:"rgba(17,29,53,0.45)", zIndex:300, backdropFilter:"blur(2px)" }} />}
      <div style={{ position:"fixed", top:0, right:0, bottom:0, width:"min(500px, calc(100vw - 40px))", background:T.white, boxShadow:"-8px 0 48px rgba(0,0,0,0.18)", zIndex:310, display:"flex", flexDirection:"column", transform:open?"translateX(0)":"translateX(105%)", transition:"transform 0.3s cubic-bezier(0.16,1,0.3,1)" }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"1.1rem 1.5rem", borderBottom:`1px solid ${T.border}`, background:T.navy, flexShrink:0 }}>
          <span style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"1.175rem", fontWeight:700, color:T.white }}>{title}</span>
          <button onClick={onClose} style={{ background:"rgba(255,255,255,0.1)", border:"none", borderRadius:6, padding:7, cursor:"pointer", color:T.white, display:"flex" }}>{Ic.x}</button>
        </div>
        <div style={{ flex:1, overflowY:"auto", padding:"1.4rem" }}>{children}</div>
      </div>
    </>
  );
}




function useBackend() {
  const [online,  setOnline]  = useState(null); // null = prüfend
  const [checked, setChecked] = useState(false);
  useEffect(() => {
    ping().then(ok => { setOnline(ok); setChecked(true); });
  }, []);
  return { online, checked };
}


function apiErrMsg(err) {
  if (!err) return "Unbekannter Fehler.";
  if (err instanceof ApiError) {
    if (err.status === 0)   return "Keine Verbindung zum Server.";
    if (err.status === 401) return "Sitzung abgelaufen. Bitte neu anmelden.";
    if (err.status === 403) return "Keine Berechtigung für diese Aktion.";
    if (err.status === 404) return "Datensatz nicht gefunden.";
    if (err.status === 409) return "Konflikt: Datensatz existiert bereits.";
    if (err.status >= 500)  return `Serverfehler (${err.status}). Bitte IT informieren.`;
    return err.message || `Fehler ${err.status}`;
  }
  return err.message || "Unbekannter Fehler.";
}


function BackendBadge({ online }) {
  if (online === null) return (
    <div style={{ display:"flex", alignItems:"center", gap:5, fontFamily:"'Figtree',sans-serif", fontSize:"0.845rem", color:"rgba(255,255,255,0.45)", padding:"4px 9px", background:"rgba(255,255,255,0.06)", borderRadius:6, border:"1px solid rgba(255,255,255,0.1)" }}>
      <span style={{ width:6, height:6, borderRadius:"50%", background:"rgba(255,255,255,0.3)" }}/>Verbinde …
    </div>
  );
  if (online) return (
    <div style={{ display:"flex", alignItems:"center", gap:5, fontFamily:"'Figtree',sans-serif", fontSize:"0.845rem", color:"rgba(100,220,150,0.9)", padding:"4px 9px", background:"rgba(16,185,129,0.1)", borderRadius:6, border:"1px solid rgba(16,185,129,0.2)" }}>
      <span style={{ width:6, height:6, borderRadius:"50%", background:T.green }}/>Live-API
    </div>
  );
  return (
    <div style={{ display:"flex", alignItems:"center", gap:5, fontFamily:"'Figtree',sans-serif", fontSize:"0.845rem", color:T.amberText, padding:"4px 9px", background:T.amberBg, borderRadius:6, border:`1px solid ${T.amber}44` }}>
      <span style={{ width:6, height:6, borderRadius:"50%", background:T.amber }}/>Demo-Modus
    </div>
  );
}


function Skeleton({ width="100%", height=18, radius=6, style={} }) {
  return (
    <div style={{ width, height, borderRadius:radius, background:"linear-gradient(90deg,#f0ece4 25%,#e8e2d8 50%,#f0ece4 75%)", backgroundSize:"200% 100%", animation:"shimmer 1.5s infinite", ...style }}/>
  );
}


function ApiErrorBanner({ error, onRetry }) {
  if (!error) return null;
  return (
    <div style={{ background:T.redBg, border:`1px solid ${T.red}33`, borderRadius:10, padding:"10px 14px", display:"flex", alignItems:"center", gap:10, fontFamily:"'Figtree',sans-serif", fontSize:"0.955rem", color:T.red, marginBottom:"1rem" }}>
      <span>⚠</span>
      <span style={{ flex:1 }}>{apiErrMsg(error)}</span>
      {onRetry && <Btn variant="danger" size="sm" onClick={onRetry}>Erneut versuchen</Btn>}
    </div>
  );
}



export { StatusBadge, Card, CardHead, KlageCardHead, Btn, FieldInput, FieldSelect, Toast, SlidePanel, useBackend, apiErrMsg, BackendBadge, Skeleton, ApiErrorBanner };
