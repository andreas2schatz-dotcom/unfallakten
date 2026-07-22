import React, { useState, useEffect, useCallback } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { Toast } from "../components/common.jsx";
import {
  wiedervorlage as apiWV,
} from "../api.js";

function WiedervorlageView({ onOpenAkte }) {
  const [wvListe,       setWvListe]       = useState(null);
  const [wvSeite,       setWvSeite]       = useState(1);
  const WV_SEITE_GROESSE = 50;
  const [bereitsErstellt, setBereitsErstellt] = useState(new Set());
  const [ramicroStatus, setRamicroStatus] = useState(null);
  const [loading,       setLoading]       = useState(true);
  const [fehler,        setFehler]        = useState(null);
  const [filterHeute,   setFilterHeute]   = useState(false);
  const [filterAlleWv,  setFilterAlleWv]  = useState(false);
  const [filterSb,      setFilterSb]      = useState("");
  const [filterGrund,   setFilterGrund]   = useState("");
  const [ausgewaehlt,   setAusgewaehlt]   = useState(new Set());
  const [batchLaeuft,   setBatchLaeuft]   = useState(false);
  const [batchFortschritt, setBatchFortschritt] = useState({ aktuell: 0, gesamt: 0 });
  const [einzelnLaedt,  setEinzelnLaedt]  = useState(new Set());
  const [toast,         setToast]         = useState("");
  const [adressatenMap, setAdressatenMap] = useState({});        // guid → [{adress_nr, name, ort, kennzeichen}]
  const [adressWahl,    setAdressWahl]    = useState({});        // guid → adress_nr (null = Fallback)
  const [beteiligteLoading, setBeteiligteLoading] = useState(new Set());

  const zeigeToast = (msg) => { setToast(msg); setTimeout(() => setToast(""), 3500); };

  const lade = useCallback(async () => {
    setLoading(true); setFehler(null);
    try {
      const [statusRes, listeRes, bereitsRes] = await Promise.allSettled([
        apiWV.status(),
        apiWV.liste({ nurHeute: filterHeute && !filterAlleWv, nurStellungnahme: !filterAlleWv, sb: filterSb || null, grund: filterGrund || null }),
        apiWV.bereitsErstellt(),
      ]);
      if (statusRes.status === "fulfilled") setRamicroStatus(statusRes.value);
      if (listeRes.status   === "fulfilled") setWvListe(listeRes.value?.wiedervorlagen || []);
      else setFehler(listeRes.reason?.message || "RA-Micro nicht erreichbar");
      if (bereitsRes.status === "fulfilled")
        setBereitsErstellt(new Set(bereitsRes.value?.aktenzeichen || []));
    } catch (e) {
      setFehler(e.message || "Unbekannter Fehler");
    } finally {
      setLoading(false);
    }
  }, [filterHeute, filterAlleWv, filterSb, filterGrund]);

  // Seite zurücksetzen wenn Filter sich ändert
  useEffect(() => { setWvSeite(1); }, [filterHeute, filterAlleWv, filterSb, filterGrund]);

  useEffect(() => { lade(); }, [lade]);

  // ── Auswahl-Logik ─────────────────────────────────────────────────────────
  const alleIds       = (wvListe || []).map(w => w.guid);
  const alleAusgewaehlt = alleIds.length > 0 && alleIds.every(id => ausgewaehlt.has(id));
  const toggleAlle    = () => setAusgewaehlt(alleAusgewaehlt ? new Set() : new Set(alleIds));
  const toggleEinen   = (id) => setAusgewaehlt(prev => {
    const n = new Set(prev);
    n.has(id) ? n.delete(id) : n.add(id);
    return n;
  });

  // ── Einzelner Download ────────────────────────────────────────────────────
  const einzelnGenerieren = async (wv) => {
    setEinzelnLaedt(p => new Set(p).add(wv.guid));
    const adressNr = adressWahl[wv.guid] ?? null;
    try {
      await apiWV.sachstandsanfrage(wv.guid, wv.aktenzeichen, adressNr);
      setBereitsErstellt(p => new Set(p).add(wv.aktenzeichen));
      zeigeToast(`✓ ${wv.aktenzeichen} – Sachstandsanfrage heruntergeladen`);
    } catch (e) {
      zeigeToast(`Fehler bei ${wv.aktenzeichen}: ${e.message}`);
    } finally {
      setEinzelnLaedt(p => { const n = new Set(p); n.delete(wv.guid); return n; });
    }
  };

  // ── Beteiligte lazy laden ────────────────────────────────────────────────
  const ladeBeteiligte = async (guid, grund = "", bezeichnung = "", referat = 0) => {
    if (adressatenMap[guid] || beteiligteLoading.has(guid)) return;
    setBeteiligteLoading(p => new Set(p).add(guid));
    try {
      const res = await apiWV.beteiligte(guid, { grund, bezeichnung, referat });
      const liste = res?.beteiligte || [];
      setAdressatenMap(prev => ({ ...prev, [guid]: liste }));
      // Vorauswahl nur setzen wenn der Nutzer noch nichts manuell gewählt hat
      if (res?.vorauswahl_adress_nr != null) {
        setAdressWahl(prev => ({
          ...prev,
          [guid]: prev[guid] !== undefined ? prev[guid] : res.vorauswahl_adress_nr,
        }));
      }
    } catch (e) {
      setAdressatenMap(prev => ({ ...prev, [guid]: [] }));
    } finally {
      setBeteiligteLoading(p => { const n = new Set(p); n.delete(guid); return n; });
    }
  };

  // ── Batch: einzeln nacheinander ───────────────────────────────────────────
  const batchEinzeln = async () => {
    const liste = (wvListe || []).filter(w => ausgewaehlt.has(w.guid));
    setBatchLaeuft(true);
    setBatchFortschritt({ aktuell: 0, gesamt: liste.length });
    let ok = 0;
    for (let i = 0; i < liste.length; i++) {
      setBatchFortschritt({ aktuell: i + 1, gesamt: liste.length });
      try {
        await apiWV.sachstandsanfrage(liste[i].guid, liste[i].aktenzeichen);
        setBereitsErstellt(p => new Set(p).add(liste[i].aktenzeichen));
        ok++;
        await new Promise(r => setTimeout(r, 350)); // kurze Pause zwischen Downloads
      } catch (e) {
        // Einzelfehler im Batch still ignorieren; Gesamtergebnis im Toast
      }
    }
    setBatchLaeuft(false);
    zeigeToast(`${ok} von ${liste.length} Sachstandsanfragen heruntergeladen`);
  };

  // ── Batch: als ZIP ────────────────────────────────────────────────────────
  const batchZip = async () => {
    const guids = [...ausgewaehlt];
    setBatchLaeuft(true);
    try {
      await apiWV.batchZip(guids);
      const neueAz = (wvListe || [])
        .filter(w => ausgewaehlt.has(w.guid))
        .map(w => w.aktenzeichen);
      setBereitsErstellt(p => new Set([...p, ...neueAz]));
      zeigeToast(`${guids.length} Sachstandsanfragen als ZIP heruntergeladen`);
    } catch (e) {
      zeigeToast(`ZIP-Fehler: ${e.message}`);
    } finally {
      setBatchLaeuft(false);
    }
  };

  // ── Sachbearbeiter-Liste für Filter ──────────────────────────────────────
  const sbListe    = [...new Set((wvListe || []).map(w => w.sachbearbeiter).filter(Boolean))].sort();
  const grundListe = [...new Set((wvListe || []).map(w => w.grund).filter(Boolean))].sort();

  // ── Marker-Komponente ─────────────────────────────────────────────────────
  const Marker = ({ erstellt }) => erstellt
    ? <span title="Sachstandsanfrage bereits erstellt" style={{
        display:"inline-flex", alignItems:"center", gap:4,
        background:"#d1fae5", color:T.greenText,
        border:"1.5px solid #6ee7b7",
        borderRadius:20, padding:"3px 10px 3px 7px",
        fontFamily:T.fontBody, fontSize:"0.8rem", fontWeight:600,
        whiteSpace:"nowrap",
      }}>
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <circle cx="6.5" cy="6.5" r="6.5" fill={T.green}/>
          <path d="M3.5 6.5L5.5 8.5L9.5 4.5" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        Erstellt
      </span>
    : <span title="Noch nicht erstellt" style={{
        display:"inline-flex", alignItems:"center", gap:4,
        background:"#fff1f2", color:"#9f1239",
        border:"1.5px solid #fca5a5",
        borderRadius:20, padding:"3px 10px 3px 7px",
        fontFamily:T.fontBody, fontSize:"0.8rem", fontWeight:600,
        whiteSpace:"nowrap",
      }}>
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <circle cx="6.5" cy="6.5" r="6.5" fill="#f87171"/>
          <path d="M4.5 4.5L8.5 8.5M8.5 4.5L4.5 8.5" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
        </svg>
        Offen
      </span>;

  // ── Status-Banner ─────────────────────────────────────────────────────────
  const StatusBanner = () => {
    if (!ramicroStatus) return null;
    const isOk  = ramicroStatus.status === "ok";
    const isDeak = ramicroStatus.status === "deaktiviert";
    return (
      <div style={{
        display:"flex", alignItems:"center", gap:10,
        background: isOk ? "#f0fdf4" : isDeak ? T.amberBg : "#fff1f2",
        border: `1px solid ${isOk ? T.greenLight : isDeak ? "#fcd34d" : T.redLight}`,
        borderRadius:10, padding:"10px 16px", marginBottom:"1.25rem",
        fontFamily:T.fontBody, fontSize:"0.885rem",
      }}>
        <span style={{ fontSize:"1.1rem" }}>{isOk ? "🟢" : isDeak ? "🟡" : "🔴"}</span>
        <span style={{ color: isOk ? T.greenText : isDeak ? T.amberText : "#9f1239", fontWeight:500 }}>
          {isOk
            ? `RA-Micro verbunden · ${ramicroStatus.host} · DB: ${ramicroStatus.datenbank}`
            : isDeak
            ? "RA-Micro Verbindung deaktiviert – RAMICRO_AKTIV=true in .env setzen"
            : `RA-Micro nicht erreichbar: ${ramicroStatus.meldung || ""}`}
        </span>
      </div>
    );
  };

  const anAusgewaehlt   = ausgewaehlt.size;
  const wvGesamtAnzahl  = (wvListe || []).length;
  const wvGesamtSeiten  = Math.max(1, Math.ceil(wvGesamtAnzahl / WV_SEITE_GROESSE));
  const wvSeiteKorr     = Math.min(wvSeite, wvGesamtSeiten);
  const wvListeSeite    = (wvListe || []).slice((wvSeiteKorr - 1) * WV_SEITE_GROESSE, wvSeiteKorr * WV_SEITE_GROESSE);

  return (
    <div style={{ flex:1, overflowY:"auto", background:T.offWhite }}>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <div style={{ maxWidth:1440, margin:"0 auto", padding:"1.75rem" }}>

        {/* Header */}
        <div style={{ marginBottom:"1.5rem", display:"flex", alignItems:"flex-end", justifyContent:"space-between", flexWrap:"wrap", gap:12 }}>
          <div>
            <h1 style={{ fontFamily:T.fontDisplay, fontSize:"2.0rem", fontWeight:700, color:T.navy, margin:0 }}>
              Wiedervorlage
            </h1>
            <p style={{ fontFamily:T.fontBody, fontSize:"0.955rem", color:T.textMuted, marginTop:4, margin:0 }}>
              Fällige Stellungnahmen Gegner · RA-Micro Integration
            </p>
          </div>
          <button onClick={lade} disabled={loading}
            style={{ display:"flex", alignItems:"center", gap:6, padding:"8px 14px",
              background:T.navy, color:T.white, border:"none", borderRadius:8,
              fontFamily:T.fontBody, fontSize:"0.9rem", fontWeight:500, cursor:"pointer", opacity:loading?0.6:1 }}>
            <span style={{ display:"inline-block", animation:loading?"spin 0.7s linear infinite":"none" }}>↻</span>
            Aktualisieren
          </button>
        </div>

        <StatusBanner />

        {/* Filterzeile */}
        <div style={{ display:"flex", gap:10, marginBottom:"1.25rem", flexWrap:"wrap", alignItems:"center" }}>
          <label style={{ display:"flex", alignItems:"center", gap:7, background:T.white, border:`1px solid ${T.border}`, borderRadius:8, padding:"7px 13px", cursor:"pointer", fontFamily:T.fontBody, fontSize:"0.895rem", color:T.textMid, userSelect:"none" }}>
            <input type="checkbox" checked={filterHeute} onChange={e => {
                setFilterHeute(e.target.checked);
                if (e.target.checked) setFilterAlleWv(false);
              }} style={{ accentColor:T.navy, width:15, height:15 }} />
            Nur heute fällig
          </label>
          <label style={{ display:"flex", alignItems:"center", gap:7, background:T.white, border:`1px solid ${T.border}`, borderRadius:8, padding:"7px 13px", cursor:"pointer", fontFamily:T.fontBody, fontSize:"0.895rem", color:T.textMid, userSelect:"none" }}>
            <input type="checkbox" checked={filterAlleWv} onChange={e => {
                setFilterAlleWv(e.target.checked);
                if (e.target.checked) setFilterHeute(false);
              }} style={{ accentColor:T.navy, width:15, height:15 }} />
            Alle Wiedervorlagen
          </label>
          {grundListe.length > 0 && (
            <select value={filterGrund} onChange={e => setFilterGrund(e.target.value)}
              style={{ padding:"7px 13px", background:T.white, border:`1px solid ${T.border}`, borderRadius:8, fontFamily:T.fontBody, fontSize:"0.895rem", color:T.textMid, cursor:"pointer", maxWidth:220 }}>
              <option value="">Alle WV-Gründe</option>
              {grundListe.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
          )}
          {sbListe.length > 0
            ? <select value={filterSb} onChange={e => setFilterSb(e.target.value)}
                style={{ padding:"7px 13px", background:T.white, border:`1px solid ${T.border}`, borderRadius:8, fontFamily:T.fontBody, fontSize:"0.895rem", color:T.textMid, cursor:"pointer" }}>
                <option value="">Alle Sachbearbeiter</option>
                {sbListe.map(sb => <option key={sb} value={sb}>{sb}</option>)}
              </select>
            : <input value={filterSb} onChange={e => setFilterSb(e.target.value)}
                placeholder="SB-Kürzel (z.B. AS)"
                style={{ padding:"7px 13px", background:T.white, border:`1px solid ${T.border}`, borderRadius:8, fontFamily:T.fontBody, fontSize:"0.895rem", color:T.textMid, width:160 }} />
          }
          {wvListe && (
            <span style={{ marginLeft:"auto", fontFamily:T.fontBody, fontSize:"0.865rem", color:T.textMuted }}>
              {wvGesamtAnzahl} Einträge
              {wvGesamtSeiten > 1 && <span> · Seite {wvSeiteKorr}/{wvGesamtSeiten}</span>}
              {anAusgewaehlt > 0 && <strong style={{ color:T.navy }}> · {anAusgewaehlt} ausgewählt</strong>}
            </span>
          )}
        </div>

        {/* Batch-Aktionsleiste */}
        {anAusgewaehlt > 0 && (
          <div style={{ display:"flex", alignItems:"center", gap:10, background:T.navy, borderRadius:10, padding:"11px 16px", marginBottom:"1.25rem", flexWrap:"wrap" }}>
            <span style={{ fontFamily:T.fontBody, fontSize:"0.9rem", color:T.white, fontWeight:500, flex:1 }}>
              {batchLaeuft && batchFortschritt.gesamt > 0
                ? `Generiere ${batchFortschritt.aktuell} / ${batchFortschritt.gesamt} …`
                : `${anAusgewaehlt} ausgewählt`}
            </span>
            <button onClick={batchEinzeln} disabled={batchLaeuft}
              style={{ display:"flex", alignItems:"center", gap:6, padding:"8px 15px", background:"rgba(255,255,255,0.12)", color:T.white, border:"1px solid rgba(255,255,255,0.25)", borderRadius:8, fontFamily:T.fontBody, fontSize:"0.9rem", fontWeight:500, cursor:batchLaeuft?"default":"pointer", opacity:batchLaeuft?0.6:1 }}>
              📄 Einzeln herunterladen
            </button>
            <button onClick={batchZip} disabled={batchLaeuft}
              style={{ display:"flex", alignItems:"center", gap:6, padding:"8px 15px", background:T.accent, color:T.navy, border:"none", borderRadius:8, fontFamily:T.fontBody, fontSize:"0.9rem", fontWeight:600, cursor:batchLaeuft?"default":"pointer", opacity:batchLaeuft?0.6:1 }}>
              🗜 Als ZIP herunterladen
            </button>
            <button onClick={() => setAusgewaehlt(new Set())}
              style={{ padding:"8px 10px", background:"transparent", color:"rgba(255,255,255,0.5)", border:"none", borderRadius:8, cursor:"pointer", fontFamily:T.fontBody, fontSize:"0.9rem" }}>
              ✕
            </button>
          </div>
        )}

        {/* Hauptinhalt */}
        {loading ? (
          <div style={{ display:"flex", justifyContent:"center", padding:"4rem", color:T.textMuted, fontFamily:T.fontBody }}>
            <div style={{ textAlign:"center" }}>
              <div style={{ width:32, height:32, border:`3px solid ${T.border}`, borderTopColor:T.navy, borderRadius:"50%", animation:"spin 0.7s linear infinite", margin:"0 auto 12px" }} />
              Lädt Wiedervorlagen aus RA-Micro …
            </div>
          </div>
        ) : fehler ? (
          <div style={{ background:"#fff1f2", border:"1px solid #fca5a5", borderRadius:12, padding:"2rem", textAlign:"center" }}>
            <div style={{ fontSize:"2rem", marginBottom:8 }}>⚠️</div>
            <div style={{ fontFamily:T.fontBody, fontWeight:600, color:"#9f1239", marginBottom:6 }}>RA-Micro nicht erreichbar</div>
            <div style={{ fontFamily:T.fontBody, fontSize:"0.875rem", color:"#6b7094" }}>{fehler}</div>
            <button onClick={lade} style={{ marginTop:14, padding:"8px 18px", background:T.navy, color:T.white, border:"none", borderRadius:8, cursor:"pointer", fontFamily:T.fontBody, fontSize:"0.9rem" }}>
              Erneut versuchen
            </button>
          </div>
        ) : !wvListe || wvListe.length === 0 ? (
          <div style={{ background:T.white, borderRadius:12, border:`1px solid ${T.border}`, padding:"3rem", textAlign:"center" }}>
            <div style={{ fontSize:"2.5rem", marginBottom:12 }}>🎉</div>
            <div style={{ fontFamily:T.fontDisplay, fontSize:"1.2rem", fontWeight:700, color:T.navy, marginBottom:6 }}>
              Keine fälligen Wiedervorlagen
            </div>
            <div style={{ fontFamily:T.fontBody, fontSize:"0.9rem", color:T.textMuted }}>
              Keine offenen „Stellungnahme Gegner"-Wiedervorlagen{filterHeute ? " für heute" : ""}.
            </div>
          </div>
        ) : (
          <div style={{ background:T.white, borderRadius:12, border:`1px solid ${T.border}`, overflow:"hidden" }}>
            <table style={{ width:"100%", borderCollapse:"collapse" }}>
              <thead>
                <tr style={{ background:T.navy }}>
                  {/* Alles-auswählen Checkbox */}
                  <th style={{ width:44, padding:"11px 14px" }}>
                    <input type="checkbox" checked={alleAusgewaehlt}
                      onChange={toggleAlle}
                      title="Alle auswählen"
                      style={{ accentColor:T.accent, width:16, height:16, cursor:"pointer" }} />
                  </th>
                  {[
                    { label:"Datum",         w:"100px"  },
                    { label:"Aktenzeichen",  w:"120px"  },
                    { label:"Akte",          w:null     },
                    { label:"SB",            w:"50px"   },
                    { label:"WV-Grund",      w:"180px"  },
                    { label:"Status",        w:"110px"  },
                    { label:"Adressat",      w:"200px"  },
                    { label:"Aktion",        w:"170px"  },
                  ].map(col => (
                    <th key={col.label} style={{ padding:"11px 14px", textAlign:"left", fontFamily:T.fontBody, fontSize:"0.8rem", fontWeight:600, color:"rgba(255,255,255,0.75)", letterSpacing:"0.06em", textTransform:"uppercase", whiteSpace:"nowrap", ...(col.w ? { width:col.w } : {}) }}>
                      {col.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {wvListeSeite.map((wv, idx) => {
                  const istErstellt  = bereitsErstellt.has(wv.aktenzeichen);
                  const istAusgewaehlt = ausgewaehlt.has(wv.guid);
                  const istAmLaden   = einzelnLaedt.has(wv.guid);
                  const istHeute     = wv.datum === new Date().toISOString().slice(0,10);
                  const istUeberfaellig = wv.datum < new Date().toISOString().slice(0,10);
                  return (
                    <tr key={wv.guid}
                      style={{ background: istAusgewaehlt ? "#f0f4ff" : idx % 2 === 0 ? T.white : "#fafaf8", borderBottom:`1px solid ${T.border}`, transition:"background 0.12s" }}
                      onMouseEnter={e => { if (!istAusgewaehlt) e.currentTarget.style.background = "#f6f4ef"; }}
                      onMouseLeave={e => { e.currentTarget.style.background = istAusgewaehlt ? "#f0f4ff" : idx % 2 === 0 ? T.white : "#fafaf8"; }}>

                      {/* Checkbox */}
                      <td style={{ padding:"10px 14px", textAlign:"center" }}>
                        <input type="checkbox" checked={istAusgewaehlt} onChange={() => toggleEinen(wv.guid)}
                          style={{ accentColor:T.navy, width:15, height:15, cursor:"pointer" }} />
                      </td>

                      {/* Datum */}
                      <td style={{ padding:"10px 14px" }}>
                        <span style={{
                          fontFamily:"ui-monospace,monospace", fontSize:"0.845rem",
                          color: istUeberfaellig ? "#b91c1c" : istHeute ? T.greenText : T.textMid,
                          fontWeight: (istUeberfaellig || istHeute) ? 600 : 400,
                        }}>
                          {wv.datum ? new Date(wv.datum + "T00:00:00").toLocaleDateString("de-DE") : "–"}
                        </span>
                        {istUeberfaellig && <div style={{ fontFamily:T.fontBody, fontSize:"0.73rem", color:T.red, fontWeight:600 }}>überfällig</div>}
                        {istHeute && <div style={{ fontFamily:T.fontBody, fontSize:"0.73rem", color:T.green, fontWeight:600 }}>heute</div>}
                      </td>

                      {/* Aktenzeichen – klickbar */}
                      <td style={{ padding:"10px 14px" }}>
                        <button onClick={() => onOpenAkte({ id: wv.aktenzeichen, az: wv.aktenzeichen, az_roh: wv.aktenzeichen, brutto: 0, hq: 100, unfalldatum: "", unfallort: "" })}
                          style={{ background:"none", border:"none", padding:0, cursor:"pointer", fontFamily:"ui-monospace,monospace", fontSize:"0.875rem", fontWeight:600, color:T.navy, textDecoration:"underline", textDecorationColor:"rgba(27,42,74,0.3)" }}>
                          {wv.aktenzeichen}
                        </button>
                      </td>

                      {/* Aktenkurz- + Langbezeichnung */}
                      <td style={{ padding:"10px 14px", maxWidth:280 }}>
                        <div style={{ fontFamily:T.fontBody, fontSize:"0.875rem", fontWeight:600, color:T.textMid, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}
                             title={wv.kurzbezeichnung}>
                          {wv.kurzbezeichnung || wv.mandant || "–"}
                        </div>
                        {wv.bezeichnung && (
                          <div style={{ fontFamily:T.fontBody, fontSize:"0.795rem", fontWeight:400, color:T.textMuted, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", marginTop:2 }}
                               title={wv.bezeichnung}>
                            {wv.bezeichnung}
                          </div>
                        )}
                      </td>

                      {/* Sachbearbeiter */}
                      <td style={{ padding:"10px 14px" }}>
                        <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.85rem", background:T.accentPale, color:T.navy, border:`1px solid ${T.accentTrim}`, borderRadius:5, padding:"2px 7px", fontWeight:600 }}>
                          {wv.sachbearbeiter || "–"}
                        </span>
                      </td>

                      {/* WV-Grund */}
                      <td style={{ padding:"10px 14px", fontFamily:T.fontBody, fontSize:"0.835rem", color:T.textMuted, maxWidth:180, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }} title={wv.grund}>
                        {wv.grund || "–"}
                        {wv.bemerkung && <div style={{ fontSize:"0.775rem", color:T.textFaint }}>{wv.bemerkung}</div>}
                      </td>

                      {/* Status-Marker */}
                      <td style={{ padding:"10px 14px" }}>
                        <Marker erstellt={istErstellt} />
                      </td>

                      {/* Adressat-Dropdown */}
                      <td style={{ padding:"8px 14px" }}>
                        <select
                          value={adressWahl[wv.guid] ?? ""}
                          onFocus={() => ladeBeteiligte(wv.guid, wv.grund, wv.bezeichnung, wv.referat)}
                          onChange={e => setAdressWahl(prev => ({
                            ...prev,
                            [wv.guid]: e.target.value ? parseInt(e.target.value) : null
                          }))}
                          style={{
                            width:"100%", padding:"5px 8px",
                            border:`1px solid ${T.border}`, borderRadius:6,
                            fontFamily:T.fontBody, fontSize:"0.825rem",
                            color:T.text, background:T.white, cursor:"pointer",
                            maxWidth:190,
                          }}>
                          <option value="">
                            {beteiligteLoading.has(wv.guid)
                              ? "Lädt…"
                              : wv.gegner_hv_name || "Standard"}
                          </option>
                          {(adressatenMap[wv.guid] || []).map(b => (
                            <option key={b.adress_nr ?? b.guid_adresse} value={b.adress_nr ?? ""}>
                              {b.kennzeichen ? `[${b.kennzeichen}] ` : ""}{b.name}{b.ort ? ` · ${b.ort}` : ""}
                            </option>
                          ))}
                        </select>
                      </td>

                      {/* Aktion */}
                      <td style={{ padding:"10px 14px" }}>
                        <button
                          onClick={() => einzelnGenerieren(wv)}
                          disabled={istAmLaden || batchLaeuft}
                          style={{
                            display:"flex", alignItems:"center", gap:6,
                            padding:"7px 13px",
                            background: istErstellt ? T.surface : T.navy,
                            color:      istErstellt ? T.textMid : T.white,
                            border: istErstellt ? `1px solid ${T.border}` : "none",
                            borderRadius:8,
                            fontFamily:T.fontBody, fontSize:"0.875rem", fontWeight:500,
                            cursor: (istAmLaden || batchLaeuft) ? "default" : "pointer",
                            opacity: (istAmLaden || batchLaeuft) ? 0.65 : 1,
                            whiteSpace:"nowrap", transition:"all 0.15s",
                          }}>
                          {istAmLaden
                            ? <><div style={{ width:11, height:11, border:"2px solid rgba(255,255,255,0.3)", borderTopColor:"white", borderRadius:"50%", animation:"spin 0.7s linear infinite" }}/> Lädt …</>
                            : istErstellt
                            ? <>↻ Erneut erstellen</>
                            : <>📄 Brief erstellen</>}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Paginierung */}
            {wvGesamtSeiten > 1 && (
              <div style={{ display:"flex", alignItems:"center", justifyContent:"center", gap:6, padding:"14px 16px", borderTop:`1px solid ${T.border}`, background:T.surface }}>
                <button onClick={() => setWvSeite(1)} disabled={wvSeiteKorr === 1}
                  style={{ padding:"5px 10px", background:"none", border:`1px solid ${T.border}`, borderRadius:6, cursor:wvSeiteKorr===1?"default":"pointer", color:T.textMid, fontFamily:T.fontBody, fontSize:"0.85rem", opacity:wvSeiteKorr===1?0.4:1 }}>
                  «
                </button>
                <button onClick={() => setWvSeite(s => Math.max(1, s-1))} disabled={wvSeiteKorr === 1}
                  style={{ padding:"5px 10px", background:"none", border:`1px solid ${T.border}`, borderRadius:6, cursor:wvSeiteKorr===1?"default":"pointer", color:T.textMid, fontFamily:T.fontBody, fontSize:"0.85rem", opacity:wvSeiteKorr===1?0.4:1 }}>
                  ‹
                </button>
                {Array.from({ length: wvGesamtSeiten }, (_, i) => i + 1)
                  .filter(p => p === 1 || p === wvGesamtSeiten || Math.abs(p - wvSeiteKorr) <= 2)
                  .reduce((acc, p, i, arr) => {
                    if (i > 0 && p - arr[i-1] > 1) acc.push("...");
                    acc.push(p);
                    return acc;
                  }, [])
                  .map((p, i) => p === "..." ? (
                    <span key={`e${i}`} style={{ padding:"5px 4px", color:T.textMuted, fontFamily:T.fontBody, fontSize:"0.85rem" }}>…</span>
                  ) : (
                    <button key={p} onClick={() => setWvSeite(p)}
                      style={{ padding:"5px 11px", background:p===wvSeiteKorr?T.navy:"none", border:`1px solid ${p===wvSeiteKorr?T.navy:T.border}`, borderRadius:6, cursor:"pointer", color:p===wvSeiteKorr?T.white:T.textMid, fontFamily:T.fontBody, fontSize:"0.85rem", fontWeight:p===wvSeiteKorr?600:400 }}>
                      {p}
                    </button>
                  ))
                }
                <button onClick={() => setWvSeite(s => Math.min(wvGesamtSeiten, s+1))} disabled={wvSeiteKorr === wvGesamtSeiten}
                  style={{ padding:"5px 10px", background:"none", border:`1px solid ${T.border}`, borderRadius:6, cursor:wvSeiteKorr===wvGesamtSeiten?"default":"pointer", color:T.textMid, fontFamily:T.fontBody, fontSize:"0.85rem", opacity:wvSeiteKorr===wvGesamtSeiten?0.4:1 }}>
                  ›
                </button>
                <button onClick={() => setWvSeite(wvGesamtSeiten)} disabled={wvSeiteKorr === wvGesamtSeiten}
                  style={{ padding:"5px 10px", background:"none", border:`1px solid ${T.border}`, borderRadius:6, cursor:wvSeiteKorr===wvGesamtSeiten?"default":"pointer", color:T.textMid, fontFamily:T.fontBody, fontSize:"0.85rem", opacity:wvSeiteKorr===wvGesamtSeiten?0.4:1 }}>
                  »
                </button>
                <span style={{ marginLeft:8, fontFamily:T.fontBody, fontSize:"0.84rem", color:T.textMuted }}>
                  {(wvSeiteKorr-1)*WV_SEITE_GROESSE+1}–{Math.min(wvSeiteKorr*WV_SEITE_GROESSE, wvGesamtAnzahl)} von {wvGesamtAnzahl}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}



export default WiedervorlageView;
