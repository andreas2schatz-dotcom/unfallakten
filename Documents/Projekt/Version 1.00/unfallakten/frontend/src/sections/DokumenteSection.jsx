import React, { useState, useRef, useEffect, useMemo } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { DOK_TYPEN, SCHADEN_F } from "../config/constants.js";
import { fmtSize, fmtEuro } from "../config/utils.js";
import { Card, CardHead, Btn, FieldSelect, Toast } from "../components/common.jsx";
import {
  dokumente as apiDokumente,
  eakte as apiEakte,
  belege as apiBelege,
  tokenStore,
  API_BASE,
} from "../api.js";

function DokumenteSection({ dokumente, dispatch, akteId, akte }) {
  const istVerkehrsunfall = akte?.referat == null || akte?.referat === 4;
  const [dragging, setDrag]   = useState(false);
  const [uploading, setUpl]   = useState(false);
  const [uploadTyp, setTyp]   = useState("gutachten");
  const [toast, setToast]     = useState("");
  const [korrekturLading, setKorrekturLading] = useState(null); // dok_id die gerade korrigiert wird
  const inputRef              = useRef(null);

  // ── E-Akte (RA-Micro) ──────────────────────────────────────────────────
  const [eakteDoks, setEakteDoks]       = useState([]);
  const [eakteLaden, setEakteLaden]     = useState(false);
  const [eakteGeladen, setEakteGeladen] = useState(false);
  const [eakteOffen, setEakteOffen]     = useState(false);
  const [eakteEmails, setEakteEmails]   = useState(false);
  const [eakteFehler, setEakteFehler]   = useState(null);
  const [eakteVorschau, setEakteVorschau] = useState(null); // Nr des Dokuments in Vorschau
  const [vorschauUrl, setVorschauUrl]     = useState(null); // Blob-URL fuer PDF-Viewer
  const [vorschauLaden, setVorschauLaden] = useState(false);
  const [eakteFilter, setEakteFilter]     = useState(""); // Absender-Filter
  const [eakteSeite, setEakteSeite]       = useState(0);  // Pagination
  const [eakteSortSpalte, setEakteSortSpalte] = useState("version"); // version|bemerkung|empfaenger|sachbearbeiter
  const [eakteSortAsc, setEakteSortAsc]   = useState(false); // false = neueste zuerst
  const [eakteImportiert, setEakteImportiert] = useState(new Set()); // importierte eakte_nrs
  const [eakteImportLaden, setEakteImportLaden] = useState(null); // Nr die gerade importiert wird
  const EAKTE_PRO_SEITE = 200;

  // ── Schadenbelege (PRD-23a) ────────────────────────────────────────────────
  const [belegMap, setBelegMap]               = useState({}); // {position_key: beleg}
  const [belegVorschau, setBelegVorschau]     = useState(null); // dokument_id
  const [belegVorschauUrl, setBelegVorschauUrl] = useState(null);
  const [batchParserLaden, setBatchParserLaden] = useState(false);
  const [batchParserFortschritt, setBatchParserFortschritt] = useState(0);
  const [batchParserTotal, setBatchParserTotal] = useState(0);
  const [debugKandidaten, setDebugKandidaten] = useState(null); // null = Dialog zu
  const [letzteKandidaten, setLetzteKandidaten] = useState(null); // Ergebnis letzter Auto-Zuordnung
  const [eakteBulkLaden, setEakteBulkLaden] = useState(false);

  const belegAnzahl = Object.keys(belegMap).length;
  const belegTotal = SCHADEN_F.length;

  useEffect(() => {
    if (!akteId) return;
    apiBelege.liste(akteId)
      .then(res => {
        const map = {};
        (res?.belege || []).forEach(b => { map[b.position_key] = b; });
        setBelegMap(map);
      })
      .catch(() => {});
  }, [akteId]);

  // Beleg-Vorschau (Blob-URL)
  useEffect(() => {
    if (!belegVorschau) {
      if (belegVorschauUrl) { URL.revokeObjectURL(belegVorschauUrl); setBelegVorschauUrl(null); }
      return;
    }
    const token = tokenStore.getAccess();
    fetch(`${API_BASE}/akten/${akteId}/dokumente/${belegVorschau}/datei`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => { if (!r.ok) throw new Error(); return r.blob(); })
      .then(blob => setBelegVorschauUrl(URL.createObjectURL(blob)))
      .catch(() => { setBelegVorschauUrl(null); setBelegVorschau(null); setToast("Vorschau fehlgeschlagen"); });
    return () => { if (belegVorschauUrl) URL.revokeObjectURL(belegVorschauUrl); };
  }, [belegVorschau]); // eslint-disable-line react-hooks/exhaustive-deps

  // Kandidaten still laden (nach Import oder Klassen-Korrektur)
  const ladeBelegeKandidaten = async () => {
    try {
      const res = await apiBelege.kandidaten(akteId);
      const kandidaten = res?.kandidaten || [];
      dispatch({ type: "SET_BELEGE_KANDIDATEN", akteId, kandidaten });
    } catch { /* still – kein Toast, da Hintergrund-Refresh */ }
  };

  // Initial laden (auch nach erneutem Login)
  useEffect(() => {
    if (!akteId) return;
    ladeBelegeKandidaten();
  }, [akteId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Batch-Parser (PRD-23b)
  const handleBatchParser = async () => {
    setBatchParserLaden(true);
    setBatchParserFortschritt(0);
    const rechnungsCount = dokumente.filter(d =>
      (d.dokumentenklasse || "").startsWith("rechnung")
    ).length;
    setBatchParserTotal(rechnungsCount);
    let cnt = 0;
    const maxAnim = Math.max(rechnungsCount, 1);
    const iv = setInterval(() => {
      cnt = Math.min(cnt + 1, maxAnim - 1);
      setBatchParserFortschritt(cnt);
    }, 200);
    try {
      // Erst lokale Dokumente neu parsen (aktualisiert parse_json in DB)
      await apiBelege.neuParsen(akteId).catch(() => {});
      const res = await apiBelege.kandidaten(akteId);
      clearInterval(iv);
      const kandidaten = res?.kandidaten || [];
      const lokalGeprueft = res?.lokal_geprueft ?? 0;
      const eakteGeprueft = res?.eakte_geprueft ?? 0;
      const eakteVerfuegbar = res?.eakte_verfuegbar ?? false;
      const gesamtGeprueft = lokalGeprueft + eakteGeprueft;
      dispatch({ type: "SET_BELEGE_KANDIDATEN", akteId, kandidaten });
      setBatchParserFortschritt(kandidaten.length);
      setBatchParserTotal(gesamtGeprueft);
      const quellen = [
        lokalGeprueft > 0 ? `${lokalGeprueft} lokal` : null,
        eakteVerfuegbar ? `${eakteGeprueft} E-Akte` : "E-Akte nicht verfügbar",
      ].filter(Boolean).join(" · ");
      setToast(`${kandidaten.length} Kandidat(en) gefunden · ${gesamtGeprueft} Dokumente geprüft (${quellen})`);
      setLetzteKandidaten(kandidaten);
    } catch(e) {
      clearInterval(iv);
      setToast("Batch-Parser fehlgeschlagen: " + (e?.message || ""));
    } finally {
      setBatchParserLaden(false);
    }
  };

  // Vorschau laden: PDF als Blob holen und Blob-URL erzeugen
  useEffect(() => {
    if (!eakteVorschau) {
      if (vorschauUrl) { URL.revokeObjectURL(vorschauUrl); setVorschauUrl(null); }
      return;
    }
    setVorschauLaden(true);
    const token = tokenStore.getAccess();
    fetch(`${API_BASE}/akten/${akteId}/eakte/${eakteVorschau}/datei`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(res => {
        if (!res.ok) throw new Error(res.status + "");
        return res.blob();
      })
      .then(blob => {
        const url = URL.createObjectURL(blob);
        setVorschauUrl(url);
      })
      .catch(() => {
        setVorschauUrl(null);
        setToast("Vorschau fehlgeschlagen – Volume-Mount prüfen");
        setEakteVorschau(null);
      })
      .finally(() => setVorschauLaden(false));
    return () => { if (vorschauUrl) URL.revokeObjectURL(vorschauUrl); };
  }, [eakteVorschau]); // eslint-disable-line react-hooks/exhaustive-deps

  // E-Akte laden wenn Klappliste geoeffnet wird (lazy load)
  useEffect(() => {
    if (!eakteOffen || eakteGeladen) return;
    if (!akteId || !String(akteId).includes("/")) return;
    setEakteLaden(true);
    setEakteFehler(null);
    apiEakte.liste(akteId, eakteEmails)
      .then(res => {
        setEakteDoks(res?.dokumente || []);
        setEakteImportiert(new Set(res?.importierte_nrs || []));
        setEakteGeladen(true);
      })
      .catch(e => {
        setEakteFehler(e?.message || "E-Akte konnte nicht geladen werden");
        setEakteDoks([]);
      })
      .finally(() => setEakteLaden(false));
  }, [akteId, eakteOffen, eakteEmails, eakteGeladen]);

  // Bei Toggle-Aenderung neu laden
  const toggleEmails = () => {
    setEakteEmails(prev => !prev);
    setEakteGeladen(false);
    setEakteSeite(0);
    setEakteFilter("");
  };

  // E-Akte-Dokument in Pipeline importieren
  const importiereEakte = async (nr, anzeigename) => {
    setEakteImportLaden(nr);
    try {
      const res = await apiEakte.importieren(akteId, nr);
      if (res?.status === "duplikat") {
        setToast("Bereits importiert: " + anzeigename);
        setEakteImportiert(prev => new Set([...prev, nr]));
      } else if (res?.status === "importiert") {
        setEakteImportiert(prev => new Set([...prev, nr]));
        const klasse = res.dokumentenklasse;
        setToast("Importiert: " + anzeigename + (klasse ? " → " + klasse : ""));
        // Dokument sofort in der lokalen Liste anzeigen
        dispatch({ type: "ADD_DOKUMENT", akteId, dokument: {
          id: res.dokument_id,
          typ: klasse || "sonstiges",
          dokumentenklasse: klasse,
          dateiname: anzeigename,
          dateityp: "pdf",
          dateigroesse: 0,
          hochgeladen_am: new Date().toLocaleString("de-DE", { year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit" }),
          parse_status: res.dispatch?.parse_status || "ausstehend",
          parse_konfidenz: res.dispatch?.konfidenz || null,
          eakte_nr: nr,
          quelle: "eakte",
        }});
        // Kandidaten im Schaden-Tab neu laden
        ladeBelegeKandidaten();
      }
    } catch (e) {
      setToast("Import fehlgeschlagen: " + (e?.message || String(e)));
    } finally {
      setEakteImportLaden(null);
    }
  };

  // Alle nicht importierten PDFs aus der E-Akte in einem Schritt importieren
  const handleBulkEakteImport = async () => {
    const zuImportieren = eakteSortiert.filter(ed => ed.dateityp === "pdf" && !eakteImportiert.has(ed.nr));
    if (zuImportieren.length === 0) {
      setToast("Alle PDFs bereits importiert.");
      return;
    }
    setEakteBulkLaden(true);
    let ok = 0, dup = 0, fehler = 0;
    for (const ed of zuImportieren) {
      try {
        const res = await apiEakte.importieren(akteId, ed.nr);
        if (res?.status === "duplikat") {
          setEakteImportiert(prev => new Set([...prev, ed.nr]));
          dup++;
        } else if (res?.status === "importiert") {
          setEakteImportiert(prev => new Set([...prev, ed.nr]));
          dispatch({ type: "ADD_DOKUMENT", akteId, dokument: {
            id: res.dokument_id,
            typ: res.dokumentenklasse || "sonstiges",
            dokumentenklasse: res.dokumentenklasse,
            dateiname: ed.bemerkung || ed.anzeigename,
            dateityp: "pdf",
            dateigroesse: 0,
            hochgeladen_am: new Date().toLocaleString("de-DE", { year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit" }),
            parse_status: res.dispatch?.parse_status || "ausstehend",
            parse_konfidenz: res.dispatch?.konfidenz || null,
            eakte_nr: ed.nr,
            quelle: "eakte",
          }});
          ok++;
        }
      } catch {
        fehler++;
      }
    }
    setEakteBulkLaden(false);
    if (ok > 0) ladeBelegeKandidaten();
    const teile = [`${ok} importiert`, dup > 0 ? `${dup} bereits vorhanden` : null, fehler > 0 ? `${fehler} Fehler` : null].filter(Boolean);
    setToast(teile.join(" · "));
  };

  // Gefilterte + sortierte + paginierte Liste
  const eakteGefiltert = eakteFilter
    ? eakteDoks.filter(ed => {
        const suchtext = eakteFilter.toLowerCase();
        const emp = (ed.empfaenger || "").toLowerCase();
        const bem = (ed.bemerkung || "").toLowerCase();
        return emp.includes(suchtext) || bem.includes(suchtext);
      })
    : eakteDoks;

  const eakteSortiert = React.useMemo(() => {
    const sorted = [...eakteGefiltert].sort((a, b) => {
      let va, vb;
      switch (eakteSortSpalte) {
        case "bemerkung":
          va = (a.bemerkung || a.anzeigename || "").toLowerCase();
          vb = (b.bemerkung || b.anzeigename || "").toLowerCase();
          return va < vb ? -1 : va > vb ? 1 : 0;
        case "empfaenger":
          va = (a.empfaenger || "").replace(/<[^>]+>/g, "").replace(/"/g, "").trim().toLowerCase();
          vb = (b.empfaenger || "").replace(/<[^>]+>/g, "").replace(/"/g, "").trim().toLowerCase();
          return va < vb ? -1 : va > vb ? 1 : 0;
        case "sachbearbeiter":
          va = (a.sachbearbeiter || "").toLowerCase();
          vb = (b.sachbearbeiter || "").toLowerCase();
          return va < vb ? -1 : va > vb ? 1 : 0;
        case "version":
        default:
          va = a.version || "";
          vb = b.version || "";
          return va < vb ? -1 : va > vb ? 1 : 0;
      }
    });
    return eakteSortAsc ? sorted : sorted.reverse();
  }, [eakteGefiltert, eakteSortSpalte, eakteSortAsc]);

  const eakteGesamtSeiten = Math.ceil(eakteSortiert.length / EAKTE_PRO_SEITE);
  const eakteSeiteAktuell = Math.min(eakteSeite, Math.max(0, eakteGesamtSeiten - 1));
  const eakteSeitenDoks = eakteSortiert.slice(
    eakteSeiteAktuell * EAKTE_PRO_SEITE,
    (eakteSeiteAktuell + 1) * EAKTE_PRO_SEITE
  );

  const eakteSortKlick = (spalte) => {
    if (eakteSortSpalte === spalte) {
      setEakteSortAsc(prev => !prev);
    } else {
      setEakteSortSpalte(spalte);
      setEakteSortAsc(spalte === "version" ? false : true); // Datum: neueste zuerst, Text: A-Z
    }
    setEakteSeite(0);
  };

  const sortPfeil = (spalte) => eakteSortSpalte === spalte ? (eakteSortAsc ? " ↑" : " ↓") : "";
  // Eindeutige Absender fuer Filter-Dropdown
  const eakteAbsender = React.useMemo(() => {
    const set = new Set();
    eakteDoks.forEach(ed => {
      const name = (ed.empfaenger || "").replace(/<[^>]+>/g, "").replace(/"/g, "").trim();
      if (name) set.add(name);
    });
    return [...set].sort();
  }, [eakteDoks]);

  const parseStyle = {
    erfolgreich:        { c:T.green,    bg:T.greenBg,  label:"Geparst"   },
    fehler:             { c:T.red,      bg:T.redBg,    label:"Fehler"    },
    ausstehend:         { c:T.textMuted,bg:T.surface,  label:"Ausstehend"},
    manuell_korrigiert: { c:T.blue,     bg:T.blueBg,   label:"Korrigiert"},
  };

  const [uploadProgress, setUploadProgress] = useState(0);

  const korrigiereKlasse = async (dokId, neueKlasse) => {
    setKorrekturLading(dokId);
    try {
      const erg = await apiDokumente.klassifikation(akteId, dokId, neueKlasse);
      if (erg?.klasse) {
        dispatch({ type:"UPDATE_DOKUMENT_KLASSE", akteId, dokId, dokumentenklasse: erg.klasse, parse_status: erg.parse_status || "ausstehend" });
        const label = DOK_TYPEN.find(t => t.value===erg.klasse)?.label || erg.klasse;
        setToast(`Korrigiert zu ${label}.${erg.parse_status==="erfolgreich" ? " Parser erfolgreich." : ""}`);
        // Kandidaten im Schaden-Tab neu laden damit neue Klasse sofort greift
        ladeBelegeKandidaten();
      }
    } catch(e) {
      setToast("Korrektur fehlgeschlagen: " + (e?.message || String(e)));
    } finally {
      setKorrekturLading(null);
    }
  };

  const fakeUpload = async files => {
    if (!files.length) return;
    const f   = files[0];
    const ext = f.name.split(".").pop().toLowerCase();
    const typ = ["jpg","jpeg","png"].includes(ext) ? "jpg" : ext==="docx" ? "docx" : "pdf";
    setUpl(true); setUploadProgress(0);

    let dokData = {
      id: Date.now(), typ: uploadTyp, dateiname: f.name, dateityp: typ,
      groesse: f.size || Math.floor(Math.random()*900000+100000),
      hochgeladen_am: new Date().toLocaleString("de-DE",{year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}),
      parse_status: typ==="pdf" ? "erfolgreich" : "ausstehend",
      parse_konfidenz: typ==="pdf" ? (0.7 + Math.random()*0.28) : null,
    };

    try {
      const created = await apiDokumente.hochladen(akteId, f, uploadTyp, pct => setUploadProgress(pct));
      // API gibt { dokument: {...}, parse_ergebnis: {...}, dispatch: {...} } zurück
      const dok = created?.dokument || created;
      if (dok?.id) dokData = { ...dokData, ...dok };
      // Dispatcher-Klasse übernehmen (hat Vorrang vor Upload-Dropdown)
      if (created?.dispatch?.klasse) dokData.dokumentenklasse = created.dispatch.klasse;
    } catch {
      // Demo-Modus: nur lokaler Fake-Upload
      await new Promise(r => setTimeout(r, 1200));
    }

    dispatch({ type:"ADD_DOKUMENT", akteId, dokument: dokData });
    setUpl(false); setUploadProgress(0);
    const klasseLabel = dokData.dokumentenklasse ? (DOK_TYPEN.find(t => t.value===dokData.dokumentenklasse)?.label || dokData.dokumentenklasse) : null;
    setToast(`${f.name} hochgeladen${klasseLabel ? ` · Erkannt als ${klasseLabel}` : (typ==="pdf" ? " und geparst" : "")}.`);
    if (typ === "pdf") ladeBelegeKandidaten();
  };

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <div style={{ display:"flex", flexDirection:"column", gap:"1.25rem" }}>

        {/* Upload */}
        <Card style={{ padding:"1.25rem 1.4rem" }}>
          <div style={{ marginBottom:"1rem", maxWidth:250 }}>
            <FieldSelect label="Dokumenttyp" value={uploadTyp} onChange={setTyp} options={DOK_TYPEN} />
          </div>
          <div
            onDragOver={e => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={e => { e.preventDefault(); setDrag(false); fakeUpload([...e.dataTransfer.files]); }}
            onClick={() => !uploading && inputRef.current?.click()}
            style={{ border:`2px dashed ${dragging?T.gold:T.border}`, borderRadius:12, padding:"2.5rem 1.5rem", textAlign:"center", cursor:uploading?"default":"pointer", background:dragging?T.goldPale:"transparent", transition:"all 0.2s" }}>
            <input ref={inputRef} type="file" accept=".pdf,.docx,.jpg,.jpeg,.png" style={{ display:"none" }} onChange={e => fakeUpload([...e.target.files])} />
            {uploading ? (
              <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:12 }}>
                <div style={{ width:32, height:32, border:`3px solid ${T.goldTrim}`, borderTopColor:T.gold, borderRadius:"50%", animation:"spin 0.8s linear infinite" }} />
                <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.975rem", color:T.textMuted }}>Hochladen und analysieren …</div>
                {uploadProgress > 0 && uploadProgress < 100 && (
                  <div style={{ width:200 }}>
                    <div style={{ height:4, background:T.border, borderRadius:4, overflow:"hidden" }}>
                      <div style={{ height:"100%", width:`${uploadProgress}%`, background:`linear-gradient(90deg,${T.gold},${T.goldLight})`, borderRadius:4, transition:"width 0.3s" }}/>
                    </div>
                    <div style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.825rem", color:T.textFaint, textAlign:"center", marginTop:3 }}>{uploadProgress} %</div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:10 }}>
                <span style={{ color:dragging?T.gold:T.textFaint }}>{Ic.upload}</span>
                <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"1.025rem", fontWeight:600, color:dragging?T.gold:T.textMid }}>Datei hier ablegen oder klicken</div>
                <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.905rem", color:T.textFaint }}>PDF, DOCX, JPG, PNG · max. 20 MB · PDFs werden automatisch geparst</div>
              </div>
            )}
          </div>
        </Card>

        {/* ── Schadenbelege-Übersicht (PRD-23a) ── nur für Referat 04 */}
        {istVerkehrsunfall && <Card>
          <CardHead
            title={`Schadenbelege (${belegAnzahl} von ${belegTotal})`}
            action={
              <div style={{ display:"flex", alignItems:"center", gap:4 }}>
                <Btn size="sm" variant="secondary" onClick={handleBatchParser} disabled={batchParserLaden}
                  title="Alle Dokumente automatisch klassifizieren und Positionen zuordnen (PRD-23b)">
                  {batchParserLaden ? `${batchParserFortschritt} / ${batchParserTotal || "?"} …` : "🤖 Auto-Zuordnung"}
                </Btn>
                {letzteKandidaten !== null && (
                  <Btn size="sm" variant="secondary" onClick={() => setDebugKandidaten(letzteKandidaten)}
                    title="Kandidaten-Übersicht anzeigen" style={{ padding:"5px 8px" }}>
                    🔍
                  </Btn>
                )}
              </div>
            }
          />
          <div style={{ padding:"0.5rem 1.4rem 1rem" }}>
            {SCHADEN_F.map((f, i) => {
              const beleg = belegMap[f.k];
              return (
                <div key={f.k} style={{ display:"flex", alignItems:"center", gap:10,
                  padding:"6px 0", borderBottom: i < SCHADEN_F.length - 1 ? `1px solid ${T.borderSoft}` : "none" }}>
                  <div style={{ width:180, fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.855rem",
                    fontWeight:500, color: beleg ? T.text : T.textFaint }}>
                    {f.l}
                  </div>
                  {beleg ? (
                    <div style={{ flex:1, display:"flex", alignItems:"center", gap:8, minWidth:0 }}>
                      <button onClick={() => setBelegVorschau(beleg.dokument_id)}
                        style={{ display:"flex", alignItems:"center", gap:5, background:"none", border:"none",
                          cursor:"pointer", padding:"2px 4px", minWidth:0, overflow:"hidden" }}
                        onMouseEnter={e => e.currentTarget.querySelector("span").style.textDecoration = "underline"}
                        onMouseLeave={e => e.currentTarget.querySelector("span").style.textDecoration = "none"}>
                        <span style={{ color:T.red, fontSize:"0.9rem", flexShrink:0 }}>📄</span>
                        <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.blue,
                          overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                          {beleg.dateiname}
                        </span>
                      </button>
                      {beleg.betrag_aus_beleg > 0 && (
                        <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.82rem",
                          color:T.navy, fontWeight:600, flexShrink:0, marginLeft:"auto" }}>
                          {fmtEuro(beleg.betrag_aus_beleg)}
                        </span>
                      )}
                      <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.7rem",
                        color:T.green, background:T.greenBg, border:`1px solid ${T.green}33`,
                        borderRadius:10, padding:"1px 6px", flexShrink:0 }}>
                        ✓
                      </span>
                    </div>
                  ) : (
                    <div style={{ flex:1, fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.textFaint, fontStyle:"italic" }}>
                      kein Beleg
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Card>}

        {/* Beleg-Vorschau Modal */}
        {belegVorschau && (
          <>
            <div onClick={() => setBelegVorschau(null)}
              style={{ position:"fixed", top:0, left:0, right:0, bottom:0,
                background:"rgba(0,0,0,0.4)", zIndex:950 }} />
            <div style={{ position:"fixed", top:"5%", left:"10%", right:"10%", bottom:"5%",
              zIndex:951, background:T.white, borderRadius:12,
              boxShadow:"0 20px 60px rgba(0,0,0,0.3)",
              display:"flex", flexDirection:"column", overflow:"hidden" }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center",
                padding:"12px 20px", borderBottom:`1px solid ${T.border}`, background:T.surface }}>
                <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.9rem", fontWeight:600, color:T.navy }}>
                  📄 Beleg-Vorschau
                </span>
                <button onClick={() => setBelegVorschau(null)}
                  style={{ background:"none", border:"none", cursor:"pointer", fontSize:"1.2rem", color:T.textFaint, lineHeight:1 }}>✕</button>
              </div>
              {belegVorschauUrl ? (
                <iframe src={belegVorschauUrl} style={{ flex:1, border:"none" }} title="Beleg" />
              ) : (
                <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", color:T.textMuted }}>
                  <div style={{ width:24, height:24, border:`3px solid ${T.goldTrim}`, borderTopColor:T.gold, borderRadius:"50%", animation:"spin 0.8s linear infinite", marginRight:10 }} />
                  PDF wird geladen…
                </div>
              )}
            </div>
          </>
        )}

        {/* Liste */}
        <Card>
          <CardHead title={`Dokumente (${dokumente.length})`} />
          {dokumente.length === 0 ? (
            <div style={{ padding:"2rem", textAlign:"center", fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.975rem", color:T.textFaint }}>Noch keine Dokumente hochgeladen.</div>
          ) : dokumente.map((d, i) => {
            const ps = parseStyle[d.parse_status] || parseStyle.ausstehend;
            const isPdf = d.dateityp === "pdf";
            return (
              <div key={d.id} style={{ display:"flex", alignItems:"center", gap:13, padding:"11px 1.4rem", borderBottom:i<dokumente.length-1?`1px solid ${T.borderSoft}`:"none", transition:"background 0.1s" }}
                onMouseEnter={e => e.currentTarget.style.background=T.surface}
                onMouseLeave={e => e.currentTarget.style.background="transparent"}>
                <div style={{ width:38, height:38, borderRadius:8, background:isPdf?T.redBg:T.blueBg, display:"flex", alignItems:"center", justifyContent:"center", color:isPdf?T.red:T.blue, flexShrink:0 }}>
                  {isPdf ? Ic.pdf : Ic.word}
                </div>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.975rem", fontWeight:600, color:T.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{d.dateiname}</div>
                  <div style={{ display:"flex", alignItems:"center", gap:6, marginTop:3, flexWrap:"wrap" }}>
                    <select
                      value={d.dokumentenklasse||d.typ||"sonstiges"}
                      disabled={korrekturLading===d.id}
                      onChange={e => korrigiereKlasse(d.id, e.target.value)}
                      style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.825rem", background:korrekturLading===d.id?T.goldPale:T.surface, color:T.textMuted, border:`1px solid ${T.border}`, borderRadius:10, padding:"1px 7px", cursor:"pointer", outline:"none", appearance:"none", WebkitAppearance:"none", paddingRight:16, backgroundImage:`url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%23999'/%3E%3C/svg%3E")`, backgroundRepeat:"no-repeat", backgroundPosition:"right 5px center" }}
                    >{DOK_TYPEN.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}</select>
                    <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.815rem", color:T.textFaint }}>{fmtSize(d.groesse)}</span>
                    {d.hochgeladen_am && (
                      <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.815rem", color:T.textFaint }}>
                        {(() => {
                          try {
                            const dt = new Date(d.hochgeladen_am.replace(" ", "T"));
                            if (isNaN(dt.getTime())) return null;
                            return dt.toLocaleString("de-DE", { day:"2-digit", month:"2-digit", year:"numeric", hour:"2-digit", minute:"2-digit" });
                          } catch { return null; }
                        })()}
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ display:"flex", alignItems:"center", gap:8, flexShrink:0 }}>
                  {isPdf && (
                    <>
                      <span style={{ display:"inline-flex", alignItems:"center", gap:4, background:ps.bg, color:ps.c, border:`1px solid ${ps.c}33`, borderRadius:10, padding:"2px 8px", fontSize:"0.825rem", fontWeight:600 }}>
                        {d.parse_status==="erfolgreich" && Ic.check} {ps.label}
                      </span>
                      {d.parse_konfidenz != null && (
                        <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.895rem", fontWeight:600, color:d.parse_konfidenz>0.7?T.green:d.parse_konfidenz>0.4?T.amber:T.red }}>{Math.round(d.parse_konfidenz*100)} %</span>
                      )}
                    </>
                  )}
                  <Btn size="sm" variant="secondary" onClick={async () => {
                    try {
                      await apiDokumente.download(akteId, d.id, d.dateiname);
                    } catch {
                      setToast(`${d.dateiname} – Download fehlgeschlagen (Demo-Modus)`);
                    }
                  }}>{Ic.download} Download</Btn>
                  <Btn size="sm" variant="danger" onClick={async () => {
                          if (!confirm(`"${d.dateiname}" wirklich löschen?`)) return;
                          try {
                            await apiDokumente.loeschen(akteId, d.id);
                            dispatch({ type:"DELETE_DOKUMENT", akteId, id:d.id });
                          } catch(e) {
                            setToast("Löschen fehlgeschlagen: " + (e?.message || String(e)));
                          }
                        }}>{Ic.trash}</Btn>
                </div>
              </div>
            );
          })}
        </Card>

        {/* ── E-Akte (RA-Micro) ──────────────────────────────────────── */}
        {String(akteId).includes("/") && (
          <Card>
            <div
              onClick={() => setEakteOffen(prev => !prev)}
              style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"0.9rem 1.4rem", cursor:"pointer", userSelect:"none", borderBottom: eakteOffen ? `1px solid ${T.border}` : "none" }}
              onMouseEnter={e => e.currentTarget.style.background=T.surface}
              onMouseLeave={e => e.currentTarget.style.background="transparent"}>
              <div style={{ display:"flex", alignItems:"center", gap:10 }}>
                <span style={{ transform: eakteOffen ? "rotate(90deg)" : "rotate(0)", transition:"transform 0.15s", display:"inline-flex" }}>{Ic.chevR}</span>
                <h3 style={{ fontFamily:"'Plus Jakarta Sans',sans-serif", fontSize:"1rem", fontWeight:700, color:T.navy, margin:0 }}>
                  E-Akte (RA-Micro)
                </h3>
                {eakteGeladen && (
                  <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.82rem", color:T.textFaint }}>
                    {eakteFilter ? `${eakteGefiltert.length} / ${eakteDoks.length}` : eakteDoks.length} Dokumente
                  </span>
                )}
              </div>
              {/* Bulk-Import + Toggle-Switch: Auch E-Mails */}
              <div style={{ display:"flex", alignItems:"center", gap:8 }} onClick={e => e.stopPropagation()}>
                {eakteOffen && eakteGeladen && eakteSortiert.some(ed => ed.dateityp === "pdf" && !eakteImportiert.has(ed.nr)) && (
                  <Btn size="sm" variant="secondary"
                    disabled={eakteBulkLaden}
                    onClick={handleBulkEakteImport}
                    title="Alle nicht importierten PDFs in die Pipeline importieren"
                    style={{ fontSize:"0.78rem", whiteSpace:"nowrap" }}>
                    {eakteBulkLaden ? "…" : "📥 Alle PDFs"}
                  </Btn>
                )}
                <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color: eakteEmails ? T.text : T.textFaint }}>E-Mails</span>
                <div
                  onClick={toggleEmails}
                  style={{
                    width:36, height:20, borderRadius:10,
                    background: eakteEmails ? T.gold : T.border,
                    position:"relative", cursor:"pointer",
                    transition:"background 0.2s",
                    boxShadow: eakteEmails ? `0 0 0 1px ${T.gold}33` : "none",
                  }}>
                  <div style={{
                    width:16, height:16, borderRadius:"50%",
                    background:T.white,
                    position:"absolute", top:2,
                    left: eakteEmails ? 18 : 2,
                    transition:"left 0.2s",
                    boxShadow:"0 1px 3px rgba(0,0,0,0.2)",
                  }} />
                </div>
              </div>
            </div>

            {eakteOffen && (
              <div>
                {eakteLaden && (
                  <div style={{ padding:"2rem", textAlign:"center", color:T.textMuted }}>
                    <div style={{ width:24, height:24, border:`3px solid ${T.goldTrim}`, borderTopColor:T.gold, borderRadius:"50%", animation:"spin 0.8s linear infinite", margin:"0 auto 8px" }} />
                    E-Akte wird geladen…
                  </div>
                )}

                {eakteFehler && (
                  <div style={{ padding:"1rem 1.4rem", color:T.red, fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.9rem" }}>
                    ⚠ {eakteFehler}
                  </div>
                )}

                {!eakteLaden && !eakteFehler && eakteDoks.length === 0 && eakteGeladen && (
                  <div style={{ padding:"2rem", textAlign:"center", fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.975rem", color:T.textFaint }}>
                    Keine E-Akte-Dokumente gefunden.
                  </div>
                )}

                {!eakteLaden && eakteDoks.length > 0 && (
                  <>
                    {/* Filter-Leiste */}
                    <div style={{ display:"flex", alignItems:"center", gap:10, padding:"8px 1.4rem", borderBottom:`1px solid ${T.border}`, background:T.offWhite }}>
                      <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.textMuted, flexShrink:0 }}>Filter:</span>
                      <select
                        value={eakteFilter}
                        onChange={e => { setEakteFilter(e.target.value); setEakteSeite(0); }}
                        style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.textMid, border:`1px solid ${T.border}`, borderRadius:6, padding:"3px 8px", background:T.white, maxWidth:280, cursor:"pointer" }}>
                        <option value="">Alle Absender ({eakteDoks.length})</option>
                        {eakteAbsender.map(a => (
                          <option key={a} value={a}>{a.length > 40 ? a.slice(0,40)+"…" : a}</option>
                        ))}
                      </select>
                      {eakteFilter && (
                        <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.78rem", color:T.textFaint }}>
                          {eakteGefiltert.length} Treffer
                        </span>
                      )}
                      {eakteFilter && (
                        <span onClick={() => { setEakteFilter(""); setEakteSeite(0); }}
                          style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.78rem", color:T.red, cursor:"pointer", textDecoration:"underline" }}>
                          Filter zurücksetzen
                        </span>
                      )}
                    </div>

                    {/* Spaltenheader (klickbar zum Sortieren) */}
                    <div style={{ display:"flex", alignItems:"center", padding:"6px 1.4rem", borderBottom:`1px solid ${T.border}`, background:T.surface }}>
                      <div style={{ width:38, flexShrink:0 }} />
                      <div onClick={() => eakteSortKlick("bemerkung")}
                        style={{ flex:2, fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.75rem", fontWeight:600, color: eakteSortSpalte==="bemerkung" ? T.gold : T.textFaint, textTransform:"uppercase", letterSpacing:"0.06em", paddingLeft:13, cursor:"pointer", userSelect:"none" }}>
                        Dokument{sortPfeil("bemerkung")}
                      </div>
                      <div onClick={() => eakteSortKlick("empfaenger")}
                        style={{ flex:1, fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.75rem", fontWeight:600, color: eakteSortSpalte==="empfaenger" ? T.gold : T.textFaint, textTransform:"uppercase", letterSpacing:"0.06em", minWidth:120, cursor:"pointer", userSelect:"none" }}>
                        Absender{sortPfeil("empfaenger")}
                      </div>
                      <div onClick={() => eakteSortKlick("sachbearbeiter")}
                        style={{ width:50, textAlign:"center", fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.75rem", fontWeight:600, color: eakteSortSpalte==="sachbearbeiter" ? T.gold : T.textFaint, textTransform:"uppercase", letterSpacing:"0.06em", flexShrink:0, cursor:"pointer", userSelect:"none" }}>
                        SB{sortPfeil("sachbearbeiter")}
                      </div>
                      <div onClick={() => eakteSortKlick("version")}
                        style={{ width:90, textAlign:"right", fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.75rem", fontWeight:600, color: eakteSortSpalte==="version" ? T.gold : T.textFaint, textTransform:"uppercase", letterSpacing:"0.06em", flexShrink:0, paddingRight:8, cursor:"pointer", userSelect:"none" }}>
                        Datum{sortPfeil("version")}
                      </div>
                      <div style={{ width:140, flexShrink:0 }} />
                    </div>

                    {eakteSeitenDoks.map((ed, i) => {
                      const istVorschau = eakteVorschau === ed.nr;
                      const absenderName = (ed.empfaenger || "").replace(/<[^>]+>/g, "").replace(/"/g, "").trim();
                      return (
                        <div key={ed.nr}>
                          <div style={{ display:"flex", alignItems:"center", padding:"10px 1.4rem", borderBottom: (!istVorschau && i < eakteSeitenDoks.length-1) ? `1px solid ${T.borderSoft}` : "none", transition:"background 0.1s", cursor:"pointer", background: istVorschau ? T.goldPale : "transparent" }}
                            onMouseEnter={e => { if (!istVorschau) e.currentTarget.style.background=T.surface; }}
                            onMouseLeave={e => { if (!istVorschau) e.currentTarget.style.background="transparent"; }}
                            onClick={() => setEakteVorschau(istVorschau ? null : ed.nr)}>
                            {/* Icon */}
                            <div style={{ width:38, height:38, borderRadius:8, background: ed.dateityp==="pdf" ? T.redBg : T.blueBg, display:"flex", alignItems:"center", justifyContent:"center", color: ed.dateityp==="pdf" ? T.red : T.blue, flexShrink:0 }}>
                              {ed.dateityp === "pdf" ? Ic.pdf : Ic.email}
                            </div>
                            {/* Dokument */}
                            <div style={{ flex:2, minWidth:0, paddingLeft:13 }}>
                              <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.93rem", fontWeight:600, color:T.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                                {ed.bemerkung || ed.anzeigename}
                              </div>
                              {ed.rubrik && (
                                <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.72rem", color:T.textFaint, background:T.goldPale, border:`1px solid ${T.goldTrim}`, borderRadius:4, padding:"0 4px", marginTop:2, display:"inline-block" }}>
                                  {ed.rubrik}
                                </span>
                              )}
                            </div>
                            {/* Absender */}
                            <div style={{ flex:1, minWidth:120 }}>
                              <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.textMuted, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", display:"block" }}>
                                {absenderName}
                              </span>
                            </div>
                            {/* SB */}
                            <div style={{ width:50, textAlign:"center", flexShrink:0 }}>
                              {ed.sachbearbeiter && (
                                <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.8rem", color:T.textMid, background:T.surface, border:`1px solid ${T.border}`, borderRadius:4, padding:"1px 6px" }}>
                                  {ed.sachbearbeiter}
                                </span>
                              )}
                            </div>
                            {/* Datum */}
                            <div style={{ width:90, textAlign:"right", flexShrink:0, paddingRight:8 }}>
                              <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.82rem", color:T.textMid }}>
                                {ed.version ? (() => {
                                  try { return new Date(ed.version).toLocaleDateString("de-DE", { day:"2-digit", month:"2-digit", year:"2-digit" }); }
                                  catch { return ""; }
                                })() : ""}
                              </span>
                            </div>
                            {/* Aktionen */}
                            <div style={{ width:140, display:"flex", alignItems:"center", justifyContent:"flex-end", gap:4, flexShrink:0 }} onClick={e => e.stopPropagation()}>
                              {eakteImportiert.has(ed.nr) ? (
                                <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.72rem", fontWeight:600, color:T.green, background:T.greenBg, border:`1px solid ${T.green}33`, borderRadius:10, padding:"2px 8px", whiteSpace:"nowrap" }}>
                                  ✓ Importiert
                                </span>
                              ) : ed.dateityp === "pdf" ? (
                                <Btn size="sm" variant="secondary" title="In Pipeline importieren"
                                  disabled={eakteImportLaden === ed.nr}
                                  onClick={() => importiereEakte(ed.nr, ed.bemerkung || ed.anzeigename)}
                                  style={{ padding:"4px 8px", fontSize:"0.75rem", whiteSpace:"nowrap" }}>
                                  {eakteImportLaden === ed.nr ? "…" : "📥 Import"}
                                </Btn>
                              ) : null}
                              {ed.dateityp === "pdf" && (
                                <Btn size="sm" variant="secondary" title="Vorschau" onClick={() => setEakteVorschau(istVorschau ? null : ed.nr)}
                                  style={{ padding:"4px 6px", fontSize:"0.78rem" }}>
                                  {istVorschau ? "✕" : "👁"}
                                </Btn>
                              )}
                              <Btn size="sm" variant="secondary" title="Download" onClick={async () => {
                                try {
                                  await apiEakte.download(akteId, ed.nr, ed.anzeigename);
                                } catch {
                                  setToast("Download fehlgeschlagen – Volume-Mount prüfen");
                                }
                              }}>{Ic.download}</Btn>
                            </div>
                          </div>
                          {/* Inline-Vorschau */}
                          {istVorschau && ed.dateityp === "pdf" && (
                            <div style={{ borderBottom:`1px solid ${T.border}`, background:T.offWhite, padding:"12px 1.4rem" }}>
                              {vorschauLaden && (
                                <div style={{ height:200, display:"flex", alignItems:"center", justifyContent:"center", color:T.textMuted }}>
                                  <div style={{ width:24, height:24, border:`3px solid ${T.goldTrim}`, borderTopColor:T.gold, borderRadius:"50%", animation:"spin 0.8s linear infinite", marginRight:10 }} />
                                  PDF wird geladen…
                                </div>
                              )}
                              {!vorschauLaden && vorschauUrl && (
                                <iframe
                                  src={vorschauUrl}
                                  style={{ width:"100%", height:600, border:`1px solid ${T.border}`, borderRadius:8, background:T.white }}
                                  title={ed.anzeigename}
                                />
                              )}
                              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginTop:8 }}>
                                <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem", color:T.textFaint }}>
                                  {ed.anzeigename}
                                </span>
                                <Btn size="sm" variant="secondary" onClick={() => setEakteVorschau(null)}>Vorschau schließen</Btn>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}

                    {/* Pagination */}
                    {eakteGesamtSeiten > 1 && (
                      <div style={{ display:"flex", alignItems:"center", justifyContent:"center", gap:8, padding:"12px 1.4rem", borderTop:`1px solid ${T.border}`, background:T.surface }}>
                        <Btn size="sm" variant="secondary" disabled={eakteSeiteAktuell === 0}
                          onClick={() => setEakteSeite(s => Math.max(0, s - 1))}>
                          ← Zurück
                        </Btn>
                        <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.85rem", color:T.textMid }}>
                          Seite {eakteSeiteAktuell + 1} von {eakteGesamtSeiten}
                          <span style={{ color:T.textFaint, marginLeft:8 }}>
                            ({eakteGefiltert.length} Dokumente)
                          </span>
                        </span>
                        <Btn size="sm" variant="secondary" disabled={eakteSeiteAktuell >= eakteGesamtSeiten - 1}
                          onClick={() => setEakteSeite(s => Math.min(eakteGesamtSeiten - 1, s + 1))}>
                          Weiter →
                        </Btn>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </Card>
        )}

      </div>

      {/* ── Debug-Dialog: Kandidaten-Übersicht ──────────────────────────── */}
      {debugKandidaten && <KandidatenDebugDialog kandidaten={debugKandidaten} onClose={() => setDebugKandidaten(null)} />}
    </>
  );
}

// ── Positions-Labels ─────────────────────────────────────────────────────────
const _POS_LABEL = {
  rep_gutachten_netto:  "Reparaturkosten lt. Gutachten",
  rep_rechnung_netto:   "Reparaturkosten lt. Rechnung (netto)",
  rep_rechnung_brutto:  "Reparaturkosten lt. Rechnung (brutto)",
  wiederbeschaffung:    "Wiederbeschaffungswert",
  restwert:             "Restwert",
  wertminderung:        "Wertminderung",
  sv_kosten:            "SV-Kosten (brutto)",
  sv_kosten_netto:      "SV-Kosten (netto)",
  mietwagenkosten:      "Mietwagenkosten",
  mietwagenkosten_netto:"Mietwagenkosten (netto)",
  abschleppkosten:      "Abschleppkosten",
  standkosten:          "Standkosten",
  unkostenpauschale:    "Unkostenpauschale",
};
// Display-Key-Mapping (gleich wie in SchadenSection)
const _DISPLAY_KEY = {
  rep_rechnung_netto:    "rep_rechnung_brutto",
  mietwagenkosten_netto: "mietwagenkosten",
  abschleppkosten_netto: "abschleppkosten",
  standkosten_netto:     "standkosten",
  sv_kosten_netto:       "sv_kosten",
};

function KandidatenDebugDialog({ kandidaten, onClose }) {
  // Winner je Display-Key berechnen (gleiche Logik wie kandidatMap in SchadenSection)
  const winnerSet = useMemo(() => {
    const map = {};
    kandidaten.forEach(k => {
      if (!k.position_key) return;
      const dk = _DISPLAY_KEY[k.position_key] || k.position_key;
      if (!map[dk] || (k.konfidenz||0) > (map[dk].konfidenz||0)) map[dk] = k;
    });
    // Set aus Referenzen der Gewinner-Objekte
    return new Set(Object.values(map));
  }, [kandidaten]);

  // Gruppieren: position_key → Liste
  const gruppen = useMemo(() => {
    const g = {};
    kandidaten.forEach(k => {
      const dk = k.position_key ? (_DISPLAY_KEY[k.position_key] || k.position_key) : "__ref__";
      if (!g[dk]) g[dk] = [];
      g[dk].push(k);
    });
    // Jede Gruppe nach Konfidenz absteigend sortieren
    Object.values(g).forEach(arr => arr.sort((a,b) => (b.konfidenz||0)-(a.konfidenz||0)));
    return g;
  }, [kandidaten]);

  const gruppenKeys = Object.keys(gruppen).sort((a,b) => a === "__ref__" ? 1 : b === "__ref__" ? -1 : a.localeCompare(b));

  return (
    <div onClick={onClose} style={{
      position:"fixed", inset:0, background:"rgba(0,0,0,0.55)", zIndex:9999,
      display:"flex", alignItems:"center", justifyContent:"center", padding:16,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background:"#fff", borderRadius:12, width:"100%", maxWidth:860,
        maxHeight:"88vh", display:"flex", flexDirection:"column",
        boxShadow:"0 8px 40px rgba(0,0,0,0.28)",
      }}>
        {/* Header */}
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
          padding:"14px 20px", borderBottom:`1px solid ${T.border}` }}>
          <div>
            <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontWeight:700, fontSize:"1rem", color:T.text }}>
              🔍 Auto-Parser Debug – Kandidaten
            </div>
            <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem", color:T.textMuted, marginTop:2 }}>
              {kandidaten.length} Kandidat(en) · <strong style={{color:T.green}}>{winnerSet.size}</strong> werden an den Schadenreiter übergeben (fett markiert)
            </div>
          </div>
          <button onClick={onClose} style={{ background:"none", border:"none", cursor:"pointer",
            fontSize:"1.3rem", color:T.textMuted, lineHeight:1, padding:"4px 8px" }}>✕</button>
        </div>

        {/* Body */}
        <div style={{ overflowY:"auto", padding:"12px 20px", flex:1 }}>
          {gruppenKeys.map(dk => {
            const isRef = dk === "__ref__";
            const posLabel = isRef ? "Referenz-Dokumente (keine Positionszuweisung)"
              : (_POS_LABEL[dk] || dk);
            return (
              <div key={dk} style={{ marginBottom:16 }}>
                {/* Gruppen-Header */}
                <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.75rem",
                  fontWeight:700, textTransform:"uppercase", letterSpacing:"0.07em",
                  color: isRef ? T.textMuted : T.gold,
                  borderBottom:`2px solid ${isRef ? T.border : T.gold+"44"}`,
                  paddingBottom:4, marginBottom:6 }}>
                  {posLabel}
                </div>

                {/* Kandidaten-Zeilen */}
                {gruppen[dk].map((k, i) => {
                  const isWinner = winnerSet.has(k);
                  const konfPct = Math.round((k.konfidenz||0)*100);
                  const konfColor = konfPct >= 85 ? T.green : konfPct >= 65 ? T.amber : T.textMuted;
                  return (
                    <div key={i} style={{
                      display:"grid", gridTemplateColumns:"1fr 60px 90px 1fr 110px",
                      gap:"0 12px", alignItems:"center",
                      padding:"5px 8px", borderRadius:6,
                      background: isWinner ? T.green+"12" : (i%2===0 ? "#fafafa" : "#fff"),
                      border: isWinner ? `1px solid ${T.green}44` : "1px solid transparent",
                      fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.82rem",
                      fontWeight: isWinner ? 700 : 400,
                      color: T.text, marginBottom:3,
                    }}>
                      <span style={{ overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}
                        title={k.dateiname}>
                        {isWinner ? "★ " : ""}{k.dateiname || "—"}
                      </span>
                      <span style={{ fontSize:"0.72rem", color: k.quelle==="eakte" ? T.blue : T.textMuted,
                        fontWeight:600, textAlign:"center" }}>
                        {k.quelle === "eakte" ? "E-Akte" : "lokal"}
                      </span>
                      <span style={{ color:konfColor, fontWeight:700, textAlign:"right" }}>
                        {konfPct} %
                      </span>
                      <span style={{ fontSize:"0.75rem", color:T.textMuted, overflow:"hidden",
                        textOverflow:"ellipsis", whiteSpace:"nowrap" }}
                        title={k.grund}>
                        {k.grund}
                      </span>
                      <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.8rem",
                        textAlign:"right", color: k.betrag_vorschlag != null ? T.text : T.textFaint }}>
                        {k.betrag_vorschlag != null ? fmtEuro(k.betrag_vorschlag) : "kein Betrag"}
                      </span>
                    </div>
                  );
                })}
              </div>
            );
          })}
          {kandidaten.length === 0 && (
            <div style={{ textAlign:"center", padding:"2rem", color:T.textMuted,
              fontFamily:"'IBM Plex Sans',sans-serif" }}>
              Keine Kandidaten gefunden.
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding:"10px 20px", borderTop:`1px solid ${T.border}`,
          display:"flex", justifyContent:"flex-end" }}>
          <button onClick={onClose} style={{
            fontFamily:"'IBM Plex Sans',sans-serif", fontWeight:600, fontSize:"0.875rem",
            background:T.gold, color:"#fff", border:"none", borderRadius:7,
            padding:"7px 20px", cursor:"pointer",
          }}>
            Schließen
          </button>
        </div>
      </div>
    </div>
  );
}



export default DokumenteSection;
