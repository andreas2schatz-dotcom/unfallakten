import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { POSITION_LABELS_FE, POSITION_IST_ABZUG, ART_LABEL, ABRECHNUNG_ART_LABEL, POS_KUERZUNG_KATEGORIE, positionKuerzungBetrag, positionenVorlage, _mapPdfPos } from "../config/constants.js";
import { fmtEuro } from "../config/utils.js";
import { Card, CardHead, Btn, FieldInput, FieldSelect, Toast, SlidePanel } from "../components/common.jsx";
import {
  akten as apiAkten,
  kuerzungsarten as apiKuerzungsarten,
  abrechnungen as apiAbrechnungen,
  pruefberichte as apiPruefberichte,
  parsePdf as apiParsePdf,
  apiDistanz,
  apiStellungnahme,
  tokenStore,
  request,
} from "../api.js";

export function PositionenTabelle({ positionen, kuerzungsarten, akteId, abid, onUpdate, readOnly }) {
  const hatKuerzung = positionen.some(p => p.kuerzung_betrag > 0);

  // Task 8: Typ-Vorschläge aus dem verketteten Begründungsdokument + Pflicht-Begründung
  const [vorschlaege, setVorschlaege] = useState([]);
  const [entwurf, setEntwurf]         = useState(null);  // { posId, kuerzungsartId, freitext, typQuelle }
  const [speichert, setSpeichert]     = useState(false);
  const [toast, setToast]             = useState("");

  useEffect(() => {
    if (readOnly || !akteId || !abid) return;
    if (!positionen.some(p => positionKuerzungBetrag(p) > 0 && !p.kuerzungsart_id)) return;
    let aktiv = true;
    apiAbrechnungen.typVorschlaege(akteId, abid)
      .then(res => { if (aktiv) setVorschlaege(res?.vorschlaege || []); })
      .catch(() => {});
    return () => { aktiv = false; };
  }, [akteId, abid, readOnly]);

  const toggleKlage = async (pos) => {
    const neu = !pos.fuer_klage_vorgemerkt;
    try {
      await apiAbrechnungen.updatePos(akteId, abid, pos.id, { fuer_klage_vorgemerkt: neu });
    } catch { /* Demo */ }
    onUpdate(pos.id, { fuer_klage_vorgemerkt: neu });
  };

  const sendeKuerzungsart = async (pos, kid, freitext, typQuelle) => {
    const payload = { kuerzungsart_id: kid };
    if (kid) {
      payload.typ_quelle = typQuelle || "manuell";
      if (freitext != null) payload.kuerzung_freitext = freitext;
    }
    setSpeichert(true);
    try {
      await apiAbrechnungen.updatePos(akteId, abid, pos.id, payload);
    } catch (e) {
      setSpeichert(false);
      setToast(e?.message || "Speichern fehlgeschlagen — Begründung ist Pflicht.");
      return false;
    }
    setSpeichert(false);
    const art = kid ? kuerzungsarten.find(k => k.id === parseInt(kid)) : null;
    onUpdate(pos.id, {
      kuerzungsart_id: kid ? parseInt(kid) : null,
      kuerzungsart_bezeichnung: art?.bezeichnung || null,
      ...(kid && freitext != null ? { kuerzung_freitext: freitext } : {}),
    });
    setEntwurf(null);
    return true;
  };

  const setKuerzungsart = (pos, kid) => {
    if (!kid) { sendeKuerzungsart(pos, null); return; }
    if ((pos.kuerzung_freitext || "").trim()) {
      sendeKuerzungsart(pos, parseInt(kid), null, "manuell");
      return;
    }
    setEntwurf({ posId: pos.id, kuerzungsartId: parseInt(kid), freitext: "", typQuelle: "manuell" });
  };

  const uebernehmeVorschlag = (pos, v) => {
    setEntwurf({ posId: pos.id, kuerzungsartId: v.kuerzungsart_id,
                 freitext: v.snippet || "", typQuelle: v.quelle || "regel" });
  };

  if (!positionen.length) return (
    <div style={{ padding:"1rem", color:T.textFaint, fontFamily:T.fontBody, fontSize:"0.9rem" }}>
      Keine Positionen erfasst.
    </div>
  );

  return (
    <>
    {toast && <Toast msg={toast} onDone={() => setToast("")} />}
    <div style={{ overflowX:"auto" }}>
      <table style={{ width:"100%", borderCollapse:"collapse", fontFamily:T.fontBody, fontSize:"0.875rem" }}>
        <thead>
          <tr style={{ background:T.surface, borderBottom:`1px solid ${T.border}` }}>
            {["Position","Gefordert","Reguliert","Kürzung","Kürzungsart","Klage"].map(h => (
              <th key={h} style={{ padding:"7px 12px", textAlign:h==="Position"?"left":"right", fontWeight:600, color:T.textMuted, fontSize:"0.78rem", textTransform:"uppercase", letterSpacing:"0.05em", whiteSpace:"nowrap" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {positionen.map((pos, i) => {
            const kuerzung = positionKuerzungBetrag(pos);
            const istAbzug = POSITION_IST_ABZUG[pos.position_key];
            const isLast = i === positionen.length - 1;
            const istEntwurf = entwurf?.posId === pos.id;
            const zeigeVorschlaege = kuerzung > 0 && !pos.kuerzungsart_id && !readOnly
              && !istEntwurf && vorschlaege.length > 0;
            return (
              <React.Fragment key={pos.id ?? i}>
              <tr style={{ borderBottom:(isLast && !zeigeVorschlaege && !istEntwurf)?"none":`1px solid ${T.border}`, background:pos.fuer_klage_vorgemerkt?"rgba(160,107,74,0.06)":"transparent" }}>
                <td style={{ padding:"8px 12px", color:T.text, fontWeight:500 }}>
                  {POSITION_LABELS_FE[pos.position_key] || pos.position_key}
                  {pos.sv_stellungnahme_ausstehend && (
                    <span style={{ marginLeft:6, fontSize:"0.72rem", background:T.amberBg, color:T.amber, borderRadius:4, padding:"1px 5px" }}>SV ausstehend</span>
                  )}
                </td>
                <td style={{ padding:"8px 12px", textAlign:"right", fontFamily:"ui-monospace,monospace", color:T.textMid }}>
                  {fmtEuro(pos.betrag_gefordert)}
                </td>
                <td style={{ padding:"8px 12px", textAlign:"right", fontFamily:"ui-monospace,monospace", color:T.green, fontWeight:600 }}>
                  {fmtEuro(pos.betrag_reguliert)}
                </td>
                <td style={{ padding:"8px 12px", textAlign:"right", fontFamily:"ui-monospace,monospace", color:kuerzung>0?T.red:T.textFaint, fontWeight:kuerzung>0?600:400 }}>
                  {kuerzung > 0
                    ? `${istAbzug ? "+" : "−"}${fmtEuro(kuerzung)}`
                    : "—"}
                </td>
                <td style={{ padding:"8px 12px", minWidth:180 }}>
                  {kuerzung > 0 && !readOnly ? (
                    <select
                      value={istEntwurf ? String(entwurf.kuerzungsartId) : (pos.kuerzungsart_id || "")}
                      onChange={e => setKuerzungsart(pos, e.target.value)}
                      style={{ width:"100%", padding:"4px 6px", border:`1px solid ${T.border}`, borderRadius:5, fontSize:"0.82rem", background:T.surface, color:pos.kuerzungsart_id?T.text:T.textFaint, cursor:"pointer" }}
                    >
                      <option value="">— Kürzungsart wählen —</option>
                      {kuerzungsarten.map(k => (
                        <option key={k.id} value={k.id}>{k.bezeichnung}</option>
                      ))}
                    </select>
                  ) : pos.kuerzungsart_bezeichnung ? (
                    <span style={{ fontSize:"0.82rem", color:T.textMid }}>{pos.kuerzungsart_bezeichnung}</span>
                  ) : (
                    <span style={{ color:T.textFaint }}>—</span>
                  )}
                </td>
                <td style={{ padding:"8px 12px", textAlign:"right" }}>
                  {kuerzung > 0 && (
                    <button
                      onClick={() => !readOnly && toggleKlage(pos)}
                      title={pos.fuer_klage_vorgemerkt ? "Aus Klage entfernen" : "Für Klage vormerken"}
                      style={{ background:pos.fuer_klage_vorgemerkt?T.accent:"transparent", border:`1px solid ${pos.fuer_klage_vorgemerkt?T.accent:T.border}`, borderRadius:5, padding:"3px 8px", fontSize:"0.78rem", color:pos.fuer_klage_vorgemerkt?T.white:T.textMuted, cursor:readOnly?"default":"pointer", fontFamily:T.fontBody, fontWeight:600, transition:"all 0.15s" }}
                    >
                      {pos.fuer_klage_vorgemerkt ? "✓ Klage" : "Klage"}
                    </button>
                  )}
                </td>
              </tr>
              {zeigeVorschlaege && (
                <tr style={{ borderBottom:isLast?"none":`1px solid ${T.border}` }}>
                  <td colSpan={6} style={{ padding:"4px 12px 8px", background:T.surface }}>
                    <span style={{ fontSize:"0.75rem", color:T.textMuted, marginRight:8 }}>Vorschlag:</span>
                    {vorschlaege.filter(v => v.kuerzungsart_id).map(v => {
                      const art = kuerzungsarten.find(k => k.id === v.kuerzungsart_id);
                      return (
                        <button
                          key={v.typ_code}
                          onClick={() => uebernehmeVorschlag(pos, v)}
                          title={v.snippet}
                          style={{ marginRight:6, marginBottom:2, background:T.amberBg,
                                   border:`1px solid ${T.amber}66`, borderRadius:12,
                                   padding:"2px 10px", fontSize:"0.78rem", color:T.textMid,
                                   cursor:"pointer", fontFamily:T.fontBody }}
                        >
                          {art?.bezeichnung || v.typ_code} ({v.typ_code})
                        </button>
                      );
                    })}
                  </td>
                </tr>
              )}
              {istEntwurf && (
                <tr style={{ borderBottom:isLast?"none":`1px solid ${T.border}` }}>
                  <td colSpan={6} style={{ padding:"6px 12px 10px", background:T.surface }}>
                    <div style={{ fontSize:"0.78rem", color:T.textMuted, marginBottom:4 }}>
                      Begründung (Wortlaut des Versicherers) — Pflicht:
                    </div>
                    <textarea
                      value={entwurf.freitext}
                      onChange={e => setEntwurf({ ...entwurf, freitext: e.target.value })}
                      rows={2}
                      aria-label="Begründung"
                      style={{ width:"100%", padding:"6px 8px", fontSize:"0.85rem",
                               fontFamily:T.fontBody, borderRadius:5, resize:"vertical",
                               border:`1px solid ${entwurf.freitext.trim() ? T.border : T.red}` }}
                    />
                    <div style={{ display:"flex", gap:8, marginTop:4 }}>
                      <Btn size="sm" variant="primary"
                        disabled={!entwurf.freitext.trim() || speichert}
                        onClick={() => sendeKuerzungsart(pos, entwurf.kuerzungsartId,
                                                         entwurf.freitext.trim(), entwurf.typQuelle)}>
                        {speichert ? "⟳ Speichere…" : "Übernehmen"}
                      </Btn>
                      <Btn size="sm" variant="secondary" onClick={() => setEntwurf(null)}>
                        Abbrechen
                      </Btn>
                    </div>
                  </td>
                </tr>
              )}
              </React.Fragment>
            );
          })}
        </tbody>
        <tfoot>
          <tr style={{ background:T.surface, borderTop:`2px solid ${T.border}` }}>
            <td style={{ padding:"8px 12px", fontWeight:700, color:T.text, fontFamily:T.fontBody }}>Gesamt</td>
            <td style={{ padding:"8px 12px", textAlign:"right", fontFamily:"ui-monospace,monospace", fontWeight:700, color:T.text }}>
              {fmtEuro(positionen.reduce((s,p) => s + p.betrag_gefordert, 0))}
            </td>
            <td style={{ padding:"8px 12px", textAlign:"right", fontFamily:"ui-monospace,monospace", fontWeight:700, color:T.green }}>
              {fmtEuro(positionen.reduce((s,p) => s + p.betrag_reguliert, 0))}
            </td>
            <td style={{ padding:"8px 12px", textAlign:"right", fontFamily:"ui-monospace,monospace", fontWeight:700, color:T.red }}>
              {positionen.reduce((s,p) => s + positionKuerzungBetrag(p), 0) > 0
                ? `−${fmtEuro(positionen.reduce((s,p) => s + positionKuerzungBetrag(p), 0))}`
                : "—"}
            </td>
            <td colSpan={2} />
          </tr>
        </tfoot>
      </table>
    </div>
    </>
  );
}



function PdfAuswahlZeile({ dok, akteId, setDn, setPhase, setFehler, setErg, setSelPos, setLlmWahl, setSchritte, dispatch }) {
  const quelleLabel = dok.quelle === "eakte" ? "E-Akte" : "Hochgeladen";
  return (
    <button onClick={() => {
      setDn(dok.dateiname);
      setPhase("loading");
      setFehler("");
      setSchritte([]);
      apiParsePdf.parseStream(akteId, dok.id, (data) => {
        if (data.schritt === "ocr") {
          setSchritte(prev => {
            const filtered = prev.filter(s => s.schritt !== "ocr");
            return [...filtered, data];
          });
        } else if (data.schritt === "parsen") {
          setSchritte(prev => {
            const filtered = prev.filter(s => s.schritt !== "parsen");
            return [...filtered, data];
          });
        } else if (data.schritt === "fertig") {
          const ergebnis = data.ergebnis || {};
          setErg({...ergebnis, _dok_id: data.dokument_id || dok.id});
          const sel = {};
          (ergebnis.positionen || []).forEach((p, i) => { sel[i] = true; });
          setSelPos(sel);
          setLlmWahl({});
          setPhase("preview");
          if (dispatch) {
            apiAkten.aktivitaeten(akteId).then(aktData => {
              if (aktData?.aktivitaeten)
                dispatch({ type:"SET_AKTIVITAETEN", akteId, aktivitaeten:aktData.aktivitaeten });
            }).catch(() => {});
          }
        } else if (data.schritt === "fehler") {
          setFehler(data.meldung || "Unbekannter Fehler");
          setPhase("error");
        }
      });
    }}
      style={{ display:"flex", alignItems:"center", gap:10, padding:"9px 12px",
        background:T.cardBg, border:`1px solid ${T.border}`, borderRadius:7,
        fontFamily:T.fontBody, fontSize:"0.875rem",
        color:T.text, cursor:"pointer", textAlign:"left", width:"100%",
        transition:"border-color 0.15s", marginBottom:4 }}
      onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent; e.currentTarget.style.background = T.accentPale; }}
      onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.background = T.cardBg; }}>
      <span style={{ color:T.red, fontSize:"1rem", flexShrink:0 }}>📄</span>
      <div style={{ flex:1, minWidth:0, textAlign:"left" }}>
        <div style={{ overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", fontWeight:600 }}>{dok.dateiname}</div>
        <div style={{ fontSize:"0.75rem", color:T.textFaint }}>{quelleLabel}{dok.hochgeladen_am ? " · " + String(dok.hochgeladen_am).slice(0,10) : ""}</div>
      </div>
      <span style={{ fontSize:"0.78rem", fontWeight:600, color:T.blue, flexShrink:0 }}>Auswählen →</span>
    </button>
  );
}

function PdfImportDialog({ akteId, kuerzungsarten, schaden, onImport, onSavePruefbericht, onCancel, dispatch, dokumente, mandantAdresse }) {
  const vorhandenePdfs = (dokumente || []).filter(d => d.dateityp === "pdf");
  // Gruppiert: Abrechnungsschreiben + Prüfberichte zuerst, dann Rest
  const abrDoks = vorhandenePdfs.filter(d => d.dokumentenklasse === "abrechnungsschreiben" || d.typ === "abrechnungsschreiben");
  const pbDoks  = vorhandenePdfs.filter(d => d.dokumentenklasse === "pruefbericht" || d.typ === "pruefbericht");
  const sonstigeDoks = vorhandenePdfs.filter(d =>
    !(d.dokumentenklasse === "abrechnungsschreiben" || d.typ === "abrechnungsschreiben") &&
    !(d.dokumentenklasse === "pruefbericht" || d.typ === "pruefbericht"));
  const startPhase = vorhandenePdfs.length > 0 ? "auswahl" : "upload";

  const [phase, setPhase]         = useState(startPhase);
  const [ergebnis, setErg]        = useState(null);
  const [fehler, setFehler]       = useState("");
  const [dateiname, setDn]        = useState("");
  const [parseSchritte, setSchritte] = useState([]);
  const [llmWahl, setLlmWahl] = useState({});  // { posIndex: 'ki' } – PRD-31
  const fileRef                   = useRef();

  // Übernahme-State: welche Positionen soll das Formular vorab ausfüllen?
  const [selectedPos, setSelPos] = useState({});

  // Inline-Entfernungsprüfung im Dialog
  const [verweisImDialog, setVerweisImDialog]   = useState(null);
  const [verweisDialogLaden, setVerweisDialogLaden] = useState(false);
  const [verweisDebug, setVerweisDebug]         = useState(null);
  const [debugLaden, setDebugLaden]             = useState(false);

  const handleDatei = async (datei) => {
    if (!datei) return;
    setDn(datei.name);
    setPhase("loading");
    setFehler("");
    setLlmWahl({});
    try {
      const res = await apiParsePdf.parse(akteId, datei);
      setErg({...res.ergebnis, _dok_id: res.dokument?.id});
      // Alle Positionen standardmäßig ausgewählt
      const sel = {};
      (res.ergebnis?.positionen || []).forEach((p, i) => { sel[i] = true; });
      setSelPos(sel);
      setPhase("preview");
      // Chronik sofort aktualisieren – Backend hat bereits logge_aktivitaet geschrieben
      if (dispatch) {
        try {
          const aktData = await apiAkten.aktivitaeten(akteId);
          if (aktData?.aktivitaeten) {
            dispatch({ type: "SET_AKTIVITAETEN", akteId, aktivitaeten: aktData.aktivitaeten });
          }
        } catch { /* Chronik-Refresh nicht kritisch */ }
      }
    } catch (e) {
      setFehler(e.message || "Unbekannter Fehler");
      setPhase("error");
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f?.name.toLowerCase().endsWith(".pdf")) handleDatei(f);
  };

  // Aus dem Parse-Ergebnis ein Abrechnungs-Formular vorbelegen
  const prüfeEntfernungImDialog = async () => {
    if (!ergebnis) return;
    const rw = ergebnis.referenzwerkstatt;
    if (!rw?.name && !rw?.adresse) return;
    setVerweisDialogLaden(true);
    try {
      // Werkstatt-Adresse zusammenbauen
      const werkstattAdresse = [rw.name, rw.adresse, rw.plz_ort].filter(Boolean).join(", ");
      // Mandant aus beteiligte (wird via prop weitergegeben)
      // Direkt prüfen via POST
      const result = await request('/distanz/prüfen', {
        method: 'POST',
        body: JSON.stringify({
          mandant_adresse:   mandantAdresse || "",
          werkstatt_adresse: werkstattAdresse,
          werkstatt_name:    rw.name || "",
          km_genannt:        rw.entfernung_km || null,
        }),
      });
      setVerweisImDialog(result);
    } catch(e) {
      setVerweisImDialog({ fehler: e?.message || "Prüfung fehlgeschlagen" });
    } finally {
      setVerweisDialogLaden(false);
    }
  };

  const zeigeDebug = async () => {
    if (!ergebnis) return;
    const rw = ergebnis.referenzwerkstatt;
    if (!rw) return;
    setDebugLaden(true); setVerweisDebug(null);
    try {
      const werkstattAdresse = [rw.name, rw.adresse, rw.plz_ort].filter(Boolean).join(", ");
      const res = await request('/distanz/debug', {
        method: 'POST',
        body: JSON.stringify({
          mandant_adresse:   mandantAdresse || "",
          werkstatt_adresse: werkstattAdresse,
          werkstatt_name:    rw.name || "",
        }),
      });
      setVerweisDebug(res);
    } catch(e) {
      setVerweisDebug({ fehler: e?.message || "Debug fehlgeschlagen" });
    } finally { setDebugLaden(false); }
  };

  const handleUebernehmen = () => {
    if (!ergebnis) return;
    const llmMap = {};
    (ergebnis.llm_positionen || []).forEach(p => {
      if (p.art && !(p.art in llmMap)) llmMap[p.art] = p.betrag_netto ?? p.betrag_brutto ?? null;
    });
    const rawPos = (ergebnis.positionen || [])
      .map((p, i) => ({ p, i }))
      .filter(({ i }) => selectedPos[i])
      .map(({ p, i }) => {
        const kiWert = llmMap[p.art] ?? null;
        if (llmWahl[i] === 'ki' && kiWert != null) {
          return { ...p, betrag_netto: kiWert, betrag_brutto: null, hinweis: "KI-Parsing" };
        }
        return p;
      });
    onImport({
      versicherung: ergebnis.versicherer   || "",
      referenz_nr:  ergebnis.schadennummer || "",
      datum:        ergebnis.schreibdatum  || "",
      positionen:   rawPos,
      _dok_id:      ergebnis._dok_id       || null,
    });
  };

  // Mapping von Parser-Art → Formular-Art
  function artToFormArt(art) {
    const MAP = {
      reparatur_brutto:  "reparaturkosten",
      reparatur_netto:   "reparaturkosten",
      sv_kosten:         "sv_kosten",
      wbw:               "wiederbeschaffungswert",
      wbw_netto:         "wiederbeschaffungswert",
      wbw_brutto:        "wiederbeschaffungswert",
      restwert:          "restwert",
      wba:               "wba",
      fahrzeugschaden:   "fahrzeugschaden",
      kostenpauschale:   "kostenpauschale",
      wertminderung:     "wertminderung",
      ra_gebuehren:      "ra_gebuehren",
    };
    return MAP[art] || "sonstiges";
  }

  const konfidenzFarbe = (k) => k >= 0.8 ? T.green : k >= 0.5 ? T.amber : T.red;

  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`,
      borderRadius: 8, padding: 24, marginBottom: 16,
    }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:20 }}>
        <h3 style={{ margin:0, color:T.accent, fontSize:16, fontWeight:600 }}>
          📄 Versicherungs-PDF importieren
        </h3>
        <Btn variant="ghost" size="sm" onClick={onCancel}>✕</Btn>
      </div>

      {/* ── Phase: Auswahl (vorhandene PDFs, gruppiert) ── */}
      {phase === "auswahl" && (
        <div>
          {abrDoks.length > 0 && (
            <div style={{ marginBottom:10 }}>
              <div style={{ fontSize:"0.78rem", color:T.textFaint, marginBottom:4, textTransform:"uppercase", letterSpacing:"0.06em" }}>
                Abrechnungsschreiben ({abrDoks.length})
              </div>
              {abrDoks.map(dok => (
                <PdfAuswahlZeile key={dok.id} dok={dok} akteId={akteId} setDn={setDn} setPhase={setPhase} setFehler={setFehler} setErg={setErg} setSelPos={setSelPos} setLlmWahl={setLlmWahl} setSchritte={setSchritte} dispatch={dispatch} />
              ))}
            </div>
          )}
          {pbDoks.length > 0 && (
            <div style={{ marginBottom:10 }}>
              <div style={{ fontSize:"0.78rem", color:T.textFaint, marginBottom:4, textTransform:"uppercase", letterSpacing:"0.06em" }}>
                Prüfberichte ({pbDoks.length})
              </div>
              {pbDoks.map(dok => (
                <PdfAuswahlZeile key={dok.id} dok={dok} akteId={akteId} setDn={setDn} setPhase={setPhase} setFehler={setFehler} setErg={setErg} setSelPos={setSelPos} setLlmWahl={setLlmWahl} setSchritte={setSchritte} dispatch={dispatch} />
              ))}
            </div>
          )}
          {sonstigeDoks.length > 0 && (
            <div style={{ marginBottom:10 }}>
              <div style={{ fontSize:"0.78rem", color:T.textFaint, marginBottom:4, textTransform:"uppercase", letterSpacing:"0.06em" }}>
                {(abrDoks.length > 0 || pbDoks.length > 0) ? "Weitere PDFs" : "Vorhandene PDFs"} ({sonstigeDoks.length})
              </div>
              {sonstigeDoks.map(dok => (
                <PdfAuswahlZeile key={dok.id} dok={dok} akteId={akteId} setDn={setDn} setPhase={setPhase} setFehler={setFehler} setErg={setErg} setSelPos={setSelPos} setLlmWahl={setLlmWahl} setSchritte={setSchritte} dispatch={dispatch} />
              ))}
            </div>
          )}
          <button onClick={() => setPhase("upload")}
            style={{ display:"flex", alignItems:"center", gap:7, padding:"7px 14px",
              background:"none", border:`1px dashed ${T.border}`, borderRadius:7,
              fontFamily:T.fontBody, fontSize:"0.855rem",
              color:T.textMuted, cursor:"pointer", width:"100%", marginTop:6 }}
            onMouseEnter={e => e.currentTarget.style.borderColor = T.accent}
            onMouseLeave={e => e.currentTarget.style.borderColor = T.border}>
            <span>📂</span> Neue PDF-Datei hochladen
          </button>
        </div>
      )}

      {/* ── Phase: Upload ── */}
      {phase === "upload" && (
        <div
          onDrop={handleDrop}
          onDragOver={e => e.preventDefault()}
          onClick={() => fileRef.current?.click()}
          style={{
            border: `2px dashed ${T.border}`, borderRadius: 8,
            padding: "40px 24px", textAlign: "center",
            cursor: "pointer", color: T.textMuted,
            transition: "border-color .2s",
          }}
          onMouseEnter={e => e.currentTarget.style.borderColor = T.accent}
          onMouseLeave={e => e.currentTarget.style.borderColor = T.border}
        >
          <div style={{ fontSize: 36, marginBottom: 12 }}>📂</div>
          <div style={{ fontWeight: 600, color: T.text, marginBottom: 6 }}>
            PDF hierher ziehen oder klicken
          </div>
          <div style={{ fontSize: 13 }}>
            Abrechnungsschreiben oder Prüfbericht (max. 20 MB)
          </div>
          <input
            ref={fileRef} type="file" accept=".pdf"
            style={{ display:"none" }}
            onChange={e => handleDatei(e.target.files[0])}
          />
        </div>
      )}

      {/* ── Phase: Laden ── */}
      {phase === "loading" && (
        <div style={{ textAlign:"center", padding:"32px 0", color:T.textMuted }}>
          <div style={{ fontSize:28, marginBottom:10 }}>⏳</div>
          <div style={{ fontWeight:600, color:T.text, marginBottom:16 }}>{dateiname}</div>
          {parseSchritte.length === 0 ? (
            <div style={{ color:T.textMuted, fontSize:"0.9rem" }}>Analysiere PDF…</div>
          ) : (
            <div style={{
              display:"inline-flex", flexDirection:"column", gap:6,
              textAlign:"left", minWidth:220,
            }}>
              {parseSchritte.map((s, i) => {
                const fertig = s.status === "fertig";
                const fehler = s.status === "fehler" || s.status === "nicht_verfuegbar";
                const label = {
                  ocr:    fertig ? `OCR abgeschlossen (${(s.zeichen||0).toLocaleString("de-DE")} Zeichen)` : fehler ? "OCR fehlgeschlagen" : "OCR läuft…",
                  parsen: fertig ? `Geparst: ${s.klasse || "unbekannt"}` : "Dokument analysieren…",
                }[s.schritt] || s.schritt;
                return (
                  <div key={i} style={{
                    display:"flex", alignItems:"center", gap:8,
                    fontSize:"0.875rem", color: fehler ? T.red : fertig ? T.green : T.textMid,
                  }}>
                    <span style={{ flexShrink:0, fontSize:"1rem" }}>
                      {fehler ? "✗" : fertig ? "✓" : "⟳"}
                    </span>
                    <span>{label}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Phase: Fehler ── */}
      {phase === "error" && (
        <div style={{ padding:16, background:"#2a1515", borderRadius:6, color:T.red }}>
          <strong>Fehler:</strong> {fehler}
          <div style={{ marginTop:12 }}>
            <Btn size="sm" onClick={() => setPhase("upload")}>Erneut versuchen</Btn>
          </div>
        </div>
      )}

      {/* ── Phase: Vorschau ── */}
      {phase === "preview" && ergebnis && (
        <div>
          {/* Metadaten-Zeile */}
          <div style={{
            display:"flex", gap:12, flexWrap:"wrap", marginBottom:16,
            padding:"12px 16px", background:T.bg, borderRadius:6,
          }}>
            <span style={{ color:T.textMuted, fontSize:13 }}>
              <strong style={{ color:T.text }}>
                {ergebnis.versicherer || "Versicherer unbekannt"}
              </strong>
            </span>
            {ergebnis.schadennummer && (
              <span style={{ fontSize:13, color:T.textMuted }}>
                Schaden-Nr.: <strong style={{ color:T.text, fontFamily:"monospace" }}>
                  {ergebnis.schadennummer}
                </strong>
              </span>
            )}
            {ergebnis.schreibdatum && (
              <span style={{ fontSize:13, color:T.textMuted }}>
                Datum: <strong style={{ color:T.text }}>{ergebnis.schreibdatum}</strong>
              </span>
            )}
            {ergebnis.abrechnungsart && ergebnis.abrechnungsart !== "unbekannt" && (
              <span style={{
                fontSize:12, padding:"2px 8px", borderRadius:4,
                background:T.surface, border:`1px solid ${T.border}`,
                color:T.accent, fontWeight:600,
              }}>
                {ABRECHNUNG_ART_LABEL[ergebnis.abrechnungsart] || ergebnis.abrechnungsart}
              </span>
            )}
            <span style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:8 }}>
              {ergebnis._dok_id && (() => {
                const token = tokenStore.getAccess() || "";
                const url = `/akten/${akteId}/dokumente/${ergebnis._dok_id}/datei${token ? "?token=" + encodeURIComponent(token) : ""}`;
                return (
                  <a href={url} target="_blank" rel="noopener noreferrer" style={{
                    display:"inline-flex", alignItems:"center", gap:4,
                    padding:"3px 9px", borderRadius:4, fontSize:11, fontWeight:600,
                    background:T.surface, border:`1px solid ${T.border}`,
                    color:T.textMid, textDecoration:"none", letterSpacing:"0.02em",
                    transition:"border-color .15s, color .15s",
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent; e.currentTarget.style.color = T.accent; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.color = T.textMid; }}
                  title="PDF in neuem Tab öffnen">
                    ↗ PDF
                  </a>
                );
              })()}
              {ergebnis.llm_verwendet && !ergebnis.llm_konflikt && (
                <span title="Gemma stimmt mit Regex-Parser überein" style={{
                  background: "rgba(139,92,246,0.18)",
                  color: "#c4b5fd",
                  border: "1px solid rgba(139,92,246,0.35)",
                  borderRadius: 4, fontSize: 11, fontWeight: 600,
                  padding: "2px 7px", letterSpacing: "0.03em",
                }}>
                  ✦ Gemma ✓
                </span>
              )}
              {ergebnis.llm_verwendet && ergebnis.llm_konflikt && (
                <span style={{
                  background: "rgba(245,158,11,0.15)", color: "#f59e0b",
                  border: "1px solid rgba(245,158,11,0.4)",
                  borderRadius: 4, fontSize: 11, fontWeight: 600,
                  padding: "2px 7px",
                }}>
                  ⚠ KI-Konflikt – wähle pro Position
                </span>
              )}
              <span style={{ fontSize:12, color:konfidenzFarbe(ergebnis.parse_konfidenz) }}>
                Konfidenz: {Math.round((ergebnis.parse_konfidenz || 0) * 100)}%
              </span>
            </span>
          </div>

          {/* Warnungen */}
          {(ergebnis.warnungen || []).length > 0 && (
            <div style={{ background:"#2a2200", borderRadius:6, padding:"10px 14px", marginBottom:12, color:T.amber, fontSize:13 }}>
              {ergebnis.warnungen.map((w, i) => <div key={i}>⚠ {w}</div>)}
            </div>
          )}

          {/* Dokumenttyp-spezifische Ansicht */}
          {ergebnis.dokumenttyp === "abrechnungsschreiben" && (
            <AbrechnungVorschau
              ergebnis={ergebnis}
              selectedPos={selectedPos}
              setSelPos={setSelPos}
              llmWahl={llmWahl}
              setLlmWahl={setLlmWahl}
            />
          )}
          {ergebnis.dokumenttyp === "pruefbericht" && (
            <PruefberichtVorschau
              ergebnis={ergebnis}
              onPrüfeEntfernung={mandantAdresse ? prüfeEntfernungImDialog : null}
              verweisErgebnis={verweisImDialog}
              verweisLaden={verweisDialogLaden}
              onZeigeDebug={mandantAdresse ? zeigeDebug : null}
              debugLaden={debugLaden}
              debugErgebnis={verweisDebug}
            />
          )}
          {ergebnis.dokumenttyp === "unbekannt" && (
            <div style={{ color:T.textMuted, padding:16, textAlign:"center" }}>
              Dokumenttyp konnte nicht erkannt werden. Bitte manuell erfassen.
            </div>
          )}

          {/* Aktions-Leiste */}
          <div style={{ display:"flex", gap:8, marginTop:16, paddingTop:16, borderTop:`1px solid ${T.border}` }}>
            {ergebnis.dokumenttyp === "abrechnungsschreiben" && (
              <Btn onClick={handleUebernehmen}>
                ✓ Ausgewählte Positionen übernehmen
              </Btn>
            )}
            {ergebnis.dokumenttyp === "pruefbericht" && onSavePruefbericht && (
              <Btn onClick={() => {
                const rw = ergebnis.referenzwerkstatt;
                onSavePruefbericht({
                  pruefdienstleister:          ergebnis.pruefdienstleister || ergebnis.versicherer_kuerzel || "",
                  vorgangsnummer:              ergebnis.vorgangsnummer || "",
                  datum:                       ergebnis.schreibdatum || "",
                  schadennummer:               ergebnis.schadennummer || "",
                  reparaturkosten_vor_pruefung: ergebnis.reparaturkosten_netto_vor_pruefung,
                  abzug_technisch:             ergebnis.abzug_technisch,
                  abzug_werkstattalternative:  ergebnis.abzug_werkstattalternative,
                  abzug_gesamt:                ergebnis.abzug_gesamt,
                  reparaturkosten_nach_pruefung: ergebnis.reparaturkosten_nach_pruefung,
                  referenzwerkstatt_name:      rw?.name || "",
                  referenzwerkstatt_adresse:   rw?.adresse || "",
                  referenzwerkstatt_plz_ort:   rw?.plz_ort || "",
                  referenzwerkstatt_entfernung: rw?.entfernung_km,
                  ist_image_pdf:               ergebnis.ist_image_pdf || false,
                  fahrzeug_hersteller:         ergebnis.fahrzeug?.hersteller || "",
                  fahrzeug_typ:                ergebnis.fahrzeug?.typ || "",
                  fahrzeug_kennzeichen:        ergebnis.fahrzeug?.kennzeichen || "",
                  kuerzungen:                  ergebnis.kuerzungen || [],
                });
                onCancel();
              }}>
                💾 Prüfbericht speichern
              </Btn>
            )}
            <Btn variant="secondary" onClick={() => { setPhase("upload"); setErg(null); }}>
              Andere Datei
            </Btn>
            <Btn variant="ghost" onClick={onCancel} style={{ marginLeft:"auto" }}>
              Abbrechen
            </Btn>
          </div>
        </div>
      )}
    </div>
  );
}


function AbrechnungVorschau({ ergebnis, selectedPos, setSelPos, llmWahl, setLlmWahl }) {
  const positionen    = ergebnis.positionen    || [];
  const zahlungen     = ergebnis.zahlungen     || [];
  const llmPositionen = ergebnis.llm_positionen || [];
  const hatKI         = ergebnis.llm_verwendet && llmPositionen.length > 0;
  const hatKonflikt   = hatKI && !!ergebnis.llm_konflikt;

  // KI-Lookup: art → erster passender Betrag (netto bevorzugt)
  const llmMap = {};
  llmPositionen.forEach(p => {
    if (p.art && !(p.art in llmMap)) {
      llmMap[p.art] = p.betrag_netto ?? p.betrag_brutto ?? null;
    }
  });

  const thStyle = { padding:"7px 10px", textAlign:"right", color:T.textMuted, fontWeight:500, fontSize:12, whiteSpace:"nowrap" };
  const tdMono  = { padding:"7px 10px", textAlign:"right", fontFamily:"monospace", fontSize:13 };

  return (
    <div>
      {positionen.length > 0 ? (
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13, marginBottom:12 }}>
          <thead>
            <tr style={{ background:T.surface }}>
              <th style={{ padding:"7px 10px", textAlign:"left", color:T.textMuted, fontWeight:500, width:32 }}></th>
              <th style={{ padding:"7px 10px", textAlign:"left", color:T.textMuted, fontWeight:500, fontSize:12 }}>Position</th>
              {hatKI && (
                <th style={{ ...thStyle, color:"#a78bfa" }} title="Qwen KI-Erkennung">
                  ✦ KI
                </th>
              )}
              <th style={thStyle}>Regex</th>
              <th style={{ ...thStyle, color:T.accent }}>Vorschlag</th>
              <th style={{ padding:"7px 10px", textAlign:"left", color:T.textMuted, fontWeight:500, fontSize:12 }}>Hinweis</th>
              {hatKonflikt && (
                <th style={{ ...thStyle, color:"#f59e0b" }}>Wählen</th>
              )}
            </tr>
          </thead>
          <tbody>
            {positionen.map((p, i) => {
              const regexBetrag   = p.betrag_netto ?? p.betrag_brutto ?? null;
              const llmBetrag     = llmMap[p.art] ?? null;
              const abweichung    = hatKI && llmBetrag != null && regexBetrag != null
                ? Math.abs(llmBetrag - regexBetrag) > 1.0
                : false;
              const kiGew = abweichung && llmWahl && llmWahl[i] === 'ki';
              const vorschlag = kiGew ? llmBetrag : regexBetrag;
              return (
                <tr key={i} style={{ borderTop:`1px solid ${T.border}` }}>
                  <td style={{ padding:"7px 10px" }}>
                    <input
                      type="checkbox"
                      checked={!!selectedPos[i]}
                      onChange={e => setSelPos(s => ({ ...s, [i]: e.target.checked }))}
                      style={{ accentColor: T.accent }}
                    />
                  </td>
                  <td style={{ padding:"7px 10px", color:T.text }}>
                    {ART_LABEL[p.art] || p.art}
                  </td>
                  {hatKI && (
                    <td style={{ ...tdMono, color: abweichung ? "#f59e0b" : "#a78bfa" }}
                        title={abweichung ? "Abweichung zum Regex-Wert" : "Übereinstimmung"}>
                      {llmBetrag != null ? fmtEuro(llmBetrag) : "—"}
                    </td>
                  )}
                  <td style={{ ...tdMono, color:T.textMuted }}>
                    {regexBetrag != null ? fmtEuro(regexBetrag) : "—"}
                  </td>
                  <td style={{ ...tdMono, fontWeight:600, color: kiGew ? "#a78bfa" : T.accent }}>
                    {vorschlag != null ? fmtEuro(vorschlag) : "—"}
                  </td>
                  <td style={{ padding:"7px 10px", color:T.textMuted, fontSize:12 }}>
                    {p.hinweis || ""}
                    {p.pruefbericht_abzug ? ` (PB-Abzug: −${fmtEuro(p.pruefbericht_abzug)})` : ""}
                  </td>
                  {hatKonflikt && (
                    <td style={{ padding:"5px 8px", whiteSpace:"nowrap" }}>
                      {abweichung ? (
                        <>
                          <button
                            onClick={() => setLlmWahl(w => { const nw = {...w}; delete nw[i]; return nw; })}
                            style={{
                              padding:"2px 7px", fontSize:11, fontWeight:600, borderRadius:4,
                              cursor:"pointer", background:"transparent",
                              border: !kiGew ? `1.5px solid ${T.green}` : `1px solid ${T.border}`,
                              color: !kiGew ? T.green : T.textMid,
                            }}
                          >Regex</button>
                          {' '}
                          <button
                            onClick={() => setLlmWahl(w => ({ ...w, [i]: 'ki' }))}
                            style={{
                              padding:"2px 7px", fontSize:11, fontWeight:600, borderRadius:4,
                              cursor:"pointer", background:"transparent",
                              border: kiGew ? `1.5px solid #a78bfa` : `1px solid ${T.border}`,
                              color: kiGew ? "#a78bfa" : T.textMid,
                            }}
                          >KI</button>
                        </>
                      ) : (
                        <span style={{ color:T.textFaint, fontSize:11 }}>—</span>
                      )}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr style={{ borderTop:`2px solid ${T.border}` }}>
              <td colSpan={2} style={{ padding:"7px 10px", textAlign:"right", color:T.textMuted, fontWeight:600, fontSize:12 }}>
                Gesamtbetrag:
              </td>
              {hatKI && (
                <td style={{ ...tdMono, color: ergebnis.llm_konflikt ? "#f59e0b" : "#a78bfa", fontWeight:700 }}
                    title={ergebnis.llm_konflikt ? "Abweichung zum Regex-Gesamtbetrag" : "Übereinstimmung"}>
                  {ergebnis.llm_gesamtbetrag != null ? fmtEuro(ergebnis.llm_gesamtbetrag) : "—"}
                </td>
              )}
              <td style={{ ...tdMono, color:T.textMuted, fontWeight:600 }}>
                {ergebnis.gesamtbetrag != null ? fmtEuro(ergebnis.gesamtbetrag) : "—"}
              </td>
              <td style={{ ...tdMono, fontWeight:700, color:T.accent, fontSize:15 }}>
                {ergebnis.gesamtbetrag != null ? fmtEuro(ergebnis.gesamtbetrag) : "—"}
              </td>
              <td />
              {hatKonflikt && <td />}
            </tr>
          </tfoot>
        </table>
      ) : (
        <div style={{ color:T.textMuted, padding:12, textAlign:"center", fontSize:13 }}>
          Keine Positionen erkannt
        </div>
      )}

      {/* Zahlungen */}
      {zahlungen.length > 0 && (
        <div style={{ background:T.bg, borderRadius:6, padding:"10px 14px", marginTop:8 }}>
          <div style={{ fontSize:12, color:T.textMuted, fontWeight:600, marginBottom:6 }}>
            ZAHLUNGEN
          </div>
          {zahlungen.map((z, i) => (
            <div key={i} style={{ display:"flex", justifyContent:"space-between", fontSize:13, padding:"3px 0" }}>
              <span style={{ color:T.text }}>
                {z.empfaenger === "kanzlei" ? "An Kanzlei" :
                 z.empfaenger === "sv_buero" ? "An SV-Büro" : z.empfaenger}
                {z.datum ? ` (${z.datum})` : ""}
              </span>
              <span style={{ fontFamily:"monospace", fontWeight:600, color:T.green }}>
                {fmtEuro(z.betrag)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


function PruefberichtVorschau({ ergebnis, onPrüfeEntfernung, verweisErgebnis, verweisLaden, onZeigeDebug, debugLaden, debugErgebnis }) {
  const fz = ergebnis.fahrzeug || {};
  const rw = ergebnis.referenzwerkstatt;

  // Entfernungsprüfung automatisch beim ersten Anzeigen anstoßen
  useEffect(() => {
    if (onPrüfeEntfernung) onPrüfeEntfernung();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ fontSize:13 }}>
      {/* Fahrzeug */}
      {(fz.hersteller || fz.kennzeichen) && (
        <div style={{ display:"flex", gap:16, marginBottom:12, padding:"10px 14px", background:T.bg, borderRadius:6 }}>
          {fz.hersteller && <span><span style={{ color:T.textMuted }}>Fahrzeug: </span><strong>{fz.hersteller} {fz.typ}</strong></span>}
          {fz.kennzeichen && <span><span style={{ color:T.textMuted }}>KZ: </span><strong>{fz.kennzeichen}</strong></span>}
          {fz.erstzulassung && <span><span style={{ color:T.textMuted }}>EZ: </span>{fz.erstzulassung}</span>}
        </div>
      )}

      {/* Prüfergebnis-Tabelle */}
      <table style={{ width:"100%", borderCollapse:"collapse", marginBottom:12 }}>
        <tbody>
          {[
            ["Reparaturkosten vor Prüfung (netto)", ergebnis.reparaturkosten_netto_vor_pruefung],
            ["Abzug technische Prüfung", ergebnis.abzug_technisch ? -ergebnis.abzug_technisch : null],
            ["Abzug Werkstattalternative", ergebnis.abzug_werkstattalternative ? -ergebnis.abzug_werkstattalternative : null],
            ["Abzug gesamt", ergebnis.abzug_gesamt ? -ergebnis.abzug_gesamt : null],
            ["Reparaturkosten nach Prüfung", ergebnis.reparaturkosten_nach_pruefung],
          ].filter(([,v]) => v != null).map(([label, val], i) => (
            <tr key={i} style={{ borderTop:`1px solid ${T.border}` }}>
              <td style={{ padding:"7px 10px", color:T.textMuted }}>{label}</td>
              <td style={{
                padding:"7px 10px", textAlign:"right", fontFamily:"monospace",
                fontWeight: label.includes("nach") ? 700 : 400,
                color: val < 0 ? T.red : label.includes("nach") ? T.green : T.text,
              }}>
                {val < 0 ? `−${fmtEuro(Math.abs(val))}` : fmtEuro(val)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Referenzwerkstatt */}
      {rw && (
        <div style={{ padding:"10px 14px", background:T.bg, borderRadius:6 }}>
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:4 }}>
            <div style={{ fontWeight:600, color:T.text }}>Referenzwerkstatt</div>
            {onPrüfeEntfernung && (
              <div style={{ display:"flex", gap:5 }}>
                <button
                  onClick={onPrüfeEntfernung}
                  disabled={verweisLaden}
                  style={{ background: verweisErgebnis?.unzumutbar ? "#dc2626" : "#1e3a5f",
                    color:"#fff", border:"none", borderRadius:5,
                    padding:"3px 10px", cursor:"pointer", fontSize:"0.78rem",
                    fontWeight:600, whiteSpace:"nowrap" }}>
                  {verweisLaden ? "⟳ Prüfe…"
                    : verweisErgebnis?.km_echt ? `${verweisErgebnis.km_echt} km tatsächlich`
                    : "🔍 Entfernung prüfen"}
                </button>
                {onZeigeDebug && (
                  <button onClick={onZeigeDebug} disabled={debugLaden}
                    title="Geocoding debuggen"
                    style={{ background:"#6b7280", color:"#fff", border:"none",
                      borderRadius:5, padding:"3px 8px", cursor:"pointer", fontSize:"0.78rem" }}>
                    {debugLaden ? "⟳" : "🗺"}
                  </button>
                )}
              </div>
            )}
          </div>
          <div style={{ color:T.textMuted }}>{rw.name}</div>
          {rw.adresse && <div style={{ color:T.textMuted, fontSize:12 }}>{rw.adresse}</div>}
          {rw.plz_ort && (
            <div style={{ display:"flex", alignItems:"center", gap:10, fontSize:12, color:T.textMuted }}>
              <span>{rw.plz_ort}</span>
              {rw.entfernung_km != null && (
                <span style={{ color:T.textMuted }}>
                  · Entfernung lt. Prüfbericht: <strong style={{ color:T.text }}>{String(rw.entfernung_km).replace(".",",")} km</strong>
                </span>
              )}
            </div>
          )}
          <div style={{ display:"flex", gap:16, marginTop:3, flexWrap:"wrap" }}>
            {!rw.plz_ort && rw.entfernung_km != null && (
              <span style={{ fontSize:12, color:T.textMuted }}>
                Entfernung lt. Prüfbericht: <strong style={{ color:T.text }}>{String(rw.entfernung_km).replace(".",",")} km</strong>
              </span>
            )}
            {verweisErgebnis?.km_echt != null && (
              <span style={{ fontSize:12, fontWeight:700,
                color: verweisErgebnis.unzumutbar ? "#dc2626" : "#166534" }}>
                Tatsächlich: {String(verweisErgebnis.km_echt).replace(".",",")} km
                {verweisErgebnis.minuten ? ` (ca. ${verweisErgebnis.minuten} Min.)` : ""}
                {verweisErgebnis.unzumutbar ? " ⚠ UNZUMUTBAR" : " ✓"}
              </span>
            )}
            {verweisErgebnis?.fehler && !verweisErgebnis.km_echt && (
              <span style={{ fontSize:12, color:T.amber }}>⚠ {verweisErgebnis.fehler}</span>
            )}
          </div>
          {rw.lohn_mechanik && (
            <div style={{ marginTop:6, display:"flex", gap:16, fontSize:12, color:T.textMuted }}>
              <span>Mechanik: {fmtEuro(rw.lohn_mechanik)}/Std.</span>
              {rw.lohn_lack && <span>Lack: {fmtEuro(rw.lohn_lack)}/Std.</span>}
            </div>
          )}
        </div>
      )}

      {/* Debug-Panel: Geocoding-Details */}
      {debugErgebnis && (
        <div style={{ marginTop:10, padding:"10px 14px", background:"#1e1e2e",
          borderRadius:6, fontSize:"0.76rem", fontFamily:"monospace", color:"#cdd6f4",
          maxHeight:320, overflowY:"auto" }}>
          <div style={{ color:"#89b4fa", fontWeight:700, marginBottom:6 }}>🗺 Geocoding Debug</div>

          {/* Mandant */}
          <div style={{ color:"#a6e3a1", marginBottom:3 }}>Mandant</div>
          <div>Anfrage: {debugErgebnis.geocoding?.mandant?.anfrage}</div>
          {(debugErgebnis.geocoding?.mandant?.treffer || []).map((t, i) => (
            <div key={i} style={{ color: i===0 ? "#f9e2af":"#6c7086", marginLeft:8 }}>
              {i===0?"→ VERWENDET:":"  "} {t.label} · lat={t.lat.toFixed(5)} lng={t.lng.toFixed(5)} · {t.land} · conf={t.confidence}
            </div>
          ))}
          {debugErgebnis.geocoding?.mandant?.fehler && (
            <div style={{ color:"#f38ba8" }}>⚠ {debugErgebnis.geocoding.mandant.fehler}</div>
          )}

          {/* Werkstatt */}
          <div style={{ color:"#a6e3a1", marginTop:6, marginBottom:3 }}>Werkstatt</div>
          <div>Anfrage: {debugErgebnis.geocoding?.werkstatt?.anfrage}</div>
          {(debugErgebnis.geocoding?.werkstatt?.treffer || []).map((t, i) => (
            <div key={i} style={{ color: i===0 ? "#f9e2af":"#6c7086", marginLeft:8 }}>
              {i===0?"→ VERWENDET:":"  "} {t.label} · lat={t.lat.toFixed(5)} lng={t.lng.toFixed(5)} · {t.land} · conf={t.confidence}
            </div>
          ))}
          {debugErgebnis.geocoding?.werkstatt?.fehler && (
            <div style={{ color:"#f38ba8" }}>⚠ {debugErgebnis.geocoding.werkstatt.fehler}</div>
          )}

          {/* Routing */}
          {debugErgebnis.routing?.km && (
            <div style={{ marginTop:6, color:"#cba6f7" }}>
              Route: {debugErgebnis.routing.km} km · {debugErgebnis.routing.minuten} Min.
              <a href={`https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=${debugErgebnis.routing.von?.lat},${debugErgebnis.routing.von?.lng};${debugErgebnis.routing.nach?.lat},${debugErgebnis.routing.nach?.lng}`}
                target="_blank" rel="noopener noreferrer"
                style={{ color:"#89dceb", marginLeft:10 }}>
                🔗 Route in OSM anzeigen
              </a>
            </div>
          )}
          {debugErgebnis.routing?.fehler && (
            <div style={{ color:"#f38ba8", marginTop:4 }}>Routing-Fehler: {debugErgebnis.routing.fehler}</div>
          )}
          {debugErgebnis.fehler && (
            <div style={{ color:"#f38ba8", marginTop:4 }}>⚠ {debugErgebnis.fehler}</div>
          )}
        </div>
      )}
    </div>
  );
}


function AbrechnungFormular({ schaden, kuerzungsarten, akteId, onSave, onCancel, prefill = null }) {
  const [form, setForm] = useState({
    datum: "", versicherung: "", referenz_nr: "",
    haftungsart: "vollhaftung", haftungsquote: 100,
    haftungsbegruendung: "", notizen: "",
  });
  const [positionen, setPositionen] = useState(() => positionenVorlage(schaden));
  const [saving, setSaving]         = useState(false);
  const [toast, setToast]           = useState("");
  const [showPdfImport, setShowPdf] = useState(false);

  // prefill aus PDF-Import anwenden
  useEffect(() => {
    if (!prefill) return;
    setForm(prev => ({
      ...prev,
      versicherung: prefill.versicherung || prev.versicherung,
      referenz_nr:  prefill.referenz_nr  || prev.referenz_nr,
      datum:        prefill.datum        || prev.datum,
    }));
    if (prefill.positionen?.length > 0) {
      setPositionen(_mapPdfPos(prefill.positionen));
    }
  }, [prefill]);

  const F = (k) => (v) => setForm(p => ({ ...p, [k]: v }));

  // Wird von internem PdfImportDialog aufgerufen
  const handlePdfImport = (importData) => {
    setForm(prev => ({
      ...prev,
      versicherung: importData.versicherung || prev.versicherung,
      referenz_nr:  importData.referenz_nr  || prev.referenz_nr,
      datum:        importData.datum        || prev.datum,
    }));
    if (importData.positionen?.length > 0) {
      setPositionen(_mapPdfPos(importData.positionen));
    }
    setShowPdf(false);
  };

  const updatePos = (idx, k, v) => {
    setPositionen(prev => prev.map((p, i) => i === idx ? { ...p, [k]: v } : p));
  };

  const save = async () => {
    if (!form.datum) { setToast("Datum ist erforderlich."); return; }
    setSaving(true);
    const payload = {
      ...form,
      haftungsquote: parseFloat(form.haftungsquote) || 100,
      positionen: positionen.map(p => ({
        ...p,
        betrag_gefordert: Math.round((parseFloat(p.betrag_gefordert) || 0) * 100) / 100,
        betrag_reguliert: Math.round((parseFloat(p.betrag_reguliert) || 0) * 100) / 100,
      })).filter(p => {
        const g = Math.round((parseFloat(p.betrag_gefordert) || 0) * 100) / 100;
        const r = Math.round((parseFloat(p.betrag_reguliert) || 0) * 100) / 100;
        return g > 0 || r > 0;  // mindestens ein Wert muss gesetzt sein
      }),
    };
    try {
      const res = await request(`/akten/${akteId}/abrechnungen`, {
        method: "POST", body: JSON.stringify(payload),
      });
      if (res?.abrechnung) {
        onSave(res.abrechnung);
      } else {
        setToast("Fehler beim Speichern – bitte Seite neu laden.");
      }
    } catch(e) {
      setToast("Fehler: " + (e?.message || String(e)));
    }
    setSaving(false);
  };

  return (
    <>
    <div style={{ background:T.accentPale, border:`1px solid ${T.accentTrim}`, borderRadius:10, padding:"1.25rem 1.4rem", marginBottom:"1rem" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:"1rem" }}>
        <div style={{ fontFamily:T.fontBody, fontSize:"0.875rem", fontWeight:600, color:T.navy, textTransform:"uppercase", letterSpacing:"0.07em" }}>
          Neues Abrechnungsschreiben
        </div>
        <Btn size="sm" variant="secondary" onClick={() => setShowPdf(o => !o)}>
          {showPdfImport ? "↑ PDF-Import schließen" : "📄 Aus PDF importieren"}
        </Btn>
      </div>

      {/* PDF-Import-Dialog */}
      {showPdfImport && (
        <PdfImportDialog
          akteId={akteId}
          kuerzungsarten={kuerzungsarten}
          schaden={schaden}
          onImport={handlePdfImport}
          onCancel={() => setShowPdf(false)}
          dispatch={dispatch}
          dokumente={dokumente}
        />
      )}

      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(170px,1fr))", gap:"0.9rem", marginBottom:"1rem" }}>
        <FieldInput label="Datum *" value={form.datum} onChange={F("datum")} type="date" />
        <FieldInput label="Versicherung" value={form.versicherung} onChange={F("versicherung")} placeholder="z.B. KRAVAG" />
        <FieldInput label="Referenz-Nr." value={form.referenz_nr} onChange={F("referenz_nr")} placeholder="VN-2025-001" />
        <FieldSelect label="Haftungsart" value={form.haftungsart} onChange={F("haftungsart")}
          options={[{value:"vollhaftung",label:"Vollhaftung 100%"},{value:"mithaftung",label:"Mithaftung"},{value:"quote",label:"Quote"},{value:"ablehnung",label:"Ablehnung"}]} />
        {(form.haftungsart === "mithaftung" || form.haftungsart === "quote") && (
          <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
            <label style={{ fontFamily:T.fontBody, fontSize:"0.825rem", fontWeight:600, color:T.textMid, textTransform:"uppercase", letterSpacing:"0.05em" }}>Haftungsquote %</label>
            <input type="number" min={0} max={100} value={form.haftungsquote}
              onChange={e => setForm(p => ({...p,haftungsquote:e.target.value}))}
              style={{ padding:"8px 10px", border:`1.5px solid ${T.border}`, borderRadius:7, fontFamily:"ui-monospace,monospace", fontSize:"0.985rem", color:T.text, background:T.surface, outline:"none" }}
              onFocus={e => e.target.style.borderColor=T.accent} onBlur={e => e.target.style.borderColor=T.border} />
          </div>
        )}
      </div>

      {/* Positionen */}
      <div style={{ marginBottom:"1rem" }}>
        <div style={{ fontFamily:T.fontBody, fontSize:"0.82rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:"0.6rem" }}>Regulierte Positionen</div>
        <div style={{ background:T.cardBg, border:`1px solid ${T.border}`, borderRadius:8, overflow:"hidden" }}>
          <table style={{ width:"100%", borderCollapse:"collapse", fontFamily:T.fontBody, fontSize:"0.875rem" }}>
            <thead>
              <tr style={{ background:T.surface }}>
                {["Position","Gefordert (€)","Reguliert (€)","Kürzung"].map(h => (
                  <th key={h} style={{ padding:"6px 10px", textAlign:h==="Position"?"left":"right", fontWeight:600, color:T.textMuted, fontSize:"0.77rem", textTransform:"uppercase", letterSpacing:"0.05em" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {positionen.map((pos, idx) => {
                const kuerzung = POSITION_IST_ABZUG[pos.position_key]
                  ? (parseFloat(pos.betrag_reguliert)||0) - (parseFloat(pos.betrag_gefordert)||0)
                  : (parseFloat(pos.betrag_gefordert)||0) - (parseFloat(pos.betrag_reguliert)||0);
                return (
                  <tr key={pos.position_key} style={{ borderTop:`1px solid ${T.border}` }}>
                    <td style={{ padding:"6px 10px", color:T.text }}>{POSITION_LABELS_FE[pos.position_key]}</td>
                    <td style={{ padding:"6px 10px", textAlign:"right" }}>
                      <input type="number" step="0.01" min="0" value={pos.betrag_gefordert} onChange={e => updatePos(idx,"betrag_gefordert",e.target.value)}
                        style={{ width:100, padding:"4px 6px", border:`1px solid ${T.border}`, borderRadius:5, fontFamily:"ui-monospace,monospace", fontSize:"0.875rem", textAlign:"right", background:T.surface, color:T.text }} />
                    </td>
                    <td style={{ padding:"6px 10px", textAlign:"right" }}>
                      <input type="number" step="0.01" min="0" value={pos.betrag_reguliert} onChange={e => updatePos(idx,"betrag_reguliert",e.target.value)}
                        style={{ width:100, padding:"4px 6px", border:`1px solid ${kuerzung>0?T.red:T.border}`, borderRadius:5, fontFamily:"ui-monospace,monospace", fontSize:"0.875rem", textAlign:"right", background:T.surface, color:T.text }} />
                    </td>
                    <td style={{ padding:"6px 10px", textAlign:"right", fontFamily:"ui-monospace,monospace", fontSize:"0.875rem", color:kuerzung>0?T.red:T.textFaint, fontWeight:kuerzung>0?600:400 }}>
                      {kuerzung > 0 ? `−${fmtEuro(kuerzung)}` : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <FieldInput label="Notizen" value={form.notizen} onChange={F("notizen")} placeholder="Interne Notiz zum Schreiben …" />

      <div style={{ display:"flex", gap:8, marginTop:"1rem" }}>
        <Btn variant="gold" onClick={save} disabled={saving}>{saving ? "…" : `${Ic.check} Speichern`}</Btn>
        <Btn variant="secondary" onClick={onCancel}>Abbrechen</Btn>
      </div>
    </div>
    {toast && <Toast msg={toast} onDone={() => setToast("")} />}
    </>
  );
}



function ManuelleAbrechnungFormular({ schaden, kuerzungsarten, akteId, versicherungDefault, initialData, onSave, onCancel }) {
  const [modus, setModus]       = useState("schnell");   // "schnell" | "vollstaendig"
  const [saving, setSaving]     = useState(false);
  const [toast, setToast]       = useState("");
  const [form, setForm]         = useState(() => initialData ? {
    datum:              initialData.datum || new Date().toISOString().slice(0, 10),
    versicherung:       initialData.versicherung || versicherungDefault || "",
    referenz_nr:        initialData.referenz_nr || "",
    haftungsart:        initialData.haftungsart || "",
    haftungsquote:      initialData.haftungsquote ?? 100,
    haftungsbegruendung: initialData.haftungsbegruendung || "",
    notizen:            initialData.notizen || "",
  } : {
    datum:              new Date().toISOString().slice(0, 10),
    versicherung:       versicherungDefault || "",
    referenz_nr:        "",
    haftungsart:        "",     // optional – leer = keine Angabe
    haftungsquote:      100,
    haftungsbegruendung: "",
    notizen:            "",
  });

  // Bekannte Positionen aus Schaden-Tab (spiegelbildlich zu positionenVorlage)
  const bekannteOptionen = React.useMemo(() => {
    return positionenVorlage(schaden)
      .filter(p => p.betrag_gefordert > 0)
      .map(p => ({
        value:            p.position_key,
        label:            POSITION_LABELS_FE[p.position_key] || p.position_key,
        betrag_gefordert: p.betrag_gefordert,
      }));
  }, [schaden]);

  // Startpositionen: aus initialData (Edit) oder erste bekannte Position
  const [positionen, setPositionen] = useState(() => {
    if (initialData?.positionen?.length > 0) {
      return initialData.positionen.map((p, i) => ({
        id: i + 1,
        typ: bekannteOptionen.some(o => o.value === p.position_key) ? "dropdown" : "freitext",
        position_key:     p.position_key || "sonstiges",
        position_label:   p.position_label || null,
        betrag_gefordert: p.betrag_gefordert ?? 0,
        betrag_reguliert: p.betrag_reguliert ?? 0,
      }));
    }
    const erste = bekannteOptionen[0];
    return erste
      ? [{ id: 1, typ: "dropdown", position_key: erste.value, position_label: null,
           betrag_gefordert: erste.betrag_gefordert, betrag_reguliert: 0 }]
      : [{ id: 1, typ: "freitext", position_key: "sonstiges", position_label: "",
           betrag_gefordert: 0, betrag_reguliert: 0 }];
  });
  const [nextId, setNextId] = useState(2);

  const F = k => v => setForm(p => ({ ...p, [k]: v }));

  const addPos = (typ) => {
    const erste = bekannteOptionen[0];
    const neu = typ === "dropdown" && erste
      ? { id: nextId, typ: "dropdown", position_key: erste.value, position_label: null,
          betrag_gefordert: erste.betrag_gefordert, betrag_reguliert: 0 }
      : { id: nextId, typ: "freitext", position_key: "sonstiges", position_label: "",
          betrag_gefordert: 0, betrag_reguliert: 0 };
    setPositionen(p => [...p, neu]);
    setNextId(n => n + 1);
  };

  const updatePos = (id, changes) =>
    setPositionen(prev => prev.map(p => p.id === id ? { ...p, ...changes } : p));

  const removePos = (id) =>
    setPositionen(prev => prev.filter(p => p.id !== id));

  const onDropdownChange = (id, value) => {
    const opt = bekannteOptionen.find(o => o.value === value);
    updatePos(id, {
      position_key:      value,
      position_label:    null,
      betrag_gefordert:  opt?.betrag_gefordert ?? 0,
      betrag_reguliert:  0,
    });
  };

  const save = async () => {
    if (!form.datum) { setToast("Datum ist erforderlich."); return; }
    const posFilt = positionen.filter(p => {
      const g = parseFloat(p.betrag_gefordert) || 0;
      const r = parseFloat(p.betrag_reguliert) || 0;
      return g > 0 || r > 0;
    });
    if (posFilt.length === 0) { setToast("Mindestens eine Position mit Betrag erforderlich."); return; }

    setSaving(true);
    const haftungsart = form.haftungsart || "vollhaftung";
    const payload = {
      ...form,
      haftungsart,
      haftungsquote: parseFloat(form.haftungsquote) || 100,
      quelle:        "manuell",
      positionen:    posFilt.map(p => ({
        position_key:      p.position_key,
        position_label:    p.typ === "freitext" ? (p.position_label || null) : null,
        betrag_gefordert:  Math.round((parseFloat(p.betrag_gefordert) || 0) * 100) / 100,
        betrag_reguliert:  Math.round((parseFloat(p.betrag_reguliert) || 0) * 100) / 100,
        kuerzungsart_id:   null,
        kuerzung_freitext: "",
        fuer_klage_vorgemerkt: false,
      })),
    };
    payload.gesamt_gefordert = Math.round(payload.positionen.reduce((s,p) => s + p.betrag_gefordert, 0) * 100) / 100;
    payload.gesamt_reguliert = Math.round(payload.positionen.reduce((s,p) => s + p.betrag_reguliert, 0) * 100) / 100;
    payload.gesamt_kuerzung  = Math.round((payload.gesamt_gefordert - payload.gesamt_reguliert) * 100) / 100;

    try {
      let res;
      if (initialData?.id) {
        // Edit-Modus: PUT
        res = await request(`/akten/${akteId}/abrechnungen/${initialData.id}`, {
          method: "PUT", body: JSON.stringify(payload),
        });
        onSave(res?.abrechnung || { ...initialData, ...payload });
      } else {
        res = await apiAbrechnungen.erstelle(akteId, payload);
        onSave(res.abrechnung);
      }
    } catch(e) {
      setToast("Fehler: " + (e?.message || String(e)));
    }
    setSaving(false);
  };

  // ── Stile ────────────────────────────────────────────────────────────────
  const sLabel = { fontFamily:T.fontBody, fontSize:"0.78rem", fontWeight:600,
                   color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:3 };
  const sInput = { width:"100%", padding:"7px 10px", border:`1px solid ${T.border}`, borderRadius:6,
                   fontFamily:T.fontBody, fontSize:"0.875rem",
                   background:T.surface, color:T.text, boxSizing:"border-box" };
  const sInputMono = { ...sInput, fontFamily:"ui-monospace,monospace", textAlign:"right" };
  const sGrid2 = { display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0.75rem" };

  return (
    <>
    <div style={{ background:T.accentPale, border:`1px solid ${T.accentTrim}`, borderRadius:10,
                  padding:"1.25rem 1.4rem", marginBottom:"1rem" }}>

      {/* Header + Modus-Toggle */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:"1rem" }}>
        <span style={{ fontFamily:T.fontBody, fontSize:"0.875rem", fontWeight:600,
                       color:T.navy, textTransform:"uppercase", letterSpacing:"0.07em" }}>
          {initialData ? "✏️ Abrechnung bearbeiten" : "✏️ Manuelle Erfassung"}
        </span>
        <div style={{ display:"flex", background:T.border, borderRadius:6, padding:2 }}>
          {[["schnell","Schnelleingabe"],["vollstaendig","Vollständig"]].map(([v,l]) => (
            <button key={v} onClick={() => setModus(v)}
              style={{ padding:"4px 12px", border:"none", borderRadius:5, cursor:"pointer",
                       fontFamily:T.fontBody, fontSize:"0.8rem", fontWeight:modus===v?600:400,
                       background:modus===v?T.surface:"transparent",
                       color:modus===v?T.navy:T.textMuted,
                       boxShadow:modus===v?"0 1px 3px rgba(0,0,0,0.1)":"none" }}>
              {l}
            </button>
          ))}
        </div>
      </div>

      {/* ── Pflichtfelder (beide Modi) ──────────────────────────────────── */}
      <div style={sGrid2}>
        <div>
          <div style={sLabel}>Datum *</div>
          <input type="date" value={form.datum} onChange={e => F("datum")(e.target.value)} style={sInput} />
        </div>
        <div>
          <div style={sLabel}>Versicherung</div>
          <input type="text" value={form.versicherung} onChange={e => F("versicherung")(e.target.value)}
            placeholder="z.B. Allianz Versicherung" style={sInput} />
        </div>
      </div>

      {/* ── Vollständig-Modus: zusätzliche Felder ──────────────────────── */}
      {modus === "vollstaendig" && (
        <div style={{ marginTop:"0.75rem", display:"flex", flexDirection:"column", gap:"0.75rem" }}>
          <div style={sGrid2}>
            <div>
              <div style={sLabel}>Referenz-Nr.</div>
              <input type="text" value={form.referenz_nr} onChange={e => F("referenz_nr")(e.target.value)}
                placeholder="Schadennummer Versicherung" style={sInput} />
            </div>
            <div>
              <div style={sLabel}>Haftungsquote (%)</div>
              <input type="number" min="0" max="100" step="1"
                value={form.haftungsquote} onChange={e => F("haftungsquote")(e.target.value)}
                style={sInputMono} />
            </div>
          </div>
          <div>
            <div style={sLabel}>Begründung Haftung</div>
            <input type="text" value={form.haftungsbegruendung}
              onChange={e => F("haftungsbegruendung")(e.target.value)}
              placeholder="z.B. alleiniges Verschulden anerkannt" style={sInput} />
          </div>
        </div>
      )}

      {/* ── Positionstabelle ────────────────────────────────────────────── */}
      <div style={{ marginTop:"1rem" }}>
        <div style={{ ...sLabel, marginBottom:"0.5rem" }}>Positionen</div>

        {/* Kopfzeile */}
        <div style={{ display:"flex", gap:8, padding:"5px 8px",
                      background:T.navy, borderRadius:"6px 6px 0 0" }}>
          <div style={{ flex:"0 0 auto", width:28 }} />
          <div style={{ flex:"1 1 auto", fontFamily:T.fontBody,
                        fontSize:"0.73rem", fontWeight:600, color:"#fff" }}>Position</div>
          <div style={{ flex:"0 0 120px", fontFamily:T.fontBody,
                        fontSize:"0.73rem", fontWeight:600, color:"#fff", textAlign:"right" }}>Gefordert (€)</div>
          <div style={{ flex:"0 0 120px", fontFamily:T.fontBody,
                        fontSize:"0.73rem", fontWeight:600, color:"#fff", textAlign:"right" }}>Reguliert (€)</div>
          <div style={{ flex:"0 0 28px" }} />
        </div>

        {/* Zeilen */}
        <div style={{ border:`1px solid ${T.border}`, borderTop:"none",
                      borderRadius:"0 0 6px 6px", overflow:"hidden" }}>
          {positionen.map((pos, idx) => {
            const g = parseFloat(pos.betrag_gefordert) || 0;
            const r = parseFloat(pos.betrag_reguliert) || 0;
            const kuerzung = Math.max(0, g - r);
            return (
              <div key={pos.id}
                style={{ display:"flex", gap:8, padding:"6px 8px", alignItems:"center",
                         background: idx%2===0 ? T.surface : T.offWhite,
                         borderTop: idx>0 ? `1px solid ${T.border}` : "none" }}>

                {/* Typ-Icon */}
                <div style={{ flex:"0 0 28px", textAlign:"center", fontSize:"0.75rem",
                              color:T.textFaint, userSelect:"none" }}>
                  {pos.typ === "dropdown" ? "▾" : "✎"}
                </div>

                {/* Position: Dropdown oder Freitext */}
                <div style={{ flex:"1 1 auto", minWidth:0 }}>
                  {pos.typ === "dropdown" ? (
                    <select value={pos.position_key}
                      onChange={e => onDropdownChange(pos.id, e.target.value)}
                      style={{ ...sInput, padding:"4px 6px", fontSize:"0.85rem" }}>
                      {bekannteOptionen.map(o => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  ) : (
                    <input type="text" value={pos.position_label || ""}
                      onChange={e => updatePos(pos.id, { position_label: e.target.value })}
                      placeholder="Beschreibung der Position …"
                      style={{ ...sInput, padding:"4px 6px", fontSize:"0.85rem" }} />
                  )}
                </div>

                {/* Gefordert */}
                <div style={{ flex:"0 0 120px" }}>
                  <input type="number" step="0.01" min="0"
                    value={pos.betrag_gefordert}
                    onChange={e => updatePos(pos.id, { betrag_gefordert: e.target.value })}
                    style={{ ...sInputMono, padding:"4px 6px", fontSize:"0.85rem", width:"100%" }} />
                </div>

                {/* Reguliert */}
                <div style={{ flex:"0 0 120px" }}>
                  <input type="number" step="0.01" min="0"
                    value={pos.betrag_reguliert}
                    onChange={e => updatePos(pos.id, { betrag_reguliert: e.target.value })}
                    style={{ ...sInputMono, padding:"4px 6px", fontSize:"0.85rem", width:"100%",
                             border:`1px solid ${kuerzung > 0.005 ? T.red : T.border}`,
                             color: r > 0 && kuerzung <= 0.005 ? T.green : (kuerzung > 0.005 ? T.red : T.text) }} />
                </div>

                {/* Löschen */}
                <div style={{ flex:"0 0 28px", textAlign:"center" }}>
                  <button onClick={() => removePos(pos.id)}
                    style={{ background:"none", border:"none", cursor:"pointer",
                             color:T.textFaint, fontSize:"0.95rem", padding:0, lineHeight:1 }}
                    title="Position entfernen">✕</button>
                </div>
              </div>
            );
          })}
        </div>

        {/* +Buttons */}
        <div style={{ display:"flex", gap:6, marginTop:"0.5rem" }}>
          {bekannteOptionen.length > 0 && (
            <button onClick={() => addPos("dropdown")}
              style={{ background:"none", border:`1px dashed ${T.border}`, borderRadius:6,
                       padding:"4px 12px", cursor:"pointer", fontSize:"0.82rem",
                       color:T.textMuted, fontFamily:T.fontBody }}>
              + Bekannte Position
            </button>
          )}
          <button onClick={() => addPos("freitext")}
            style={{ background:"none", border:`1px dashed ${T.border}`, borderRadius:6,
                     padding:"4px 12px", cursor:"pointer", fontSize:"0.82rem",
                     color:T.textMuted, fontFamily:T.fontBody }}>
            + Freitext
          </button>
        </div>
      </div>

      {/* Notiz + Buttons */}
      <div style={{ marginTop:"0.75rem" }}>
        <div style={sLabel}>Notiz (optional)</div>
        <input type="text" value={form.notizen} onChange={e => F("notizen")(e.target.value)}
          placeholder="Interne Notiz …" style={sInput} />
      </div>

      <div style={{ display:"flex", gap:8, marginTop:"1rem" }}>
        <Btn variant="gold" onClick={save} disabled={saving}>
          {saving ? "…" : `${Ic.check} Speichern`}
        </Btn>
        <Btn variant="secondary" onClick={onCancel}>Abbrechen</Btn>
      </div>
    </div>
    {toast && <Toast msg={toast} onDone={() => setToast("")} />}
    </>
  );
}



function PruefberichteGespeichertListe({ pruefberichte, mandantAdresse, akteId, onVerketteErfolg }) {
  const [expanded, setExpanded] = useState(null);
  const [verweis, setVerweis]   = useState({});   // { [pbId]: ergebnis }
  const [verweisLaden, setVerweisLaden] = useState({});

  // Task 7: Verkettung Abrechnungsschreiben <-> Prüfbericht
  const [kandidaten, setKandidaten]           = useState({});  // { [pbId]: [...] }
  const [kandidatenLaden, setKandidatenLaden] = useState({});
  const [auswahl, setAuswahl]                 = useState({});  // { [pbId]: abId }
  const [verketteSpeichern, setVerketteSpeichern] = useState({});

  const ladeKandidaten = async (pb) => {
    if (kandidaten[pb.id] || kandidatenLaden[pb.id]) return;
    setKandidatenLaden(p => ({ ...p, [pb.id]: true }));
    try {
      const res = await apiPruefberichte.kandidaten(akteId, pb.id);
      setKandidaten(p => ({ ...p, [pb.id]: res?.kandidaten || [] }));
    } catch {
      setKandidaten(p => ({ ...p, [pb.id]: [] }));
    } finally {
      setKandidatenLaden(p => ({ ...p, [pb.id]: false }));
    }
  };

  const speichereVerkettung = async (pb) => {
    const abId = auswahl[pb.id];
    if (!abId) return;
    setVerketteSpeichern(p => ({ ...p, [pb.id]: true }));
    try {
      const res = await apiPruefberichte.verkette(akteId, pb.id, Number(abId));
      onVerketteErfolg?.(pb.id, res?.pruefbericht?.abrechnungsschreiben_id ?? Number(abId));
    } catch { /* Fehler bleibt sichtbar über unveränderten Status */ }
    finally {
      setVerketteSpeichern(p => ({ ...p, [pb.id]: false }));
    }
  };

  // Gespeichertes pb → ergebnis-Format für PruefberichtVorschau mappen
  const pbZuErgebnis = (pb) => {
    // plz_ort: entweder direkt aus neuem DB-Feld, oder aus kombinierter Adresse splitten (Legacy)
    const plz_ort  = pb.referenzwerkstatt_plz_ort || (() => {
      const parts = (pb.referenzwerkstatt_adresse || "").split(", ");
      return (parts.length >= 2 && /^\d{4,5}/.test(parts[parts.length - 1]))
        ? parts[parts.length - 1] : "";
    })();
    const strasse  = pb.referenzwerkstatt_plz_ort
      ? (pb.referenzwerkstatt_adresse || "")   // neu: Straße direkt
      : (() => {
          const parts = (pb.referenzwerkstatt_adresse || "").split(", ");
          return (parts.length >= 2 && /^\d{4,5}/.test(parts[parts.length - 1]))
            ? parts.slice(0, -1).join(", ") : (pb.referenzwerkstatt_adresse || "");
        })();

    return {
      pruefdienstleister:               pb.pruefdienstleister || "",
      vorgangsnummer:                   pb.vorgangsnummer || "",
      schreibdatum:                     pb.datum || "",
      schadennummer:                    pb.schadennummer || "",
      reparaturkosten_netto_vor_pruefung: pb.reparaturkosten_vor_pruefung ?? pb.reparaturkosten_netto_vor_pruefung,
      abzug_technisch:                  pb.abzug_technisch,
      abzug_werkstattalternative:       pb.abzug_werkstattalternative,
      abzug_gesamt:                     pb.abzug_gesamt,
      reparaturkosten_nach_pruefung:    pb.reparaturkosten_nach_pruefung,
      ist_image_pdf:                    pb.ist_image_pdf || false,
      warnungen:                        pb.ist_image_pdf ? ["Bild-PDF (DEKRA) – automatische Textextraktion nicht möglich."] : [],
      fahrzeug: {
        hersteller:   pb.fahrzeug_hersteller || "",
        typ:          pb.fahrzeug_typ || "",
        kennzeichen:  pb.fahrzeug_kennzeichen || "",
        erstzulassung: "",
      },
      referenzwerkstatt: pb.referenzwerkstatt_name ? {
        name:          pb.referenzwerkstatt_name,
        adresse:       strasse,
        plz_ort:       plz_ort,
        entfernung_km: pb.referenzwerkstatt_entfernung ?? null,
        lohn_mechanik: null,
        lohn_lack:     null,
      } : null,
    };
  };

  const prüfeEntfernung = async (pb) => {
    const rw = pbZuErgebnis(pb).referenzwerkstatt;
    if (!rw?.name || !mandantAdresse) return;
    setVerweisLaden(p => ({...p, [pb.id]: true}));
    try {
      const werkstattAdresse = [rw.name, rw.adresse, rw.plz_ort].filter(Boolean).join(", ");
      const result = await request('/distanz/prüfen', {
        method: 'POST',
        body: JSON.stringify({
          mandant_adresse:   mandantAdresse,
          werkstatt_adresse: werkstattAdresse,
          werkstatt_name:    rw.name,
          km_genannt:        rw.entfernung_km ?? null,
        }),
      });
      setVerweis(p => ({...p, [pb.id]: result}));
    } catch(e) {
      setVerweis(p => ({...p, [pb.id]: { fehler: e?.message || "Prüfung fehlgeschlagen" }}));
    } finally {
      setVerweisLaden(p => ({...p, [pb.id]: false}));
    }
  };

  return (
    <div style={{ padding:"0 1.4rem 1rem", display:"flex", flexDirection:"column", gap:8 }}>
      {pruefberichte.map((pb, i) => {
        const isOpen = expanded === (pb.id || i);
        const ergebnis = pbZuErgebnis(pb);
        return (
          <div key={pb.id || i} style={{
            border:`1px solid ${T.amber}44`,
            background:T.amberBg,
            borderRadius:8, overflow:"hidden",
          }}>
            {/* ── Header-Zeile (immer sichtbar, klickbar) ── */}
            <div
              onClick={() => setExpanded(isOpen ? null : (pb.id || i))}
              style={{
                display:"flex", justifyContent:"space-between", alignItems:"center",
                padding:"0.8rem 1rem", cursor:"pointer",
                background: isOpen ? T.amberBg : "transparent",
                transition:"background 0.15s",
              }}
              onMouseEnter={e => { if (!isOpen) e.currentTarget.style.background = T.surface; }}
              onMouseLeave={e => { if (!isOpen) e.currentTarget.style.background = "transparent"; }}
            >
              <div style={{ display:"flex", alignItems:"center", gap:10, flex:1, flexWrap:"wrap" }}>
                <span style={{ fontWeight:600, color:T.text, fontSize:"0.935rem" }}>
                  {pb.pruefdienstleister || "Prüfdienstleister"}
                </span>
                {pb.vorgangsnummer && (
                  <span style={{ fontFamily:"monospace", fontSize:12, color:T.textMuted }}>
                    #{pb.vorgangsnummer}
                  </span>
                )}
                {pb.datum && (
                  <span style={{ fontSize:12, color:T.textFaint }}>{pb.datum}</span>
                )}
                {pb.abzug_gesamt > 0 && (
                  <span style={{ fontSize:12, color:T.red, fontWeight:600 }}>
                    −{fmtEuro(pb.abzug_gesamt)} Abzug
                  </span>
                )}
                {pb.ist_image_pdf && (
                  <span style={{ fontSize:11, color:T.amber, background:T.amberBg,
                    border:`1px solid ${T.amber}44`, borderRadius:4, padding:"1px 6px" }}>
                    Bild-PDF
                  </span>
                )}
              </div>
              <div style={{ display:"flex", alignItems:"center", gap:12, flexShrink:0 }}>
                {pb.reparaturkosten_nach_pruefung && (
                  <div style={{ textAlign:"right" }}>
                    <div style={{ fontSize:11, color:T.textMuted }}>nach Prüfung</div>
                    <div style={{ fontFamily:"monospace", fontWeight:700, color:T.green, fontSize:"0.935rem" }}>
                      {fmtEuro(pb.reparaturkosten_nach_pruefung)}
                    </div>
                  </div>
                )}
                <svg viewBox="0 0 24 24" fill={T.textFaint} style={{
                  width:14, height:14,
                  transform: isOpen ? "rotate(180deg)" : "none",
                  transition:"transform 0.2s",
                }}>
                  <path d="M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z"/>
                </svg>
              </div>
            </div>

            {/* ── Ausgeklappter Inhalt ── */}
            {isOpen && (
              <div style={{ borderTop:`1px solid ${T.border}`, padding:"1rem 1.2rem", background:T.surface }}>
                {!pb.abrechnungsschreiben_id && (
                  <div style={{
                    display:"flex", alignItems:"center", gap:8, flexWrap:"wrap",
                    padding:"0.6rem 0.8rem", marginBottom:"0.8rem",
                    background:T.amberBg, border:`1px solid ${T.amber}44`, borderRadius:6,
                  }}>
                    <span style={{ fontSize:"0.85rem", color:T.textMid, fontWeight:600 }}>
                      Nicht verkettet
                    </span>
                    {!kandidaten[pb.id] && !kandidatenLaden[pb.id] && (
                      <Btn size="sm" variant="secondary" onClick={() => ladeKandidaten(pb)}>
                        Kandidaten laden
                      </Btn>
                    )}
                    {kandidatenLaden[pb.id] && (
                      <span style={{ fontSize:"0.85rem", color:T.textFaint }}>⟳ Lade…</span>
                    )}
                    {kandidaten[pb.id] && kandidaten[pb.id].length === 0 && (
                      <span style={{ fontSize:"0.85rem", color:T.textFaint }}>
                        Keine Abrechnungsschreiben in dieser Akte gefunden.
                      </span>
                    )}
                    {kandidaten[pb.id] && kandidaten[pb.id].length > 0 && (
                      <>
                        <FieldSelect
                          value={auswahl[pb.id] || ""}
                          onChange={v => setAuswahl(p => ({ ...p, [pb.id]: v }))}
                          options={[
                            { value: "", label: "— Abrechnungsschreiben wählen —" },
                            ...kandidaten[pb.id].map(k => ({
                              value: String(k.abrechnungsschreiben_id),
                              label: `${k.datum || "?"} · ${k.versicherung || "?"}`
                                + (k.grund ? ` (${k.grund})` : ""),
                            })),
                          ]}
                        />
                        <Btn size="sm" variant="primary"
                          disabled={!auswahl[pb.id] || verketteSpeichern[pb.id]}
                          onClick={() => speichereVerkettung(pb)}>
                          {verketteSpeichern[pb.id] ? "⟳ Speichere…" : "Verketten"}
                        </Btn>
                      </>
                    )}
                  </div>
                )}
                <PruefberichtVorschau
                  ergebnis={ergebnis}
                  onPrüfeEntfernung={mandantAdresse && ergebnis.referenzwerkstatt ? () => prüfeEntfernung(pb) : null}
                  verweisErgebnis={verweis[pb.id] || null}
                  verweisLaden={!!verweisLaden[pb.id]}
                  onZeigeDebug={null}
                  debugLaden={false}
                  debugErgebnis={null}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}



const RUNDEN_STATUS = {
  nachzahlung:      { label: "Nachzahlung",      farbe: "green"  },
  aufrechterhalten: { label: "aufrechterhalten", farbe: "grau"   },
  neu:              { label: "neu",              farbe: "rot"    },
  erhoeht:          { label: "erhöht",           farbe: "rot"    },
};

function RundenVergleichKachel({ akteId, kuerzungsarten, refreshKey }) {
  const [daten, setDaten] = useState(null);

  useEffect(() => {
    let aktiv = true;
    apiAbrechnungen.runden(akteId)
      .then(d => { if (aktiv) setDaten(d); })
      .catch(() => { if (aktiv) setDaten(null); });
    return () => { aktiv = false; };
  }, [akteId, refreshKey]);

  if (!daten || (daten.runden || []).length < 2) return null;

  const statusFarbe = s => {
    const f = RUNDEN_STATUS[s]?.farbe;
    return f === "green" ? T.green : f === "rot" ? T.redText : T.textMid;
  };

  return (
    <Card>
      <CardHead title={`Runden-Vergleich (${daten.runden.length} Abrechnungsrunden)`} />
      <div style={{ padding: "0.5rem 1.1rem 0.9rem" }}>
        {daten.vergleich.length === 0 ? (
          <div style={{ fontFamily: T.fontBody, fontSize: "0.875rem", color: T.textFaint }}>
            Keine Kürzungen zwischen den Runden zu vergleichen.
          </div>
        ) : daten.vergleich.map((v, i) => {
          const art = kuerzungsarten.find(k => k.id === v.kuerzungsart_id);
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10,
              padding: "6px 0", borderBottom: `1px solid ${T.border}`,
              fontFamily: T.fontBody, fontSize: "0.875rem" }}>
              <span style={{ flex: 1, color: T.text, fontWeight: 500 }}>
                {POSITION_LABELS_FE[v.position_key] || v.position_key}
              </span>
              {v.typ_code && (
                <span title={art?.bezeichnung || ""}
                  style={{ padding: "1px 8px", borderRadius: 10, fontSize: "0.75rem",
                    fontWeight: 600, background: T.blueBg, color: T.blue,
                    whiteSpace: "nowrap" }}>
                  {v.typ_code}
                </span>
              )}
              <span style={{ fontFamily: "ui-monospace,monospace", color: T.textMid,
                whiteSpace: "nowrap" }}>
                {fmtEuro(v.betrag_alt)} → {fmtEuro(v.betrag_neu)}
              </span>
              <span style={{ minWidth: 150, textAlign: "right", fontWeight: 600,
                color: statusFarbe(v.status), whiteSpace: "nowrap" }}>
                {v.delta > 0 ? "+" : ""}{fmtEuro(v.delta)} · {RUNDEN_STATUS[v.status]?.label || v.status}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function RegulierungSection({ brutto, hq, regulierungStatus, dispatch, akteId, schaden, abrechnungenCached, beteiligte, dokumente }) {
  const [abrechnungen, setAbrechnungen]   = useState([]);
  const [kuerzungsarten, setKuerzungsarten] = useState([]);
  const [pruefberichte, setPruefberichte] = useState([]);
  const [loading, setLoading]             = useState(true);
  const [toast, setToast]                 = useState("");

  // HQ editierbar
  const [hqVal, setHqVal]       = useState(hq || 100);
  const [hqEditing, setHqEditing] = useState(false);
  const [hqSaving, setHqSaving]   = useState(false);

  const [regStatus,  setRegStatus]  = useState(regulierungStatus ?? "offen");
  const [regProzent, setRegProzent] = useState(hq > 0 && hq < 100 ? hq : 70);
  const [regSaving,  setRegSaving]  = useState(false);

  // Aufgeklappte Zahlungshistorien
  const [expanded, setExpanded] = useState(new Set());

  // Inline Gezahlt-Edit
  const [gezahltEdit, setGezahltEdit]   = useState(null); // {posKey, value}
  const [gezahltSaving, setGezahltSaving] = useState(false);

  // Kürzungsarten multi-select
  const [kuerzungMap, setKuerzungMap]         = useState({}); // {posKey: [id, ...]}
  const [kuerzungDropdown, setKuerzungDropdown] = useState(null);

  // PDF Import + Prüfbericht
  const [showPdf, setShowPdf]     = useState(false);
  const [wdmLaden, setWdmLaden]   = useState(false);
  const [wdmHinweis, setWdmHinweis] = useState(null);

  // Verweisbetrieb
  const [verweis, setVerweis]               = useState(null);
  const [verweisLaden, setVerweisLaden]     = useState(false);
  const [verweisFlag, setVerweisFlag]       = useState(false);
  const [verweisBaustein, setVerweisBaustein] = useState("");

  // Stellungnahme generieren
  const [stellungLaedt, setStellungLaedt] = useState(false);
  const [wizardOffen, setWizardOffen]     = useState(false);
  const [loeschenLaedt, setLoeschenLaedt] = useState(null); // ab_id die gerade gelöscht wird

  // Einzelne Abrechnung löschen
  const loescheAbrechnung = async (abId, label) => {
    if (!confirm(`Abrechnung "${label || abId}" wirklich löschen?`)) return;
    setLoeschenLaedt(abId);
    try {
      await apiAbrechnungen.loesche(akteId, abId);
      ladeAlles();
      setToast("Abrechnung gelöscht.");
    } catch (e) {
      setToast("Löschen fehlgeschlagen: " + (e?.message || String(e)));
    } finally {
      setLoeschenLaedt(null);
    }
  };

  // Alle Abrechnungen löschen
  const loescheAlleAbrechnungen = async () => {
    if (!abrechnungen.length) return;
    if (!confirm(`Alle ${abrechnungen.length} Abrechnungen unwiderruflich löschen?`)) return;
    setLoeschenLaedt("alle");
    try {
      for (const ab of abrechnungen) {
        await apiAbrechnungen.loesche(akteId, ab.id);
      }
      ladeAlles();
      setToast(`${abrechnungen.length} Abrechnungen gelöscht.`);
    } catch (e) {
      setToast("Löschen fehlgeschlagen: " + (e?.message || String(e)));
      ladeAlles(); // Trotzdem neu laden, einige könnten gelöscht sein
    } finally {
      setLoeschenLaedt(null);
    }
  };

  const handleStellungnahme = async () => {
    setStellungLaedt(true);
    try {
      await apiStellungnahme.generieren(akteId);
    } catch (e) {
      setToast("Stellungnahme fehlgeschlagen: " + (e?.message || String(e)));
    } finally {
      setStellungLaedt(false);
    }
  };

  const mandantAdresse = React.useMemo(() => {
    const m = beteiligte?.find(b => b.rolle === "mandant");
    if (!m) return "";
    return [m.anschrift, [m.plz, m.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  }, [beteiligte]);

  // Importierte/hochgeladene PDFs nach Klasse (PRD-22b)
  const abrechnungsDoks = React.useMemo(() =>
    (dokumente || []).filter(d => d.dateityp === "pdf" &&
      (d.dokumentenklasse === "abrechnungsschreiben" || d.typ === "abrechnungsschreiben")),
    [dokumente]);
  const pruefberichtDoks = React.useMemo(() =>
    (dokumente || []).filter(d => d.dateityp === "pdf" &&
      (d.dokumentenklasse === "pruefbericht" || d.typ === "pruefbericht")),
    [dokumente]);

  const versicherungDefault = React.useMemo(() => {
    if (!beteiligte) return "";
    const ghpv = beteiligte.find(b => ["GHPV","GHV","GBEV"].includes((b.kuerzel||"").toUpperCase()))
      || beteiligte.find(b => b.rolle === "gegner");
    return ghpv?.versicherung || ghpv?.firma || ghpv?.name || "";
  }, [beteiligte]);

  // ── Daten laden ────────────────────────────────────────────────────────────
  const ladeAlles = React.useCallback(() => {
    setLoading(true);
    Promise.all([
      request(`/akten/${akteId}/abrechnungen`),
      apiKuerzungsarten.liste(true),
      apiPruefberichte.liste(akteId),
    ]).then(([abRes, kaRes, pbRes]) => {
      const list = abRes?.abrechnungen || [];
      setAbrechnungen(list);
      dispatch({ type: "SET_ABRECHNUNGEN", akteId, abrechnungen: list });
      setKuerzungsarten(kaRes?.kuerzungsarten || []);
      setPruefberichte(pbRes?.pruefberichte || []);
      // Kürzungsarten aus bestehenden Positionen rekonstruieren
      const km = {};
      list.forEach(ab => {
        (ab.positionen || []).forEach(p => {
          const k = p.position_key;
          if (!km[k]) km[k] = [];
          if (p.kuerzungsart_id && !km[k].includes(p.kuerzungsart_id))
            km[k].push(p.kuerzungsart_id);
          try {
            const extra = JSON.parse(p.kuerzung_freitext || "[]");
            if (Array.isArray(extra)) extra.forEach(id => { if (!km[k].includes(id)) km[k].push(id); });
          } catch {}
        });
      });
      setKuerzungMap(km);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [akteId]);

  useEffect(() => { ladeAlles(); }, [ladeAlles]);

  // ── posMap: Gefordert aus Schaden + Zahlungen aus Abrechnungen ────────────
  const posVorlage = React.useMemo(() => {
    const sd = schaden || {};
    // PRD-14: Fahrzeugschaden kommt direkt aus Backend-Berechnung (Single Source of Truth)
    const fzgBetrag = parseFloat(sd.abrechnungsberechnung?.fahrzeugschaden) || 0;

    const vorlage = [];

    // Fahrzeugschaden als erste Zeile (wenn Betrag > 0)
    if (fzgBetrag > 0) {
      vorlage.push({ position_key: "fahrzeugschaden_netto", betrag_gefordert: fzgBetrag });
    }

    // Weitere Positionen aus Schaden-Tab
    const WEITERE = [
      "wertminderung", "nutzungsausfall", "mietwagenkosten",
      "sv_kosten", "abschleppkosten", "standkosten", "anabmeldekosten",
      "schmerzensgeld", "verdienstausfall", "haushalt", "unkostenpauschale", "sonstiges",
    ];
    WEITERE.forEach(k => {
      const v = parseFloat(sd[k] || 0);
      if (v > 0) vorlage.push({ position_key: k, betrag_gefordert: v });
    });

    // Extras (sonstige Schäden aus WDM)
    const extras = (() => {
      if (sd._extras?.length) return sd._extras;
      try { const p = JSON.parse(sd.wdm_extras_json || "[]"); return Array.isArray(p) ? p : []; }
      catch { return []; }
    })();
    extras.filter(e => (e.betrag || 0) > 0).forEach(e => {
      vorlage.push({ position_key: `extra_${e.id}`, betrag_gefordert: e.betrag,
        _label: e.label || "Sonstiger Schaden" });
    });

    // Labels eintragen
    return vorlage.map(p => ({
      ...p,
      label: p.position_key === "fahrzeugschaden_netto"
        ? "Fahrzeugschaden"
        : (p._label || POSITION_LABELS_FE[p.position_key] || p.position_key),
    }));
  }, [schaden]);

  const posMap = React.useMemo(() => {
    const map = {};

    // Alle Fahrzeugschaden-Keys die in der DB stehen können → auf fahrzeugschaden_netto mappen
    const ALLE_FZG_KEYS = new Set([
      "wiederbeschaffung","restwert","rep_gutachten_netto",
      "rep_rechnung_netto","rep_rechnung_brutto","reparaturkosten",
      "fahrzeugschaden","fahrzeugschaden_netto","wbw","wbw_netto","wbw_brutto","wba",
      "reparatur_brutto","reparatur_netto","reparatur_fiktiv",
    ]);
    const erlaubteFzgKeys = new Set(posVorlage.map(p => p.position_key));

    // Basis aus positionenVorlage - nur diese Keys erscheinen in der Tabelle
    posVorlage.forEach(p => {
      map[p.position_key] = {
        key:       p.position_key,
        label:     p.label || POSITION_LABELS_FE[p.position_key] || p.position_key,
        gefordert: p.betrag_gefordert,
        zahlungen: [],
        fuer_klage: false,
      };
    });

    // Reverse-Map: Extra-Label (lowercase) → Extra-position_key
    // z.B. "restkraftstoff" → "extra_1" wenn Restkraftstoff als Sonstiger Schaden erfasst ist
    const extraLabelToKey = {};
    posVorlage.forEach(p => {
      if (p.position_key.startsWith("extra_")) {
        const lbl = (p._label || "").toLowerCase().trim();
        if (lbl) extraLabelToKey[lbl] = p.position_key;
      }
    });

    // Zahlungen aus allen Abrechnungen eintragen
    abrechnungen.forEach(ab => {
      (ab.positionen || []).forEach(p => {
        let key = ALLE_FZG_KEYS.has(p.position_key) && p.position_key !== "fahrzeugschaden_netto"
          ? "fahrzeugschaden_netto"   // alle alten Fahrzeugkeys → eine Zeile
          : p.position_key;
        // Remap sonstiges_wdm_X → extra_wdm_ssX (gleicher Key wie posVorlage-Extras)
        const _wm = /^sonstiges_wdm_(\d+)$/.exec(key);
        if (_wm) key = `extra_wdm_ss${_wm[1]}`;
        // Remap Parser-Art-Keys → Schaden-Tab-Keys (für alte Abrechnungen ohne _ART_TO_POS_KEY-Mapping)
        if (key === "kostenpauschale") key = "unkostenpauschale";
        // Remap Parser-Art-Key → Extra-Schaden-Key wenn Label übereinstimmt
        // z.B. "restkraftstoff" → "extra_1" wenn der Nutzer "Restkraftstoff" als Sonstiger Schaden erfasst hat
        if (!ALLE_FZG_KEYS.has(key) && extraLabelToKey[key.toLowerCase()]) {
          key = extraLabelToKey[key.toLowerCase()];
        }
        // Fahrzeugschadenkeys nur übernehmen wenn fahrzeugschaden_netto in posVorlage ist
        if (key === "fahrzeugschaden_netto" && !erlaubteFzgKeys.has("fahrzeugschaden_netto")) return;
        if (!map[key]) {
          // Nicht-Fahrzeugposition die im Schaden-Tab > 0 ist aber noch nicht in posVorlage
          if (ALLE_FZG_KEYS.has(key)) return; // Fahrzeugkey ohne Betrag → überspringen
          map[key] = {
            key, label: POSITION_LABELS_FE[key] || key,
            gefordert: p.betrag_gefordert || 0,
            zahlungen: [], fuer_klage: false,
          };
        }
        if (p.betrag_reguliert != null) {
          map[key].zahlungen.push({
            datum:        ab.datum || "",
            versicherung: ab.versicherung || "",
            betrag:       p.betrag_reguliert,
            ab_id:        ab.id,
            pos_id:       p.id,
            quelle:       ab.quelle || "pdf",
          });
        }
        if (p.fuer_klage_vorgemerkt) map[key].fuer_klage = true;
      });
    });
    return map;
  }, [posVorlage, abrechnungen]);

  const allePos = Object.values(posMap);
  const getGezahlt = (pos) => pos.zahlungen.length
    ? pos.zahlungen.reduce((s, z) => s + z.betrag, 0)
    : null;

  // KPIs
  const gesamtGefordert = allePos.reduce((s, p) => s + p.gefordert, 0);
  const gesamtGezahlt   = allePos.reduce((s, p) => s + (getGezahlt(p) || 0), 0);
  const gesamtOffen     = gesamtGefordert - gesamtGezahlt;
  const klagebetrag     = allePos
    .filter(p => p.fuer_klage && (p.gefordert - (getGezahlt(p) || 0)) > 0.01)
    .reduce((s, p) => s + Math.max(0, p.gefordert - (getGezahlt(p) || 0)), 0);

  // letzte Abrechnung für Kopfzeile
  const letzteAb  = abrechnungen[0];
  const versName  = letzteAb?.versicherung || versicherungDefault;
  const referenzNr = letzteAb?.referenz_nr || "";

  // ── HQ speichern ──────────────────────────────────────────────────────────
  const saveHq = async () => {
    setHqSaving(true);
    try {
      await apiAkten.aktualisieren(akteId, { haftungsquote: parseFloat(hqVal) || 100 });
      setHqEditing(false);
      setToast("Haftungsquote gespeichert.");
    } catch { setToast("HQ-Speichern fehlgeschlagen."); }
    finally { setHqSaving(false); }
  };

  // ── Gezahlt inline speichern ──────────────────────────────────────────────
  const saveGezahlt = async (posKey, betrag) => {
    setGezahltSaving(true);
    const pos = posMap[posKey];
    try {
      // Wenn eine bestehende Position vorhanden → PATCH (überschreiben, nicht addieren)
      if (gezahltEdit?.ab_id && gezahltEdit?.pos_id) {
        await apiAbrechnungen.updatePos(akteId, gezahltEdit.ab_id, gezahltEdit.pos_id, {
          betrag_reguliert: betrag,
        });
        setToast("Zahlung aktualisiert.");
        ladeAlles();
        return;
      }

      // Keine bestehende Position → neue Abrechnung anlegen
      const hatVorherigeZahlungen = (pos?.zahlungen?.length || 0) > 0;
      // fahrzeugschaden_netto → echten position_key aus Backend-Berechnung
      let backendKey = posKey;
      if (posKey === "fahrzeugschaden_netto") {
        backendKey = schaden?.abrechnungsberechnung?.fahrzeugschaden_key || "rep_gutachten_netto";
      }
      const kIds = kuerzungMap[posKey] || [];
      const payload = {
        datum:          gezahltEdit?.datum || new Date().toISOString().slice(0, 10),
        versicherung:   gezahltEdit?.versicherung || versicherungDefault,
        referenz_nr:    gezahltEdit?.referenz_nr || "",
        haftungsart:    "vollhaftung",
        haftungsquote:  parseFloat(hqVal) || 100,
        quelle:         "manuell",
        positionen: [{
          position_key:         backendKey,
          betrag_gefordert:     pos?.gefordert || 0,
          betrag_reguliert:     betrag,
          kuerzungsart_id:      kIds[0] || null,
          kuerzung_freitext:    kIds.length > 1 ? JSON.stringify(kIds.slice(1)) : "",
          fuer_klage_vorgemerkt: pos?.fuer_klage || false,
        }],
      };
      await apiAbrechnungen.erstelle(akteId, payload);
      setToast(hatVorherigeZahlungen
        ? "Neue Abrechnung angelegt – Betrag = Zahlung dieses Schreibens."
        : "Neue Abrechnung angelegt.");
      ladeAlles();
    } catch (e) {
      setToast("Fehler: " + (e?.message || String(e)));
    } finally {
      setGezahltSaving(false);
      setGezahltEdit(null);
    }
  };

  // ── Klage-Flag togglen ────────────────────────────────────────────────────
  const toggleKlage = async (posKey) => {
    const pos = posMap[posKey];
    const neuFlag = !pos.fuer_klage;
    for (const ab of [...abrechnungen].reverse()) {
      const p = (ab.positionen || []).find(x => x.position_key === posKey);
      if (p?.id) {
        try {
          await apiAbrechnungen.updatePos(akteId, ab.id, p.id, { fuer_klage_vorgemerkt: neuFlag });
          ladeAlles();
        } catch {}
        break;
      }
    }
  };

  // ── Kürzungsart hinzufügen / entfernen ────────────────────────────────────
  const toggleKuerzungsart = async (posKey, artId) => {
    const current = kuerzungMap[posKey] || [];
    const neu = current.includes(artId)
      ? current.filter(id => id !== artId)
      : [...current, artId];
    setKuerzungMap(p => ({...p, [posKey]: neu}));
    // In letzter Abrechnung für diese Position speichern
    for (const ab of [...abrechnungen].reverse()) {
      const p = (ab.positionen || []).find(x => x.position_key === posKey);
      if (p?.id) {
        try {
          await apiAbrechnungen.updatePos(akteId, ab.id, p.id, {
            kuerzungsart_id:    neu[0] || null,
            kuerzung_freitext:  neu.length > 1 ? JSON.stringify(neu.slice(1)) : "",
          });
        } catch {}
        break;
      }
    }
  };

  // ── WDM Import ────────────────────────────────────────────────────────────
  const onWdmImport = async () => {
    setWdmLaden(true);
    try {
      const res = await request(`/akten/${akteId}/abrechnungen/wdm-import`, { method: "POST" });
      if (res?.abrechnung || res?.id) {
        ladeAlles();
        setWdmHinweis(null);
        setToast("WDM-Daten importiert.");
      } else if (res?.error) { setToast("WDM: " + res.error); }
    } catch (e) {
      if (e?.status === 409) setToast("WDM bereits importiert.");
      else setToast("WDM-Import fehlgeschlagen: " + (e?.message || String(e)));
    }
    setWdmLaden(false);
  };

  // ── Prüfbericht speichern ─────────────────────────────────────────────────
  const onSavePruefbericht = async (daten) => {
    try {
      const res = await apiPruefberichte.erstelle(akteId, daten);
      if (!res?.pruefbericht) throw new Error("Kein pruefbericht in der Antwort");
      setPruefberichte(prev => [res.pruefbericht, ...prev]);
      setToast("Prüfbericht gespeichert.");
    } catch (err) {
      setToast(`Speichern fehlgeschlagen: ${(err?.message || String(err)).slice(0, 120)}`);
    }
  };

  // ── Verweisbetrieb ────────────────────────────────────────────────────────
  const prüfeVerweisbetrieb = async (volltext, dokId, kmGenannt, pbId) => {
    setVerweisLaden(true); setVerweis(null);
    try {
      if (pbId || dokId) {
        const res = await apiDistanz.prüfenAusDokument(akteId, dokId, pbId);
        if (res?.verweis_gefunden) {
          setVerweis(res);
          if (res.unzumutbar) { setVerweisFlag(true); setVerweisBaustein(res.textbaustein || ""); }
        } else { setVerweis({ verweis_gefunden: false }); }
        return;
      }
      if (volltext) {
        const parseRes = await apiDistanz.parsen(volltext);
        if (!parseRes?.gefunden) { setVerweis({ verweis_gefunden: false }); return; }
        const werkstattAdresse = [parseRes.adresse, parseRes.plz_ort].filter(Boolean).join(", ");
        if (!werkstattAdresse.trim()) {
          setVerweis({ verweis_gefunden: true, fehler: "Werkstatt-Adresse unvollständig", werkstatt_name: parseRes.name });
          return;
        }
        const result = await apiDistanz.prüfen(mandantAdresse, werkstattAdresse, parseRes.name, parseRes.km_genannt);
        result.verweis_gefunden = true;
        setVerweis(result);
        if (result.unzumutbar) { setVerweisFlag(true); setVerweisBaustein(result.textbaustein || ""); }
      } else { setVerweis({ verweis_gefunden: false }); }
    } catch (e) {
      setVerweis({ fehler: e?.message || "Prüfung fehlgeschlagen" });
    } finally { setVerweisLaden(false); }
  };

  const speichereRegStatus = async (neuerStatus, prozent) => {
    const alterStatus = regStatus;
    setRegSaving(true);
    const body = { regulierung_status: neuerStatus };
    if (neuerStatus === "abgelehnt") body.haftungsquote = 0;
    else if (neuerStatus === "offen") body.haftungsquote = 100;
    else if (neuerStatus === "teilhaftung") body.haftungsquote = prozent;
    try {
      const res = await apiAkten.aktualisieren(akteId, body);
      if (res?.regulierung_status) dispatch({ type: "SET_REGULIERUNG_STATUS", akteId, regulierungStatus: res.regulierung_status });
      setRegStatus(res?.regulierung_status ?? neuerStatus);
      if (neuerStatus === "teilhaftung") setRegProzent(prozent);
      setToast("Regulierungsstatus gespeichert.");
    } catch {
      setRegStatus(alterStatus);
      setToast("Fehler beim Speichern.");
    } finally {
      setRegSaving(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────
  if (loading) return (
    <div style={{ display:"flex", alignItems:"center", gap:10, padding:"2rem",
      color:T.textFaint, fontFamily:T.fontBody }}>
      <div style={{ width:16, height:16, border:`2px solid ${T.accent}`, borderTopColor:"transparent",
        borderRadius:"50%", animation:"spin 0.7s linear infinite" }}/>
      Lade Regulierungsdaten…
    </div>
  );

  return (
    <>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <div style={{ display:"flex", flexDirection:"column", gap:"1.25rem" }}>

        {/* ── Regulierungsstatus-Kachel ── */}
        <Card>
          <CardHead titel="Regulierung abgelehnt?" />
          <div style={{ padding:"0.75rem 1.1rem", display:"flex", flexDirection:"column", gap:12 }}>
            <div style={{ display:"flex", gap:24, alignItems:"center" }}>
              {[
                { val:"offen",       label:"Nein"        },
                { val:"abgelehnt",   label:"Ja"          },
                { val:"teilhaftung", label:"Teilhaftung" },
              ].map(opt => (
                <label key={opt.val} style={{
                  display:"flex", alignItems:"center", gap:7,
                  cursor: regSaving ? "default" : "pointer",
                  fontFamily:T.fontBody, fontSize:"0.95rem", color:T.text,
                }}>
                  <input
                    type="radio"
                    name={`reg-status-${akteId}`}
                    value={opt.val}
                    checked={regStatus === opt.val}
                    disabled={regSaving}
                    onChange={() => {
                      setRegStatus(opt.val);
                      if (opt.val !== "teilhaftung") speichereRegStatus(opt.val, regProzent);
                    }}
                    style={{ accentColor:T.navy, width:16, height:16 }}
                  />
                  {opt.label}
                </label>
              ))}
              {regSaving && (
                <div style={{
                  width:14, height:14,
                  border:`2px solid ${T.border}`,
                  borderTopColor:T.navy, borderRadius:"50%",
                  animation:"spin 0.7s linear infinite",
                }}/>
              )}
            </div>
            {regStatus === "teilhaftung" && (
              <div style={{ display:"flex", alignItems:"center", gap:10 }}>
                <span style={{ fontFamily:T.fontBody, fontSize:"0.9rem", color:T.textMid }}>
                  Versicherung reguliert:
                </span>
                <input
                  type="number"
                  min={1} max={99}
                  value={regProzent}
                  disabled={regSaving}
                  onChange={e => setRegProzent(Number(e.target.value))}
                  onBlur={() => speichereRegStatus("teilhaftung", regProzent)}
                  onKeyDown={e => e.key === "Enter" && speichereRegStatus("teilhaftung", regProzent)}
                  style={{
                    width:70, padding:"5px 8px",
                    border:`1.5px solid ${T.border}`,
                    borderRadius:6, fontFamily:"ui-monospace,monospace",
                    fontSize:"0.95rem", color:T.text, textAlign:"right",
                  }}
                />
                <span style={{ fontFamily:T.fontBody, fontSize:"0.9rem", color:T.textMid }}>%</span>
              </div>
            )}
          </div>
        </Card>

        {/* ── Verweis-Banner ── */}
        {verweisLaden && (
          <div style={{ padding:"0.75rem 1.25rem", background:T.blueBg, borderRadius:8,
            border:"1px solid #bfdbfe", fontFamily:T.fontBody,
            fontSize:"0.875rem", color:"#1d4ed8", display:"flex", alignItems:"center", gap:8 }}>
            <span style={{ animation:"spin 1s linear infinite", display:"inline-block" }}>⟳</span>
            Prüfe Verweisbetrieb-Entfernung…
          </div>
        )}
        {verweis && !verweisLaden && verweis.verweis_gefunden && (
          <div style={{ background: verweis.unzumutbar ? T.redBg : "#f0fdf4",
            border:`1.5px solid ${verweis.unzumutbar ? T.redLight : T.greenLight}`,
            borderRadius:10, padding:"1rem 1.25rem",
            fontFamily:T.fontBody }}>
            <div style={{ fontWeight:700, fontSize:"0.95rem",
              color: verweis.unzumutbar ? T.redText : "#166534" }}>
              {verweis.unzumutbar
                ? `⚠ Verweisbetrieb zu weit – ${verweis.km_echt} km`
                : `✓ Verweisbetrieb – ${verweis.km_echt} km`}
            </div>
            {verweisFlag && (
              <textarea value={verweisBaustein} onChange={e => setVerweisBaustein(e.target.value)}
                style={{ marginTop:8, width:"100%", minHeight:100, padding:"8px 10px",
                  fontSize:"0.84rem", fontFamily:T.fontBody,
                  border:"1px solid #d1d5db", borderRadius:7, resize:"vertical",
                  boxSizing:"border-box", background:T.amberBg }} />
            )}
          </div>
        )}

        {/* ── Info-Karten: Erfasste Dokumente (PRD-22b) ── */}
        {(abrechnungsDoks.length > 0 || pruefberichtDoks.length > 0) && (
          <div style={{ display:"flex", gap:10, marginBottom:"1rem", flexWrap:"wrap" }}>
            {abrechnungsDoks.length > 0 && (
              <div style={{ flex:1, minWidth:200, padding:"10px 14px", background:T.greenBg, border:`1px solid ${T.green}33`, borderRadius:8, display:"flex", alignItems:"center", gap:10 }}>
                <span style={{ color:T.green, fontSize:"1.1rem", flexShrink:0 }}>📄</span>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontFamily:T.fontBody, fontSize:"0.85rem", fontWeight:600, color:T.green }}>
                    {abrechnungsDoks.length === 1 ? "1 Abrechnungsschreiben" : `${abrechnungsDoks.length} Abrechnungsschreiben`}
                  </div>
                  <div style={{ fontFamily:T.fontBody, fontSize:"0.78rem", color:T.textMuted, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                    {abrechnungsDoks.map(d => d.dateiname).join(", ")}
                  </div>
                </div>
              </div>
            )}
            {pruefberichtDoks.length > 0 && (
              <div style={{ flex:1, minWidth:200, padding:"10px 14px", background:T.blueBg, border:`1px solid ${T.blue}33`, borderRadius:8, display:"flex", alignItems:"center", gap:10 }}>
                <span style={{ color:T.blue, fontSize:"1.1rem", flexShrink:0 }}>🔍</span>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontFamily:T.fontBody, fontSize:"0.85rem", fontWeight:600, color:T.blue }}>
                    {pruefberichtDoks.length === 1 ? "1 Prüfbericht" : `${pruefberichtDoks.length} Prüfberichte`}
                  </div>
                  <div style={{ fontFamily:T.fontBody, fontSize:"0.78rem", color:T.textMuted, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                    {pruefberichtDoks.map(d => d.dateiname).join(", ")}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Runden-Vergleich (Task 9): sichtbar ab 2 Abrechnungsrunden ── */}
        <RundenVergleichKachel akteId={akteId} kuerzungsarten={kuerzungsarten}
          refreshKey={abrechnungen.length} />

        {/* ── Haupt-Regulierungskarte ── */}
        <Card>

          {/* Kopfzeile */}
          <div style={{ padding:"0.9rem 1.4rem", borderBottom:`1px solid ${T.border}`,
            display:"flex", alignItems:"center", justifyContent:"space-between",
            flexWrap:"wrap", gap:10 }}>
            <div style={{ display:"flex", alignItems:"center", gap:"1.5rem", flexWrap:"wrap" }}>
              {versName && (
                <span style={{ fontFamily:T.fontBody, fontSize:"0.875rem", color:T.textMid }}>
                  <span style={{ color:T.textFaint }}>Versicherung: </span><strong>{versName}</strong>
                </span>
              )}
              {referenzNr && (
                <span style={{ fontFamily:T.fontBody, fontSize:"0.875rem", color:T.textMid }}>
                  <span style={{ color:T.textFaint }}>Referenz: </span><strong>{referenzNr}</strong>
                </span>
              )}
              <span style={{ fontFamily:T.fontBody, fontSize:"0.875rem",
                color:T.textMid, display:"flex", alignItems:"center", gap:6 }}>
                <span style={{ color:T.textFaint }}>HQ: </span>
                {hqEditing ? (
                  <>
                    <input type="number" min="0" max="100" step="1" value={hqVal}
                      onChange={e => setHqVal(e.target.value)}
                      onKeyDown={e => { if (e.key==="Enter") saveHq(); if (e.key==="Escape") setHqEditing(false); }}
                      autoFocus
                      style={{ width:56, padding:"2px 6px", border:`1.5px solid ${T.accent}`,
                        borderRadius:5, fontFamily:"ui-monospace,monospace",
                        fontSize:"0.875rem", outline:"none" }} />
                    <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.875rem" }}>%</span>
                    <button onClick={saveHq} disabled={hqSaving}
                      style={{ background:T.accent, border:"none", borderRadius:5, padding:"2px 8px",
                        cursor:"pointer", color:"#fff", fontSize:"0.8rem", fontWeight:600 }}>
                      {hqSaving ? "…" : "✓"}
                    </button>
                    <button onClick={() => setHqEditing(false)}
                      style={{ background:"none", border:"none", cursor:"pointer",
                        color:T.textFaint, fontSize:"0.8rem" }}>✕</button>
                  </>
                ) : (
                  <>
                    <strong style={{ fontFamily:"ui-monospace,monospace" }}>{hqVal} %</strong>
                    <button onClick={() => setHqEditing(true)}
                      title="Haftungsquote bearbeiten"
                      style={{ background:"none", border:"none", cursor:"pointer",
                        color:T.textFaint, padding:"2px", fontSize:"0.85rem", lineHeight:1 }}>✎</button>
                  </>
                )}
              </span>
            </div>
            <div style={{ display:"flex", gap:6 }}>
              <Btn size="sm" variant="secondary"
                onClick={() => setShowPdf(o => !o)}>
                📄 PDF
              </Btn>
              <Btn size="sm" variant="secondary"
                onClick={onWdmImport} disabled={wdmLaden}>
                {wdmLaden ? "…" : "📋 WDM"}
              </Btn>
              <Btn size="sm" variant="secondary"
                onClick={handleStellungnahme} disabled={stellungLaedt}
                title="Stellungnahme zu den Kürzungen als Word-Dokument generieren">
                {stellungLaedt ? "⏳ …" : "📝 Stellungnahme"}
              </Btn>
              <Btn size="sm" variant="secondary"
                onClick={() => setWizardOffen(true)} title="Geführter Stellungnahme-Wizard">
                📋 Wizard
              </Btn>
              {abrechnungen.length > 0 && (
                <Btn size="sm" variant="danger"
                  onClick={loescheAlleAbrechnungen}
                  disabled={loeschenLaedt === "alle"}
                  title="Alle Abrechnungen löschen">
                  {loeschenLaedt === "alle" ? "…" : Ic.trash}
                </Btn>
              )}
            </div>
          </div>

          {/* PDF-Import-Dialog */}
          {showPdf && (
            <div style={{ padding:"0 1.4rem 1rem" }}>
              <PdfImportDialog
                akteId={akteId}
                kuerzungsarten={kuerzungsarten}
                schaden={schaden}
                mandantAdresse={mandantAdresse}
                onImport={(importData) => {
                  setShowPdf(false);
                  // Abrechnung aus PDF direkt speichern
                  const payload = {
                    datum:       importData.datum || new Date().toISOString().slice(0,10),
                    versicherung: importData.versicherung || "",
                    referenz_nr: importData.referenz_nr || "",
                    haftungsart: "vollhaftung",
                    haftungsquote: parseFloat(hqVal) || 100,
                    quelle: "pdf",
                    positionen: (importData.positionen || []).map(p => ({
                      position_key:       p.art || p.position_key || "sonstiges",
                      betrag_gefordert:   Number((p.betrag_netto ?? p.betrag_brutto ?? 0).toFixed(2)),
                      betrag_reguliert:   Number((p.betrag_netto ?? p.betrag_brutto ?? 0).toFixed(2)),
                      kuerzungsart_id:    null,
                      kuerzung_freitext:  "",
                      fuer_klage_vorgemerkt: false,
                    })),
                  };
                  apiAbrechnungen.erstelle(akteId, payload)
                    .then(() => { ladeAlles(); setToast("PDF-Abrechnung importiert."); })
                    .catch(e => setToast("Import fehlgeschlagen: " + (e?.message || String(e))));
                }}
                onSavePruefbericht={(daten) => {
                  onSavePruefbericht(daten);
                  const dokId = daten._dok_id || daten.dok_id || null;
                  prüfeVerweisbetrieb(daten._volltext || null, dokId);
                  setShowPdf(false);
                }}
                onCancel={() => setShowPdf(false)}
                dispatch={dispatch}
                dokumente={dokumente}
              />
            </div>
          )}

          {/* Tabelle */}
          <div style={{ overflowX:"auto" }}>
            <table style={{ width:"100%", borderCollapse:"collapse",
              fontFamily:T.fontBody, fontSize:"0.875rem" }}>
              <thead>
                <tr style={{ background:T.navy }}>
                  {[
                    { l:"",               w:28,  align:"left"   },
                    { l:"Schadenposition",w:null, align:"left"   },
                    { l:"Gefordert",      w:110, align:"right"  },
                    { l:"Gezahlt",        w:130, align:"right"  },
                    { l:"Kürzung",        w:120, align:"right"  },
                    { l:"Kürzungsarten",  w:200, align:"left"   },
                    { l:"Klage",          w:80,  align:"center" },
                    { l:"",               w:36,  align:"center" },
                  ].map((col, i) => (
                    <th key={i} style={{ padding:"9px 12px", textAlign:col.align,
                      fontFamily:T.fontBody, fontSize:"0.775rem",
                      fontWeight:600, color:"rgba(255,255,255,0.8)",
                      letterSpacing:"0.06em", textTransform:"uppercase",
                      whiteSpace:"nowrap", ...(col.w ? { width:col.w } : {}) }}>
                      {col.l}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {allePos.length === 0 ? (
                  <tr><td colSpan={8} style={{ padding:"2.5rem", textAlign:"center",
                    color:T.textFaint }}>
                    Noch keine Schadenpositionen erfasst. Bitte zuerst Schaden-Tab ausfüllen.
                  </td></tr>
                ) : allePos.map((pos, idx) => {
                  const gezahlt  = getGezahlt(pos);
                  const kuerzung = gezahlt !== null ? pos.gefordert - gezahlt : null;
                  const hatKuerzung  = kuerzung !== null && kuerzung > 0.005;
                  const beglichen    = kuerzung !== null && kuerzung <= 0.005;
                  const isExpanded   = expanded.has(pos.key);
                  const isEditing    = gezahltEdit?.posKey === pos.key;
                  const mehrZahlungen = pos.zahlungen.length >= 1;
                  const kIds = kuerzungMap[pos.key] || [];

                  return (
                    <React.Fragment key={pos.key}>
                      <tr style={{ borderBottom:`1px solid ${T.border}`,
                        background: idx%2===0 ? T.cardBg : T.surface,
                        transition:"background 0.1s" }}
                        onMouseEnter={e => e.currentTarget.style.background = T.accentPale}
                        onMouseLeave={e => e.currentTarget.style.background = idx%2===0 ? T.cardBg : T.surface}>

                        {/* Expand-Button */}
                        <td style={{ padding:"8px 4px 8px 12px", textAlign:"center" }}>
                          {mehrZahlungen ? (
                            <button onClick={() => setExpanded(p => {
                              const n = new Set(p);
                              n.has(pos.key) ? n.delete(pos.key) : n.add(pos.key);
                              return n;
                            })} style={{ background:"none", border:"none", cursor:"pointer",
                              color:T.textFaint, padding:2, fontSize:"0.75rem",
                              transform: isExpanded ? "rotate(90deg)" : "none",
                              transition:"transform 0.15s", lineHeight:1,
                              display:"flex", flexDirection:"column", alignItems:"center", gap:1 }}
                              title={`${pos.zahlungen.length} Zahlung${pos.zahlungen.length !== 1 ? "en" : ""}`}>
                              <span>▶</span>
                              {pos.zahlungen.length > 1 && (
                                <span style={{ fontSize:"0.6rem", color:T.textFaint, lineHeight:1 }}>
                                  {pos.zahlungen.length}×
                                </span>
                              )}
                            </button>
                          ) : <span style={{ display:"inline-block", width:14 }}/>}
                        </td>

                        {/* Position */}
                        <td style={{ padding:"8px 12px", color:T.text, fontWeight:500 }}>
                          {pos.label}
                        </td>

                        {/* Gefordert */}
                        <td style={{ padding:"8px 12px", textAlign:"right",
                          fontFamily:"ui-monospace,monospace", color:T.textMid }}>
                          {fmtEuro(pos.gefordert)}
                        </td>

                        {/* Gezahlt – inline editierbar */}
                        <td style={{ padding:"8px 12px", textAlign:"right" }}>
                          {isEditing ? (
                            <>
                              {/* Backdrop */}
                              <div onClick={() => setGezahltEdit(null)}
                                style={{ position:"fixed", top:0, left:0, right:0, bottom:0,
                                  background:"rgba(0,0,0,0.15)", zIndex:900 }} />
                              {/* Popup – fixiert mittig im Viewport */}
                              <div onMouseDown={e => e.stopPropagation()}
                                style={{ position:"fixed", top:"50%", left:"50%",
                                  transform:"translate(-50%, -50%)",
                                  zIndex:901, background:T.cardBg,
                                  border:`1.5px solid ${T.accent}`,
                                  borderRadius:10, boxShadow:"0 12px 40px rgba(0,0,0,0.2)",
                                  padding:"18px 20px", width:300,
                                  display:"flex", flexDirection:"column", gap:10 }}>
                                <div style={{ fontFamily:T.fontDisplay,
                                  fontSize:"0.95rem", fontWeight:700, color:T.navy, marginBottom:2 }}>
                                  Zahlung erfassen · {pos.label}
                                </div>
                                {/* Betrag */}
                                <div>
                                  <div style={{ fontFamily:T.fontBody,
                                    fontSize:"0.75rem", fontWeight:600, color:T.textMuted,
                                    textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:3 }}>
                                    Gezahlt (€)
                                  </div>
                                  <input type="text" inputMode="decimal" autoFocus
                                    value={gezahltEdit.value}
                                    onChange={e => setGezahltEdit(p => ({...p, value: e.target.value.replace(/[^\d,.]/g,"")}))}
                                    onKeyDown={e => { if (e.key==="Escape") setGezahltEdit(null); }}
                                    style={{ width:"100%", padding:"5px 8px",
                                      border:`1.5px solid ${T.accent}`, borderRadius:5,
                                      fontFamily:"ui-monospace,monospace",
                                      fontSize:"0.975rem", outline:"none",
                                      boxSizing:"border-box" }} />
                                </div>
                                {/* Datum */}
                                <div>
                                  <div style={{ fontFamily:T.fontBody,
                                    fontSize:"0.75rem", fontWeight:600, color:T.textMuted,
                                    textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:3 }}>
                                    Datum Abrechnungsschreiben
                                  </div>
                                  <input type="date"
                                    value={gezahltEdit.datum}
                                    onChange={e => setGezahltEdit(p => ({...p, datum: e.target.value}))}
                                    style={{ width:"100%", padding:"5px 8px",
                                      border:`1px solid ${T.border}`, borderRadius:5,
                                      fontFamily:T.fontBody,
                                      fontSize:"0.875rem", outline:"none",
                                      boxSizing:"border-box" }} />
                                </div>
                                {/* Versicherung */}
                                <div>
                                  <div style={{ fontFamily:T.fontBody,
                                    fontSize:"0.75rem", fontWeight:600, color:T.textMuted,
                                    textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:3 }}>
                                    Versicherung
                                  </div>
                                  <input type="text"
                                    value={gezahltEdit.versicherung}
                                    onChange={e => setGezahltEdit(p => ({...p, versicherung: e.target.value}))}
                                    style={{ width:"100%", padding:"5px 8px",
                                      border:`1px solid ${T.border}`, borderRadius:5,
                                      fontFamily:T.fontBody,
                                      fontSize:"0.875rem", outline:"none",
                                      boxSizing:"border-box" }} />
                                </div>
                                {/* Referenz-Nr */}
                                <div>
                                  <div style={{ fontFamily:T.fontBody,
                                    fontSize:"0.75rem", fontWeight:600, color:T.textMuted,
                                    textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:3 }}>
                                    Referenz-Nr. (optional)
                                  </div>
                                  <input type="text"
                                    value={gezahltEdit.referenz_nr}
                                    onChange={e => setGezahltEdit(p => ({...p, referenz_nr: e.target.value}))}
                                    style={{ width:"100%", padding:"5px 8px",
                                      border:`1px solid ${T.border}`, borderRadius:5,
                                      fontFamily:T.fontBody,
                                      fontSize:"0.875rem", outline:"none",
                                      boxSizing:"border-box" }} />
                                </div>
                                {/* Buttons */}
                                <div style={{ display:"flex", gap:6, paddingTop:2 }}>
                                  <button
                                    onClick={() => {
                                      const v = parseFloat(String(gezahltEdit.value).replace(",",".")) || 0;
                                      saveGezahlt(pos.key, v);
                                    }}
                                    disabled={gezahltSaving}
                                    style={{ flex:1, background:T.navy, border:"none",
                                      borderRadius:6, padding:"6px 0", cursor:"pointer",
                                      color:"#fff", fontSize:"0.875rem", fontWeight:600 }}>
                                    {gezahltSaving ? "…" : "✓ Speichern"}
                                  </button>
                                  <button onClick={() => setGezahltEdit(null)}
                                    style={{ background:"none", border:`1px solid ${T.border}`,
                                      borderRadius:6, padding:"6px 10px", cursor:"pointer",
                                      color:T.textMuted, fontSize:"0.875rem" }}>
                                    Abbrechen
                                  </button>
                                </div>
                              </div>
                              {/* Trigger-Anzeige im Feld */}
                              <div style={{ fontFamily:"ui-monospace,monospace",
                                color:T.accent, fontSize:"0.875rem", textAlign:"right",
                                padding:"2px 4px" }}>
                                {gezahltEdit.value || "—"}
                              </div>
                            </>
                          ) : (
                            <div onClick={() => {
                              // Letzte manuell editierbare Zahlung für Update-Pfad merken
                              const letzteZ = pos.zahlungen.length > 0
                                ? pos.zahlungen[pos.zahlungen.length - 1]
                                : null;
                              setGezahltEdit({
                                posKey:      pos.key,
                                value:       gezahlt !== null ? String(gezahlt).replace(".",",") : "",
                                datum:       letzteZ?.datum || new Date().toISOString().slice(0,10),
                                versicherung: letzteZ?.versicherung || versicherungDefault,
                                referenz_nr:  referenzNr,
                                // Wenn genau eine Zahlung existiert: direkt updaten statt neue anlegen
                                ab_id:  pos.zahlungen.length === 1 ? letzteZ.ab_id  : null,
                                pos_id: pos.zahlungen.length === 1 ? letzteZ.pos_id : null,
                              });
                            }}
                              title="Klicken zum Bearbeiten"
                              style={{ cursor:"text", fontFamily:"ui-monospace,monospace",
                                color: gezahlt !== null ? T.text : T.textFaint,
                                textAlign:"right", padding:"2px 4px", borderRadius:4,
                                border:"1px solid transparent", transition:"border-color 0.15s",
                                minWidth:80, display:"inline-block" }}
                              onMouseEnter={e => e.currentTarget.style.borderColor = T.border}
                              onMouseLeave={e => e.currentTarget.style.borderColor = "transparent"}>
                              {gezahlt !== null
                                ? fmtEuro(gezahlt)
                                : <span style={{ fontSize:"0.78rem" }}>— eintragen</span>}
                            </div>
                          )}
                        </td>

                        {/* Kürzung */}
                        <td style={{ padding:"8px 12px", textAlign:"right" }}>
                          {gezahlt === null ? (
                            <span style={{ color:T.textFaint, fontFamily:"ui-monospace,monospace", fontSize:"0.82rem" }}>—</span>
                          ) : beglichen ? (
                            <span style={{ display:"inline-flex", alignItems:"center", gap:4,
                              background:T.greenBg, color:T.green, borderRadius:20,
                              padding:"2px 10px", fontSize:"0.8rem", fontWeight:600,
                              border:`1px solid ${T.green}33`, whiteSpace:"nowrap" }}>
                              ✓ beglichen
                            </span>
                          ) : (
                            <span style={{ fontFamily:"ui-monospace,monospace",
                              fontWeight:700, color:T.red }}>
                              −{fmtEuro(Math.abs(kuerzung))}
                            </span>
                          )}
                        </td>

                        {/* Kürzungsarten multi-tag */}
                        <td style={{ padding:"8px 12px" }}>
                          <div style={{ display:"flex", flexWrap:"wrap", gap:4, alignItems:"center" }}>
                            {kIds.map(id => {
                              const art = kuerzungsarten.find(k => k.id === id);
                              return art ? (
                                <span key={id} style={{ display:"inline-flex", alignItems:"center",
                                  gap:3, background:T.surface, border:`1px solid ${T.border}`,
                                  borderRadius:20, padding:"1px 8px", fontSize:"0.76rem",
                                  color:T.textMid, whiteSpace:"nowrap" }}>
                                  {art.bezeichnung}
                                  <button onClick={() => toggleKuerzungsart(pos.key, id)}
                                    style={{ background:"none", border:"none", cursor:"pointer",
                                      color:T.textFaint, padding:0, lineHeight:1, fontSize:"0.72rem",
                                      marginLeft:2 }}>✕</button>
                                </span>
                              ) : null;
                            })}
                            <div style={{ position:"relative" }}>
                              <button onClick={() => setKuerzungDropdown(p => p === pos.key ? null : pos.key)}
                                style={{ background:"none", border:`1px dashed ${T.border}`,
                                  borderRadius:20, padding:"1px 8px", cursor:"pointer",
                                  fontSize:"0.76rem", color:T.textFaint,
                                  transition:"border-color 0.15s" }}
                                onMouseEnter={e => e.currentTarget.style.borderColor = T.navy}
                                onMouseLeave={e => e.currentTarget.style.borderColor = T.border}>
                                + Art
                              </button>
                              {kuerzungDropdown === pos.key && (
                                <div onMouseDown={e => e.preventDefault()}
                                  style={{ position:"absolute", top:"calc(100% + 4px)", left:0,
                                  zIndex:200, background:T.cardBg, border:`1px solid ${T.border}`,
                                  borderRadius:8, boxShadow:"0 4px 20px rgba(0,0,0,0.12)",
                                  minWidth:240, maxHeight:220, overflowY:"auto" }}>
                                  {(() => {
                                    const relevKat = POS_KUERZUNG_KATEGORIE[pos.key] || null;
                                    const gefiltert = kuerzungsarten.filter(k => k.aktiv);
                                    const relevant  = relevKat
                                      ? gefiltert.filter(k => relevKat.includes(k.kategorie))
                                      : gefiltert;
                                    const andere    = relevKat
                                      ? gefiltert.filter(k => !relevKat.includes(k.kategorie))
                                      : [];
                                    const renderItem = (k) => (
                                      <label key={k.id}
                                        style={{ display:"flex", alignItems:"center", gap:8,
                                          padding:"6px 12px", cursor:"pointer",
                                          borderBottom:`1px solid ${T.borderSoft}`,
                                          background:"transparent", userSelect:"none" }}
                                        onMouseEnter={e => e.currentTarget.style.background = T.surface}
                                        onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                                        <input type="checkbox"
                                          checked={kIds.includes(k.id)}
                                          onChange={() => toggleKuerzungsart(pos.key, k.id)}
                                          style={{ accentColor:T.navy, width:14, height:14,
                                            cursor:"pointer", flexShrink:0 }} />
                                        <span style={{ fontSize:"0.83rem", color:T.text,
                                          fontWeight: kIds.includes(k.id) ? 600 : 400 }}>
                                          {k.bezeichnung}
                                        </span>
                                      </label>
                                    );
                                    return (
                                      <>
                                        {relevant.length > 0 && (
                                          <>
                                            {relevKat && (
                                              <div style={{ padding:"5px 12px 3px",
                                                fontSize:"0.72rem", fontWeight:600,
                                                color:T.textFaint, textTransform:"uppercase",
                                                letterSpacing:"0.07em", background:T.surface }}>
                                                Typisch für diese Position
                                              </div>
                                            )}
                                            {relevant.map(renderItem)}
                                          </>
                                        )}
                                        {andere.length > 0 && (
                                          <>
                                            <div style={{ padding:"5px 12px 3px",
                                              fontSize:"0.72rem", fontWeight:600,
                                              color:T.textFaint, textTransform:"uppercase",
                                              letterSpacing:"0.07em", background:T.surface }}>
                                              Weitere
                                            </div>
                                            {andere.map(renderItem)}
                                          </>
                                        )}
                                        <div style={{ padding:"6px 12px", borderTop:`1px solid ${T.border}`,
                                          background:T.surface, textAlign:"right" }}>
                                          <button
                                            onMouseDown={e => { e.preventDefault(); setKuerzungDropdown(null); }}
                                            style={{ background:T.navy, border:"none", borderRadius:5,
                                              padding:"3px 12px", cursor:"pointer",
                                              fontSize:"0.78rem", color:"#fff", fontWeight:600 }}>
                                            Fertig
                                          </button>
                                        </div>
                                      </>
                                    );
                                  })()}
                                </div>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* Klage */}
                        <td style={{ padding:"8px 12px", textAlign:"center" }}>
                          {hatKuerzung ? (
                            <button onClick={() => toggleKlage(pos.key)}
                              title={pos.fuer_klage ? "Klage-Flag entfernen" : "Für Klage vormerken"}
                              style={{ background: pos.fuer_klage ? T.accent : "transparent",
                                border:`1px solid ${pos.fuer_klage ? T.accent : T.border}`,
                                borderRadius:5, padding:"3px 9px", cursor:"pointer",
                                fontSize:"0.775rem", fontFamily:T.fontBody,
                                fontWeight: pos.fuer_klage ? 700 : 400,
                                color: pos.fuer_klage ? T.white : T.textMuted,
                                transition:"all 0.15s", whiteSpace:"nowrap" }}>
                              {pos.fuer_klage ? "✓ Klage" : "Klage"}
                            </button>
                          ) : <span style={{ color:T.textFaint, fontSize:"0.82rem" }}>—</span>}
                        </td>

                        {/* Löschen */}
                        <td style={{ padding:"4px 6px", textAlign:"center" }}>
                          {pos.zahlungen.length > 0 && (
                            <button onClick={() => {
                              if (pos.zahlungen.length === 1) {
                                loescheAbrechnung(pos.zahlungen[0].ab_id, pos.label);
                              } else {
                                setExpanded(p => { const n = new Set(p); n.add(pos.key); return n; });
                              }
                            }}
                              disabled={loeschenLaedt === pos.zahlungen[0]?.ab_id}
                              title={pos.zahlungen.length === 1 ? "Zahlung löschen" : "Aufklappen zum Löschen"}
                              style={{ background:"none", border:"none", cursor:"pointer",
                                color:T.textFaint, fontSize:"0.78rem", padding:2, lineHeight:1,
                                opacity:0.5, transition:"opacity 0.15s" }}
                              onMouseEnter={e => e.currentTarget.style.opacity = "1"}
                              onMouseLeave={e => e.currentTarget.style.opacity = "0.5"}>
                              {loeschenLaedt === pos.zahlungen[0]?.ab_id ? "…" : "🗑"}
                            </button>
                          )}
                        </td>
                      </tr>

                      {/* Zahlungshistorie (aufgeklappt) */}
                      {isExpanded && pos.zahlungen.map((z, zi) => (
                        <tr key={`${pos.key}-z${zi}`} style={{
                          background: idx%2===0 ? T.surface : T.offWhite,
                          borderBottom:`1px solid ${T.borderSoft}` }}>
                          <td />
                          <td style={{ padding:"5px 12px 5px 28px",
                            color:T.textFaint, fontSize:"0.82rem" }}>
                            <span style={{ marginRight:6, color:T.textFaint }}>↳</span>
                            <span style={{ color:T.textMid }}>
                              {z.versicherung || "Manuell"}
                            </span>
                            {z.quelle === "manuell" && (
                              <span style={{ marginLeft:6, fontSize:"0.72rem", color:T.textFaint,
                                background:T.surface, border:`1px solid ${T.border}`,
                                borderRadius:3, padding:"1px 5px" }}>manuell</span>
                            )}
                          </td>
                          <td />
                          <td style={{ padding:"5px 12px", textAlign:"right",
                            fontFamily:"ui-monospace,monospace", fontSize:"0.82rem",
                            color:T.textMid }}>
                            {fmtEuro(z.betrag)}
                          </td>
                          <td colSpan={3} style={{ padding:"5px 12px",
                            fontSize:"0.82rem", color:T.textFaint }}>
                            {z.datum}
                          </td>
                          <td style={{ padding:"5px 8px", textAlign:"center" }}>
                            {z.ab_id && (
                              <button onClick={() => loescheAbrechnung(z.ab_id, z.versicherung + " " + z.datum)}
                                disabled={loeschenLaedt === z.ab_id}
                                title="Abrechnung löschen"
                                style={{ background:"none", border:"none", cursor:"pointer",
                                  color:T.textFaint, fontSize:"0.78rem", padding:2, lineHeight:1,
                                  opacity: loeschenLaedt === z.ab_id ? 0.4 : 0.6,
                                  transition:"opacity 0.15s" }}
                                onMouseEnter={e => e.currentTarget.style.opacity = "1"}
                                onMouseLeave={e => e.currentTarget.style.opacity = "0.6"}>
                                {loeschenLaedt === z.ab_id ? "…" : "🗑"}
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </React.Fragment>
                  );
                })}
              </tbody>

              {/* Summen-Footer */}
              {allePos.length > 0 && (
                <tfoot>
                  <tr style={{ background:T.navyDark, borderTop:`2px solid ${T.accent}44` }}>
                    <td colSpan={2} style={{ padding:"10px 12px",
                      fontFamily:T.fontBody, fontWeight:700,
                      color:T.white, fontSize:"0.875rem" }}>Gesamt</td>
                    <td style={{ padding:"10px 12px", textAlign:"right",
                      fontFamily:"ui-monospace,monospace", fontWeight:700,
                      color:T.white }}>{fmtEuro(gesamtGefordert)}</td>
                    <td style={{ padding:"10px 12px", textAlign:"right",
                      fontFamily:"ui-monospace,monospace", fontWeight:700,
                      color:T.greenLight }}>{fmtEuro(gesamtGezahlt)}</td>
                    <td style={{ padding:"10px 12px", textAlign:"right",
                      fontFamily:"ui-monospace,monospace", fontWeight:700,
                      color: gesamtOffen > 0.01 ? T.redLight : T.greenLight }}>
                      {gesamtOffen > 0.01 ? `−${fmtEuro(gesamtOffen)}` : "✓ vollständig"}
                    </td>
                    <td colSpan={3} style={{ padding:"10px 12px" }}>
                      {klagebetrag > 0.01 && (
                        <span style={{ fontFamily:"ui-monospace,monospace",
                          fontSize:"0.84rem", color:T.accent, fontWeight:600 }}>
                          🏛 Klage: {fmtEuro(klagebetrag)}
                        </span>
                      )}
                    </td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </Card>

        {/* ── Klage-Zusammenfassung ── */}
        {klagebetrag > 0.01 && (
          <Card style={{ border:`1.5px solid ${T.accentTrim}`, background:T.accentPale }}>
            <CardHead title="Klagegegenstand" />
            <div style={{ padding:"0 1.4rem 1rem" }}>
              {allePos.filter(p => p.fuer_klage && (p.gefordert - (getGezahlt(p)||0)) > 0.01)
                .map((p, i, arr) => {
                  const offenBetrag = p.gefordert - (getGezahlt(p)||0);
                  const kIds = kuerzungMap[p.key] || [];
                  return (
                    <div key={p.key} style={{ display:"flex", justifyContent:"space-between",
                      alignItems:"center", padding:"7px 0",
                      borderBottom: i < arr.length-1 ? `1px solid ${T.border}` : "none",
                      fontFamily:T.fontBody, fontSize:"0.875rem" }}>
                      <div>
                        <span style={{ color:T.text, fontWeight:500 }}>{p.label}</span>
                        {kIds.length > 0 && (
                          <span style={{ marginLeft:8, fontSize:"0.78rem", color:T.textFaint }}>
                            ({kIds.map(id => kuerzungsarten.find(k=>k.id===id)?.bezeichnung).filter(Boolean).join(", ")})
                          </span>
                        )}
                      </div>
                      <span style={{ fontFamily:"ui-monospace,monospace", fontWeight:700, color:T.red }}>
                        −{fmtEuro(offenBetrag)}
                      </span>
                    </div>
                  );
                })}
              <div style={{ display:"flex", justifyContent:"space-between", padding:"10px 0 0",
                fontFamily:T.fontDisplay, fontSize:"1.125rem", fontWeight:700 }}>
                <span style={{ color:T.navy }}>Gesamt Klagegegenstand</span>
                <span style={{ color:T.red }}>{fmtEuro(klagebetrag)}</span>
              </div>
            </div>
          </Card>
        )}

        {/* ── Prüfberichte ── */}
        <Card>
          <CardHead
            title={`Prüfberichte (${pruefberichte.length})`}
            action={
              <div style={{ display:"flex", gap:6 }}>
                {(pruefberichte.length > 0 || abrechnungen.some(a => a.quelle === "pdf")) && (
                  <Btn size="sm"
                    variant={verweisFlag ? "danger" : "secondary"}
                    disabled={verweisLaden}
                    onClick={() => {
                      const pb = pruefberichte[0];
                      const abPdf = abrechnungen.find(a => a.quelle === "pdf");
                      if (pb) prüfeVerweisbetrieb(null, null, null, pb.id);
                      else if (abPdf?.dokument_id) prüfeVerweisbetrieb(null, abPdf.dokument_id);
                    }}>
                    {verweisLaden ? "⟳ Prüfe…" : verweisFlag ? "⚠️ Verweis zu weit" : "🔍 Verweis prüfen"}
                  </Btn>
                )}
                <Btn size="sm" variant="secondary" onClick={() => setShowPdf(true)}>
                  📄 Prüfbericht aus PDF
                </Btn>
              </div>
            }
          />
          {pruefberichte.length === 0 ? (
            <div style={{ padding:"1.5rem", textAlign:"center", color:T.textFaint, fontSize:"0.9rem" }}>
              Noch keine Prüfberichte erfasst.
            </div>
          ) : (
            <PruefberichteGespeichertListe
              pruefberichte={pruefberichte}
              mandantAdresse={mandantAdresse}
              akteId={akteId}
              onVerketteErfolg={(pbId, abId) => setPruefberichte(prev =>
                prev.map(pb => pb.id === pbId ? { ...pb, abrechnungsschreiben_id: abId } : pb))}
            />
          )}
        </Card>

      </div>

      <SlidePanel
        open={wizardOffen}
        onClose={() => setWizardOffen(false)}
        title="Stellungnahme erstellen"
      >
        <ReguWizard az={akteId} onClose={() => setWizardOffen(false)} />
      </SlidePanel>
    </>
  );
}

// ── ReguWizard ────────────────────────────────────────────────────────────────

const _STICKY_NAV = {
  position: "sticky", bottom: 0,
  background: T.cardBg, borderTop: "1px solid #e8ecf0",
  padding: "0.9rem 0 0", marginTop: "1.25rem",
  display: "flex", gap: "0.5rem", flexWrap: "wrap",
};

function ReguWizard({ az, onClose }) {
  const [step, setStep]               = useState(0);
  const [positionen, setPositionen]   = useState([]);
  const [texte, setTexte]             = useState({});
  const [frist, setFrist]             = useState(14);
  const [laden, setLaden]             = useState(true);
  const [generieren, setGenerieren]   = useState(false);
  const [speichernLaeuft, setSpeichernLaeuft] = useState(false);
  const [gespeichert, setGespeichert] = useState(false);
  const [fehler, setFehler]           = useState("");

  useEffect(() => {
    apiStellungnahme.vorschau(az)
      .then(data => {
        const posis = data.positionen || [];
        setPositionen(posis);
        const initTexte = {};
        posis.forEach(p => { initTexte[p._gruppe_key] = p.textbaustein_vorschlag || ""; });
        setTexte(initTexte);
      })
      .catch(e => setFehler(e.message))
      .finally(() => setLaden(false));
  }, [az]);

  const pos_steps_count = positionen.length;

  async function handleSpeichern() {
    setSpeichernLaeuft(true);
    setFehler("");
    try {
      await apiStellungnahme.texteSpeichern(az, texte);
      setGespeichert(true);
      setTimeout(() => setGespeichert(false), 2500);
    } catch (e) {
      setFehler(e.message);
    } finally {
      setSpeichernLaeuft(false);
    }
  }

  async function handleGenerieren() {
    setGenerieren(true);
    setFehler("");
    try {
      await apiStellungnahme.texteSpeichern(az, texte);
      await apiStellungnahme.generieren(az, null, texte);
      onClose();
    } catch (e) {
      setFehler(e.message);
      setGenerieren(false);
    }
  }

  if (laden) return (
    <div style={{ padding: "2rem", textAlign: "center", color: T.textMuted }}>Lade Kürzungspositionen…</div>
  );

  if (fehler && !positionen.length) return (
    <div style={{ padding: "2rem", color: T.red }}>
      <strong>Fehler:</strong> {fehler}
      <br /><br /><Btn size="sm" variant="secondary" onClick={onClose}>Schließen</Btn>
    </div>
  );

  // Step 0: Intro
  if (step === 0) return (
    <div>
      <h3 style={{ marginTop: 0, fontFamily: T.fontDisplay, color: T.navy }}>Stellungnahme erstellen</h3>
      <p style={{ color: T.textMid, lineHeight: 1.6 }}>
        Für diese Akte wurden <strong>{pos_steps_count}</strong> Kürzungsposition(en) gefunden.
        Der Assistent führt Sie durch jede Position und schlägt einen Gegenargument-Text vor.
      </p>
      {pos_steps_count === 0 && (
        <p style={{ color: T.amber }}>⚠ Keine Kürzungspositionen gefunden. Bitte zuerst ein Abrechnungsschreiben erfassen.</p>
      )}
      <div style={_STICKY_NAV}>
        <Btn size="sm" variant="secondary" onClick={onClose}>Abbrechen</Btn>
        <Btn size="sm" variant="primary" onClick={() => setStep(1)} disabled={pos_steps_count === 0}>Weiter →</Btn>
      </div>
    </div>
  );

  // Steps 1..pos_steps_count: Kürzungspositionen
  if (step >= 1 && step <= pos_steps_count) {
    const pos = positionen[step - 1];
    const key = pos._gruppe_key;
    return (
      <div>
        <div style={{ fontSize: "0.78rem", color: T.textFaint, marginBottom: "0.4rem", fontFamily: T.fontBody, fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase" }}>
          Position {step} von {pos_steps_count}
        </div>
        <h3 style={{ marginTop: 0, fontFamily: T.fontDisplay, color: T.navy, marginBottom: "0.35rem" }}>
          {pos.label || pos.bezeichnung}
        </h3>
        <div style={{ marginBottom: "0.85rem", fontSize: "0.88rem", color: T.textMid }}>
          Kürzungsbetrag: <strong style={{ color: T.red }}>−{Number(pos.kuerzung_gesamt).toFixed(2).replace(".", ",")} €</strong>
        </div>
        {pos.begruendung_roh && (
          <div style={{ marginBottom: "0.6rem", padding: "6px 10px", background: T.surface,
            borderLeft: `3px solid ${T.border}`, borderRadius: 4,
            fontFamily: T.fontBody, fontSize: "0.84rem", fontStyle: "italic", color: T.textMid }}>
            Versicherer: „{pos.begruendung_roh}“
          </div>
        )}
        <label style={{ display: "block", marginBottom: "0.35rem", fontFamily: T.fontBody, fontSize: "0.82rem", fontWeight: 600, color: T.textMid, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Gegenargument
        </label>
        <textarea
          rows={9}
          style={{ width: "100%", fontFamily: T.fontBody, fontSize: "0.92rem", padding: "0.6rem 0.75rem", boxSizing: "border-box", border: `1.5px solid ${T.border}`, borderRadius: 7, color: T.text, background: T.surface, resize: "vertical", lineHeight: 1.55 }}
          value={texte[key] || ""}
          onChange={e => setTexte(prev => ({ ...prev, [key]: e.target.value }))}
        />
        <div style={_STICKY_NAV}>
          <Btn size="sm" variant="secondary" onClick={() => setStep(s => s - 1)}>← Zurück</Btn>
          <Btn size="sm" variant="secondary" onClick={() => setTexte(prev => ({ ...prev, [key]: "" }))}>Überspringen</Btn>
          <Btn size="sm" variant="primary" onClick={() => setStep(s => s + 1)}>
            {step < pos_steps_count ? "Weiter →" : "Zur Frist →"}
          </Btn>
        </div>
      </div>
    );
  }

  // Frist-Step
  if (step === pos_steps_count + 1) return (
    <div>
      <h3 style={{ marginTop: 0, fontFamily: T.fontDisplay, color: T.navy }}>Zahlungsfrist</h3>
      <label style={{ fontFamily: T.fontBody, fontSize: "0.92rem", color: T.textMid, display: "flex", alignItems: "center", gap: "0.6rem" }}>
        Frist in Tagen ab heute:
        <input
          type="number" min={1} max={90} value={frist}
          onChange={e => setFrist(Number(e.target.value))}
          style={{ width: "4.5rem", textAlign: "center", padding: "6px 8px", border: `1.5px solid ${T.border}`, borderRadius: 7, fontFamily: T.fontBody, fontSize: "1rem" }}
        />
      </label>
      <div style={_STICKY_NAV}>
        <Btn size="sm" variant="secondary" onClick={() => setStep(s => s - 1)}>← Zurück</Btn>
        <Btn size="sm" variant="primary" onClick={() => setStep(s => s + 1)}>Zusammenfassung →</Btn>
      </div>
    </div>
  );

  // Abschluss-Step
  const mitText = positionen.filter(p => texte[p._gruppe_key]).length;
  return (
    <div>
      <h3 style={{ marginTop: 0, fontFamily: T.fontDisplay, color: T.navy }}>Zusammenfassung</h3>
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: "0.9rem 1.1rem", marginBottom: "0.75rem", fontSize: "0.92rem", color: T.textMid, lineHeight: 1.6 }}>
        <div><strong style={{ color: T.navy }}>{mitText}</strong> von {pos_steps_count} Positionen mit Gegenargument</div>
        <div>Zahlungsfrist: <strong style={{ color: T.navy }}>{frist} Tage</strong></div>
      </div>
      {fehler && <div style={{ color: T.red, marginBottom: "0.5rem", fontSize: "0.88rem" }}>{fehler}</div>}
      {gespeichert && <div style={{ color: T.green, marginBottom: "0.5rem", fontSize: "0.88rem" }}>✓ Texte gespeichert</div>}
      <div style={_STICKY_NAV}>
        <Btn size="sm" variant="secondary" onClick={() => setStep(s => s - 1)}>← Zurück</Btn>
        <Btn size="sm" variant="secondary" onClick={handleSpeichern} disabled={speichernLaeuft}>
          {speichernLaeuft ? "Speichere…" : "Speichern"}
        </Btn>
        <Btn size="sm" variant="primary" onClick={handleGenerieren} disabled={generieren}>
          {generieren ? "Generiere…" : "Word-Dokument erstellen"}
        </Btn>
      </div>
    </div>
  );
}

export default RegulierungSection;
