import React, { useState, useRef, useEffect } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { STATUS_MAP } from "../config/constants.js";
import { BackendBadge, StatusBadge } from "./common.jsx";

function TopNav({ user, onLogout, backendOnline }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ height:56, background:T.navy, borderBottom:`3px solid ${T.gold}`, display:"flex", alignItems:"center", padding:"0 1.5rem", gap:16, flexShrink:0, zIndex:50, position:"relative" }}>
      <div style={{ display:"flex", alignItems:"center", gap:10 }}>
        <div style={{ width:32, height:32, background:T.gold, borderRadius:6, display:"flex", alignItems:"center", justifyContent:"center", color:T.navy }}>{Ic.logo}</div>
        <div>
          <div style={{ fontFamily:"'Plus Jakarta Sans',sans-serif", fontSize:"1.025rem", color:T.white }}>Koch, Schatz &amp; Kollegen</div>
          <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.745rem", color:"rgba(255,255,255,0.45)", letterSpacing:"0.1em", textTransform:"uppercase" }}>Unfallakten-System v1.0</div>
        </div>
      </div>
      <div style={{ flex:1 }} />
      <BackendBadge online={backendOnline} />
      <div style={{ position:"relative" }}>
        <button onClick={() => setOpen(o => !o)} style={{ display:"flex", alignItems:"center", gap:8, background:"rgba(255,255,255,0.08)", border:"1px solid rgba(255,255,255,0.12)", borderRadius:8, padding:"6px 12px", cursor:"pointer", color:T.white, fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.955rem" }}>
          <div style={{ width:26, height:26, background:T.gold, borderRadius:"50%", display:"flex", alignItems:"center", justifyContent:"center", color:T.navy }}>{Ic.user}</div>
          <span style={{ maxWidth:120, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{user.name}</span>
          <span style={{ fontSize:"0.755rem", background:"rgba(200,168,75,0.2)", color:T.white, border:"1px solid rgba(200,168,75,0.3)", padding:"1px 7px", borderRadius:10 }}>Admin</span>
        </button>
        {open && (
          <div style={{ position:"absolute", top:"calc(100% + 8px)", right:0, background:T.white, border:`1px solid ${T.border}`, borderRadius:10, boxShadow:"0 8px 32px rgba(0,0,0,0.15)", minWidth:200, overflow:"hidden", zIndex:200 }}>
            <div style={{ padding:"12px 14px 8px", borderBottom:`1px solid ${T.border}` }}>
              <div style={{ fontSize:"0.945rem", fontWeight:600, color:T.text }}>{user.name}</div>
              <div style={{ fontSize:"0.855rem", color:T.textMuted }}>{user.email}</div>
            </div>
            <button onClick={() => { setOpen(false); onLogout(); }} style={{ width:"100%", display:"flex", alignItems:"center", gap:8, padding:"10px 14px", background:"none", border:"none", cursor:"pointer", fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.955rem", color:T.red }}>
              {Ic.logout} Abmelden
            </button>
          </div>
        )}
      </div>
    </div>
  );
}



function TabBar({ tabs, active, onActivate, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current?.querySelector('[data-active="true"]');
    el?.scrollIntoView({ behavior:"smooth", block:"nearest", inline:"nearest" });
  }, [active]);

  // Nur Aktentabs (id beginnt mit "akte-")
  const akteTabs = tabs.filter(t => t.id.startsWith("akte-"));

  if (akteTabs.length === 0) return (
    <div style={{ height:38, background:T.navyDark, borderBottom:"1px solid rgba(200,168,75,0.12)", display:"flex", alignItems:"center", padding:"0 1.2rem" }}>
      <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem", color:"rgba(255,255,255,0.25)", fontStyle:"italic" }}>Keine Akten geöffnet</span>
    </div>
  );

  return (
    <div style={{ background:T.navyDark, borderBottom:"1px solid rgba(200,168,75,0.18)", display:"flex", alignItems:"stretch", flexShrink:0, height:38 }}>
      <div ref={ref} style={{ display:"flex", alignItems:"stretch", overflowX:"auto", flex:1, scrollbarWidth:"none" }}>
        {akteTabs.map(tab => {
          const isA = tab.id === active;
          return (
            <div key={tab.id} data-active={isA} onClick={() => onActivate(tab.id)}
              style={{ display:"flex", alignItems:"center", gap:7, padding:"0 12px", minWidth:140, maxWidth:210, cursor:"pointer", background:isA?"rgba(255,255,255,0.07)":"transparent", borderRight:"1px solid rgba(255,255,255,0.06)", borderBottom:isA?`2px solid ${T.gold}`:"2px solid transparent", transition:"background 0.15s", flexShrink:0, userSelect:"none" }}>
              <span style={{ color:isA?T.gold:"rgba(255,255,255,0.38)", flexShrink:0, fontSize:"0.85rem" }}>{Ic.akte}</span>
              <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.885rem", fontWeight:isA?600:400, color:isA?T.white:"rgba(255,255,255,0.52)", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", flex:1 }}>{tab.label}</span>
              {tab.status && <span style={{ width:6, height:6, borderRadius:"50%", background:STATUS_MAP[tab.status]?.color||"#888", flexShrink:0 }} />}
              {tab.aktion_erforderlich && (
                <span title="Aktion erforderlich"
                  style={{ width:7, height:7, borderRadius:"50%", background:T.amber, flexShrink:0 }} />
              )}
              <span onClick={e => { e.stopPropagation(); onClose(tab.id); }}
                style={{ display:"flex", alignItems:"center", justifyContent:"center", width:16, height:16, borderRadius:3, color:"rgba(255,255,255,0.33)", transition:"all 0.12s", flexShrink:0 }}
                onMouseEnter={e => { e.currentTarget.style.background="rgba(239,68,68,0.16)"; e.currentTarget.style.color="#ef4444"; }}
                onMouseLeave={e => { e.currentTarget.style.background="transparent"; e.currentTarget.style.color="rgba(255,255,255,0.33)"; }}>
                {Ic.x}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}



export { TopNav, TabBar };
