import React, { useState, useCallback, useReducer, useMemo, lazy, Suspense, useRef, useEffect } from "react";
import { auth as apiAuth, ramicroListe, emailImport } from "./api.js";
import T from "./config/theme.js";
import Ic from "./config/icons.jsx";
import { INITIAL_STATE } from "./config/constants.js";
import reducer from "./state/reducer.js";
import LoginPage from "./components/LoginPage.jsx";
import { TopNav, TabBar } from "./components/layout.jsx";
import { useBackend } from "./components/common.jsx";

// Lazy-geladene Views — werden erst beim ersten Aufruf heruntergeladen
const ActionBoardView      = lazy(() => import("./views/ActionBoardView.jsx"));
const StatistikenView      = lazy(() => import("./views/StatistikenView.jsx"));
const AktensucheView       = lazy(() => import("./views/AktensucheView.jsx"));
const EmailImportView      = lazy(() => import("./views/EmailImportView.jsx"));
const WiedervorlageView    = lazy(() => import("./views/WiedervorlageView.jsx"));
const KuerzungskatalogSection = lazy(() => import("./views/KuerzungskatalogView.jsx"));
const EinstellungenView    = lazy(() => import("./views/EinstellungenView.jsx"));
const AkteDetailView       = lazy(() => import("./components/AkteDetailView.jsx"));

function QuickAkteSearch({ onOpenAkte }) {
  const [q, setQ]           = useState("");
  const [items, setItems]   = useState([]);
  const [open, setOpen]     = useState(false);
  const containerRef        = useRef(null);
  const timerRef            = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const search = useCallback((val) => {
    clearTimeout(timerRef.current);
    if (val.length < 2) { setItems([]); setOpen(false); return; }
    timerRef.current = setTimeout(async () => {
      try {
        const res = await emailImport.aktensuche(val);
        setItems(res.akten || []);
        setOpen(true);
      } catch { setItems([]); }
    }, 180);
  }, []);

  const select = useCallback((akte) => {
    onOpenAkte({ az: akte.az, az_roh: akte.az, label: akte.label });
    setQ(""); setItems([]); setOpen(false);
  }, [onOpenAkte]);

  const onKey = (e) => {
    if (e.key === "Enter" && items.length > 0) { select(items[0]); }
    if (e.key === "Escape") { setOpen(false); setQ(""); setItems([]); }
  };

  return (
    <div ref={containerRef} style={{ padding:"0 0.5rem 0.5rem", position:"relative" }}>
      <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.72rem", fontWeight:600, color:"rgba(255,255,255,0.35)", letterSpacing:"0.12em", textTransform:"uppercase", padding:"6px 6px 4px" }}>
        Schnellaufruf
      </div>
      <div style={{ position:"relative" }}>
        <input
          value={q}
          onChange={e => { setQ(e.target.value); search(e.target.value); }}
          onKeyDown={onKey}
          onFocus={() => { if (items.length > 0) setOpen(true); }}
          placeholder="Az. / Name …"
          style={{ width:"100%", boxSizing:"border-box", padding:"7px 10px 7px 30px", background:"rgba(255,255,255,0.07)", border:"1px solid rgba(255,255,255,0.13)", borderRadius:7, color:"rgba(255,255,255,0.85)", fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem", outline:"none" }}
        />
        <span style={{ position:"absolute", left:9, top:"50%", transform:"translateY(-50%)", fontSize:"0.8rem", color:"rgba(255,255,255,0.35)", pointerEvents:"none" }}>🔍</span>
      </div>
      {open && items.length > 0 && (
        <div style={{ position:"absolute", left:"0.5rem", right:"0.5rem", top:"calc(100% - 2px)", background:"#fff", border:"1px solid #ddd", borderRadius:7, boxShadow:"0 6px 20px rgba(0,0,0,0.18)", zIndex:200, overflow:"hidden" }}>
          {items.slice(0, 6).map((a, i) => (
            <div key={i}
              onMouseDown={() => select(a)}
              style={{ padding:"7px 10px", cursor:"pointer", fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem", borderBottom: i < Math.min(items.length, 6) - 1 ? "1px solid #f0f0f0" : "none" }}
              onMouseEnter={e => e.currentTarget.style.background="#f5f1ec"}
              onMouseLeave={e => e.currentTarget.style.background="transparent"}>
              <span style={{ fontWeight:600, fontFamily:"ui-monospace,monospace", fontSize:"0.82rem" }}>{a.az}</span>
              {a.label && <span style={{ color:"#666", marginLeft:6, fontSize:"0.8rem" }}>{a.label}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AppShell({ user, onLogout }) {
  const [tabs, setTabs]          = useState([]);
  const [active, setActive]      = useState("dashboard");   // "dashboard" | "email-import" | "wiedervorlage" | "akte-N"
  const [aktenState, dispatch]   = useReducer(reducer, INITIAL_STATE);
  const [pendingEmailId, setPendingEmailId] = useState(null);
  const { online }               = useBackend();

  const handleLogout = useCallback(async () => {
    await apiAuth.logout().catch(() => {});
    onLogout();
  }, [onLogout]);

  const openAkte = useCallback((baseAkte) => {
    const azVoll  = baseAkte.az_roh || baseAkte.az || String(baseAkte.id);
    // SB-Kürzel entfernen für SQLite-PK und RA-Micro-Suche: "1213/25AS" → "1213/25"
    const azBasis = azVoll.replace(/[A-Z]{2,3}$/i, "").trim();
    const az      = azBasis.includes("/") ? azBasis : azVoll;
    const tabId   = `akte-${az}`;
    setTabs(prev => prev.find(t => t.id===tabId) ? prev : [
      ...prev,
      { id:tabId, label:azVoll, status:aktenState[az]?.status||baseAkte.status||"offen",
        akte:{ ...baseAkte, id:az, az:azVoll, az_roh:az } }
    ]);
    setActive(tabId);
    // On-demand SQLite-Anlage mit Basis-AZ (fire and forget)
    if (az.includes("/")) {
      ramicroListe.onDemand(az).catch(() => {});
    }
  }, [aktenState]);

  const openEmail = useCallback(({ logId }) => {
    setActive("email-import");
    setPendingEmailId(logId);
  }, []);

  const closeTab = useCallback((tabId) => {
    setTabs(prev => {
      const filtered = prev.filter(t => t.id!==tabId);
      if (active===tabId) {
        const idx = prev.findIndex(t => t.id===tabId);
        const fallback = filtered[Math.max(0, idx-1)]?.id || "dashboard";
        setActive(fallback);
      }
      return filtered;
    });
  }, [active]);

  const tabsLive = useMemo(() => tabs.map(t => t.akte ? {
    ...t,
    status: aktenState[t.akte.id]?.status || t.status,
    aktion_erforderlich: aktenState[t.akte.id]?.aktion_erforderlich || 0,
  } : t), [tabs, aktenState]);
  const activeTab = tabs.find(t => t.id===active);

  // Linke Menü-Einträge
  const navItems = [
    { id:"dashboard",       icon:Ic.dash,  label:"Dashboard"       },
    { id:"aktensuche",      icon:"🔍",     label:"Aktensuche"       },
    { id:"email-import",    icon:Ic.email, label:"E-Mail-Import"    },
    { id:"wiedervorlage",   icon:"📋",     label:"Wiedervorlage"    },
    { id:"kuerzungskatalog",icon:"⚖️",    label:"Kürzungskatalog"  },
    { id:"einstellungen",   icon:Ic.settings, label:"Einstellungen"  },
  ];

  return (
    <div style={{ height:"100vh", display:"flex", flexDirection:"column", overflow:"hidden" }}>
      <TopNav user={user} onLogout={handleLogout} backendOnline={online} />

      {/* Haupt-Layout: Seitenmenü + Inhalt */}
      <div style={{ flex:1, display:"flex", overflow:"hidden" }}>

        {/* ── Linke Menüspalte ────────────────────────────────── */}
        <div style={{ width:210, background:T.navy, borderRight:`1px solid ${T.accentTrim}`, display:"flex", flexDirection:"column", flexShrink:0, zIndex:10 }}>

          {/* Schnellaufruf – ganz oben */}
          <div style={{ borderBottom:"1px solid rgba(255,255,255,0.08)" }}>
            <QuickAkteSearch onOpenAkte={openAkte} />
          </div>

          {/* Navigationseinträge */}
          <div style={{ padding:"0.6rem 0.5rem", flex:1 }}>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.72rem", fontWeight:600, color:"rgba(255,255,255,0.35)", letterSpacing:"0.12em", textTransform:"uppercase", padding:"8px 10px 4px" }}>
              Navigation
            </div>
            {navItems.map(item => {
              const isA = active === item.id;
              return (
                <button key={item.id} onClick={() => setActive(item.id)}
                  style={{ width:"100%", display:"flex", alignItems:"center", justifyContent:"flex-start", gap:10, padding:"9px 12px", borderRadius:7, border:"none", cursor:"pointer",
                    background:isA?T.accentTrim:"transparent",
                    color: T.white,
                    fontFamily:"'Figtree',sans-serif", fontSize:"1rem",
                    fontWeight:isA?600:400, textAlign:"left", transition:"all 0.12s", marginBottom:2,
                    ...(isA ? { boxShadow:`inset 2px 0 0 ${T.accent}` } : {}) }}
                  onMouseEnter={e => { if (!isA) e.currentTarget.style.background="rgba(255,255,255,0.06)"; }}
                  onMouseLeave={e => { if (!isA) e.currentTarget.style.background="transparent"; }}>
                  <span style={{ fontSize:"1rem", flexShrink:0 }}>{item.icon}</span>
                  <span style={{ overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{item.label}</span>
                </button>
              );
            })}

            {/* Trennlinie vor offenen Akten */}
            {tabs.filter(t => t.id.startsWith("akte-")).length > 0 && (
              <>
                <div style={{ margin:"8px 10px", borderTop:"1px solid rgba(255,255,255,0.08)" }} />
                <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.72rem", fontWeight:600, color:"rgba(255,255,255,0.35)", letterSpacing:"0.12em", textTransform:"uppercase", padding:"4px 10px 4px" }}>
                  Offene Akten
                </div>
                {tabs.filter(t => t.id.startsWith("akte-")).map(t => {
                  const isA = active === t.id;
                  const hatAktion = aktenState[t.akte?.id]?.aktion_erforderlich;
                  return (
                    <button key={t.id} onClick={() => setActive(t.id)}
                      style={{ width:"100%", display:"flex", alignItems:"center", gap:8, padding:"8px 12px", borderRadius:7, border:"none", cursor:"pointer",
                        background: isA ? "rgba(160,107,74,0.15)" : "transparent",
                        fontFamily:"ui-monospace,monospace", fontSize:"0.855rem",
                        fontWeight: isA ? 700 : 400, color: isA ? T.accentLight : "rgba(255,255,255,0.55)",
                        textAlign:"left", transition:"all 0.12s", marginBottom:1,
                        ...(isA ? { boxShadow:`inset 2px 0 0 ${T.accentLight}` } : {}) }}
                      onMouseEnter={e => { if (!isA) e.currentTarget.style.background="rgba(255,255,255,0.06)"; }}
                      onMouseLeave={e => { if (!isA) e.currentTarget.style.background="transparent"; }}>
                      <span style={{ fontSize:"0.85rem", flexShrink:0 }}>{Ic.akte}</span>
                      <span style={{ overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", flex:1 }}>{t.label}</span>
                      {hatAktion && (
                        <span title="Aktion erforderlich"
                          style={{ width:8, height:8, borderRadius:"50%", background:T.amber, flexShrink:0 }} />
                      )}
                    </button>
                  );
                })}
              </>
            )}
          </div>

          {/* User-Info unten */}
          <div style={{ padding:"0.75rem 0.75rem", borderTop:"1px solid rgba(255,255,255,0.08)", fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem", color:"rgba(255,255,255,0.45)" }}>
            <div style={{ overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{user?.name}</div>
          </div>
        </div>

        {/* ── Rechter Bereich: TabBar + Inhalt ────────────────── */}
        <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>
          <TabBar tabs={tabsLive} active={active} onActivate={setActive} onClose={closeTab} />
          <Suspense fallback={
            <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", background:T.offWhite }}>
              <div style={{ width:32, height:32, border:`3px solid ${T.accentTrim}`, borderTopColor:T.accent, borderRadius:"50%", animation:"spin 0.7s linear infinite" }} />
            </div>
          }>
          <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>
            {active==="dashboard"        ? <ActionBoardView onOpenAkte={openAkte} onOpenEmail={openEmail} />
            : active==="statistiken"     ? <StatistikenView />
            : active==="aktensuche"      ? <AktensucheView onOpenAkte={openAkte} />
            : active==="email-import"    ? <EmailImportView onOpenAkte={openAkte} dispatch={dispatch} initialEmailId={pendingEmailId} />
            : active==="wiedervorlage"   ? <WiedervorlageView onOpenAkte={openAkte} />
            : active==="kuerzungskatalog"? <KuerzungskatalogSection />
            : active==="einstellungen"   ? <EinstellungenView />
            : activeTab?.akte            ? <AkteDetailView akte={activeTab.akte} st={aktenState[activeTab.akte.id]||{}} dispatch={dispatch} />
            : null}
          </div>
          </Suspense>
        </div>
      </div>
    </div>
  );
}



export default function App() {
  const [user, setUser] = useState(null);
  if (!user) return <LoginPage onLogin={setUser} />;
  return <AppShell user={user} onLogout={() => setUser(null)} />;
}
