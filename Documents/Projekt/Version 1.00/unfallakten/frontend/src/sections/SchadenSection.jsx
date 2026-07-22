import React, { useState, useEffect, useMemo } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { ROLLEN_LABEL, ROLLEN_ICON, SCHADEN_F, ermittleAbrechnungsart, apiPS } from "../config/constants.js";
import { fmtEuro } from "../config/utils.js";
import { Card, CardHead, Btn, Toast } from "../components/common.jsx";
import {
  akten as apiAkten,
  schaden as apiSchaden,
  parsePdf as apiParsePdf,
  ramicroWdm,
  belege as apiBelege,
  tokenStore,
  API_BASE,
} from "../api.js";

// PRD-23b: Backend position_keys → SCHADEN_F display-keys (netto-Varianten auf UI-Felder mappen)
const KANDIDAT_DISPLAY_KEY = {
  rep_rechnung_netto:    "rep_rechnung_brutto",
  mietwagenkosten_netto: "mietwagenkosten",
  abschleppkosten_netto: "abschleppkosten",
  standkosten_netto:     "standkosten",
  sv_kosten_netto:       "sv_kosten",
};

const QUELLE_LABELS = { manuell:"Manuell", gutachten_pdf:"Gutachten (PDF)", abrechnung_pdf:"Abrechnung (PDF)", korrektur:"Korrektur", wdm_ramicro:"RA-Micro (WDM)" };
const QUELLE_COLORS = { manuell:{c:T.textMuted,bg:T.surface}, gutachten_pdf:{c:T.blue,bg:T.blueBg}, abrechnung_pdf:{c:T.green,bg:T.greenBg}, korrektur:{c:T.amber,bg:T.amberBg}, wdm_ramicro:{c:"#6b21a8",bg:"#f5f3ff"} };

function SchadenSection({ schaden, hq, dispatch, akteId, vorsteuer = false, dokumente, belegeKandidaten = [] }) {
  const [form, setForm]         = useState({ ...schaden });
  const [schadenTab, setSchadenTab] = useState("sachschaden");

  // Personenschaden-State
  const [psForm, setPsForm]   = useState({});
  const [psChg, setPsChg]     = useState(false);
  const [psSaving, setPsSave] = useState(false);
  const [psToast, setPsToast] = useState("");

  // Personenschaden laden
  React.useEffect(() => {
    if (!akteId) return;
    apiPS.laden(akteId)
      .then(d => { if (d?.personenschaden) setPsForm(d.personenschaden); })
      .catch(() => {});
  }, [akteId]);

  const savePsForm = async () => {
    setPsSave(true);
    try {
      await apiPS.speichern(akteId, psForm);
      setPsToast("✓ Personenschaden gespeichert."); setPsChg(false);
    } catch(e) {
      setPsToast("⚠ Speichern fehlgeschlagen.");
    } finally { setPsSave(false); }
  };
  const psUpd = (k, v) => { setPsForm(p => ({...p, [k]: v})); setPsChg(true); };

  // formInitialisiert: verhindert dass nach Speichern der Store die form überschreibt
  const [formInitialisiert, setFormInitialisiert] = useState(false);

  // Wenn die Schaden-Prop nachgeladen wird (nach DB-Fetch), form aktualisieren
  // Aber NUR wenn noch nicht initialisiert (= erste Ladung oder Akte wechsel)
  useEffect(() => {
    if (formInitialisiert) return; // Bereits initialisiert → nicht überschreiben
    if (schaden && Object.keys(schaden).some(k => (schaden[k] || 0) > 0)) {
      setForm({ ...schaden });
      setFormInitialisiert(true);
      // Vorschlag berechnen wenn abrechnungsart noch nicht gesetzt
      if (!schaden.abrechnungsart) setArtVorschlag(ermittleAbrechnungsart(schaden, vorsteuer));
      // _extras aus _extras (Store nach WDM-Übernahme) oder wdm_extras_json (nach DB-Reload)
      if (schaden._extras && schaden._extras.length > 0) {
        setExtras(schaden._extras);
      } else if (schaden.wdm_extras_json) {
        try {
          const p = JSON.parse(schaden.wdm_extras_json);
          if (Array.isArray(p) && p.length > 0) setExtras(p);
        } catch {}
      }
    }
  }, [schaden, formInitialisiert]); // eslint-disable-line react-hooks/exhaustive-deps

  // Bei Akte-Wechsel: Initialisierung zurücksetzen
  useEffect(() => {
    setFormInitialisiert(false);
    setChg(false);
  }, [akteId]); // eslint-disable-line react-hooks/exhaustive-deps
  const [changed, setChg]       = useState(false);
  const [saving, setSaving]     = useState(false);
  const [toast, setToast]       = useState("");
  // _extras: entweder direkt (nach WDM-Übernahme im Store) oder aus wdm_extras_json parsen
  const _initExtras = (() => {
    if (schaden._extras && schaden._extras.length > 0) return schaden._extras;
    if (schaden.wdm_extras_json) {
      try { const p = JSON.parse(schaden.wdm_extras_json); if (Array.isArray(p)) return p; } catch {}
    }
    return [];
  })();
  const [extras, setExtras]     = useState(_initExtras);
  const [showAdd, setShowAdd]   = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newBetrag, setNewBetrag] = useState("");
  const [newMwst, setNewMwst]   = useState("");

  // ── WDM-Discovery ────────────────────────────────────────────────────────
  const [wdmLaden, setWdmLaden]         = useState(false);
  const [wdmSchadenDaten, setWdmSchaden]= useState(null);
  // true wenn User explizit "WDM neu laden" geklickt hat → Panel immer anzeigen
  const [wdmExplizit, setWdmExplizit]   = useState(false);
  // Automatisch erkannte Abrechnungsart (Vorschlag)
  const [artVorschlag, setArtVorschlag] = useState(null);

  // Prüfen ob lokale DB Schadendaten hat
  const hatLokaleWerte = React.useMemo(() => {
    const felder = ["rep_gutachten_netto","rep_rechnung_brutto","wiederbeschaffung",
                    "wertminderung","nutzungsausfall","mietwagenkosten","sv_kosten",
                    "mietwagenkosten_netto","sv_kosten_netto","abschleppkosten_netto",
                    "standkosten_netto","anabmeldekosten_netto",
                    "schmerzensgeld","abschleppkosten","standkosten","anabmeldekosten",
                    "verdienstausfall","haushalt","unkostenpauschale","sonstiges"];
    return felder.some(k => (schaden[k] || 0) > 0) || (schaden._extras?.length > 0);
  }, [schaden]);



  const uebernehmeWdmSchaden = async () => {
    if (!wdmSchadenDaten?.schaden) return;
    const neu = { ...form };
    // Alle Schaden-Felder übernehmen (inkl. neuer netto/ust-Felder aus Migration 14)
    Object.entries(wdmSchadenDaten.schaden).forEach(([k, v]) => {
      if (v > 0) neu[k] = v;
    });
    neu.quelle = "wdm_ramicro";

    // Extras (sonstige Schäden 1-6) mit netto/mwst/brutto übernehmen
    const wdmExtras = (wdmSchadenDaten.extras || []).filter(e => (e.betrag||0) > 0);
    const mergedExtras = wdmExtras.length > 0
      ? [...extras.filter(e => !String(e.id).startsWith("wdm_ss")), ...wdmExtras]
      : extras;

    if (wdmExtras.length > 0) {
      setExtras(mergedExtras);
      neu._extras = mergedExtras;
    }

    // Abrechnungsart-Vorschlag aus WDM-Daten berechnen
    const wdmArtVorschlag = ermittleAbrechnungsart(neu, vorsteuer);
    if (wdmArtVorschlag && !neu.abrechnungsart) {
      neu.abrechnungsart = wdmArtVorschlag.art;
    }
    setArtVorschlag(wdmArtVorschlag);
    setForm(neu);
    setFormInitialisiert(true); // WDM-Daten sind jetzt die Basis → nicht durch Store überschreiben
    setChg(false);
    setWdmExplizit(false); // Panel nach Übernahme schließen

    // Direkt in SQLite speichern — nicht auf manuelles Speichern warten
    setSaving(true);
    const schadenBrutto = calcBrutto(neu, mergedExtras);

    const schadenData = { ...neu, gesamt_brutto: schadenBrutto, _extras: mergedExtras };
    try {
      const res = await apiSchaden.speichern(akteId, schadenData);
      const serverSchaden = res?.schaden || schadenData;
      dispatch({ type:"SAVE_SCHADEN", akteId, schaden: { ...schadenData, gesamt_brutto: serverSchaden.gesamt_brutto ?? schadenBrutto, abrechnungsberechnung: serverSchaden.abrechnungsberechnung } });
      const n = Object.values(wdmSchadenDaten.schaden).filter(v => v > 0).length;
      const x = wdmExtras.length;
      setToast(`✓ ${n} Schadenpositionen${x>0?` + ${x} sonstige Schäden`:""} aus RA-Micro übernommen und gespeichert.`);
    } catch(err) {
      const msg = err?.message || String(err);
      dispatch({ type:"SAVE_SCHADEN", akteId, schaden: schadenData });
      setToast(`⚠ Speichern fehlgeschlagen: ${msg.slice(0,120)}`);
    } finally {
      setSaving(false);
    }
  };

  const upd = (k, v) => {
    setForm(p => {
      const neu = {...p, [k]: typeof v === "number" ? v : (parseFloat(v)||0)};
      // Vorschlag sofort neu berechnen wenn relevantes Feld geändert
      const relevant = ["rep_gutachten_netto","rep_rechnung_netto","rep_rechnung_brutto",
                        "reparaturkosten","wiederbeschaffung","restwert"];
      if (relevant.includes(k)) setArtVorschlag(ermittleAbrechnungsart(neu, vorsteuer));
      return neu;
    });
    setChg(true);
  };

  // Schadensumme — einheitliche Fahrzeugschaden-Logik
  const calcBrutto = (f, ex) => {
    const g   = k => parseFloat(f[k]) || 0;
    const repN  = g("rep_gutachten_netto") || g("reparaturkosten");
    const repRN = g("rep_rechnung_netto");
    const effRep = repRN > 0 ? repRN : repN;
    const wbw  = g("wiederbeschaffung");
    const rst  = g("restwert");
    const nettoFzg  = wbw - rst;
    const ist130Fall = repRN > 0 && wbw > 0 && repRN > nettoFzg && repRN <= 1.3 * wbw;
    const art = f.abrechnungsart || null;
    // Fahrzeugschaden: explizite abrechnungsart hat Vorrang vor Auto-Logik
    let fahrzeug;
    if (art === "totalschaden") {
      fahrzeug = wbw > 0 ? nettoFzg : 0;
    } else if (art === "fiktiv") {
      fahrzeug = repN;
    } else if (art === "konkret") {
      fahrzeug = repRN > 0 ? repRN : repN;
    } else {
      // Auto-Logik (kein art gesetzt)
      fahrzeug = wbw > 0
        ? (ist130Fall || (effRep > 0 && effRep <= nettoFzg) ? effRep : nettoFzg)
        : effRep;
    }
    return fahrzeug
      + g("wertminderung") + g("nutzungsausfall") + g("mietwagenkosten")
      + g("sv_kosten") + g("abschleppkosten") + g("standkosten")
      + g("anabmeldekosten") + g("schmerzensgeld") + g("sonstiges")
      + g("verdienstausfall") + g("haushalt") + g("unkostenpauschale")
      + g("kostennb") + g("kostennb_ust")
      + (ex || []).reduce((s, e) => s + (parseFloat(e.betrag) || 0), 0);
  };

  const brutto = calcBrutto(form, extras);
  const netto  = brutto * (hq / 100);

  const save = async () => {
    setSaving(true);
    // Abrechnungsart automatisch setzen wenn noch leer
    const autoArt = !form.abrechnungsart ? ermittleAbrechnungsart(form, vorsteuer) : null;
    const schadenData = {
      ...form,
      gesamt_brutto: brutto,
      _extras: extras,
      ...(autoArt ? { abrechnungsart: autoArt.art } : {}),
    };
    if (autoArt) { setForm(p => ({...p, abrechnungsart: autoArt.art})); setArtVorschlag(autoArt); }
    try {
      const res = await apiSchaden.speichern(akteId, schadenData);
      // Backend liefert korrektes gesamt_brutto zurück — diesen Wert nutzen
      const serverSchaden = res?.schaden || schadenData;
      dispatch({ type:"SAVE_SCHADEN", akteId, schaden: { ...schadenData, gesamt_brutto: serverSchaden.gesamt_brutto ?? brutto, abrechnungsberechnung: serverSchaden.abrechnungsberechnung } });
      setSaving(false); setChg(false); setToast("✓ Schaden gespeichert.");
    } catch(err) {
      const msg = err?.message || String(err);
      setSaving(false);
      setToast(`⚠ Speichern fehlgeschlagen: ${msg.slice(0,120)}`);
    }
  };

  const qc = QUELLE_COLORS[form.quelle] || QUELLE_COLORS.manuell;

  // Gutachten-PDF-Import
  const [showGutImport, setShowGutImport] = useState(false);
  const [gutFile, setGutFile]     = useState(null);
  const [gutLoading, setGutLoad]  = useState(false);
  const [gutErgebnis, setGutErg]  = useState(null);
  const [gutError, setGutError]   = useState("");
  const [gutDocId, setGutDocId]   = useState(null); // dok_id des gewählten Gutachtens
  const [llmWahl, setLlmWahl]    = useState({});   // { rep_netto:'ki', wbw:'ki', ... } PRD-31

  // Vorhandene Gutachten-PDFs aus importierten/hochgeladenen Dokumenten
  const gutachtenDoks = useMemo(() =>
    (dokumente || []).filter(d =>
      d.dateityp === "pdf" &&
      (d.dokumentenklasse === "gutachten" || d.typ === "gutachten")
    ), [dokumente]);

  // Vorhandenes PDF parsen (kein Upload)
  const handleGutVorhandenes = async (dokId, dateiname) => {
    setGutLoad(true);
    setGutError("");
    setGutErg(null);
    setLlmWahl({});
    setGutDocId(dokId);
    setGutFile({ name: dateiname });
    try {
      const res = await apiParsePdf.parseVorhandenes(akteId, dokId, "gutachten");
      if (res?.warnung) {
        setGutError(res.warnung);
      } else if (res?.ergebnis) {
        setGutErg(res.ergebnis);
      } else {
        setGutError("Dokument konnte nicht verarbeitet werden.");
      }
    } catch(e) {
      setGutError("Fehler beim Parsen: " + (e?.message || String(e)));
    } finally {
      setGutLoad(false);
    }
  };

  const handleGutDatei = async (file) => {
    if (!file) return;
    setGutFile(file);
    setGutDocId(null); // Neu-Upload: kein bestehender Datensatz
    setGutLoad(true);
    setGutError("");
    setGutErg(null);
    setLlmWahl({});
    try {
      const res = await apiParsePdf.parse(akteId, file);
      if (res?.ergebnis?.dokumenttyp === "gutachten") {
        setGutErg(res.ergebnis);
        // Chronik sofort aktualisieren – Backend hat bereits logge_aktivitaet geschrieben
        try {
          const aktData = await apiAkten.aktivitaeten(akteId);
          if (aktData?.aktivitaeten) {
            dispatch({ type: "SET_AKTIVITAETEN", akteId, aktivitaeten: aktData.aktivitaeten });
          }
        } catch { /* Chronik-Refresh nicht kritisch */ }
      } else if (res?.ergebnis) {
        setGutError(`Dokument wurde als „${res.ergebnis.dokumenttyp}" erkannt, nicht als Gutachten. Bitte richtiges Dokument wählen.`);
      } else {
        setGutError("Dokument konnte nicht verarbeitet werden.");
      }
    } catch(e) {
      setGutError("Fehler beim Parsen: " + (e?.message || String(e)));
    } finally {
      setGutLoad(false);
    }
  };

  const handleGutachtenUebernehmen = async () => {
    if (!gutErgebnis?.schadenpositionen) return;
    const pos = gutErgebnis.schadenpositionen;
    const updates = {};
    // Für jede Position: wenn User 'ki' gewählt hat, LLM-Wert nehmen, sonst Regex
    const _pick = (regex, llm, key) => llmWahl[key] === 'ki' && llm ? llm : regex;
    const repNetto = _pick(pos.rep_gutachten_netto || pos.reparaturkosten, gutErgebnis.llm_reparaturkosten_netto, 'rep_netto');
    if (repNetto)              updates.rep_gutachten_netto = repNetto;
    const wbw = _pick(pos.wiederbeschaffung, gutErgebnis.llm_wbw, 'wbw');
    if (wbw)                   updates.wiederbeschaffung   = wbw;
    const rv  = _pick(pos.restwert, gutErgebnis.llm_restwert, 'restwert');
    if (rv)                    updates.restwert             = rv;
    const wm  = _pick(pos.wertminderung, gutErgebnis.llm_wertminderung, 'wertminderung');
    if (wm)                    updates.wertminderung        = wm;
    if (pos.nutzungsausfall)   updates.nutzungsausfall      = pos.nutzungsausfall; // kein LLM-Gesamtbetrag
    const sv  = _pick(pos.sv_kosten, gutErgebnis.llm_sv_kosten_netto, 'sv_netto');
    if (sv)                    updates.sv_kosten            = sv;
    setLlmWahl({});
    setForm(prev => {
      const neu = { ...prev, ...updates, quelle: "gutachten_pdf" };
      setArtVorschlag(ermittleAbrechnungsart(neu, vorsteuer));
      return neu;
    });
    setChg(true);
    setShowGutImport(false);
    setGutErg(null);
    setGutFile(null);

    // Beleg-Einträge für alle Gutachten-Positionen registrieren
    if (gutDocId) {
      await Promise.all(
        Object.entries(updates).map(([posKey, betrag]) =>
          apiBelege.zuordnen(akteId, posKey, gutDocId, betrag).catch(() => {})
        )
      );
      try {
        const res = await apiBelege.liste(akteId);
        const map = {};
        (res?.belege || []).forEach(b => { map[b.position_key] = b; });
        setBelegMap(map);
      } catch { /* nicht kritisch */ }
    }

    setGutDocId(null);
    setToast("Gutachten-Werte übernommen – bitte prüfen und speichern.");
  };

  const [focusedField, setFocusedField] = useState(null);
  const [editValue, setEditValue]       = useState("");
  // ── Belege (PRD-23a) ──────────────────────────────────────────────────────
  const [belegMap, setBelegMap]           = useState({});  // {position_key: {id, dokument_id, dateiname, betrag, ...}}
  const [belegVorschau, setBelegVorschau] = useState(null); // dokument_id fuer Vorschau
  const [belegVorschauUrl, setBelegVorschauUrl] = useState(null);
  const [belegZuordnen, setBelegZuordnen] = useState(null); // position_key die gerade zugeordnet wird

  // ── Rechnungs-Kandidaten (PRD-23b) ────────────────────────────────────────
  const [kandidatView, setKandidatView]         = useState(null); // position_key
  const [kandidatVorschauUrl, setKandidatVorschauUrl] = useState(null);
  const [kandidatVorschauLaden, setKandidatVorschauLaden] = useState(false);

  const kandidatMap = useMemo(() => {
    const map = {};
    (belegeKandidaten || []).forEach(k => {
      if (!k.position_key) return;
      const dk = KANDIDAT_DISPLAY_KEY[k.position_key] || k.position_key;
      // Höchste Konfidenz gewinnt (sv_rechnung 0.93 schlägt gutachten 0.80)
      if (!map[dk] || (k.konfidenz || 0) > (map[dk].konfidenz || 0)) map[dk] = k;
    });
    return map;
  }, [belegeKandidaten]);

  // Kandidaten ohne Positionszuweisung (z.B. Abrechnungsschreiben)
  const referenzKandidaten = useMemo(() =>
    (belegeKandidaten || []).filter(k => !k.position_key),
    [belegeKandidaten]);

  const aktiverKandidat = kandidatView ? (kandidatMap[kandidatView] || null) : null;

  // Vorschau für aktiven Kandidaten laden
  useEffect(() => {
    if (!aktiverKandidat) {
      if (kandidatVorschauUrl) { URL.revokeObjectURL(kandidatVorschauUrl); setKandidatVorschauUrl(null); }
      return;
    }
    setKandidatVorschauLaden(true);
    setKandidatVorschauUrl(null);
    const token = tokenStore.getAccess();
    const url = aktiverKandidat.quelle === "eakte"
      ? `${API_BASE}/akten/${akteId}/eakte/${aktiverKandidat.eakte_nr}/datei`
      : `${API_BASE}/akten/${akteId}/dokumente/${aktiverKandidat.dok_id}/datei`;
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => { if (!r.ok) throw new Error(); return r.blob(); })
      .then(blob => setKandidatVorschauUrl(URL.createObjectURL(blob)))
      .catch(() => { setKandidatVorschauUrl(null); setToast("Vorschau fehlgeschlagen"); })
      .finally(() => setKandidatVorschauLaden(false));
    return () => { if (kandidatVorschauUrl) URL.revokeObjectURL(kandidatVorschauUrl); };
  }, [kandidatView]); // eslint-disable-line react-hooks/exhaustive-deps

  // Alle vorhandenen PDFs fuer Dropdown
  const belegfaehigePdfs = useMemo(() =>
    (dokumente || []).filter(d => d.dateityp === "pdf" && d.id),
    [dokumente]);

  // Belege laden
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

  // Vorschau laden (Blob-URL)
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

  // Beleg zuordnen
  const handleBelegZuordnen = async (posKey, dokId) => {
    try {
      await apiBelege.zuordnen(akteId, posKey, dokId);
      // Neu laden
      const res = await apiBelege.liste(akteId);
      const map = {};
      (res?.belege || []).forEach(b => { map[b.position_key] = b; });
      setBelegMap(map);
      setBelegZuordnen(null);
      setToast("Beleg zugeordnet.");
    } catch (e) {
      setToast("Zuordnung fehlgeschlagen: " + (e?.message || ""));
    }
  };

  // Beleg entfernen
  const handleBelegEntfernen = async (posKey) => {
    const beleg = belegMap[posKey];
    if (!beleg) return;
    try {
      await apiBelege.entfernen(akteId, beleg.id);
      setBelegMap(prev => { const n = { ...prev }; delete n[posKey]; return n; });
      setToast("Beleg-Zuordnung entfernt.");
    } catch (e) {
      setToast("Entfernen fehlgeschlagen: " + (e?.message || ""));
    }
  };

  // Alle Vorschläge auf einmal übernehmen (≥ 80 % Konfidenz)
  const [alleUebernehmenLaden, setAlleUebernehmenLaden] = useState(false);

  const handleAlleVorschlaegeUebernehmen = async () => {
    const treffer = Object.entries(kandidatMap).filter(
      ([, k]) => k.betrag_vorschlag != null && (k.konfidenz || 0) >= 0.80
    );
    if (treffer.length === 0) {
      setToast("Keine sicheren Vorschläge (≥ 80 %) vorhanden.");
      return;
    }
    setAlleUebernehmenLaden(true);
    const updates = Object.fromEntries(treffer.map(([dk, k]) => [dk, k.betrag_vorschlag]));
    setForm(prev => ({ ...prev, ...updates }));
    setChg(true);
    try {
      await Promise.all(
        treffer
          .filter(([, k]) => k.dok_id)
          .map(([dk, k]) => apiBelege.zuordnen(akteId, dk, k.dok_id, k.betrag_vorschlag).catch(() => {}))
      );
      const res = await apiBelege.liste(akteId);
      const map = {};
      (res?.belege || []).forEach(b => { map[b.position_key] = b; });
      setBelegMap(map);
    } catch { /* nicht kritisch */ }
    setAlleUebernehmenLaden(false);
    setToast(`${treffer.length} ${treffer.length === 1 ? "Vorschlag" : "Vorschläge"} übernommen – bitte speichern.`);
  };

  // Kandidat übernehmen (PRD-23b)
  const handleKandidatUebernehmen = async (displayKey, kandidat) => {
    const betrag = kandidat.betrag_vorschlag;
    setForm(prev => ({ ...prev, [displayKey]: betrag }));
    setChg(true);
    if (kandidat.dok_id) {
      try {
        await apiBelege.zuordnen(akteId, displayKey, kandidat.dok_id, betrag);
        const res = await apiBelege.liste(akteId);
        const map = {};
        (res?.belege || []).forEach(b => { map[b.position_key] = b; });
        setBelegMap(map);
      } catch { /* Beleg-Fehler nicht kritisch */ }
    }
    setToast(`${fmtEuro(betrag)} übernommen – bitte speichern.`);
    setKandidatView(null);
  };

  const fmtField = (v) => v ? new Intl.NumberFormat("de-DE", { minimumFractionDigits:2, maximumFractionDigits:2 }).format(v) : "";

  const rowStyle   = { display:"grid", gridTemplateColumns:"220px 1fr auto", alignItems:"center", gap:"0.75rem", padding:"0.55rem 0", borderBottom:`1px solid ${T.borderSoft}` };
  const labelStyle = { fontFamily:T.fontBody, fontSize:"0.895rem", fontWeight:600, color:T.textMid, letterSpacing:"0.02em" };

  const renderEuroInput = (fieldKey, { abzug=false, extraValue, onExtraChange } = {}) => {
    const isExtra = extraValue !== undefined;
    const storedVal = isExtra ? extraValue : (form[fieldKey]||0);
    const isFoc   = focusedField === fieldKey;
    // WBW-Sentinel: "ausreichend" anzeigen wenn nicht im Fokus
    const isWbwAusreichend = !isExtra && fieldKey === "wiederbeschaffung" && storedVal >= 999_999 && !isFoc;
    return (
      <div style={{ display:"flex", border:`1.5px solid ${isFoc ? T.accent : isWbwAusreichend ? T.green+"66" : T.border}`, borderRadius:5, overflow:"hidden", background:isWbwAusreichend ? T.green+"10" : T.surface, maxWidth:240, transition:"border-color 0.15s" }}>
        <span style={{ padding:"4px 7px", fontFamily:"ui-monospace,monospace", fontSize:"0.82rem", color:abzug?T.red:isWbwAusreichend?T.green:T.textFaint, background:T.offWhite, borderRight:`1px solid ${T.border}`, flexShrink:0 }}>{abzug?"−€":"€"}</span>
        <input
          type="text"
          inputMode="decimal"
          value={isFoc ? editValue : isWbwAusreichend ? "ausreichend" : fmtField(storedVal)}
          onChange={e => {
            // Nur Ziffern, Komma und Punkt erlauben
            const cleaned = e.target.value.replace(/[^\d,.]/g, "");
            setEditValue(cleaned);
          }}
          onFocus={() => {
            setFocusedField(fieldKey);
            // Beim Fokussieren: gespeicherten Wert als Rohstring anzeigen (0 → leer)
            setEditValue(storedVal ? String(storedVal).replace(".", ",") : "");
          }}
          onBlur={() => {
            // Beim Verlassen: String in Zahl umwandeln und speichern
            const raw = editValue.replace(",", ".");
            const num = parseFloat(raw) || 0;
            if (isExtra) onExtraChange(num);
            else upd(fieldKey, num);
            setFocusedField(null);
            setEditValue("");
          }}
          placeholder="0,00"
          style={{ flex:1, minWidth:0, padding:"4px 8px 4px 6px", border:"none", background:"transparent", outline:"none", fontFamily:"ui-monospace,monospace", fontSize:"0.82rem", color:isWbwAusreichend?T.green:T.text, textAlign:"right", fontWeight:isWbwAusreichend?600:400 }}
        />
      </div>
    );
  };

  // 130%-Fall-Erkennung für Hinweis-Banner
  const _cb = k => parseFloat(form[k]) || 0;
  const _cbRepRN = _cb("rep_rechnung_netto");
  const _cbWbw   = _cb("wiederbeschaffung");
  const _cbRst   = _cb("restwert");
  const zeige130Hinweis = _cbRepRN > 0 && _cbWbw > 0
    && _cbRepRN > (_cbWbw - _cbRst) && _cbRepRN <= 1.3 * _cbWbw;

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      {psToast && <Toast msg={psToast} onDone={() => setPsToast("")} />}

      {/* Beleg-Vorschau Modal (PRD-23a) */}
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
              <span style={{ fontFamily:T.fontBody, fontSize:"0.9rem", fontWeight:600, color:T.navy }}>
                📄 Beleg-Vorschau
              </span>
              <button onClick={() => setBelegVorschau(null)}
                style={{ background:"none", border:"none", cursor:"pointer", fontSize:"1.2rem", color:T.textFaint, lineHeight:1 }}>✕</button>
            </div>
            {belegVorschauUrl ? (
              <iframe src={belegVorschauUrl} style={{ flex:1, border:"none" }} title="Beleg" />
            ) : (
              <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", color:T.textMuted }}>
                <div style={{ width:24, height:24, border:`3px solid ${T.accentTrim}`, borderTopColor:T.accent, borderRadius:"50%", animation:"spin 0.8s linear infinite", marginRight:10 }} />
                PDF wird geladen…
              </div>
            )}
          </div>
        </>
      )}

      {/* Beleg-Vorschau Modal */}
      {belegVorschau && (
        <>
          <div onClick={() => setBelegVorschau(null)}
            style={{ position:"fixed", top:0, left:0, right:0, bottom:0, background:"rgba(0,0,0,0.4)", zIndex:950 }} />
          <div style={{ position:"fixed", top:"5%", left:"10%", right:"10%", bottom:"5%",
            zIndex:951, background:T.white, borderRadius:12,
            boxShadow:"0 16px 48px rgba(0,0,0,0.25)", display:"flex", flexDirection:"column" }}>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center",
              padding:"12px 18px", borderBottom:`1px solid ${T.border}` }}>
              <span style={{ fontFamily:T.fontBody, fontSize:"0.9rem", fontWeight:600, color:T.navy }}>
                📄 Beleg-Vorschau
              </span>
              <button onClick={() => setBelegVorschau(null)}
                style={{ background:"none", border:"none", cursor:"pointer", fontSize:"1.2rem", color:T.textFaint, padding:4 }}>✕</button>
            </div>
            <div style={{ flex:1, padding:12 }}>
              {belegVorschauUrl ? (
                <iframe src={belegVorschauUrl} style={{ width:"100%", height:"100%", border:`1px solid ${T.border}`, borderRadius:8 }} title="Beleg" />
              ) : (
                <div style={{ display:"flex", alignItems:"center", justifyContent:"center", height:"100%", color:T.textMuted }}>
                  <div style={{ width:24, height:24, border:`3px solid ${T.accentTrim}`, borderTopColor:T.accent, borderRadius:"50%", animation:"spin 0.8s linear infinite", marginRight:10 }} />
                  PDF wird geladen…
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* ── Kandidat-Split-View (PRD-23b) ──────────────────────────────── */}
      {kandidatView && aktiverKandidat && (
        <>
          <div onClick={() => setKandidatView(null)}
            style={{ position:"fixed", top:0, left:0, right:0, bottom:0, background:"rgba(0,0,0,0.4)", zIndex:950 }} />
          <div style={{ position:"fixed", top:"4%", left:"4%", right:"4%", bottom:"4%",
            zIndex:951, background:T.white, borderRadius:12,
            boxShadow:"0 20px 60px rgba(0,0,0,0.3)", display:"flex", flexDirection:"column", overflow:"hidden" }}>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center",
              padding:"12px 20px", borderBottom:`1px solid ${T.border}`, background:T.surface }}>
              <span style={{ fontFamily:T.fontBody, fontSize:"0.9rem", fontWeight:600, color:T.navy }}>
                📎 Rechnungsvorschlag – {SCHADEN_F.find(sf => sf.k === kandidatView)?.l || kandidatView}
              </span>
              <button onClick={() => setKandidatView(null)}
                style={{ background:"none", border:"none", cursor:"pointer", fontSize:"1.2rem", color:T.textFaint, lineHeight:1 }}>✕</button>
            </div>
            <div style={{ flex:1, display:"flex", overflow:"hidden" }}>
              {/* Links: Infos + Aktionen */}
              <div style={{ width:270, flexShrink:0, padding:"1.25rem 1.5rem", borderRight:`1px solid ${T.border}`, display:"flex", flexDirection:"column", gap:16, overflowY:"auto" }}>
                <div>
                  <div style={{ fontSize:"0.72rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em", marginBottom:4 }}>Vorschlag</div>
                  <div style={{ fontSize:"1.6rem", fontWeight:700, color:T.navy, fontFamily:"ui-monospace,monospace" }}>
                    {aktiverKandidat.betrag_vorschlag != null ? fmtEuro(aktiverKandidat.betrag_vorschlag) : "—"}
                  </div>
                  <div style={{ fontSize:"0.8rem", color:T.textFaint, marginTop:2 }}>
                    {aktiverKandidat.betrag_ist_netto ? "Nettobetrag" : "Bruttobetrag"}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize:"0.72rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em", marginBottom:4 }}>Konfidenz</div>
                  <div style={{ fontSize:"1.15rem", fontWeight:700, fontFamily:"ui-monospace,monospace",
                    color: (aktiverKandidat.konfidenz||0) >= 0.70 ? T.green : T.amber }}>
                    {Math.round((aktiverKandidat.konfidenz||0) * 100)} %
                  </div>
                </div>
                {aktiverKandidat.lieferant && (
                  <div>
                    <div style={{ fontSize:"0.72rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em", marginBottom:4 }}>Lieferant</div>
                    <div style={{ fontSize:"0.9rem", color:T.text }}>{aktiverKandidat.lieferant}</div>
                  </div>
                )}
                {aktiverKandidat.dateiname && (
                  <div>
                    <div style={{ fontSize:"0.72rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em", marginBottom:4 }}>Datei</div>
                    <div style={{ fontSize:"0.82rem", color:T.textFaint, wordBreak:"break-word" }}>{aktiverKandidat.dateiname}</div>
                  </div>
                )}
                <div style={{ marginTop:"auto", display:"flex", flexDirection:"column", gap:8 }}>
                  <Btn variant="gold" onClick={() => handleKandidatUebernehmen(kandidatView, aktiverKandidat)}
                    disabled={aktiverKandidat.betrag_vorschlag == null}>
                    ✓ Übernehmen
                  </Btn>
                  <Btn variant="ghost" onClick={() => setKandidatView(null)}>✗ Schließen</Btn>
                </div>
              </div>
              {/* Rechts: PDF-Vorschau */}
              <div style={{ flex:1, position:"relative" }}>
                {kandidatVorschauLaden ? (
                  <div style={{ display:"flex", alignItems:"center", justifyContent:"center", height:"100%", color:T.textMuted }}>
                    <div style={{ width:24, height:24, border:`3px solid ${T.accentTrim}`, borderTopColor:T.accent, borderRadius:"50%", animation:"spin 0.8s linear infinite", marginRight:10 }} />
                    PDF wird geladen…
                  </div>
                ) : kandidatVorschauUrl ? (
                  <iframe src={kandidatVorschauUrl} style={{ width:"100%", height:"100%", border:"none" }} title="Rechnung" />
                ) : (
                  <div style={{ display:"flex", alignItems:"center", justifyContent:"center", height:"100%", color:T.textFaint, fontFamily:T.fontBody, fontSize:"0.9rem" }}>
                    Keine Vorschau verfügbar
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Tab-Navigation ──────────────────────────────────────────────── */}
      <div style={{ display:"flex", borderBottom:`2px solid ${T.border}`, marginBottom:"1.25rem" }}>
        {[
          { id:"sachschaden",     label:"🚗 Sachschaden"     },
          { id:"personenschaden", label:"🏥 Personenschaden" },
        ].map(tab => (
          <button key={tab.id} onClick={() => setSchadenTab(tab.id)} style={{
            padding:"9px 22px", border:"none", background:"none", cursor:"pointer",
            fontFamily:T.fontBody, fontSize:"0.935rem",
            fontWeight: schadenTab===tab.id ? 700 : 500,
            color:      schadenTab===tab.id ? T.navy : T.textMuted,
            borderBottom: schadenTab===tab.id ? `3px solid ${T.navy}` : "3px solid transparent",
            marginBottom:"-2px", transition:"all 0.15s",
          }}>{tab.label}</button>
        ))}
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          TAB: SACHSCHADEN
      ══════════════════════════════════════════════════════════════════ */}
      {schadenTab === "sachschaden" && <>

      {/* ── 130%-Hinweis-Banner ─────────────────────────────────────────── */}
      {zeige130Hinweis && (
        <div style={{ background:T.amberBg, border:"1.5px solid #f59e0b", borderRadius:9,
          padding:"0.75rem 1.1rem", marginBottom:"1rem", display:"flex", gap:10, alignItems:"flex-start",
          fontFamily:T.fontBody, fontSize:"0.875rem", color:T.amberText }}>
          <span style={{ fontSize:"1.1rem", flexShrink:0 }}>⚠️</span>
          <div>
            <strong>Möglicher 130%-Fall:</strong> Die Reparaturrechnung ({new Intl.NumberFormat("de-DE",{style:"currency",currency:"EUR"}).format(_cbRepRN)})
            übersteigt den Fahrzeugschaden (WBW − Restwert), liegt aber noch im 130%-Rahmen.
            Im Forderungsschreiben wird die konkrete Reparatur geltend gemacht.
            Bitte Abrechnungsart auf <strong>„konkret"</strong> setzen.
          </div>
        </div>
      )}

      {/* ── Auto-WDM Ladeindikator ──────────────────────────────────────── */}
      {wdmLaden && (
        <Card>
          <div style={{ padding:"0.8rem 1.4rem", display:"flex", alignItems:"center", gap:10, fontFamily:T.fontBody, fontSize:"0.875rem", color:"#6b21a8" }}>
            <span style={{ animation:"spin 0.8s linear infinite", display:"inline-block" }}>⟳</span>
            Schadenpositionen aus RA-Micro werden geladen…
          </div>
        </Card>
      )}

      {/* ── WDM-Ergebnis-Panel ──────────────────────────────────────────── */}
      {wdmSchadenDaten && ((wdmSchadenDaten.felder_gefunden||0) > 0 || (wdmSchadenDaten.extras_gefunden||0) > 0) && (!hatLokaleWerte || wdmExplizit) && (
        <Card>
          <div style={{ padding:"1rem 1.4rem" }}>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:"0.75rem" }}>
              <div style={{ fontFamily:T.fontBody, fontSize:"0.9rem", fontWeight:700, color:"#6b21a8" }}>
                📊 {wdmSchadenDaten.felder_gefunden} Schadenpositionen aus RA-Micro
                {(wdmSchadenDaten.extras_gefunden||0) > 0 && ` + ${wdmSchadenDaten.extras_gefunden} sonstige Schäden`}
              </div>
              <Btn size="sm" variant="ghost" onClick={() => setWdmSchaden(null)}>✕</Btn>
            </div>
            <div style={{ display:"flex", flexWrap:"wrap", gap:"0.4rem 1.5rem", marginBottom:10 }}>
              {Object.entries(wdmSchadenDaten.schaden).filter(([,v]) => v > 0).map(([k, v]) => (
                <div key={k} style={{ fontSize:"0.82rem" }}>
                  <span style={{ color:T.textMuted, fontFamily:"ui-monospace,monospace", fontSize:"0.75rem" }}>{wdmSchadenDaten.quellen[k]}</span>
                  <span style={{ color:T.textMuted }}> → </span>
                  <span style={{ color:"#6b21a8", fontWeight:600 }}>{SCHADEN_F.find(f=>f.k===k)?.l || k}: </span>
                  <span style={{ color:T.navy, fontWeight:700 }}>{fmtEuro(v)}</span>
                </div>
              ))}
            </div>
            {(wdmSchadenDaten.extras||[]).filter(e=>e.betrag>0).map(e => (
              <div key={e.id} style={{ fontSize:"0.82rem", fontFamily:"ui-monospace,monospace", marginBottom:2 }}>
                <span style={{ color:T.textMuted, fontSize:"0.75rem" }}>{e.wdm_var}</span>
                <span style={{ color:T.textMuted }}> → </span>
                <span style={{ color:"#6b21a8", fontWeight:600 }}>{e.label}: </span>
                <span style={{ color:T.navy, fontWeight:700 }}>{fmtEuro(e.betrag)}</span>
                <span style={{ color:T.textMuted, fontSize:"0.75rem" }}> (netto {fmtEuro(e.netto)} + MwSt {fmtEuro(e.mwst)})</span>
              </div>
            ))}
            {Object.keys(wdmSchadenDaten.info||{}).length > 0 && (
              <div style={{ marginTop:8, display:"flex", gap:"1rem", flexWrap:"wrap" }}>
                {wdmSchadenDaten.info.fahrzeugklasse_na && <span style={{ fontSize:"0.8rem", color:T.textMuted }}>🚗 NA-Klasse {wdmSchadenDaten.info.fahrzeugklasse_na}</span>}
                {wdmSchadenDaten.info.na_tagessatz > 0 && <span style={{ fontSize:"0.8rem", color:T.textMuted }}>📅 Tagessatz {fmtEuro(wdmSchadenDaten.info.na_tagessatz)}</span>}
                {wdmSchadenDaten.info.reparaturdauer > 0 && <span style={{ fontSize:"0.8rem", color:T.textMuted }}>🔧 Reparaturdauer {wdmSchadenDaten.info.reparaturdauer} Tage</span>}
              </div>
            )}
            <Btn variant="gold" size="sm" onClick={uebernehmeWdmSchaden} style={{ marginTop:12 }}>
              ↓ Alle Werte übernehmen
            </Btn>
          </div>
        </Card>
      )}

      <Card>
        <CardHead
          title="Schadenpositionen"
          action={
            <div style={{ display:"flex", alignItems:"center", gap:8 }}>
              <span style={{ display:"inline-flex", alignItems:"center", gap:5, background:qc.bg, color:qc.c, border:`1px solid ${qc.c}33`, borderRadius:12, padding:"2px 8px", fontSize:"0.825rem", fontWeight:600 }}>
                {QUELLE_LABELS[form.quelle]||form.quelle}
              </span>
              {akteId?.includes("/") && (
                <Btn size="sm" variant="secondary" onClick={() => {
                  setWdmLaden(true); setWdmExplizit(true);
                  ramicroWdm.schaden(akteId).then(s => { setWdmSchaden(s); }).catch(()=>{}).finally(()=>setWdmLaden(false));
                }} disabled={wdmLaden}>
                  {wdmLaden ? "…" : hatLokaleWerte ? "🔍 WDM neu laden" : "🔍 RA-Micro WDM"}
                </Btn>
              )}
              {Object.values(kandidatMap).filter(k => k.betrag_vorschlag != null && (k.konfidenz||0) >= 0.80).length > 0 && (
                <Btn size="sm" variant="gold" onClick={handleAlleVorschlaegeUebernehmen} disabled={alleUebernehmenLaden}>
                  {alleUebernehmenLaden ? "…" : "« Alle übernehmen"}
                </Btn>
              )}
              <Btn size="sm" variant="secondary" onClick={() => { setShowGutImport(o=>!o); setGutErg(null); setGutError(""); }}>
                📄 Aus Gutachten
              </Btn>
              {changed && <Btn variant="gold" onClick={save} disabled={saving}>{saving?"…":Ic.check} Speichern</Btn>}
            </div>
          }
        />

        {/* Gutachten-Import-Panel */}
        {showGutImport && (
          <div style={{ margin:"0 1.4rem 1rem", padding:"1rem 1.2rem", background:T.blueBg, border:`1.5px solid ${T.blue}44`, borderRadius:9 }}>
            <div style={{ fontSize:"0.84rem", fontWeight:600, color:T.navy, marginBottom:8 }}>
              📄 Gutachten-PDF auswählen
            </div>

            {!gutErgebnis && !gutLoading && (
              <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
                {/* Vorhandene Gutachten-PDFs */}
                {gutachtenDoks.length > 0 && (
                  <div style={{ marginBottom:4 }}>
                    <div style={{ fontSize:"0.78rem", color:T.textFaint, marginBottom:4, textTransform:"uppercase", letterSpacing:"0.06em" }}>Vorhandene Gutachten</div>
                    {gutachtenDoks.map(gd => (
                      <div key={gd.id}
                        onClick={() => handleGutVorhandenes(gd.id, gd.dateiname)}
                        style={{ display:"flex", alignItems:"center", gap:10, padding:"8px 12px", borderRadius:7, cursor:"pointer", border:`1px solid ${T.border}`, background:T.white, marginBottom:4, transition:"all 0.15s" }}
                        onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent; e.currentTarget.style.background = T.accentPale; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.background = T.white; }}>
                        <span style={{ color:T.red, flexShrink:0 }}>{Ic.pdf}</span>
                        <div style={{ flex:1, minWidth:0 }}>
                          <div style={{ fontSize:"0.875rem", fontWeight:600, color:T.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{gd.dateiname}</div>
                          <div style={{ fontSize:"0.75rem", color:T.textFaint }}>
                            {gd.quelle === "eakte" ? "E-Akte" : "Hochgeladen"}
                            {gd.hochgeladen_am ? " · " + gd.hochgeladen_am : ""}
                          </div>
                        </div>
                        <span style={{ fontSize:"0.78rem", fontWeight:600, color:T.blue }}>Auswählen →</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Trennlinie wenn PDFs vorhanden */}
                {gutachtenDoks.length > 0 && (
                  <div style={{ borderTop:`1px solid ${T.border}`, margin:"4px 0", paddingTop:8 }}>
                    <div style={{ fontSize:"0.78rem", color:T.textFaint, marginBottom:4, textTransform:"uppercase", letterSpacing:"0.06em" }}>Neue Datei</div>
                  </div>
                )}

                {/* Upload-Option */}
                <label style={{ display:"flex", alignItems:"center", gap:10, cursor:"pointer", padding:"8px 12px", borderRadius:7, border:`1px dashed ${T.border}`, transition:"all 0.15s" }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; }}>
                  <input type="file" accept=".pdf" style={{ display:"none" }}
                    onChange={e => { const f=e.target.files[0]; if(f) handleGutDatei(f); }} />
                  <div style={{ padding:"6px 14px", background:T.navy, color:T.white, borderRadius:7, fontSize:"0.84rem", fontWeight:600 }}>
                    📁 PDF hochladen
                  </div>
                  <span style={{ fontSize:"0.84rem", color:T.textMuted }}>
                    Neue Datei vom Computer wählen
                  </span>
                </label>
              </div>
            )}
            {gutLoading && (
              <div style={{ display:"flex", alignItems:"center", gap:10, color:T.textMuted, fontSize:"0.875rem" }}>
                <div style={{ width:16, height:16, border:`2px solid ${T.border}`, borderTopColor:T.navy, borderRadius:"50%", animation:"spin 0.7s linear infinite" }} />
                Gutachten wird analysiert …
              </div>
            )}
            {gutError && (
              <div style={{ color:T.red, fontSize:"0.875rem", marginTop:4 }}>⚠ {gutError}</div>
            )}
            {gutErgebnis && (() => {
              const sp      = gutErgebnis.schadenpositionen || {};
              const hatKi   = gutErgebnis.llm_verwendet;
              const hatKonf = gutErgebnis.llm_konflikt;
              const _toggle = fk => setLlmWahl(w => ({ ...w, [fk]: w[fk] === 'ki' ? 'regex' : 'ki' }));
              const _fmt    = v  => v == null ? "—" : (v >= 999_000 ? "ausreichend" : fmtEuro(v));
              const _istKonf = (rv, lv) => hatKi && lv != null && rv != null && rv < 999_000 && Math.abs(rv - lv) > 1.0;
              const btnS    = { padding:"2px 7px", borderRadius:4, fontSize:11, fontWeight:600, cursor:"pointer", border:"1px solid", background:"transparent" };
              const reihen  = [
                ["Reparaturkosten",        sp.reparaturkosten,  gutErgebnis.llm_reparaturkosten_netto, "rep_netto"   ],
                ["Wiederbeschaffungswert", sp.wiederbeschaffung, gutErgebnis.llm_wbw,                  "wbw"         ],
                ["Restwert (Abzug)",       sp.restwert,          gutErgebnis.llm_restwert,             "restwert"    ],
                ["Wertminderung",          sp.wertminderung,     gutErgebnis.llm_wertminderung,        "wertminderung"],
                ["Nutzungsausfall",        sp.nutzungsausfall,   null,                                  null          ],
                ["SV-Kosten",             sp.sv_kosten,          gutErgebnis.llm_sv_kosten_netto,      "sv_netto"    ],
              ].filter(([,rv,lv]) => (rv != null && rv > 0) || (lv != null && lv > 0));
              return (
                <div>
                  {/* Header */}
                  <div style={{ display:"flex", alignItems:"center", gap:8, flexWrap:"wrap", marginBottom:8 }}>
                    <div style={{ fontSize:"0.84rem", color:T.green, fontWeight:600 }}>
                      ✓ Erkannt: {gutErgebnis.sv_buero || "SV-Gutachten"} · {gutErgebnis.schadenart === "totalschaden" ? "🔴 Totalschaden" : "🟡 Reparaturschaden"}
                      {gutErgebnis.fahrzeug?.kennzeichen && ` · ${gutErgebnis.fahrzeug.kennzeichen}`}
                    </div>
                    {hatKi && !hatKonf && (
                      <span style={{ background:"rgba(139,92,246,0.18)", color:"#c4b5fd", border:"1px solid rgba(139,92,246,0.35)", borderRadius:4, fontSize:11, fontWeight:600, padding:"2px 7px" }}>✦ Qwen ✓</span>
                    )}
                    {hatKi && hatKonf && (
                      <span style={{ background:"rgba(245,158,11,0.15)", color:"#f59e0b", border:"1px solid rgba(245,158,11,0.4)", borderRadius:4, fontSize:11, fontWeight:600, padding:"2px 7px" }}>⚠ KI-Konflikt</span>
                    )}
                  </div>
                  {/* Vergleichstabelle */}
                  <table style={{ width:"100%", borderCollapse:"collapse", fontSize:"0.855rem", marginBottom:10 }}>
                    <thead>
                      <tr style={{ background:"rgba(0,0,0,0.04)" }}>
                        <th style={{ padding:"5px 10px", textAlign:"left",  color:T.textMuted, fontWeight:600, fontSize:"0.78rem", textTransform:"uppercase" }}>Position</th>
                        <th style={{ padding:"5px 10px", textAlign:"right", color:T.textMuted, fontWeight:600, fontSize:"0.78rem", textTransform:"uppercase" }}>Regex</th>
                        {hatKi && <th style={{ padding:"5px 10px", textAlign:"right", color:"#a78bfa", fontWeight:600, fontSize:"0.78rem", textTransform:"uppercase" }}>Qwen KI</th>}
                        {hatKi && hatKonf && <th style={{ padding:"5px 10px", textAlign:"center", color:T.textMuted, fontWeight:600, fontSize:"0.78rem", textTransform:"uppercase", width:100 }}>Wählen</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {reihen.map(([label, rv, lv, fk]) => {
                        const istKonf = fk ? _istKonf(rv, lv) : false;
                        const kiGew   = llmWahl[fk] === 'ki';
                        return (
                          <tr key={label} style={{ borderTop:`1px solid ${T.border}`, background: istKonf ? "rgba(245,158,11,0.04)" : "transparent" }}>
                            <td style={{ padding:"5px 10px", color:T.text }}>{label}</td>
                            <td style={{ padding:"5px 10px", textAlign:"right", fontFamily:"monospace", fontWeight:600,
                              color: rv >= 999_000 ? T.green : (istKonf && !kiGew ? T.green : T.navy) }}>
                              {rv >= 999_000 ? "ausreichend" : (rv != null ? fmtEuro(rv) : "—")}
                              {istKonf && !kiGew && <span style={{ marginLeft:3, fontSize:8 }}>✓</span>}
                            </td>
                            {hatKi && (
                              <td style={{ padding:"5px 10px", textAlign:"right", fontFamily:"monospace",
                                color: istKonf ? (kiGew ? T.green : "#f59e0b") : "#a78bfa", fontWeight: kiGew ? 700 : 500 }}>
                                {_fmt(lv)}
                                {istKonf && kiGew && <span style={{ marginLeft:3, fontSize:8 }}>✓</span>}
                              </td>
                            )}
                            {hatKi && hatKonf && (
                              <td style={{ padding:"5px 10px", textAlign:"center" }}>
                                {istKonf && fk ? (
                                  <div style={{ display:"inline-flex", gap:3 }}>
                                    <button onClick={() => kiGew   && _toggle(fk)} style={{ ...btnS, borderColor: !kiGew ? T.green : T.border, color: !kiGew ? T.green : T.textMuted }}>Regex</button>
                                    <button onClick={() => !kiGew  && _toggle(fk)} style={{ ...btnS, borderColor:  kiGew ? T.green : T.border, color:  kiGew ? T.green : "#a78bfa" }}>KI</button>
                                  </div>
                                ) : <span style={{ fontSize:11, color:T.textFaint }}>—</span>}
                              </td>
                            )}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {(gutErgebnis.warnungen||[]).length > 0 && (
                    <div style={{ fontSize:"0.8rem", color:T.amber, marginBottom:8 }}>
                      ⚠ {gutErgebnis.warnungen.join(" · ")}
                    </div>
                  )}
                  <div style={{ display:"flex", gap:8 }}>
                    <Btn variant="gold" onClick={handleGutachtenUebernehmen}>✓ Werte übernehmen</Btn>
                    <Btn variant="secondary" onClick={() => { setGutErg(null); setGutFile(null); setLlmWahl({}); }}>Andere Datei</Btn>
                    <Btn variant="ghost" onClick={() => setShowGutImport(false)} style={{ marginLeft:"auto" }}>Abbrechen</Btn>
                  </div>
                </div>
              );
            })()}
          </div>
        )}
        <div style={{ padding:"0.5rem 1.4rem 1.25rem" }}>

          {/* Gutachten-Info-Karte (wenn ein Gutachten importiert ist) */}
          {gutachtenDoks.length > 0 && !showGutImport && (
            <div style={{ marginBottom:"1rem", padding:"10px 14px", background:T.greenBg, border:`1px solid ${T.green}33`, borderRadius:8, display:"flex", alignItems:"center", gap:10 }}>
              <span style={{ color:T.green, fontSize:"1.1rem", flexShrink:0 }}>📄</span>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontFamily:T.fontBody, fontSize:"0.875rem", fontWeight:600, color:T.green }}>
                  {gutachtenDoks.length === 1 ? "Gutachten erfasst" : `${gutachtenDoks.length} Gutachten erfasst`}
                </div>
                <div style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.textMuted, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                  {gutachtenDoks.map(g => g.dateiname).join(", ")}
                </div>
              </div>
              <Btn size="sm" variant="secondary" onClick={() => { setShowGutImport(true); setGutErg(null); setGutError(""); }}
                style={{ fontSize:"0.78rem", whiteSpace:"nowrap" }}>
                📄 Neu parsen
              </Btn>
            </div>
          )}

          {/* Feste Positionen */}
          <div style={{ marginBottom:"0.5rem" }}>
            <div style={{ overflowX:"auto" }}>
              <table style={{ width:"100%", borderCollapse:"collapse", fontFamily:T.fontBody, fontSize:"0.875rem" }}>
                <thead>
                  <tr style={{ background:T.navy }}>
                    {["Position","Betrag","Beleg"].map((h,i) => (
                      <th key={h} style={{ padding:"9px 12px", textAlign:i===0?"left":"right", fontWeight:600, color:"rgba(255,255,255,0.8)", fontSize:"0.775rem", textTransform:"uppercase", letterSpacing:"0.06em", whiteSpace:"nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
            {SCHADEN_F.map((f, fi) => {
              const beleg = belegMap[f.k];
              const istZuordnen = belegZuordnen === f.k;
              const isLast = fi === SCHADEN_F.length - 1;
              return (
                <tr key={f.k}
                  style={{ borderBottom:`1px solid ${T.border}`, background:fi%2===0?T.white:T.surface, transition:"background 0.1s" }}
                  onMouseEnter={e => e.currentTarget.style.background = T.accentPale}
                  onMouseLeave={e => e.currentTarget.style.background = fi%2===0?T.white:T.surface}>
                  <td style={{ padding:"6px 12px", color:f.abzug?T.red:T.text, fontWeight:500 }}>
                    {f.l}
                  </td>
                  <td style={{ padding:"6px 12px" }}>
                    <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                      {renderEuroInput(f.k, { abzug: f.abzug })}
                      {kandidatMap[f.k] && (() => {
                        const kand = kandidatMap[f.k];
                        const isHigh = (kand.konfidenz||0) >= 0.85;
                        const chipColor = isHigh ? T.green : T.amber;
                        const chipBg    = isHigh ? (T.green+"18") : (T.amber+"15");
                        const chipBord  = chipColor + "66";
                        const baseStyle = {
                          fontFamily:T.fontBody, fontSize:"0.75rem", fontWeight:600,
                          cursor:"pointer", whiteSpace:"nowrap", flexShrink:0,
                          color:chipColor, background:chipBg,
                          display:"flex", alignItems:"center",
                        };
                        // Sentinel: WBW 1.000.000 = "ausreichend"
                        const betragLabel = (f.k === "wiederbeschaffung" && kand.betrag_vorschlag >= 999_999)
                          ? "ausreichend"
                          : kand.betrag_vorschlag != null ? fmtEuro(kand.betrag_vorschlag) : null;
                        return (
                          <div style={{ display:"flex", alignItems:"center", flexShrink:0 }}>
                            {kand.betrag_vorschlag != null && (
                              <button
                                onClick={() => handleKandidatUebernehmen(f.k, kand)}
                                title={`${betragLabel} übernehmen`}
                                style={{ ...baseStyle,
                                  padding:"2px 7px",
                                  border:`1px solid ${chipBord}`,
                                  borderRight:"none",
                                  borderRadius:"5px 0 0 5px",
                                  gap:4,
                                }}
                                onMouseEnter={e => e.currentTarget.style.opacity="0.75"}
                                onMouseLeave={e => e.currentTarget.style.opacity="1"}
                              >
                                « {betragLabel}
                              </button>
                            )}
                            <button
                              onClick={() => setKandidatView(f.k)}
                              title={`${kand.lieferant || "Dokument"} öffnen · ${Math.round((kand.konfidenz||0)*100)} %`}
                              style={{ ...baseStyle,
                                padding:"2px 6px",
                                border:`1px solid ${chipBord}`,
                                borderRadius: kand.betrag_vorschlag != null ? "0 5px 5px 0" : 5,
                              }}
                              onMouseEnter={e => e.currentTarget.style.opacity="0.75"}
                              onMouseLeave={e => e.currentTarget.style.opacity="1"}
                            >
                              📄
                            </button>
                          </div>
                        );
                      })()}
                    </div>
                    {f.k==="sonstiges" && (
                      <input placeholder="Beschreibung" value={form.sonstiges_beschr||""} onChange={e => { setForm(p => ({...p,sonstiges_beschr:e.target.value})); setChg(true); }} style={{ marginTop:4, width:"100%", maxWidth:220, padding:"5px 8px", border:`1px solid ${T.border}`, borderRadius:6, fontFamily:T.fontBody, fontSize:"0.895rem", color:T.textMid, background:T.surface, outline:"none", boxSizing:"border-box" }} />
                    )}
                  </td>
                  <td style={{ padding:"6px 12px", textAlign:"right" }}>
                    <div style={{ display:"flex", alignItems:"center", justifyContent:"flex-end", gap:4 }}>
                    {beleg ? (
                      <>
                        {beleg.betrag_aus_beleg > 0 && beleg.betrag_aus_beleg !== (form[f.k]||0) && (
                          <button onClick={() => { setForm(p => ({...p, [f.k]: beleg.betrag_aus_beleg})); setChg(true); setToast(`${fmtEuro(beleg.betrag_aus_beleg)} übernommen.`); }}
                            title={`${fmtEuro(beleg.betrag_aus_beleg)} aus Beleg übernehmen`}
                            style={{ fontFamily:T.fontBody, fontSize:"0.72rem", fontWeight:600,
                              color:T.blue, background:T.blueBg, border:`1px solid ${T.blue}33`,
                              borderRadius:5, padding:"2px 6px", cursor:"pointer", whiteSpace:"nowrap" }}>
                            ← {fmtEuro(beleg.betrag_aus_beleg)}
                          </button>
                        )}
                        <button onClick={() => setBelegVorschau(beleg.dokument_id)}
                          title={beleg.dateiname || "Beleg öffnen"}
                          style={{ display:"flex", alignItems:"center", gap:4, background:"none", border:"none",
                            cursor:"pointer", padding:"2px 4px", maxWidth:180, overflow:"hidden" }}
                          onMouseEnter={e => e.currentTarget.style.opacity = "0.7"}
                          onMouseLeave={e => e.currentTarget.style.opacity = "1"}>
                          <span style={{ fontSize:"0.9rem", flexShrink:0 }}>📄</span>
                          <span style={{ fontFamily:T.fontBody, fontSize:"0.75rem", color:T.blue,
                            overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                            {beleg.dateiname || "Beleg"}
                          </span>
                        </button>
                        <button onClick={() => handleBelegEntfernen(f.k)}
                          title="Beleg-Zuordnung entfernen"
                          style={{ background:"none", border:"none", cursor:"pointer", padding:2, fontSize:"0.72rem", color:T.textFaint, lineHeight:1, opacity:0.4, transition:"opacity 0.15s" }}
                          onMouseEnter={e => e.currentTarget.style.opacity = "1"}
                          onMouseLeave={e => e.currentTarget.style.opacity = "0.4"}>
                          ✕
                        </button>
                      </>
                    ) : (
                      <div style={{ position:"relative" }}>
                        <button onClick={() => setBelegZuordnen(istZuordnen ? null : f.k)}
                          title="Beleg zuordnen"
                          style={{ fontFamily:T.fontBody, fontSize:"0.72rem",
                            color:T.textFaint, background:"none", border:`1px dashed ${T.border}`,
                            borderRadius:5, padding:"2px 7px", cursor:"pointer",
                            opacity:0.5, transition:"opacity 0.15s" }}
                          onMouseEnter={e => e.currentTarget.style.opacity = "1"}
                          onMouseLeave={e => e.currentTarget.style.opacity = "0.5"}>
                          + Beleg
                        </button>
                        {istZuordnen && (
                          <>
                            <div onClick={() => setBelegZuordnen(null)} style={{ position:"fixed", top:0, left:0, right:0, bottom:0, zIndex:800 }} />
                            <div style={{ position:"absolute", top:"calc(100% + 4px)", right:0, zIndex:801,
                              background:T.white, border:`1px solid ${T.border}`, borderRadius:8,
                              boxShadow:"0 4px 16px rgba(0,0,0,0.12)", minWidth:260, maxHeight:200, overflowY:"auto" }}>
                              {belegfaehigePdfs.length > 0 ? belegfaehigePdfs.map(d => (
                                <button key={d.id} onClick={() => handleBelegZuordnen(f.k, d.id)}
                                  style={{ display:"flex", alignItems:"center", gap:8, width:"100%",
                                    padding:"7px 12px", background:"transparent", border:"none",
                                    borderBottom:`1px solid ${T.borderSoft}`, cursor:"pointer",
                                    fontFamily:T.fontBody, fontSize:"0.82rem",
                                    color:T.text, textAlign:"left" }}
                                  onMouseEnter={e => e.currentTarget.style.background = T.surface}
                                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                                  <span style={{ color:T.red, flexShrink:0 }}>📄</span>
                                  <span style={{ flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{d.dateiname}</span>
                                  <span style={{ fontSize:"0.72rem", color:T.textFaint, flexShrink:0 }}>{d.quelle === "eakte" ? "E-Akte" : ""}</span>
                                </button>
                              )) : (
                                <div style={{ padding:"14px 16px", color:T.textFaint, fontFamily:T.fontBody, fontSize:"0.84rem", textAlign:"center" }}>
                                  Keine PDFs vorhanden. Bitte zuerst ein Dokument hochladen oder aus der E-Akte importieren.
                                </div>
                              )}
                            </div>
                          </>
                        )}
                      </div>
                    )}
                    </div>
                  </td>
                </tr>
              );
            })}
                </tbody>
              </table>
            </div>

            {/* Referenz-Dokumente (Abrechnungsschreiben, ohne Positionszuweisung) */}
            {referenzKandidaten.length > 0 && (
              <div style={{ marginTop:"0.75rem", padding:"0.5rem 0.75rem", borderRadius:7, border:`1px solid ${T.border}`, background:T.surface }}>
                <div style={{ fontSize:"0.75rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em", marginBottom:6 }}>
                  Referenz-Dokumente (ohne Positionszuweisung)
                </div>
                {referenzKandidaten.map((k, i) => {
                  const chipColor = (k.konfidenz||0) >= 0.75 ? T.green : T.amber;
                  const url = k.quelle === "eakte"
                    ? `${API_BASE}/akten/${akteId}/eakte/${k.eakte_nr}/datei`
                    : `${API_BASE}/akten/${akteId}/dokumente/${k.dok_id}/datei`;
                  return (
                    <div key={i} style={{ display:"flex", alignItems:"center", gap:8, padding:"3px 0", borderTop: i>0 ? `1px solid ${T.borderSoft}` : "none" }}>
                      <span style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.text, flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                        {k.dateiname || "Dokument"}
                      </span>
                      <span style={{ fontSize:"0.72rem", color:chipColor, fontWeight:600, flexShrink:0 }}>
                        {Math.round((k.konfidenz||0)*100)} %
                      </span>
                      <button
                        onClick={() => {
                          const token = tokenStore.getAccess();
                          fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
                            .then(r => r.blob()).then(blob => window.open(URL.createObjectURL(blob)));
                        }}
                        title="Dokument öffnen"
                        style={{ background:"none", border:`1px solid ${T.border}`, borderRadius:5, padding:"2px 6px", cursor:"pointer", fontSize:"0.8rem", color:T.textMid, flexShrink:0 }}
                      >
                        📄
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Sonstige Schäden – Tabelle mit Bezeichnung, Netto, MwSt */}
            {(extras.length > 0 || showAdd) && (
              <div style={{ marginTop:"1rem" }}>
                <div style={{ fontSize:"0.8rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em", marginBottom:6 }}>
                  Sonstige Schäden
                </div>
                <table style={{ width:"100%", borderCollapse:"collapse", fontFamily:T.fontBody, fontSize:"0.875rem" }}>
                  <thead>
                    <tr style={{ background:T.surface, borderBottom:`1px solid ${T.border}` }}>
                      {["Bezeichnung","Netto (€)","MwSt (€)","Brutto (€)",""].map((h,i) => (
                        <th key={h} style={{ padding:"7px 12px", textAlign:i===0?"left":"right", fontWeight:600, color:T.textMuted, fontSize:"0.78rem", textTransform:"uppercase", letterSpacing:"0.05em", whiteSpace:"nowrap" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {extras.map((e, i) => (
                      <tr key={e.id} style={{ borderBottom:`1px solid ${T.border}` }}>
                        <td style={{ padding:"8px 12px" }}>
                          <input
                            value={e.label||""}
                            onChange={ev => { const upd = extras.map(x => x.id===e.id ? {...x,label:ev.target.value} : x); setExtras(upd); setForm(p=>({...p,_extras:upd})); setChg(true); }}
                            style={{ width:"100%", border:"none", background:"transparent", outline:"none", fontFamily:T.fontBody, fontSize:"0.875rem", color:T.text }}
                          />
                        </td>
                        <td style={{ padding:"8px 12px", textAlign:"right" }}>
                          <input
                            value={focusedField===`${e.id}_n` ? editValue : fmtField(e.netto||0)}
                            onChange={ev => setEditValue(ev.target.value)}
                            onFocus={() => { setFocusedField(`${e.id}_n`); setEditValue(String(e.netto||0).replace(".",",")); }}
                            onBlur={ev => {
                              const v = parseFloat(ev.target.value.replace(",",".")) || 0;
                              const brutto = v + (e.mwst||0);
                              const upd = extras.map(x => x.id===e.id ? {...x,netto:v,betrag:brutto} : x);
                              setExtras(upd); setForm(p=>({...p,_extras:upd})); setChg(true); setFocusedField(null);
                            }}
                            style={{ width:90, border:"none", background:"transparent", outline:"none", fontFamily:"ui-monospace,monospace", fontSize:"0.875rem", color:T.text, textAlign:"right" }}
                          />
                        </td>
                        <td style={{ padding:"8px 12px", textAlign:"right" }}>
                          <input
                            value={focusedField===`${e.id}_m` ? editValue : fmtField(e.mwst||0)}
                            onChange={ev => setEditValue(ev.target.value)}
                            onFocus={() => { setFocusedField(`${e.id}_m`); setEditValue(String(e.mwst||0).replace(".",",")); }}
                            onBlur={ev => {
                              const v = parseFloat(ev.target.value.replace(",",".")) || 0;
                              const brutto = (e.netto||0) + v;
                              const upd = extras.map(x => x.id===e.id ? {...x,mwst:v,betrag:brutto} : x);
                              setExtras(upd); setForm(p=>({...p,_extras:upd})); setChg(true); setFocusedField(null);
                            }}
                            style={{ width:90, border:"none", background:"transparent", outline:"none", fontFamily:"ui-monospace,monospace", fontSize:"0.875rem", color:T.text, textAlign:"right" }}
                          />
                        </td>
                        <td style={{ padding:"8px 12px", textAlign:"right", fontFamily:"ui-monospace,monospace", fontWeight:600, color:T.navy }}>
                          {fmtEuro((e.netto||0)+(e.mwst||0))}
                        </td>
                        <td style={{ padding:"8px 12px", textAlign:"center" }}>
                          <button onClick={() => { const upd = extras.filter(x=>x.id!==e.id); setExtras(upd); setForm(p=>({...p,_extras:upd})); setChg(true); }}
                            style={{ background:"none", border:"none", cursor:"pointer", color:T.red, padding:2, borderRadius:4, lineHeight:1 }}
                            onMouseEnter={ev=>ev.currentTarget.style.background=T.redBg}
                            onMouseLeave={ev=>ev.currentTarget.style.background="none"}>
                            {Ic.trash}
                          </button>
                        </td>
                      </tr>
                    ))}
                    {/* Neue Zeile */}
                    {showAdd && (
                      <tr style={{ background:T.accentPale }}>
                        <td style={{ padding:"8px 12px" }}>
                          <input autoFocus value={newLabel} onChange={e=>setNewLabel(e.target.value)}
                            placeholder="Bezeichnung"
                            style={{ width:"100%", border:`1px solid ${T.accent}`, borderRadius:4, padding:"3px 6px", fontFamily:T.fontBody, fontSize:"0.875rem", outline:"none" }} />
                        </td>
                        <td style={{ padding:"8px 12px" }}>
                          <input value={newBetrag} onChange={e=>setNewBetrag(e.target.value)} placeholder="0,00"
                            style={{ width:90, border:`1px solid ${T.accent}`, borderRadius:4, padding:"3px 6px", fontFamily:"ui-monospace,monospace", fontSize:"0.875rem", textAlign:"right", outline:"none" }} />
                        </td>
                        <td style={{ padding:"8px 12px" }}>
                          <input value={newMwst} onChange={e=>setNewMwst(e.target.value)} placeholder="0,00"
                            style={{ width:90, border:`1px solid ${T.accent}`, borderRadius:4, padding:"3px 6px", fontFamily:"ui-monospace,monospace", fontSize:"0.875rem", textAlign:"right", outline:"none" }} />
                        </td>
                        <td style={{ padding:"8px 12px", textAlign:"right", fontFamily:"ui-monospace,monospace", fontSize:"0.875rem", color:T.textMuted }}>
                          {fmtEuro((parseFloat(newBetrag.replace(",","."))||0)+(parseFloat(newMwst.replace(",","."))||0))}
                        </td>
                        <td style={{ padding:"8px 12px", display:"flex", gap:4 }}>
                          <button onClick={() => {
                            if (!newLabel.trim()) return;
                            const netto = parseFloat(newBetrag.replace(",",".")) || 0;
                            const mwst  = parseFloat(newMwst.replace(",",".")) || 0;
                            const entry = { id:Date.now(), label:newLabel.trim(), netto, mwst, betrag:netto+mwst };
                            const upd = [...extras, entry];
                            setExtras(upd); setForm(p=>({...p,_extras:upd})); setChg(true);
                            setNewLabel(""); setNewBetrag(""); setNewMwst(""); setShowAdd(false);
                          }} style={{ background:T.accent, border:"none", borderRadius:4, color:"#fff", cursor:"pointer", padding:"2px 7px", fontSize:"0.8rem", fontWeight:600 }}>✓</button>
                          <button onClick={()=>{setShowAdd(false);setNewLabel("");setNewBetrag("");setNewMwst("");}}
                            style={{ background:T.redBg, border:"none", borderRadius:4, color:T.red, cursor:"pointer", padding:"2px 6px", fontSize:"0.8rem" }}>✕</button>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Button: Sonstigen Schaden hinzufügen – Eingabe läuft jetzt inline in der Tabelle oben */}
          {!showAdd && (
            <button onClick={() => setShowAdd(true)}
              style={{ display:"flex", alignItems:"center", gap:6, padding:"7px 12px", background:"none", border:`1.5px dashed ${T.border}`, borderRadius:8, cursor:"pointer", fontFamily:T.fontBody, fontSize:"0.895rem", color:T.textMuted, marginTop:"0.5rem", transition:"all 0.15s" }}
              onMouseEnter={ev => { ev.currentTarget.style.borderColor=T.navy; ev.currentTarget.style.color=T.navy; }}
              onMouseLeave={ev => { ev.currentTarget.style.borderColor=T.border; ev.currentTarget.style.color=T.textMuted; }}>
              {Ic.plus} Sonstigen Schaden hinzufügen
            </button>
          )}

          {/* Summe */}
          <div style={{ borderTop:`2px solid ${T.border}`, paddingTop:"1rem", marginTop:"1.25rem", display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:"1rem" }}>
            {[
              { l:"Gesamtschaden (Brutto)",   v:fmtEuro(brutto), c:T.navy,  bg:T.surface   },
              { l:`Netto (Haftung ${hq} %)`, v:fmtEuro(netto),  c:T.navy,  bg:T.accentPale  },
              { l:"Quelle",                   v:null,             c:T.text,  bg:T.surface   },
            ].map((s, i) => (
              <div key={i} style={{ background:s.bg, borderRadius:10, padding:"0.85rem 1rem", border:`1px solid ${T.border}` }}>
                <div style={{ fontFamily:T.fontBody, fontSize:"0.815rem", color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:6 }}>{s.l}</div>
                {i < 2 ? (
                  <div style={{ fontFamily:T.fontDisplay, fontSize:"1.625rem", fontWeight:700, color:s.c }}>{s.v}</div>
                ) : (
                  <select value={form.quelle||"manuell"} onChange={e => { setForm(p => ({...p,quelle:e.target.value})); setChg(true); }} style={{ padding:"5px 8px", border:`1px solid ${T.border}`, borderRadius:6, fontFamily:T.fontBody, fontSize:"0.955rem", color:T.text, background:T.white, cursor:"pointer", outline:"none" }}>
                    <option value="manuell">Manuell</option>
                    <option value="gutachten_pdf">Gutachten (PDF)</option>
                    <option value="abrechnung_pdf">Abrechnung (PDF)</option>
                    <option value="korrektur">Korrektur</option>
                  </select>
                )}
              </div>
            ))}
          </div>
          {/* Abrechnungsart: Vorschlag-Banner + Dropdown */}
          {artVorschlag && artVorschlag.art !== form.abrechnungsart && (
            <div style={{ marginTop:"1rem", padding:"0.7rem 1rem",
              background:"#f0f9ff", border:"1.5px solid #38bdf8", borderRadius:9,
              display:"flex", alignItems:"flex-start", gap:10,
              fontFamily:T.fontBody, fontSize:"0.875rem", color:"#0369a1" }}>
              <span style={{ flexShrink:0, fontSize:"1rem" }}>🔍</span>
              <div style={{ flex:1 }}>
                <strong>Vorschlag: {
                  artVorschlag.art === "fiktiv" ? "Fiktive Abrechnung" :
                  artVorschlag.art === "konkret" ? "Konkrete Abrechnung" : "Totalschaden"
                }</strong>
                <div style={{ fontSize:"0.82rem", color:"#0284c7", marginTop:2 }}>{artVorschlag.begruendung}</div>
              </div>
              <button onClick={() => { setForm(p=>({...p,abrechnungsart:artVorschlag.art})); setChg(true); setArtVorschlag(null); }}
                style={{ flexShrink:0, padding:"5px 12px", background:"#0369a1", color:"#fff",
                  border:"none", borderRadius:6, fontSize:"0.82rem", fontWeight:600, cursor:"pointer",
                  whiteSpace:"nowrap" }}>
                ↓ Übernehmen
              </button>
            </div>
          )}
          <div style={{ marginTop:"1rem", display:"flex", alignItems:"center", gap:12,
            padding:"0.75rem 1rem", background:T.surface, borderRadius:9, border:`1px solid ${T.border}` }}>
            <span style={{ fontFamily:T.fontBody, fontSize:"0.875rem",
              fontWeight:600, color:T.textMid, minWidth:130 }}>Abrechnungsart</span>
            <select value={form.abrechnungsart||""} onChange={e => { setForm(p=>({...p,abrechnungsart:e.target.value})); setChg(true); setArtVorschlag(null); }}
              style={{ padding:"6px 10px", border:`1.5px solid ${T.border}`, borderRadius:7,
                fontFamily:T.fontBody, fontSize:"0.895rem", color:T.text,
                background:T.white, cursor:"pointer", outline:"none", minWidth:180 }}>
              <option value="">— nicht gesetzt —</option>
              <option value="fiktiv">Fiktive Abrechnung (Gutachten, netto)</option>
              <option value="konkret">Konkrete Abrechnung (Rechnung, netto)</option>
              <option value="totalschaden">Totalschaden (WBW − Restwert)</option>
            </select>
            {form.abrechnungsart === "konkret" && zeige130Hinweis && (
              <span style={{ fontSize:"0.82rem", color:T.amberText, background:T.amberBg,
                border:"1px solid #f59e0b", borderRadius:6, padding:"3px 8px" }}>
                ⚠ 130%-Fall prüfen
              </span>
            )}
          </div>
        </div>
      </Card>
      </>}{/* Ende Sachschaden-Tab */}

      {/* ══════════════════════════════════════════════════════════════════
          TAB: PERSONENSCHADEN
      ══════════════════════════════════════════════════════════════════ */}
      {schadenTab === "personenschaden" && (
        <PersonenschadenTab akteId={akteId} psForm={psForm} setPsForm={setPsForm}
          psChg={psChg} setPsChg={setPsChg} psSaving={psSaving} setPsSaving={setPsSave}
          setPsToast={setPsToast} savePsForm={savePsForm} psUpd={psUpd} />
      )}
    </>
  );
}



function PersonenschadenTab({ akteId, psForm, setPsForm, psChg, setPsChg,
  psSaving, setPsSaving, setPsToast, savePsForm, psUpd }) {

  const [beteiligte, setBeteiligte]     = useState([]);
  const [betLaden, setBetLaden]         = useState(false);
  const [betQuelle, setBetQuelle]       = useState("leer");
  const [wdmGespeichert, setWdmGespeichert] = useState(false);

  // Suchfeld-State: welche Rolle wird gerade gesucht (null = kein Such-Panel)
  const [sucheRolle, setSucheRolle]     = useState(null);
  const [sucheQ, setSucheQ]             = useState("");
  const [sucheErg, setSucheErg]         = useState([]);
  const [sucheLaden, setSucheLaden]     = useState(false);
  const [gewaehlt, setGewaehlt]         = useState(null);
  const [neueNotizen, setNeueNotizen]   = useState("");

  const [wdmPsLaden, setWdmPsLaden] = useState(false);
  const [wdmPsDaten, setWdmPsDaten] = useState(null);

  // Beteiligte + WDM-Daten laden
  React.useEffect(() => {
    if (!akteId) return;
    // Beteiligte laden
    setBetLaden(true);
    apiPS.beteiligteLaden(akteId)
      .then(d => {
        setBeteiligte(d.beteiligte || []);
        setBetQuelle(d.quelle || "leer");
      })
      .catch(() => {})
      .finally(() => setBetLaden(false));

    // WDM-Textfelder laden (nur wenn AZ-Format korrekt)
    if (!akteId.includes("/")) return;
    setWdmPsLaden(true);
    apiPS.wdmLaden(akteId)
      .then(d => {
        if (!d || (d.felder_gefunden === 0 && d.adressen_gefunden === 0)) return;

        // Prüfen ob bereits manuelle SQLite-Daten vorliegen
        // psForm kommt als Prop von außen – wenn leer → auto-übernehmen
        const hatManuelleWerte = Object.keys(psForm).some(k => {
          const v = psForm[k];
          return v !== null && v !== undefined && v !== "" && v !== 0;
        });

        if (!hatManuelleWerte) {
          // Keine manuellen Daten → WDM direkt und still übernehmen
          // Textfelder sofort in Form setzen
          Object.entries(d.textfelder || {}).forEach(([k, v]) => {
            if (v !== undefined && v !== null && v !== "") setPsForm(p => ({...p, [k]: v}));
          });
          // Beteiligte speichern wenn vorhanden
          if ((d.adressen || []).length > 0) {
            const batch = d.adressen.map((a, i) => ({
              adressnr: a.adressnr, rolle: a.rolle,
              quelle: "wdm", notizen: a.notizen || "", sortierung: i,
            }));
            apiPS.beteiligterSpeichern(akteId, { batch })
              .then(res => {
                if (res.beteiligte) setBeteiligte(res.beteiligte);
              })
              .catch(() => {});
          }
          // Automatisch in SQLite speichern
          apiPS.speichern(akteId, {...psForm, ...d.textfelder})
            .catch(() => {});
        } else {
          // Manuelle Daten vorhanden → nur Banner anzeigen für optionale Ergänzung
          setWdmPsDaten(d);
        }
      })
      .catch(() => {})
      .finally(() => setWdmPsLaden(false));
  }, [akteId]); // eslint-disable-line react-hooks/exhaustive-deps

  // WDM-Einträge einmalig in SQLite speichern
  React.useEffect(() => {
    if (betQuelle !== "wdm" || !beteiligte.length || wdmGespeichert) return;
    const batch = beteiligte.map((b, i) => ({
      adressnr: b.adressnr, rolle: b.rolle,
      quelle: "wdm", notizen: b.notizen || "", sortierung: i,
    }));
    apiPS.beteiligterSpeichern(akteId, { batch })
      .then(res => {
        if (res.beteiligte) { setBeteiligte(res.beteiligte); setBetQuelle("sqlite"); }
        setWdmGespeichert(true);
      })
      .catch(() => {});
  }, [betQuelle, beteiligte, wdmGespeichert]);

  // WDM-Felder übernehmen (Textfelder + Beteiligte)
  const uebernehmeWdmPs = async () => {
    if (!wdmPsDaten) return;
    // Textfelder in psForm übernehmen (nur wenn noch leer)
    const updates = {};
    Object.entries(wdmPsDaten.textfelder || {}).forEach(([k, v]) => {
      if (!psForm[k] && v !== undefined) updates[k] = v;
    });
    if (Object.keys(updates).length > 0) {
      Object.entries(updates).forEach(([k,v]) => psUpd(k, v));
      setPsChg(true);
    }
    // Adress-Beteiligte speichern
    const neueBet = (wdmPsDaten.adressen || []).filter(a =>
      !beteiligte.find(b => b.adressnr === a.adressnr && b.rolle === a.rolle)
    );
    if (neueBet.length > 0) {
      try {
        const batch = neueBet.map((a, i) => ({
          adressnr: a.adressnr, rolle: a.rolle,
          quelle: "wdm", notizen: a.notizen || "",
          sortierung: beteiligte.length + i,
        }));
        const res = await apiPS.beteiligterSpeichern(akteId, { batch });
        if (res.beteiligte) {
          setBeteiligte(prev => {
            const ids = new Set(res.beteiligte.map(b => b.id));
            return [...prev.filter(b => !ids.has(b.id)), ...res.beteiligte];
          });
        }
      } catch(e) { setPsToast("⚠ WDM-Beteiligte konnten nicht gespeichert werden."); }
    }
    setWdmPsDaten(null);
  };

  // Suche starten (nur auf Enter oder Button-Klick)
  const suchStarten = () => {
    if (sucheQ.trim().length < 2) return;
    setSucheLaden(true);
    setSucheErg([]);
    apiPS.adressSuche(sucheQ.trim())
      .then(d => setSucheErg(d.ergebnisse || []))
      .catch(() => setSucheErg([]))
      .finally(() => setSucheLaden(false));
  };

  // Such-Panel öffnen für eine bestimmte Rolle
  const oeffneSuche = (rolle) => {
    setSucheRolle(rolle);
    setSucheQ(""); setSucheErg([]); setGewaehlt(null); setNeueNotizen("");
  };

  const schliesseSuche = () => {
    setSucheRolle(null); setSucheQ(""); setSucheErg([]);
    setGewaehlt(null); setNeueNotizen("");
  };

  const beteiligterHinzufuegen = async () => {
    if (!gewaehlt || !sucheRolle) return;
    try {
      const res = await apiPS.beteiligterSpeichern(akteId, {
        adressnr: gewaehlt.adressnr, rolle: sucheRolle,
        quelle: "manuell", notizen: neueNotizen,
        sortierung: beteiligte.filter(b => b.rolle===sucheRolle).length,
      });
      if (res.beteiligte?.length) {
        setBeteiligte(prev => {
          const neu = res.beteiligte;
          const ids = new Set(neu.map(b => b.id));
          return [...prev.filter(b => !ids.has(b.id)), ...neu];
        });
      }
    } catch { setPsToast("⚠ Fehler beim Speichern."); }
    schliesseSuche();
  };

  const beteiligterLoeschen = async (b) => {
    if (b.id == null) return;
    try {
      await apiPS.beteiligterLoeschen(akteId, b.id);
      setBeteiligte(prev => prev.filter(x => x.id !== b.id));
    } catch { setPsToast("⚠ Löschen fehlgeschlagen."); }
  };

  const notizAktualisieren = async (b, notizen) => {
    if (b.id == null) return;
    try {
      await apiPS.beteiligterAktualisieren(akteId, b.id, { notizen, quelle:"manuell" });
      setBeteiligte(prev => prev.map(x => x.id===b.id ? {...x,notizen,quelle:"manuell"} : x));
    } catch {}
  };

  // Such-Panel JSX (wird inline in Klapp-Kacheln gerendert)
  const SuchPanel = ({ rolle }) => (
    <div style={{ gridColumn:"1/-1", marginTop:"0.5rem", padding:"0.9rem 1rem",
      background:T.blueBg, border:`1.5px solid ${T.blue}44`, borderRadius:8 }}>
      <div style={{ fontFamily:T.fontBody, fontSize:"0.82rem", fontWeight:700,
        color:T.navy, marginBottom:"0.6rem" }}>
        🔍 {ROLLEN_LABEL[rolle]} aus RA-Micro suchen
      </div>
      <div style={{ display:"flex", gap:"0.5rem", marginBottom:"0.6rem" }}>
        <input value={sucheQ} onChange={e=>setSucheQ(e.target.value)}
          onKeyDown={e=>{ if(e.key==="Enter") suchStarten(); }}
          placeholder="Name oder Adressnummer, dann Enter…" autoFocus
          style={{ flex:1, padding:"7px 10px", border:`1.5px solid ${T.border}`,
            borderRadius:7, fontFamily:T.fontBody, fontSize:"0.875rem",
            background:T.white, outline:"none" }} />
        <Btn size="sm" variant="secondary" onClick={suchStarten} disabled={sucheLaden}>
          {sucheLaden ? "⟳" : "Suchen"}
        </Btn>
        <Btn size="sm" variant="ghost" onClick={schliesseSuche}>✕</Btn>
      </div>

      {sucheErg.length > 0 && (
        <div style={{ border:`1px solid ${T.border}`, borderRadius:7, overflow:"hidden",
          background:T.white, maxHeight:200, overflowY:"auto", marginBottom:"0.6rem" }}>
          {sucheErg.map(e => (
            <div key={e.adressnr} onClick={() => setGewaehlt(e)}
              style={{ padding:"7px 12px", cursor:"pointer",
                borderBottom:`1px solid ${T.borderSoft}`,
                background: gewaehlt?.adressnr===e.adressnr ? T.blueBg : "transparent",
                display:"flex", justifyContent:"space-between", alignItems:"center" }}>
              <div>
                <div style={{ fontFamily:T.fontBody, fontSize:"0.875rem",
                  fontWeight:600, color:T.text }}>{e.name}</div>
                <div style={{ fontFamily:T.fontBody, fontSize:"0.78rem",
                  color:T.textMuted }}>
                  {[e.strasse, e.plz&&e.ort ? `${e.plz} ${e.ort}` : e.ort].filter(Boolean).join(" · ")}
                </div>
              </div>
              <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.75rem",
                color:T.textFaint, flexShrink:0, marginLeft:8 }}>#{e.adressnr}</span>
            </div>
          ))}
        </div>
      )}
      {sucheQ.length >= 2 && !sucheLaden && sucheErg.length === 0 && (
        <div style={{ fontFamily:T.fontBody, fontSize:"0.82rem",
          color:T.textMuted, marginBottom:"0.5rem" }}>Keine Treffer in RA-Micro.</div>
      )}

      {gewaehlt && (
        <div style={{ padding:"0.6rem 0.8rem", background:T.surface, borderRadius:7,
          border:`1.5px solid ${T.blue}55`, marginBottom:"0.6rem" }}>
          <div style={{ fontFamily:T.fontBody, fontSize:"0.875rem",
            fontWeight:700, color:T.navy }}>
            ✓ {gewaehlt.name}
            <span style={{ fontWeight:400, color:T.textFaint, marginLeft:6 }}>#{gewaehlt.adressnr}</span>
          </div>
          <div style={{ fontFamily:T.fontBody, fontSize:"0.8rem", color:T.textMuted }}>
            {[gewaehlt.strasse, gewaehlt.plz&&gewaehlt.ort ? `${gewaehlt.plz} ${gewaehlt.ort}` : gewaehlt.ort, gewaehlt.telefon ? `☎ ${gewaehlt.telefon}` : ""].filter(Boolean).join(" · ")}
          </div>
          <input value={neueNotizen} onChange={e=>setNeueNotizen(e.target.value)}
            placeholder="Notiz (z.B. '10 Sitzungen', 'Hausarzt')"
            style={{ marginTop:5, width:"100%", padding:"4px 7px",
              border:`1px solid ${T.border}`, borderRadius:5,
              fontFamily:T.fontBody, fontSize:"0.84rem",
              background:T.white, outline:"none", boxSizing:"border-box" }} />
        </div>
      )}
      <Btn variant="gold" onClick={beteiligterHinzufuegen} disabled={!gewaehlt}>
        ↓ Als {ROLLEN_LABEL[rolle]} übernehmen
      </Btn>
    </div>
  );

  // Beteiligte-Karte für eine Rolle (mini, wie Mandantenkachel)
  const BeteiligtenListe = ({ rolle }) => {
    const liste = beteiligte.filter(b => b.rolle === rolle);
    if (!liste.length) return null;
    return (
      <div style={{ gridColumn:"1/-1", display:"flex", flexDirection:"column", gap:"0.4rem", marginTop:"0.25rem" }}>
        {liste.map((b, i) => (
          <div key={b.id ?? `b_${i}`} style={{ display:"flex", alignItems:"flex-start",
            gap:"0.6rem", padding:"0.55rem 0.8rem",
            background:T.white, border:`1px solid ${T.border}`, borderRadius:7 }}>
            <span style={{ fontSize:"1rem", flexShrink:0, marginTop:1 }}>{ROLLEN_ICON[rolle]}</span>
            <div style={{ flex:1, minWidth:0 }}>
              <div style={{ fontFamily:T.fontBody, fontSize:"0.875rem",
                fontWeight:600, color:T.text, display:"flex", alignItems:"center", gap:6, flexWrap:"wrap" }}>
                {b.name || <em style={{color:T.textFaint,fontWeight:400}}>Keine Adresse</em>}
                <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.72rem",
                  color:T.textFaint }}>#{b.adressnr}</span>
                <span style={{ fontSize:"0.68rem", padding:"1px 5px", borderRadius:8,
                  background: b.quelle==="wdm" ? "#f0fdf4" : "#f0f9ff",
                  color: b.quelle==="wdm" ? "#16a34a" : "#0369a1",
                  border:`1px solid ${b.quelle==="wdm" ? T.greenLight : "#bae6fd"}`,
                  fontFamily:T.fontBody, fontWeight:600 }}>
                  {b.quelle?.toUpperCase()}
                </span>
              </div>
              {(b.strasse||b.ort) && (
                <div style={{ fontFamily:T.fontBody, fontSize:"0.79rem",
                  color:T.textMuted, marginTop:1 }}>
                  {[b.strasse, b.plz&&b.ort ? `${b.plz} ${b.ort}` : b.ort, b.telefon ? `☎ ${b.telefon}` : ""].filter(Boolean).join(" · ")}
                </div>
              )}
              <input value={b.notizen||""} placeholder="Notiz…"
                onChange={e => setBeteiligte(prev => prev.map(x => x.id===b.id ? {...x,notizen:e.target.value} : x))}
                onBlur={e => notizAktualisieren(b, e.target.value)}
                style={{ marginTop:3, width:"100%", border:"none",
                  borderBottom:`1px dashed ${T.border}`, background:"transparent", outline:"none",
                  fontFamily:T.fontBody, fontSize:"0.79rem",
                  color:T.textMuted, padding:"1px 0" }} />
            </div>
            <button onClick={() => beteiligterLoeschen(b)} title="Entfernen"
              style={{ background:"none", border:"none", cursor:"pointer",
                color:T.red, fontSize:"1rem", padding:"2px 4px", borderRadius:4,
                flexShrink:0, lineHeight:1 }}
              onMouseEnter={e=>e.currentTarget.style.background=T.redBg}
              onMouseLeave={e=>e.currentTarget.style.background="none"}>
              🗑
            </button>
          </div>
        ))}
      </div>
    );
  };

  return (
    <>
      {betLaden && (
        <div style={{ fontFamily:T.fontBody, fontSize:"0.875rem",
          color:"#6b21a8", padding:"0.5rem 0", display:"flex", alignItems:"center", gap:8 }}>
          <span style={{ animation:"spin 0.8s linear infinite", display:"inline-block" }}>⟳</span>
          Lade Beteiligte aus RA-Micro…
        </div>
      )}

      {/* WDM-Daten-Banner */}
      {wdmPsDaten && (wdmPsDaten.felder_gefunden > 0 || wdmPsDaten.adressen_gefunden > 0) && (
        <div style={{ background:"#f5f3ff", border:"1.5px solid #a78bfa", borderRadius:9,
          padding:"0.85rem 1.1rem", display:"flex", alignItems:"flex-start", gap:10 }}>
          <span style={{ fontSize:"1.1rem", flexShrink:0 }}>📋</span>
          <div style={{ flex:1 }}>
            <div style={{ fontFamily:T.fontBody, fontSize:"0.875rem",
              fontWeight:700, color:"#6b21a8", marginBottom:4 }}>
              RA-Micro WDM: {wdmPsDaten.felder_gefunden} Felder
              {wdmPsDaten.adressen_gefunden > 0 && ` + ${wdmPsDaten.adressen_gefunden} Beteiligte`} gefunden
            </div>
            <div style={{ fontFamily:T.fontBody, fontSize:"0.82rem",
              color:"#7c3aed", display:"flex", flexWrap:"wrap", gap:"0.3rem 1rem" }}>
              {Object.entries(wdmPsDaten.textfelder || {}).map(([k,v]) => (
                <span key={k}>
                  <strong>{k}:</strong> {typeof v === "number" ? (v ? "Ja" : "Nein") : String(v)}
                </span>
              ))}
              {(wdmPsDaten.adressen || []).map((a,i) => (
                <span key={i}>
                  <strong>{ROLLEN_LABEL[a.rolle]}:</strong> {a.name || `#${a.adressnr}`}
                </span>
              ))}
            </div>
          </div>
          <div style={{ display:"flex", flexDirection:"column", gap:6, flexShrink:0 }}>
            <button onClick={uebernehmeWdmPs}
              style={{ padding:"5px 12px", background:"#7c3aed", color:"#fff",
                border:"none", borderRadius:6, fontFamily:T.fontBody,
                fontSize:"0.82rem", fontWeight:600, cursor:"pointer", whiteSpace:"nowrap" }}>
              ↓ Alle übernehmen
            </button>
            <button onClick={() => setWdmPsDaten(null)}
              style={{ padding:"4px 12px", background:"transparent", color:"#6b21a8",
                border:"1px solid #a78bfa", borderRadius:6, fontFamily:T.fontBody,
                fontSize:"0.82rem", cursor:"pointer" }}>
              Verwerfen
            </button>
          </div>
        </div>
      )}

      {/* ── Verletzungen & Heilbehandlung ────────────────────────── */}
      <Card>
        <CardHead title="Verletzungen & Heilbehandlung"
          action={
            <div style={{ display:"flex", alignItems:"center", gap:8 }}>
              {akteId?.includes("/") && (
                <Btn size="sm" variant="secondary"
                  disabled={wdmPsLaden}
                  onClick={() => {
                    setWdmPsLaden(true);
                    apiPS.wdmLaden(akteId)
                      .then(d => {
                        if (d.felder_gefunden > 0 || d.adressen_gefunden > 0) {
                          setWdmPsDaten(d); // manueller Klick → immer Banner
                        } else {
                          setPsToast("RA-Micro: keine Personenschaden-Daten in WDM gefunden.");
                        }
                      })
                      .catch(() => setPsToast("⚠ WDM konnte nicht geladen werden."))
                      .finally(() => setWdmPsLaden(false));
                  }}>
                  {wdmPsLaden ? "…" : wdmPsDaten ? "🔍 WDM neu laden" : "🔍 RA-Micro WDM"}
                </Btn>
              )}
              {psChg && (
                <Btn variant="gold" onClick={savePsForm} disabled={psSaving}>
                  {psSaving ? "…" : "✓ Speichern"}
                </Btn>
              )}
            </div>
          }
        />
        <div style={{ padding:"0.5rem 1.4rem 1.4rem" }}>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0 2rem" }}>

            <div style={{ gridColumn:"1/-1", marginBottom:"0.9rem" }}>
              <PsLabel>Art und Umfang der Verletzungen</PsLabel>
              <textarea value={psForm.verletzungen_text||""} onChange={e=>psUpd("verletzungen_text",e.target.value)} rows={3}
                style={{ width:"100%", padding:"7px 10px", border:`1.5px solid ${T.border}`, borderRadius:7,
                  fontFamily:T.fontBody, fontSize:"0.895rem", color:T.text,
                  background:T.surface, outline:"none", resize:"vertical", boxSizing:"border-box" }} />
            </div>

            {/* Krankenhaus */}
            <PsKlappSection label="🏥 Stationärer Krankenhausaufenthalt" field="krankenhaus_aufenthalt" form={psForm} upd={psUpd}
              addLabel="+ Krankenhaus" onAdd={() => oeffneSuche("krankenhaus")}>
              <PsRow label="Aufnahme (von)" field="krankenhaus_von" form={psForm} upd={psUpd} type="date" placeholder="TT.MM.JJJJ" />
              <PsRow label="Entlassung (bis, voraussichtl.)" field="krankenhaus_bis" form={psForm} upd={psUpd} type="date" placeholder="TT.MM.JJJJ" />
              <BeteiligtenListe rolle="krankenhaus" />
              {sucheRolle === "krankenhaus" && <SuchPanel rolle="krankenhaus" />}
            </PsKlappSection>

            {/* Krankschreibung */}
            <PsKlappSection label="📋 Krankgeschrieben" field="krankgeschrieben" form={psForm} upd={psUpd}>
              <PsRow label="Krank von" field="krank_von" form={psForm} upd={psUpd} type="date" placeholder="TT.MM.JJJJ" />
              <PsRow label="Krank bis (voraussichtl.)" field="krank_bis" form={psForm} upd={psUpd} type="date" placeholder="TT.MM.JJJJ" />
            </PsKlappSection>

            {/* Ärzte */}
            <div style={{ gridColumn:"1/-1", marginBottom:"1rem" }}>
              <div style={{ fontFamily:T.fontBody, fontSize:"0.8rem", fontWeight:700,
                color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em",
                marginBottom:"0.5rem", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
                <span>🩺 Behandelnde Ärzte</span>
                <button onClick={() => oeffneSuche("arzt")}
                  style={{ background:T.accentPale, border:`1px solid ${T.accent}`, borderRadius:6,
                    padding:"3px 10px", fontFamily:T.fontBody, fontSize:"0.8rem",
                    fontWeight:600, color:T.navy, cursor:"pointer" }}>
                  + Arzt
                </button>
              </div>
              <BeteiligtenListe rolle="arzt" />
              {sucheRolle === "arzt" && <SuchPanel rolle="arzt" />}
              {beteiligte.filter(b=>b.rolle==="arzt").length === 0 && sucheRolle !== "arzt" && (
                <div style={{ fontFamily:T.fontBody, fontSize:"0.82rem",
                  color:T.textFaint, padding:"0.4rem 0" }}>
                  Noch keine Ärzte erfasst.
                </div>
              )}
            </div>

            {/* Physiotherapie */}
            <PsKlappSection label="🧘 Physiotherapie erforderlich" field="physiotherapie" form={psForm} upd={psUpd}
              addLabel="+ Physiotherapeut" onAdd={() => oeffneSuche("physiotherapeut")}>
              <PsRow label="Anzahl Sitzungen" field="physiotherapie_anzahl" form={psForm} upd={psUpd} type="number" />
              <BeteiligtenListe rolle="physiotherapeut" />
              {sucheRolle === "physiotherapeut" && <SuchPanel rolle="physiotherapeut" />}
            </PsKlappSection>

            {/* Heilbehandlung + Dauerfolgen */}
            <PsSection label="⚕️ Heilbehandlung">
              <PsCheckRow label="Heilbehandlung abgeschlossen" field="heilbehandlung_abgeschlossen" form={psForm} upd={psUpd} />
              {psForm.heilbehandlung_abgeschlossen ? (
                <PsRow label="Ende der Heilbehandlung" field="heilbehandlung_ende" form={psForm} upd={psUpd} type="date" placeholder="TT.MM.JJJJ" />
              ) : null}
              <PsCheckRow label="Schweigepflicht-Entbindung" field="schweigepflicht_entbindung" form={psForm} upd={psUpd} />
            </PsSection>

            <PsKlappSection label="⚠️ Dauerfolgen / Dauerschäden" field="dauerfolgen" form={psForm} upd={psUpd}>
              <div style={{ gridColumn:"1/-1" }}>
                <PsLabel>Beschreibung der Dauerfolgen</PsLabel>
                <textarea value={psForm.dauerfolgen_text||""} onChange={e=>psUpd("dauerfolgen_text",e.target.value)} rows={3}
                  style={{ width:"100%", padding:"6px 9px", border:`1.5px solid ${T.border}`, borderRadius:6,
                    fontFamily:T.fontBody, fontSize:"0.875rem", color:T.text,
                    background:T.surface, outline:"none", resize:"vertical", boxSizing:"border-box" }} />
              </div>
            </PsKlappSection>

            {/* Arbeitgeber */}
            <div style={{ gridColumn:"1/-1", marginBottom:"1rem" }}>
              <div style={{ fontFamily:T.fontBody, fontSize:"0.8rem", fontWeight:700,
                color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em",
                marginBottom:"0.5rem", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
                <span>🏢 Arbeitgeber</span>
                <button onClick={() => oeffneSuche("arbeitgeber")}
                  style={{ background:T.accentPale, border:`1px solid ${T.accent}`, borderRadius:6,
                    padding:"3px 10px", fontFamily:T.fontBody, fontSize:"0.8rem",
                    fontWeight:600, color:T.navy, cursor:"pointer" }}>
                  + Arbeitgeber
                </button>
              </div>
              <BeteiligtenListe rolle="arbeitgeber" />
              {sucheRolle === "arbeitgeber" && <SuchPanel rolle="arbeitgeber" />}
              <PsCheckRow label="Selbstständig (kein Arbeitgeber)" field="selbststaendig" form={psForm} upd={psUpd} />
              {!psForm.selbststaendig && (
                <PsRow label="Monatl. Nettoeinkommen (€)" field="nettoeinkommen_monatlich" form={psForm} upd={psUpd} type="number" />
              )}
            </div>

            {/* Krankenkasse */}
            <div style={{ gridColumn:"1/-1", marginBottom:"1rem" }}>
              <div style={{ fontFamily:T.fontBody, fontSize:"0.8rem", fontWeight:700,
                color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em",
                marginBottom:"0.5rem", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
                <span>💊 Krankenkasse</span>
                <button onClick={() => oeffneSuche("krankenkasse")}
                  style={{ background:T.accentPale, border:`1px solid ${T.accent}`, borderRadius:6,
                    padding:"3px 10px", fontFamily:T.fontBody, fontSize:"0.8rem",
                    fontWeight:600, color:T.navy, cursor:"pointer" }}>
                  + Krankenkasse
                </button>
              </div>
              <BeteiligtenListe rolle="krankenkasse" />
              {sucheRolle === "krankenkasse" && <SuchPanel rolle="krankenkasse" />}
            </div>

            {/* Berufsgenossenschaft */}
            <PsKlappSection label="🏭 Berufsunfall / Wegeunfall" field="berufsunfall" form={psForm} upd={psUpd}
              addLabel="+ Berufsgenossenschaft" onAdd={() => oeffneSuche("bg")}>
              <BeteiligtenListe rolle="bg" />
              {sucheRolle === "bg" && <SuchPanel rolle="bg" />}
              <PsRow label="BG Name (falls nicht in RA-Micro)" field="bg_name" form={psForm} upd={psUpd} />
              <PsCheckRow label="Gesetzlich rentenversichert" field="rentenversichert" form={psForm} upd={psUpd} />
              <PsRow label="Rentenversicherung (Anstalt)" field="rentenversicherung_name" form={psForm} upd={psUpd} />
            </PsKlappSection>

            {/* Persönliche Daten */}
            <PsSection label="👤 Persönliche Daten">
              <PsRow label="Familienstand" field="familienstand" form={psForm} upd={psUpd} />
              <PsRow label="Kinder (Anzahl)" field="kinder_anzahl" form={psForm} upd={psUpd} type="number" />
              <PsRow label="Kinder Alter (z.B. 11, 10, 6)" field="kinder_alter_text" form={psForm} upd={psUpd} />
              <PsRow label="Geburtsdatum" field="geburtsdatum" form={psForm} upd={psUpd} type="date" placeholder="TT.MM.JJJJ" />
              <PsRow label="Beruf" field="beruf" form={psForm} upd={psUpd} />
            </PsSection>

            <div style={{ gridColumn:"1/-1", marginTop:"0.5rem" }}>
              <PsLabel>Interne Notizen</PsLabel>
              <textarea value={psForm.notizen||""} onChange={e=>psUpd("notizen",e.target.value)} rows={3}
                style={{ width:"100%", padding:"7px 10px", border:`1.5px solid ${T.border}`, borderRadius:7,
                  fontFamily:T.fontBody, fontSize:"0.895rem", color:T.text,
                  background:T.surface, outline:"none", resize:"vertical", boxSizing:"border-box" }} />
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}


const DateInput = ({ value, onChange, placeholder = "TT.MM.JJJJ", style = {} }) => {
  // TT.MM.JJJJ → YYYY-MM-DD für input[type=date]
  const toISO = (v) => {
    if (!v) return "";
    const m = String(v).match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
    if (m) return `${m[3]}-${m[2].padStart(2,"0")}-${m[1].padStart(2,"0")}`;
    // Bereits ISO-Format?
    if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return v;
    return "";
  };
  // YYYY-MM-DD → TT.MM.JJJJ
  const fromISO = (v) => {
    if (!v) return "";
    const m = v.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    return m ? `${m[3]}.${m[2]}.${m[1]}` : v;
  };

  return (
    <input
      type="date"
      value={toISO(value)}
      onChange={e => onChange(fromISO(e.target.value))}
      placeholder={placeholder}
      style={{
        width:"100%", padding:"6px 9px",
        border:`1.5px solid ${T.border}`, borderRadius:6,
        fontFamily:T.fontBody, fontSize:"0.875rem",
        color: value ? T.text : T.textFaint,
        background:T.white, outline:"none", boxSizing:"border-box",
        cursor:"pointer",
        ...style
      }}
    />
  );
};


const PsLabel = ({children}) => (
  <div style={{ fontFamily:T.fontBody, fontSize:"0.825rem", fontWeight:600,
    color:"#64748b", marginBottom:3, textTransform:"uppercase", letterSpacing:"0.05em" }}>
    {children}
  </div>
);


const PsSection = ({label, children}) => (
  <div style={{ marginBottom:"1.25rem" }}>
    <div style={{ fontFamily:T.fontBody, fontSize:"0.8rem", fontWeight:700,
      color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em",
      marginBottom:"0.6rem", paddingBottom:"4px", borderBottom:`1px solid ${T.borderSoft}` }}>
      {label}
    </div>
    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0.5rem 1.5rem" }}>{children}</div>
  </div>
);


const PsRow = ({label, field, form, upd, type="text", placeholder=""}) => (
  <div>
    <PsLabel>{label}</PsLabel>
    {type === "date" ? (
      <DateInput value={form[field]||""} onChange={v => upd(field, v)} placeholder={placeholder} />
    ) : (
      <input type={type} value={form[field]||""} onChange={e=>upd(field, type==="number" ? (parseFloat(e.target.value)||0) : e.target.value)}
        placeholder={placeholder}
        style={{ width:"100%", padding:"6px 9px", border:`1.5px solid ${T.border}`, borderRadius:6,
          fontFamily:T.fontBody, fontSize:"0.875rem", color:T.text,
          background:T.white, outline:"none", boxSizing:"border-box" }} />
    )}
  </div>
);


const PsCheckRow = ({label, field, form, upd}) => (
  <div style={{ display:"flex", alignItems:"center", gap:8, cursor:"pointer" }} onClick={()=>upd(field, form[field] ? 0 : 1)}>
    <div style={{ width:18, height:18, borderRadius:4, border:`2px solid ${form[field] ? T.navy : T.border}`,
      background: form[field] ? T.navy : "transparent", flexShrink:0, display:"flex", alignItems:"center", justifyContent:"center" }}>
      {form[field] ? <span style={{ color:"#fff", fontSize:11, lineHeight:1 }}>✓</span> : null}
    </div>
    <span style={{ fontFamily:T.fontBody, fontSize:"0.875rem", color:T.textMid }}>{label}</span>
  </div>
);

// Klapp-Kachel: zeigt Inhalt nur wenn aktiv (Boolean-Feld steuert es)


const PsKlappSection = ({label, field, form, upd, children, addLabel, onAdd}) => {
  const aktiv = !!form[field];
  return (
    <div style={{ gridColumn:"1/-1", marginBottom:"1rem" }}>
      {/* Header-Zeile mit Toggle */}
      <div
        onClick={() => upd(field, aktiv ? 0 : 1)}
        style={{ display:"flex", alignItems:"center", gap:10, cursor:"pointer",
          padding:"0.6rem 0.9rem", borderRadius:8,
          background: aktiv ? T.blueBg : T.surface,
          border:`1.5px solid ${aktiv ? T.blue+"55" : T.border}`,
          transition:"all 0.15s", userSelect:"none" }}>
        {/* Checkbox-ähnlicher Toggle */}
        <div style={{ width:20, height:20, borderRadius:5, flexShrink:0,
          border:`2px solid ${aktiv ? T.navy : T.border}`,
          background: aktiv ? T.navy : "transparent",
          display:"flex", alignItems:"center", justifyContent:"center" }}>
          {aktiv && <span style={{ color:"#fff", fontSize:12, lineHeight:1 }}>✓</span>}
        </div>
        <span style={{ fontFamily:T.fontBody, fontSize:"0.895rem",
          fontWeight:600, color: aktiv ? T.navy : T.textMid }}>
          {label}
        </span>
        <div style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:8 }}>
          {aktiv && onAdd && (
            <button onClick={e => { e.stopPropagation(); onAdd(); }}
              style={{ background:"#fefce8", border:"1px solid #fbbf24", borderRadius:6,
                padding:"2px 9px", fontFamily:T.fontBody, fontSize:"0.78rem",
                fontWeight:600, color:T.amberText, cursor:"pointer" }}>
              {addLabel || "+ Beteiligter"}
            </button>
          )}
          <span style={{ color:T.textFaint, fontSize:"0.85rem" }}>
            {aktiv ? "▲" : "▼"}
          </span>
        </div>
      </div>
      {/* Inhalt – nur wenn aktiv */}
      {aktiv && (
        <div style={{ marginTop:"0.6rem", padding:"0.75rem 1rem",
          background:T.surface, border:`1px solid ${T.border}`,
          borderRadius:8, display:"grid",
          gridTemplateColumns:"1fr 1fr", gap:"0.5rem 1.5rem" }}>
          {children}
        </div>
      )}
    </div>
  );
};



export default SchadenSection;
