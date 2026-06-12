import React, { useState, useEffect, useCallback, useRef } from "react";
import T from "../../config/theme.js";
import Ic from "../../config/icons.jsx";
import { IMAP_CONFIG, IMPORT_STEPS, normalisiereLogEintrag } from "../../config/constants.js";
import { Card, Toast } from "../../components/common.jsx";
import { emailImport as apiEmail, request } from "../../api.js";
import ImapKonfigDialog from "./components/ImapKonfigDialog.jsx";
import FragebogenErstkontaktKarte from "./components/FragebogenErstkontaktKarte.jsx";
import EmailKarte from "./components/EmailKarte.jsx";
import EmailDetailView from "./EmailDetailView.jsx";


const STREAM_CHIPS = [
  { id:"alle",         label:"Alle"         },
  { id:"versicherung", label:"Versicherung" },
  { id:"gutachter",    label:"Gutachter"    },
  { id:"gericht",      label:"Gericht"      },
  { id:"sonstiges",    label:"Sonstiges"    },
];

function gruppiereNachZeit(emails) {
  const heute   = new Date(); heute.setHours(0, 0, 0, 0);
  const gestern = new Date(heute); gestern.setDate(gestern.getDate() - 1);
  const woche   = new Date(heute); woche.setDate(woche.getDate() - 6);

  const gruppen = [
    { label:"Heute",       emails:[] },
    { label:"Gestern",     emails:[] },
    { label:"Diese Woche", emails:[] },
    { label:"Älter",       emails:[] },
  ];

  for (const e of emails) {
    const d = new Date(e.empfangen_am || 0); d.setHours(0, 0, 0, 0);
    if      (d >= heute)   gruppen[0].emails.push(e);
    else if (d >= gestern) gruppen[1].emails.push(e);
    else if (d >= woche)   gruppen[2].emails.push(e);
    else                   gruppen[3].emails.push(e);
  }
  return gruppen.filter(g => g.emails.length > 0);
}


// ══════════════════════════════════════════════════════════════
//  unfall@ – Hauptview (PRD-22d)
//  Wird in EmailImportView.jsx als Tab gerendert.
// ══════════════════════════════════════════════════════════════

function UnfallEmailView({ onOpenAkte, dispatch, initialEmailId }) {
  const [log, setLog]               = useState([]);
  const [importing, setImporting]   = useState(false);
  const [importStep, setStep]       = useState(-1);
  const [importResult, setResult]   = useState(null);
  const [toast, setToast]           = useState("");
  const [imapCfg, setImapCfg]       = useState(null);
  const [cfgStatus, setCfgStatus]   = useState(null);
  const [showKonfigDialog, setShowKonfigDialog] = useState(false);

  const [zuordnungState, setZuordnungState] = useState({});
  const [fragebogenListe, setFragebogenListe] = useState([]);
  const [streamFilter,   setStreamFilter]   = useState("alle");
  const [streamSuche,    setStreamSuche]    = useState("");
  const [ansichtsModus,  setAnsichtsModus]  = useState("stream");
  const [laedt,          setLaedt]          = useState(true);
  const [geoeffneteEmail, setGeoeffneteEmail] = useState(null);
  const letzteInitialId = useRef(null);

  const onInAkteImportiert = useCallback((logId, res) => {
    setLog(prev => prev.map(e => e.id === logId
      ? { ...e, in_akte_importiert: 1, in_akte_importiert_am: res?.importiert_am }
      : e
    ));
    setGeoeffneteEmail(prev => prev?.id === logId
      ? { ...prev, in_akte_importiert: 1, in_akte_importiert_am: res?.importiert_am }
      : prev
    );
    const eintrag = log.find(e => e.id === logId);
    const akteRaw = eintrag?.akte_az || eintrag?.akte_id;
    const akteId  = akteRaw ? akteRaw.replace(/[A-Z]{2,3}$/i, "").trim() : null;
    if (akteId && dispatch) {
      request(`/akten/${akteId}`)
        .then(data => {
          if (data?.dokumente) {
            dispatch({ type: "SET_DOKUMENTE", akteId, dokumente: data.dokumente });
          }
        })
        .catch(() => {});
    }
  }, [log, dispatch]);

  useEffect(() => {
    apiEmail.status()
      .then(d => { setCfgStatus(d); if (d?.konfiguration) setImapCfg(d.konfiguration); })
      .catch(() => {});
    apiEmail.log({ limit: 200 })
      .then(d => { if (d?.log) setLog(d.log.map(normalisiereLogEintrag)); })
      .catch(() => {})
      .finally(() => setLaedt(false));
    apiEmail.fragebogenErstkontakt({ status: "neu" })
      .then(d => { if (d?.eintraege) setFragebogenListe(d.eintraege); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!initialEmailId || initialEmailId === letzteInitialId.current) return;
    if (log.length === 0) return;
    const entry = log.find(e => e.id === initialEmailId);
    if (entry) {
      setGeoeffneteEmail(entry);
      letzteInitialId.current = initialEmailId;
    }
  }, [initialEmailId, log]);

  const angezeigteKfg = imapCfg ?? IMAP_CONFIG;
  const verbunden     = cfgStatus?.verbindung_ok ?? false;

  const zugeordnet            = log.filter(e => e.status === "zugeordnet");
  const nichtZugeordnet       = log.filter(e => e.status !== "zugeordnet");
  const aktionNichtZugeordnet = log.filter(e => e.status === "nicht_zugeordnet" && e.email_typ !== "fragebogen");

  const streamEmails = log
    .filter(e => streamFilter === "alle" || e.absender_kategorie === streamFilter)
    .filter(e => {
      if (!streamSuche) return true;
      const q = streamSuche.toLowerCase();
      return (e.betreff   || "").toLowerCase().includes(q)
          || (e.absender  || "").toLowerCase().includes(q)
          || (e.von_name  || "").toLowerCase().includes(q)
          || (e.akte_az   || "").toLowerCase().includes(q);
    });

  const startImport = async () => {
    if (importing) return;
    setImporting(true); setResult(null); setStep(0);
    let step = 0;
    const tick = () => new Promise(r => {
      step++;
      setStep(step < IMPORT_STEPS.length ? step : step);
      setTimeout(r, 400 + Math.random() * 160);
    });
    const animPromise = (async () => { for (let i = 0; i < IMPORT_STEPS.length; i++) await tick(); })();
    const apiPromise  = apiEmail.starten();
    let res = null;
    let importFehler = null;
    try {
      [, res] = await Promise.all([animPromise, apiPromise]);
    } catch (err) {
      await animPromise.catch(() => {});
      importFehler = err?.message || "Import fehlgeschlagen";
    }

    if (res?.details) {
      const gueltig = res.details.filter(e => e.betreff);
      setResult({ neu: gueltig.length, zugeordnet: res.verarbeitet ?? 0, anhaenge: res.anhaenge ?? 0 });
      setToast(`Import: ${gueltig.length} neue E-Mail(s).`);
      apiEmail.log({ limit: 200 })
        .then(d => { if (d?.log) setLog(d.log.map(normalisiereLogEintrag)); })
        .catch(() => {});
      apiEmail.fragebogenErstkontakt({ status: "neu" })
        .then(d => { if (d?.eintraege) setFragebogenListe(d.eintraege); })
        .catch(() => {});
    } else {
      setToast(importFehler
        ? `Import fehlgeschlagen: ${importFehler}`
        : "Import fehlgeschlagen. Bitte IMAP-Konfiguration prüfen."
      );
    }
    setImporting(false); setStep(-1);
  };

  const oeffneZuordnung = (id) => setZuordnungState(prev => ({
    ...prev,
    [id]: { offen: true, suche: "", treffer: [], laedt: false }
  }));

  const schliessZuordnung = (id) => setZuordnungState(prev => ({
    ...prev, [id]: { ...prev[id], offen: false }
  }));

  const sucheAkten = async (id, q) => {
    setZuordnungState(prev => ({ ...prev, [id]: { ...prev[id], suche: q, laedt: true } }));
    if (q.length < 2) {
      setZuordnungState(prev => ({ ...prev, [id]: { ...prev[id], treffer: [], laedt: false } }));
      return;
    }
    try {
      const res = await apiEmail.aktensuche(q);
      setZuordnungState(prev => ({ ...prev, [id]: { ...prev[id], treffer: res?.akten || [], laedt: false } }));
    } catch {
      setZuordnungState(prev => ({ ...prev, [id]: { ...prev[id], treffer: [], laedt: false } }));
    }
  };

  const fuehreZuordnungDurch = async (logEntry, az) => {
    try {
      await apiEmail.zuordnen(logEntry.id, az);
      setLog(prev => prev.map(e => e.id === logEntry.id
        ? { ...e, akte_id: az, akte_az: az, status: "zugeordnet" }
        : e
      ));
      schliessZuordnung(logEntry.id);
      setToast(`E-Mail „${(logEntry.betreff || "").slice(0, 40)}…" → Akte ${az} zugeordnet.`);
    } catch {
      setLog(prev => prev.map(e => e.id === logEntry.id
        ? { ...e, akte_id: az, akte_az: az, status: "zugeordnet" }
        : e
      ));
      schliessZuordnung(logEntry.id);
      setToast(`Akte ${az} zugeordnet (Demo-Modus).`);
    }
  };

  const handleOpenAkte = (entry) => {
    if (!entry.akte_az) return;
    onOpenAkte({ az: entry.akte_az, id: entry.akte_az, az_roh: entry.akte_az,
                 brutto: 0, hq: 100, unfalldatum: "", unfallort: "" });
  };

  const handleOpenEmail = useCallback((entry) => {
    setGeoeffneteEmail(entry);
  }, []);

  const handleEmailZurueck = useCallback(() => {
    setGeoeffneteEmail(null);
  }, []);

  const fragebogenAlsBearbeitet = async (id) => {
    try {
      await apiEmail.fragebogenErstkontaktStatus(id, "bearbeitet");
      setFragebogenListe(prev => prev.filter(e => e.id !== id));
      setToast("Fragebogen als bearbeitet markiert.");
    } catch {
      setToast("Fehler beim Aktualisieren des Status.");
    }
  };

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")}/>}

      {geoeffneteEmail ? (
        <EmailDetailView
          entry={geoeffneteEmail}
          onBack={handleEmailZurueck}
          onOpenAkte={handleOpenAkte}
          onInAkteImportiert={onInAkteImportiert}
        />
      ) : (
        <>
      {/* Aktionszeile: Verbindungsstatus + Import-Button */}
      <div style={{ display:"flex", gap:10, alignItems:"center", justifyContent:"flex-end", marginBottom:"1.25rem", flexWrap:"wrap" }}>
        <div onClick={() => setShowKonfigDialog(true)}
          style={{ display:"flex", alignItems:"center", gap:7, background:T.white, border:`1px solid ${T.border}`,
            borderRadius:8, padding:"7px 13px", fontFamily:"'Figtree',sans-serif",
            fontSize:"0.925rem", color:T.textMid, cursor:"pointer" }}>
          <span style={{ width:8, height:8, borderRadius:"50%", background: verbunden ? T.green : T.amber, display:"block",
            boxShadow: verbunden ? `0 0 0 3px ${T.green}22` : `0 0 0 3px ${T.amber}22` }}/>
          {verbunden ? `Verbunden · ${angezeigteKfg.host}` : "Nicht konfiguriert"}
          <span style={{ color:T.textMuted, fontSize:"0.8rem" }}>· Einstellungen</span>
        </div>
        <button onClick={startImport} disabled={importing}
          style={{ display:"flex", alignItems:"center", gap:8, padding:"9px 20px",
            background: importing ? T.navyMid : T.navy, color:T.white, border:"none",
            borderRadius:8, fontFamily:"'Figtree',sans-serif", fontSize:"0.975rem",
            fontWeight:600, cursor: importing ? "default" : "pointer",
            position:"relative", overflow:"hidden", minWidth:210 }}>
          {importing
            ? <><div style={{ width:14, height:14, border:"2px solid rgba(255,255,255,0.3)",
                borderTopColor:"white", borderRadius:"50%", animation:"spin 0.7s linear infinite" }}/>
                {IMPORT_STEPS[importStep] || "…"}</>
            : <>{Ic.refresh} Jetzt importieren</>}
          <div style={{ position:"absolute", bottom:0, left:0, right:0, height:2,
            background:`linear-gradient(90deg,${T.accent},${T.accentLight})` }}/>
        </button>
      </div>

      {/* Result-Banner */}
      {importResult && (
        <div style={{ background:T.greenBg, border:`1px solid ${T.green}33`, borderRadius:10,
          padding:"11px 16px", marginBottom:"1.1rem", display:"flex", alignItems:"center",
          gap:12, fontFamily:"'Figtree',sans-serif", fontSize:"0.955rem", color:T.green }}>
          {Ic.check}
          <span><strong>{importResult.neu} neue E-Mails</strong> · {importResult.zugeordnet} zugeordnet · {importResult.anhaenge} Anhang</span>
          <button onClick={() => setResult(null)} aria-label="Meldung schließen" style={{ marginLeft:"auto", background:"none", border:"none", cursor:"pointer", color:T.green, display:"flex" }}>{Ic.x}</button>
        </div>
      )}

      {/* KPI-Leiste */}
      <div style={{ display:"flex", gap:"0.75rem", marginBottom:"1.25rem", flexWrap:"wrap" }}>
        {[
          { label:"Gesamt",           v: log.length,             c: T.navy  },
          { label:"Zugeordnet",       v: zugeordnet.length,      c: T.green },
          { label:"Nicht zugeordnet", v: nichtZugeordnet.length, c: T.amber },
          { label:"Anhänge",          v: log.reduce((s,e) => s + (e.anhaenge_anzahl||0), 0), c: T.blue },
        ].map((k,i) => (
          <div key={i} style={{ background:k.c + "0d", borderRadius:10, padding:"0.75rem 1.1rem",
            border:`1.5px solid ${k.c}30`, minWidth:120 }}>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.75rem", fontWeight:700,
              letterSpacing:"0.1em", textTransform:"uppercase", color:k.c, marginBottom:5, opacity:0.8 }}>{k.label}</div>
            <div style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"2rem",
              fontWeight:800, color:k.c, lineHeight:1 }}>{k.v}</div>
          </div>
        ))}
      </div>

      {/* Aktionspflichtig-Block (PRD-22d Session 2) */}
      {(aktionNichtZugeordnet.length > 0 || fragebogenListe.length > 0) && (
        <div style={{
          marginBottom:"1.5rem",
          border:`1.5px solid ${T.amber}55`,
          borderRadius:12,
          overflow:"hidden",
        }}>
          {/* Block-Header */}
          <div style={{
            background:`linear-gradient(135deg, ${T.amberBg}, #fff8e7)`,
            borderBottom:`1px solid ${T.amber}33`,
            padding:"0.75rem 1.25rem",
            display:"flex", alignItems:"center", gap:10,
          }}>
            <span style={{
              width:9, height:9, borderRadius:"50%", background:T.amber,
              display:"block", boxShadow:`0 0 0 3px ${T.amber}33`, flexShrink:0,
            }}/>
            <span style={{
              fontFamily:"'Figtree',sans-serif", fontSize:"0.84rem",
              fontWeight:700, color:T.amber,
              textTransform:"uppercase", letterSpacing:"0.08em",
            }}>Aktionspflichtig</span>
            <span style={{
              background:T.amber, color:T.white, borderRadius:10,
              padding:"1px 8px", fontSize:"0.775rem", fontWeight:700,
              fontFamily:"ui-monospace,monospace",
            }}>
              {aktionNichtZugeordnet.length + fragebogenListe.length}
            </span>
          </div>

          {/* Zwei-Spalten-Inhalt */}
          <div style={{
            display:"grid", gridTemplateColumns:"1fr 1fr", gap:0,
            background:T.offWhite,
          }}>
            {/* Links: Nicht zugeordnete E-Mails */}
            <div style={{
              padding:"1rem 1.1rem",
              borderRight:`1px solid ${T.border}`,
            }}>
              <div style={{ display:"flex", alignItems:"center", gap:6, marginBottom:"0.65rem" }}>
                <span style={{
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                  fontWeight:700, color:T.textMid,
                  textTransform:"uppercase", letterSpacing:"0.07em",
                }}>Nicht zugeordnet</span>
                <span style={{
                  background:T.amberBg, color:T.amber, border:`1px solid ${T.amber}33`,
                  borderRadius:10, padding:"1px 7px",
                  fontSize:"0.775rem", fontWeight:600, fontFamily:"ui-monospace,monospace",
                }}>{aktionNichtZugeordnet.length}</span>
              </div>
              {aktionNichtZugeordnet.length === 0 ? (
                <div style={{
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.9rem",
                  color:T.textMuted, padding:"1.5rem", textAlign:"center",
                  background:T.white, border:`1px solid ${T.border}`, borderRadius:8,
                }}>
                  Alle E-Mails zugeordnet ✓
                </div>
              ) : (
                <div>
                  {aktionNichtZugeordnet.map((e, i) => (
                    <EmailKarte
                      key={e.id ?? i}
                      entry={e}
                      seite="nicht_zugeordnet"
                      onOpenAkte={handleOpenAkte}
                      onOpenEmail={handleOpenEmail}
                      zuordnungState={zuordnungState[e.id]}
                      onOeffneZuordnung={oeffneZuordnung}
                      onSchliessZuordnung={schliessZuordnung}
                      onSucheAkten={sucheAkten}
                      onZuordnen={fuehreZuordnungDurch}
                      onInAkteImportiert={onInAkteImportiert}
                      letzter={i === aktionNichtZugeordnet.length - 1}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Rechts: Fragebogen-Erstkontakte */}
            <div style={{ padding:"1rem 1.1rem" }}>
              <div style={{ display:"flex", alignItems:"center", gap:6, marginBottom:"0.65rem" }}>
                <span style={{
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                  fontWeight:700, color:T.textMid,
                  textTransform:"uppercase", letterSpacing:"0.07em",
                }}>Fragebogen-Erstkontakt</span>
                <span style={{
                  background:T.amberBg, color:T.amber, border:`1px solid ${T.amber}33`,
                  borderRadius:10, padding:"1px 7px",
                  fontSize:"0.775rem", fontWeight:600, fontFamily:"ui-monospace,monospace",
                }}>{fragebogenListe.length}</span>
              </div>
              {fragebogenListe.length === 0 ? (
                <div style={{
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.9rem",
                  color:T.textMuted, padding:"1.5rem", textAlign:"center",
                  background:T.white, border:`1px solid ${T.border}`, borderRadius:8,
                }}>
                  Keine neuen Fragebogen ✓
                </div>
              ) : (
                <div>
                  {fragebogenListe.map(e => (
                    <FragebogenErstkontaktKarte
                      key={e.id}
                      eintrag={e}
                      onAlsBearbeitet={fragebogenAlsBearbeitet}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* E-Mail-Stream + AktenAnsicht (PRD-22d Session 3+4) */}
      <div>
        {/* Header: Titel + Zähler + Ansichts-Umschalter + Filter-Chips + Suche */}
        <div style={{
          display:"flex", alignItems:"center", gap:"0.6rem",
          marginBottom:"1rem", flexWrap:"wrap",
        }}>
          <h2 style={{
            fontFamily:"'Figtree',sans-serif", fontSize:"1rem",
            fontWeight:700, color:T.navy, margin:0,
          }}>
            {ansichtsModus === "stream" ? "E-Mail-Stream" : "Akten-Ansicht"}
          </h2>
          {ansichtsModus === "stream" && (
            <span style={{
              background:T.white, border:`1px solid ${T.border}`,
              color:T.textMuted, borderRadius:12, padding:"1px 9px",
              fontSize:"0.845rem", fontWeight:600,
            }}>{streamEmails.length}</span>
          )}

          {/* Ansichts-Umschalter */}
          <div style={{
            display:"flex", background:T.offWhite,
            border:`1px solid ${T.border}`, borderRadius:20,
            padding:2, gap:0, flexShrink:0,
          }}>
            {[
              { id:"stream", label:"Stream" },
              { id:"akten",  label:"Akten"  },
            ].map(m => (
              <button key={m.id} onClick={() => setAnsichtsModus(m.id)}
                title={m.id === "akten" ? "Akten-Ansicht – geplant in PRD-22d" : undefined}
                style={{
                  padding:"4px 14px",
                  background: ansichtsModus === m.id ? T.navy : "none",
                  border:"none", borderRadius:18,
                  fontFamily:"ui-monospace,monospace",
                  fontSize:"0.83rem",
                  fontWeight: ansichtsModus === m.id ? 700 : 400,
                  color: ansichtsModus === m.id ? T.white : T.textMuted,
                  cursor:"pointer",
                }}>
                {m.label}
              </button>
            ))}
          </div>

          {/* Filter-Chips (nur im Stream-Modus) */}
          {ansichtsModus === "stream" && (
            <div style={{ display:"flex", gap:5, flexWrap:"wrap" }}>
              {STREAM_CHIPS.map(chip => {
                const aktiv = streamFilter === chip.id;
                return (
                  <button key={chip.id} onClick={() => setStreamFilter(chip.id)}
                    style={{
                      padding:"4px 13px",
                      background: aktiv ? T.navy : T.white,
                      border:`1px solid ${aktiv ? T.navy : T.border}`,
                      borderRadius:20,
                      fontFamily:"'Figtree',sans-serif",
                      fontSize:"0.845rem", fontWeight: aktiv ? 600 : 400,
                      color: aktiv ? T.white : T.textMid,
                      cursor:"pointer",
                      transition:"background 0.15s, color 0.15s, border-color 0.15s",
                    }}>
                    {chip.label}
                  </button>
                );
              })}
            </div>
          )}

          {/* Suche (nur im Stream-Modus) */}
          {ansichtsModus === "stream" && (
            <div style={{ marginLeft:"auto", position:"relative", minWidth:230 }}>
              <span style={{
                position:"absolute", left:9, top:"50%", transform:"translateY(-50%)",
                color:T.textFaint, display:"flex", pointerEvents:"none",
              }}>{Ic.search}</span>
              <input
                value={streamSuche}
                onChange={ev => setStreamSuche(ev.target.value)}
                placeholder="Betreff, Absender, AZ …"
                aria-label="E-Mails durchsuchen"
                style={{
                  width:"100%", padding:"7px 30px 7px 30px",
                  border:`1.5px solid ${streamSuche ? T.navy : T.border}`,
                  borderRadius:8, outline:"none",
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.895rem",
                  color:T.text, background:T.white, boxSizing:"border-box",
                }}
              />
              {streamSuche && (
                <button onClick={() => setStreamSuche("")}
                  aria-label="Suche zurücksetzen"
                  style={{
                    position:"absolute", right:7, top:"50%", transform:"translateY(-50%)",
                    background:"none", border:"none", cursor:"pointer",
                    color:T.textFaint, display:"flex", padding:2,
                  }}>{Ic.x}</button>
              )}
            </div>
          )}
        </div>

        {/* Zeitgruppierte E-Mails */}
        {laedt ? (
          /* Skeleton-Platzhalter während Datenabruf */
          <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
            {[1,2,3].map(i => (
              <div key={i} style={{
                background:T.white, border:`1px solid ${T.border}`,
                borderRadius:9, padding:"1rem 1.1rem",
                animation:"pulse 1.4s ease-in-out infinite",
              }}>
                <div style={{ display:"flex", gap:10, marginBottom:10, alignItems:"center" }}>
                  <div style={{ width:32, height:32, borderRadius:"50%", background:T.offWhite }}/>
                  <div style={{ flex:1 }}>
                    <div style={{ height:12, borderRadius:4, background:T.offWhite, marginBottom:6, width:"45%" }}/>
                    <div style={{ height:10, borderRadius:4, background:T.offWhite, width:"30%" }}/>
                  </div>
                  <div style={{ height:10, borderRadius:4, background:T.offWhite, width:60 }}/>
                </div>
                <div style={{ height:11, borderRadius:4, background:T.offWhite, width:"80%" }}/>
              </div>
            ))}
            <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }`}</style>
          </div>
        ) : ansichtsModus === "akten" ? (
          /* AktenAnsicht-Stub (PRD-22d Session 4) */
          <div style={{
            background:T.white, border:`1px solid ${T.border}`, borderRadius:12,
            padding:"3rem 2rem", textAlign:"center",
            boxShadow:"0 2px 8px rgba(0,0,0,0.04)",
          }}>
            <div style={{ color:T.navy, opacity:0.35, marginBottom:"0.75rem", display:"flex", justifyContent:"center" }}>
              <svg viewBox="0 0 24 24" fill="currentColor" style={{width:40,height:40}}><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
            </div>
            <h3 style={{
              fontFamily:"'Bricolage Grotesque',sans-serif",
              fontSize:"1.2rem", fontWeight:700,
              color:T.navy, margin:"0 0 0.5rem",
            }}>Akten-Ansicht</h3>
            <p style={{
              fontFamily:"'Figtree',sans-serif",
              fontSize:"0.955rem", color:T.textMuted,
              lineHeight:1.6, maxWidth:460, margin:"0 auto 1.25rem",
            }}>
              E-Mails gruppiert nach Aktenzeichen – für eine schnelle Übersicht
              aller Posteingänge je Mandat.
            </p>
            <div style={{
              background:T.offWhite, border:`1px solid ${T.border}`,
              borderRadius:8, padding:"1rem 1.25rem",
              textAlign:"left", maxWidth:380, margin:"0 auto",
            }}>
              <div style={{
                fontFamily:"'Figtree',sans-serif",
                fontSize:"0.8rem", fontWeight:600,
                letterSpacing:"0.07em", textTransform:"uppercase",
                color:T.textMuted, marginBottom:"0.6rem",
              }}>Geplante Funktionen</div>
              {[
                "E-Mails nach Aktenzeichen gruppiert",
                "Anzahl ungelesener E-Mails pro Akte",
                "Direktlink zur Akte",
                "Letzte Aktivität je Akte",
              ].map((f, i) => (
                <div key={i} style={{
                  display:"flex", gap:8, alignItems:"flex-start",
                  fontFamily:"'Figtree',sans-serif",
                  fontSize:"0.9rem", color:T.textMid, marginBottom:"0.4rem",
                }}>
                  <span style={{ color:T.textFaint, flexShrink:0 }}>·</span>
                  {f}
                </div>
              ))}
            </div>
          </div>
        ) : streamEmails.length === 0 ? (
          <div style={{
            background:T.white, border:`1px solid ${T.border}`, borderRadius:10,
            padding:"3rem", textAlign:"center",
            fontFamily:"'Figtree',sans-serif", fontSize:"0.955rem", color:T.textMuted,
          }}>
            {streamSuche
              ? `Keine Ergebnisse für „${streamSuche}"`
              : streamFilter !== "alle"
                ? `Keine E-Mails der Kategorie „${STREAM_CHIPS.find(c => c.id === streamFilter)?.label}"`
                : "Noch keine E-Mails importiert"}
          </div>
        ) : (
          gruppiereNachZeit(streamEmails).map(gruppe => (
            <div key={gruppe.label} style={{ marginBottom:"1.25rem" }}>
              <div style={{
                display:"flex", alignItems:"center", gap:10, marginBottom:"0.55rem",
              }}>
                <span style={{
                  fontFamily:"ui-monospace,monospace", fontSize:"0.775rem",
                  fontWeight:700, color:T.textMuted,
                  letterSpacing:"0.08em", textTransform:"uppercase",
                  flexShrink:0,
                }}>{gruppe.label}</span>
                <div style={{ flex:1, height:1, background:T.border }}/>
                <span style={{
                  fontFamily:"ui-monospace,monospace", fontSize:"0.77rem",
                  color:T.textMuted, flexShrink:0,
                }}>{gruppe.emails.length}</span>
              </div>
              <Card>
                {gruppe.emails.map((e, i) => (
                  <EmailKarte
                    key={e.id ?? i}
                    entry={e}
                    seite={e.status === "zugeordnet" ? "zugeordnet" : "nicht_zugeordnet"}
                    onOpenAkte={handleOpenAkte}
                    onOpenEmail={handleOpenEmail}
                    zuordnungState={zuordnungState[e.id]}
                    onOeffneZuordnung={oeffneZuordnung}
                    onSchliessZuordnung={schliessZuordnung}
                    onSucheAkten={sucheAkten}
                    onZuordnen={fuehreZuordnungDurch}
                    onInAkteImportiert={onInAkteImportiert}
                    letzter={i === gruppe.emails.length - 1}
                  />
                ))}
              </Card>
            </div>
          ))
        )}
      </div>

      {/* IMAP-Konfigurationsdialog */}
      {showKonfigDialog && (
        <ImapKonfigDialog
          cfg={angezeigteKfg}
          onClose={() => setShowKonfigDialog(false)}
          onGespeichert={(neueCfg) => {
            setImapCfg(neueCfg);
            setShowKonfigDialog(false);
            setToast("Konfiguration gespeichert. Bitte Server neu starten.");
          }}
        />
      )}
        </>
      )}
    </>
  );
}

export default UnfallEmailView;
