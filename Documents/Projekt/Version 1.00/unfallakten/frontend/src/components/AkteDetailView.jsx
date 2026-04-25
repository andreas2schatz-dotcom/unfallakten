import React, { useState, useEffect, useCallback, useMemo, lazy, Suspense } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { STATUS_MAP } from "../config/constants.js";
import { fmtEuro } from "../config/utils.js";
import { Toast } from "../components/common.jsx";
import {
  akten as apiAkten,
  beteiligte as apiBeteiligte,
  schaden as apiSchaden,
  apiTodos,
  request,
  ramicroWdm,
  belege as apiBelege,
  portalAkteAktivieren,
} from "../api.js";

// Immer synchron: Default-Tab + kleine Hilfskomponenten
import UebersichtSection from "../sections/UebersichtSection.jsx";
import { TodoSection } from "../sections/UebersichtSection.jsx";
import RaMicroSachstandsCard from "../sections/RaMicroSachstandsCard.jsx";
import AktionBadge from "../views/email_import/components/AktionBadge.jsx";

// Lazy: Werden erst beim ersten Tabwechsel geladen
const BeteiligteSection    = lazy(() => import("../sections/BeteiligteSection.jsx"));
const SchadenSection       = lazy(() => import("../sections/SchadenSection.jsx"));
const RegulierungSection   = lazy(() => import("../sections/RegulierungSection.jsx"));
const DokumenteSection     = lazy(() => import("../sections/DokumenteSection.jsx"));
const WordSection          = lazy(() => import("../sections/WordSection.jsx"));
const UnfalldetailsSection = lazy(() => import("../sections/UnfalldetailsSection.jsx"));
const GebuehrenSection     = lazy(() => import("../sections/GebuehrenSection.jsx"));
const KlageSection         = lazy(() => import("../sections/KlageSection.jsx"));

function AkteDetailView({ akte, st, dispatch }) {
  const [sec, setSec] = useState("uebersicht");
  const [aktionErledigt, setAktionErledigt] = useState(false);
  const [todoKlapp, setTodoKlapp] = useState(false);
  const [statusOffen, setStatusOffen] = useState(false);
  const [statusSpeichert, setStatusSpeichert] = useState(false);
  const [toast, setToast] = useState("");

  const [headerTodos, setHeaderTodos] = useState([]);
  const [headerTodosLoaded, setHeaderTodosLoaded] = useState(false);

  // Portal-aktiv Toggle (lokaler State, da kein SET_AKTE im Reducer)
  const [portalAktiv, setPortalAktiv] = useState(false);
  React.useEffect(() => {
    if (akte?.portal_aktiv !== undefined) setPortalAktiv(!!akte.portal_aktiv);
  }, [akte?.portal_aktiv]);

  const handlePortalToggle = async (aktiv) => {
    try {
      await portalAkteAktivieren(akte.az, aktiv);
      setPortalAktiv(aktiv);
      setToast(aktiv ? "Portal aktiviert" : "Portal deaktiviert");
    } catch (err) {
      console.error("Portal-Toggle fehlgeschlagen:", err);
      setToast("Portal-Toggle fehlgeschlagen: " + (err?.message || String(err)));
    }
  };

  // To-Dos für Header laden + Reload-Funktion für Live-Sync
  const ladeHeaderTodos = React.useCallback(() => {
    if (!akte.az) return;
    const timeout = new Promise((_, reject) => setTimeout(() => reject(), 8000));
    Promise.race([apiTodos.liste(akte.az), timeout])
      .then(r => setHeaderTodos(r?.todos || []))
      .catch(() => setHeaderTodos([]))
      .finally(() => setHeaderTodosLoaded(true));
  }, [akte.az]);

  React.useEffect(() => { ladeHeaderTodos(); }, [ladeHeaderTodos]);

  // Beim ersten Öffnen: Schaden, Regulierungen, Beteiligte und Dokumente aus DB laden
  useEffect(() => {
    const id = akte.id;
    // Schaden laden
    if (!st.schaden) {
      apiSchaden.holen(id)
        .then(res => {
          if (res?.schaden) dispatch({ type:"SAVE_SCHADEN", akteId:id, schaden:res.schaden });
        })
        .catch(() => {});
    }
    // Beteiligte laden
    if (!st.beteiligte) {
      apiBeteiligte.liste(id)
        .then(res => {
          if (res?.beteiligte?.length) dispatch({ type:"SET_BETEILIGTE", akteId:id, beteiligte:res.beteiligte });
        })
        .catch(() => {});
    }
    // Dokumente laden – immer frisch aus DB (werden auch per E-Mail-Import hinzugefügt)
    // Status ebenfalls aus DB laden und in State schreiben
    request(`/akten/${id}`)
      .then(data => {
        if (data?.dokumente) dispatch({ type:"SET_DOKUMENTE", akteId:id, dokumente:data.dokumente });
        if (data?.status)    dispatch({ type:"SET_STATUS",    akteId:id, status:data.status });
        if (data?.abrechnungen) dispatch({ type:"SET_ABRECHNUNGEN", akteId:id, abrechnungen:data.abrechnungen });
      })
      .catch(() => {});
  }, [akte.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── PRD-15: WDM automatisch laden wenn keine lokalen Schadendaten ────────
  const [wdmAutoGeladen, setWdmAutoGeladen] = useState(false);

  useEffect(() => {
    if (wdmAutoGeladen) return;
    if (!st.schaden) return; // Schaden noch nicht aus DB geladen
    if (!akte.id || !String(akte.id).includes("/")) return; // Kein RA-Micro AZ

    // Prüfen ob lokale Schadendaten vorhanden sind
    const felder = ["rep_gutachten_netto","rep_rechnung_brutto","wiederbeschaffung",
                    "wertminderung","nutzungsausfall","mietwagenkosten","sv_kosten",
                    "mietwagenkosten_netto","sv_kosten_netto","abschleppkosten_netto",
                    "standkosten_netto","anabmeldekosten_netto",
                    "schmerzensgeld","abschleppkosten","standkosten","anabmeldekosten",
                    "verdienstausfall","haushalt","unkostenpauschale","sonstiges"];
    const hatLokal = felder.some(k => (st.schaden[k] || 0) > 0);
    if (hatLokal) { setWdmAutoGeladen(true); return; }

    setWdmAutoGeladen(true);
    ramicroWdm.schaden(akte.id)
      .then(async (wdm) => {
        if (!wdm?.schaden || (wdm.felder_gefunden || 0) === 0 && (wdm.extras_gefunden || 0) === 0) return;

        // Schaden-Daten aus WDM zusammenbauen
        const neu = { ...(st.schaden || {}) };
        Object.entries(wdm.schaden).forEach(([k, v]) => {
          if (v > 0) neu[k] = v;
        });
        neu.quelle = "wdm_ramicro";

        // Extras (sonstige Schäden)
        const wdmExtras = (wdm.extras || []).filter(e => (e.betrag || 0) > 0);
        if (wdmExtras.length > 0) {
          neu._extras = wdmExtras;
        }

        // Direkt in DB speichern
        const schadenData = { ...neu };
        try {
          const res = await apiSchaden.speichern(akte.id, schadenData);
          const serverSchaden = res?.schaden || schadenData;
          dispatch({
            type: "SAVE_SCHADEN",
            akteId: akte.id,
            schaden: { ...schadenData, gesamt_brutto: serverSchaden.gesamt_brutto ?? 0 },
          });
        } catch {
          // Bei Fehler trotzdem in Store dispatchen (Daten sind immerhin da)
          dispatch({ type: "SAVE_SCHADEN", akteId: akte.id, schaden: schadenData });
        }
      })
      .catch(() => {}); // WDM nicht verfügbar – kein Fehler
  }, [akte.id, st.schaden, wdmAutoGeladen]); // eslint-disable-line react-hooks/exhaustive-deps

  // Kandidaten-Refresh wenn Schaden-Tab geöffnet wird
  useEffect(() => {
    if (sec !== "schaden" || !akte.id) return;
    apiBelege.kandidaten(akte.id)
      .then(res => {
        const kandidaten = res?.kandidaten || [];
        dispatch({ type: "SET_BELEGE_KANDIDATEN", akteId: akte.id, kandidaten });
      })
      .catch(() => {});
  }, [sec]); // eslint-disable-line react-hooks/exhaustive-deps

  // Live-Schadensumme — PRD-14: Brutto aus Backend-Berechnung (Single Source of Truth)
  const liveBrutto = useMemo(() => {
    const _sd = st.schaden || {};
    const _b  = _sd.abrechnungsberechnung?.gesamt_brutto ?? _sd.gesamt_brutto ?? 0;
    return _b > 0 ? _b : (_sd.gesamt_brutto || akte.brutto || 0);
  }, [st.schaden, akte.brutto]);

  // Badge-Logik: localStorage-Timestamps für Neu-Indikatoren
  const azKey    = (akte?.az || "").replace(/\//g, "-");
  const lsKeyDok = `tab-letztbesucht-${azKey}-dokumente`;
  const lsKeyReg = `tab-letztbesucht-${azKey}-regulierung`;
  // Als React-State damit Badges innerhalb einer Session reaktiv verschwinden
  const [besuchDok, setBesuchDok] = useState(() => localStorage.getItem(lsKeyDok));
  const [besuchReg, setBesuchReg] = useState(() => localStorage.getItem(lsKeyReg));

  // IMP-06: Timestamp setzen wenn Tab beim Laden einer neuen Akte bereits aktiv ist
  useEffect(() => {
    if (!akte?.az) return;
    const now = new Date().toISOString();
    if (sec === "dokumente" && !besuchDok) {
      localStorage.setItem(lsKeyDok, now);
      setBesuchDok(now);
    }
    if (sec === "regulierung" && !besuchReg) {
      localStorage.setItem(lsKeyReg, now);
      setBesuchReg(now);
    }
  }, [akte?.az]); // eslint-disable-line react-hooks/exhaustive-deps

  // PRD-16: Status-Punkte je Reiter — memoized, da bei jedem Render neu berechnet
  const tabs = useMemo(() => {
    const beteiligteOk  = (st.beteiligte||[]).some(b => b.rolle === "mandant") &&
                          (st.beteiligte||[]).some(b => ["gegner","GHPV","GHV","GBEV"].includes(b.rolle||b.kuerzel||""));
    const schadenOk     = (st.schaden?.gesamt_brutto || st.schaden?.abrechnungsberechnung?.gesamt_brutto || 0) > 0;
    const dokumenteAnz  = st.dokumente?.length || 0;
    const regulierungOk = (st.abrechnungen?.length || 0) > 0;
    const klageStatus   = akte.status === "klage";

    const neueDokumente = besuchDok
      ? (st.dokumente || []).filter(d => d.erstellt_am && d.erstellt_am > besuchDok).length
      : 0;
    const neueAbrechnung = besuchReg && (st.abrechnungen || []).length > 0
      ? (st.abrechnungen[0]?.erstellt_am || "") > besuchReg
      : false;

    const sp = (ok, fehlt) => {
      if (ok)    return { dot: "✅", color: T.green };
      if (fehlt) return { dot: "⚠️", color: T.amber };
      return { dot: "⬜", color: T.textFaint };
    };

    return [
      { id:"uebersicht",    label:"⚡ Übersicht" },
      { id:"beteiligte",    label:`👥 Beteiligte`, ...sp(beteiligteOk,  !beteiligteOk  && st.beteiligte  !== undefined) },
      { id:"unfalldetails", label:"🔍 Unfalldetails" },
      { id:"schaden",       label:`🚗 Schaden`,    ...sp(schadenOk,     !schadenOk     && st.schaden     !== undefined) },
      { id:"dokumente",     label: neueDokumente > 0 ? `📄 Dokumente (${dokumenteAnz}) 🔴${neueDokumente}` : `📄 Dokumente (${dokumenteAnz})` },
      { id:"regulierung",   label: neueAbrechnung ? `💶 Regulierung 🔴` : `💶 Regulierung`, ...sp(regulierungOk, false) },
      { id:"gebuehren",     label:"⚖️ Gebühren" },
      { id:"klage",         label:`⚖ Klage`,        ...sp(klageStatus,   false) },
      { id:"word",          label:"📝 Word" },
      { id:"todos",         label:`📋 To-Dos` },
    ];
  }, [st.beteiligte, st.schaden, st.dokumente, st.abrechnungen, akte.status, besuchDok, besuchReg]);

  return (
    <>
    <div style={{ flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>

      {/* Header – alles auf einer Zeile */}
      <div style={{ background:T.navy, padding:"0.85rem 1.75rem 0", flexShrink:0 }}>
        <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:"0.75rem", flexWrap:"nowrap" }}>

          {/* ── Links: Icon + AZ + Status-Dropdown ── */}
          <div style={{ display:"flex", alignItems:"center", gap:10, flexShrink:0 }}>
            <div style={{ width:36, height:36, background:T.accentTrim, borderRadius:8,
              border:`1px solid ${T.accentTrim}`, display:"flex", alignItems:"center",
              justifyContent:"center", color:T.white, flexShrink:0 }}>{Ic.akte}</div>
            <div>
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.7rem",
                color:T.accentLight, letterSpacing:"0.14em", textTransform:"uppercase",
                lineHeight:1, fontWeight:600 }}>Aktenzeichen</div>
              <h1 style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"2.2rem",
                fontWeight:800, color:T.white, margin:"2px 0 0", lineHeight:1.05,
                letterSpacing:"-0.01em" }}>{akte.az}</h1>
            </div>
          {/* ── Status-Dropdown (neben AZ) ── */}
          {(() => {
            const aktStatus = st.status || akte.status || "offen";
            const sm = STATUS_MAP[aktStatus] || STATUS_MAP["offen"];
            return (
              <div style={{ position:"relative", flexShrink:0 }}>
                <button onClick={() => setStatusOffen(o => !o)}
                  style={{ display:"flex", alignItems:"center", gap:5,
                    padding:"4px 10px 4px 8px", borderRadius:20, cursor:"pointer",
                    border:`1.5px solid ${sm.color}`,
                    background:sm.bg, color:sm.color,
                    fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                    fontWeight:700, transition:"all 0.15s", whiteSpace:"nowrap" }}>
                  {sm.label}
                  <span style={{ fontSize:"0.65rem", opacity:0.7,
                    transform: statusOffen ? "rotate(180deg)" : "none",
                    transition:"transform 0.2s", lineHeight:1 }}>▾</span>
                </button>
                {statusOffen && (
                  <>
                    <div onClick={() => setStatusOffen(false)}
                      style={{ position:"fixed", inset:0, zIndex:299 }} />
                    <div style={{ position:"absolute", top:"calc(100% + 6px)", left:0,
                      background:T.navy, border:`1px solid ${T.accentTrim}`,
                      borderRadius:10, zIndex:300, overflow:"hidden",
                      boxShadow:"0 8px 24px rgba(0,0,0,0.4)", minWidth:160 }}>
                      {["offen","in_regulierung","abgeschlossen","klage"].map(s => {
                        const smi = STATUS_MAP[s];
                        const isA = aktStatus === s;
                        return (
                          <button key={s} onClick={async () => {
                            setStatusOffen(false);
                            dispatch({ type:"SET_STATUS", akteId:akte.id, status:s });
                            try {
                              await apiAkten.aktualisieren(akte.id, { status: s });
                            } catch(e) {
                              dispatch({ type:"SET_STATUS", akteId:akte.id, status:aktStatus });
                              setToast("Status konnte nicht gespeichert werden: " + (e?.message || String(e)));
                            }
                          }} style={{
                            display:"block", width:"100%", textAlign:"left",
                            padding:"8px 14px", background: isA ? "rgba(255,255,255,0.08)" : "transparent",
                            border:"none", borderBottom:"1px solid rgba(255,255,255,0.07)",
                            color: isA ? smi.color : "rgba(255,255,255,0.7)",
                            fontFamily:"'Figtree',sans-serif", fontSize:"0.85rem",
                            fontWeight: isA ? 700 : 400, cursor:"pointer",
                            transition:"background 0.1s" }}
                            onMouseEnter={e => e.currentTarget.style.background="rgba(255,255,255,0.08)"}
                            onMouseLeave={e => e.currentTarget.style.background=isA?"rgba(255,255,255,0.08)":"transparent"}>
                            <span style={{ display:"inline-block", width:8, height:8,
                              borderRadius:"50%", background:smi.color,
                              marginRight:7, verticalAlign:"middle" }} />
                            {smi.label}
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            );
          })()}
          </div>

          {/* ── Mitte: To-Do Aufklapp-Kachel (flex-grow, so weit links wie möglich) ── */}
          {(() => {
            const offeneTodos = headerTodos.filter(t => !t.erledigt);
            const FARBEN_DOT = { rot:T.red, orange:"#f97316", gelb:"#eab308", grau:"rgba(255,255,255,0.3)" };
            const heute = new Date(); heute.setHours(0,0,0,0);
            const dring = (todo) => {
              if (todo.faellig_am) {
                const tage = Math.round((new Date(todo.faellig_am) - heute) / 86400000);
                return tage < 3 ? "rot" : tage < 7 ? "orange" : tage < 14 ? "gelb" : "grau";
              }
              const alter = Math.round((heute - new Date(todo.erstellt_am)) / 86400000);
              return alter >= 15 ? "rot" : alter >= 8 ? "orange" : alter >= 4 ? "gelb" : "grau";
            };
            const sortiert = [...offeneTodos].sort((a,b) =>
              ({rot:0,orange:1,gelb:2,grau:3}[dring(a)]||3) - ({rot:0,orange:1,gelb:2,grau:3}[dring(b)]||3)
            );
            const preview = sortiert.slice(0, 2);
            return (
              <div style={{ flex:"1 1 0", position:"relative", maxWidth:780 }}>
                <button onClick={() => setTodoKlapp(o => !o)}
                  style={{ width:"100%", background:"rgba(255,255,255,0.07)",
                    border:`1px solid ${offeneTodos.length > 0 ? "rgba(160,107,74,0.5)" : "rgba(255,255,255,0.12)"}`,
                    borderRadius:10, padding:"6px 14px", cursor:"pointer",
                    display:"flex", alignItems:"center", gap:10,
                    transition:"all 0.15s", textAlign:"left" }}>
                  <span style={{ fontSize:"0.85rem", flexShrink:0 }}>📋</span>
                  <div style={{ flex:1, minWidth:0 }}>
                    {offeneTodos.length === 0 ? (
                      <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                        color:"rgba(255,255,255,0.4)" }}>Keine To-Do's erfasst</div>
                    ) : (<>
                      {preview.map(t => (
                        <div key={t.id} style={{ display:"flex", alignItems:"center", gap:6,
                          marginBottom: preview.length > 1 ? 2 : 0 }}>
                          <span style={{ width:6, height:6, borderRadius:"50%", flexShrink:0,
                            background:FARBEN_DOT[dring(t)], display:"inline-block" }} />
                          <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                            color:"rgba(255,255,255,0.75)", overflow:"hidden",
                            textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{t.text}</span>
                        </div>
                      ))}
                      {offeneTodos.length > 2 && (
                        <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.72rem",
                          color:"rgba(255,255,255,0.35)", marginTop:1 }}>
                          + {offeneTodos.length - 2} weitere
                        </div>
                      )}
                    </>)}
                  </div>
                  <span style={{ color:T.accent, fontSize:"0.75rem", flexShrink:0,
                    transform: todoKlapp ? "rotate(180deg)" : "none",
                    transition:"transform 0.2s", lineHeight:1 }}>▾</span>
                </button>
                {todoKlapp && (
                  <div onClick={() => setTodoKlapp(false)}
                    style={{ position:"fixed", inset:0, zIndex:199 }} />
                )}
                {todoKlapp && (
                  <div style={{ position:"absolute", top:"calc(100% + 6px)", left:0,
                    width:"100%", background:T.navy, border:`1px solid ${T.accentTrim}`,
                    borderRadius:10, zIndex:200, padding:"10px 14px",
                    boxShadow:"0 8px 32px rgba(0,0,0,0.4)" }}>
                    {sortiert.length === 0 ? (
                      <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.85rem",
                        color:"rgba(255,255,255,0.4)", textAlign:"center", padding:"8px 0" }}>
                        Keine To-Do's erfasst
                      </div>
                    ) : sortiert.map(t => (
                      <div key={t.id} style={{ display:"flex", alignItems:"flex-start", gap:7,
                        padding:"6px 0", borderBottom:"1px solid rgba(255,255,255,0.08)" }}>
                        <button onClick={async () => {
                          try {
                            const r = await apiTodos.update(akte.az, t.id, { erledigt: true });
                            setHeaderTodos(prev => prev.map(x => x.id === t.id ? r.todo : x));
                          } catch {}
                        }} title="Als erledigt markieren"
                          style={{ flexShrink:0, width:16, height:16, borderRadius:"50%",
                            border:`2px solid ${FARBEN_DOT[dring(t)]}`, background:"transparent",
                            cursor:"pointer", marginTop:3, padding:0, transition:"all 0.15s" }}
                          onMouseEnter={e => e.currentTarget.style.background=FARBEN_DOT[dring(t)]}
                          onMouseLeave={e => e.currentTarget.style.background="transparent"} />
                        <div style={{ flex:1, minWidth:0 }}>
                          <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.83rem",
                            color:"rgba(255,255,255,0.85)", lineHeight:1.4 }}>{t.text}</div>
                          {t.faellig_am && (
                            <div style={{ fontSize:"0.72rem", color:"rgba(255,255,255,0.35)",
                              fontFamily:"ui-monospace,monospace", marginTop:1 }}>
                              Fällig: {(() => { try { const [y,m,d]=t.faellig_am.split("-"); return `${d}.${m}.${y}`; } catch{return t.faellig_am;}})()}
                              {t.frist_typ==="verjaehrung" && " ⚠️"}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    <button onClick={() => { setTodoKlapp(false); setSec("todos"); }}
                      style={{ marginTop:8, width:"100%", background:T.accentTrim,
                        border:`1px solid rgba(160,107,74,0.3)`, borderRadius:7,
                        color:T.accent, fontFamily:"'Figtree',sans-serif",
                        fontSize:"0.8rem", padding:"5px 0", cursor:"pointer", fontWeight:600 }}>
                      Alle To-Dos anzeigen →
                    </button>
                  </div>
                )}
              </div>
            );
          })()}

          {/* ── Portal-aktiv Toggle ── */}
          <div style={{ display:"flex", alignItems:"center", gap:8, flexShrink:0 }}>
            <label style={{ display:"flex", alignItems:"center", gap:5, cursor:"pointer" }}>
              <input
                type="checkbox"
                checked={portalAktiv}
                onChange={(e) => handlePortalToggle(e.target.checked)}
                style={{ width:15, height:15, accentColor:T.accent, cursor:"pointer" }}
              />
              <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem",
                color:"rgba(255,255,255,0.55)", letterSpacing:"0.04em" }}>Portal</span>
            </label>
            {akte?.portal_last_sync && (
              <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.7rem",
                color:"rgba(255,255,255,0.35)" }}>
                ↑ {new Date(akte.portal_last_sync).toLocaleString("de-DE", {
                  day:"2-digit", month:"2-digit", hour:"2-digit", minute:"2-digit"
                })}
              </span>
            )}
          </div>

          {/* ── Rechts: KPI rechtsbündig ── */}
          <div style={{ display:"flex", gap:10, background:"rgba(255,255,255,0.05)",
            border:"1px solid rgba(255,255,255,0.1)", borderRadius:10,
            padding:"7px 14px", flexShrink:0, marginLeft:"auto" }}>
            {(() => {
              const gefordert = liveBrutto * ((akte.hq || 100) / 100);
              const reguliert = (st.abrechnungen||[]).reduce((s,ab) => s + (parseFloat(ab.gesamt_reguliert)||0), 0);
              const offen     = Math.max(0, gefordert - reguliert);
              return [
                { l:"Gefordert", v:fmtEuro(gefordert), farbe: gefordert===0?T.green:T.amber, divider:false },
                { l:"Reguliert", v:fmtEuro(reguliert), farbe:T.green,                        divider:true  },
                { l:"Offen",     v:fmtEuro(offen),     farbe: offen===0?T.green:T.red,       divider:true  },
              ].map((s,i) => (
                <React.Fragment key={i}>
                  {s.divider && <div style={{ width:1, background:"rgba(255,255,255,0.12)",
                    alignSelf:"stretch", margin:"2px 6px" }} />}
                  <div style={{ textAlign:"center", padding:"0 6px" }}>
                    <div style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"1.25rem",
                      fontWeight:800, color:s.farbe, lineHeight:1 }}>{s.v}</div>
                    <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.7rem",
                      color:"rgba(255,255,255,0.45)", marginTop:3, letterSpacing:"0.06em",
                      textTransform:"uppercase" }}>{s.l}</div>
                  </div>
                </React.Fragment>
              ));
            })()}
          </div>

        </div>

        <div style={{ display:"flex", overflowX:"auto", scrollbarWidth:"none" }}>
          {tabs.map(t => (
            <button key={t.id} onClick={() => {
              setSec(t.id);
              if (t.id === "dokumente" || t.id === "regulierung") {
                const now = new Date().toISOString();
                const lsTabKey = `tab-letztbesucht-${azKey}-${t.id}`;
                localStorage.setItem(lsTabKey, now);
                if (t.id === "dokumente") setBesuchDok(now);
                if (t.id === "regulierung") setBesuchReg(now);
              }
            }}
              style={{ padding:"9px 17px", background:"transparent", border:"none",
                borderBottom:sec===t.id?`2px solid ${T.accent}`:"2px solid transparent",
                color:sec===t.id?T.white:"rgba(255,255,255,0.48)",
                fontFamily:"'Figtree',sans-serif", fontSize:"0.935rem",
                fontWeight:sec===t.id?700:400, cursor:"pointer",
                transition:"all 0.15s", whiteSpace:"nowrap", flexShrink:0,
                display:"flex", alignItems:"center", gap:5 }}>
              {t.label}
              {t.dot && t.dot !== "⬜" && (
                <span style={{ fontSize:"0.7rem", lineHeight:1 }}>{t.dot}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Section content */}
      <div style={{ flex:1, overflowY:"auto", background:T.offWhite, padding:"1.5rem 1.75rem" }}>
        <div style={{ maxWidth:1200 }}>
          {!aktionErledigt && akte.aktion_erforderlich ? (
            <AktionBadge
              az={akte.az_roh || akte.id}
              aktion={{ aktiv: true, typ: akte.aktion_typ, seit: akte.aktion_seit }}
              onErledigt={() => setAktionErledigt(true)}
            />
          ) : null}
          {/* Synchron: Übersicht + To-Dos */}
          {sec==="uebersicht" && <UebersichtSection akte={akte} st={st} dispatch={dispatch} onNavigate={setSec} />}
          {sec==="todos"      && <TodoSection akteId={akte.id} az={akte.az} onTodoChange={ladeHeaderTodos} />}
          {/* Lazy: alle anderen Sections – werden erst bei erstem Tabwechsel geladen */}
          <Suspense fallback={
            <div style={{ display:"flex", justifyContent:"center", padding:"3rem 0" }}>
              <div style={{ width:28, height:28, border:`2px solid ${T.accentTrim}`, borderTopColor:T.accent, borderRadius:"50%", animation:"spin 0.7s linear infinite" }} />
            </div>
          }>
            {sec==="beteiligte"    && <BeteiligteSection beteiligte={st.beteiligte||[]} dispatch={dispatch} akteId={akte.id} />}
            {sec==="schaden"       && <SchadenSection schaden={st.schaden||{}} hq={akte.hq} dispatch={dispatch} akteId={akte.id} vorsteuer={(st.beteiligte||[]).find(b=>b.rolle==="mandant")?.vorsteuer==="Y"} dokumente={st.dokumente||[]} belegeKandidaten={st.belegeKandidaten||[]} />}
            {sec==="dokumente"     && <DokumenteSection dokumente={st.dokumente||[]} dispatch={dispatch} akteId={akte.id} akte={akte} belegeKandidaten={st.belegeKandidaten||[]} schaden={st.schaden||{}} vorsteuer={(st.beteiligte||[]).find(b=>b.rolle==="mandant")?.vorsteuer==="Y"} />}
            {sec==="regulierung"   && <RegulierungSection brutto={st.schaden?.gesamt_brutto ?? liveBrutto} hq={akte.hq} dispatch={dispatch} akteId={akte.id} schaden={st.schaden||{}} abrechnungenCached={st.abrechnungen||[]} beteiligte={st.beteiligte||[]} dokumente={st.dokumente||[]} />}
            {sec==="gebuehren"     && <GebuehrenSection akteId={akte.id} akte={akte} />}
            {sec==="klage"         && <KlageSection akteId={akte.id} akte={akte} st={st} dispatch={dispatch} />}
            {sec==="word"          && <WordSection akte={akte} st={st} dispatch={dispatch} />}
            {sec==="unfalldetails" && <UnfalldetailsSection akteId={akte.id} />}
          </Suspense>
        </div>
      </div>
    </div>
    {toast && <Toast msg={toast} onDone={() => setToast("")} />}
    </>
  );
}



export default AkteDetailView;
