import React, { useState, useRef, useEffect, useMemo } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { DOK_TYPEN, SCHADEN_F, KLASSE_TO_POS } from "../config/constants.js";
import { fmtSize, fmtEuro } from "../config/utils.js";
import { Card, CardHead, Btn, FieldSelect, Toast } from "../components/common.jsx";
import DokumentAktionsmenue from "../components/DokumentAktionsmenue.jsx";
import {
  dokumente as apiDokumente,
  eakte as apiEakte,
  belege as apiBelege,
  schaden as apiSchaden,
  emailImport as apiEmail,
  tokenStore,
  API_BASE,
} from "../api.js";

function DokumenteSection({ dokumente, dispatch, akteId, akte, belegeKandidaten = [], schaden = {}, vorsteuer = false }) {
  const istVerkehrsunfall = akte?.referat == null || akte?.referat === 4;
  const [dragging, setDrag]   = useState(false);
  const [uploading, setUpl]   = useState(false);
  const [uploadTyp, setTyp]   = useState("gutachten");
  const [toast, setToast]     = useState("");
  const [korrekturLading, setKorrekturLading] = useState(null); // dok_id die gerade korrigiert wird
  const [bezEdit, setBezEdit] = useState(null); // dok_id dessen Bezeichnung gerade editiert wird
  const [bezText, setBezText] = useState("");
  const inputRef              = useRef(null);
  const bezAbbrechenRef       = useRef(false);

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
  const [emailAnhangVorschau, setEmailAnhangVorschau] = useState(null); // {logId, index, name}
  const [emailAnhangUrl,     setEmailAnhangUrl]     = useState(null);
  const [batchParserLaden, setBatchParserLaden] = useState(false);
  const [batchParserFortschritt, setBatchParserFortschritt] = useState(0);
  const [batchParserTotal, setBatchParserTotal] = useState(0);
  const [debugKandidaten, setDebugKandidaten] = useState(null); // null = Dialog zu
  const [letzteKandidaten, setLetzteKandidaten] = useState(null); // Ergebnis letzter Auto-Zuordnung
  const [eakteBulkLaden, setEakteBulkLaden] = useState(false);

  // ── KI-Analyse-Dialog (PRD-31) ─────────────────────────────────────────────
  const [kiDialog, setKiDialog]     = useState(null);   // dok_id | null
  const [kiErgebnis, setKiErgebnis] = useState(null);   // parse_ergebnis object
  const [kiLaden, setKiLaden]       = useState(false);
  const [kiWahl, setKiWahl]         = useState({});     // { field: 'ki' } – nur KI-Overrides
  const [kiSpeichert, setKiSpeichert] = useState(false);

  // ── Inbox-Filter + Inline-Zuordnung (PRD-34) ──────────────────────────────
  const [zeigeAlle, setZeigeAlle]             = useState(false);
  const [promptAbgelehnt, setPromptAbgelehnt] = useState(new Set());
  const [promptForced, setPromptForced]       = useState(new Set());
  const [inlineWahl, setInlineWahl]           = useState({});
  const [inlineAnnehmenLaden, setInlineAnnehmenLaden] = useState(null);
  const [highlightPos, setHighlightPos]       = useState(null);

  // ── E-Mail-Gruppe ──────────────────────────────────────────────────────────
  const [emailDoks, setEmailDoks]         = useState([]);
  const [emailGruppeGeladen, setEmailGruppeGeladen] = useState(false);
  const [emailExpanded, setEmailExpanded] = useState({});
  const [emailMeta, setEmailMeta]         = useState({});

  const belegAnzahl = Object.keys(belegMap).length;
  const belegTotal = SCHADEN_F.length;

  // Belegte + Gutachten Dok-IDs für Inbox-Filter
  const belegDokIds = useMemo(() => {
    const ids = new Set();
    Object.values(belegMap).forEach(b => { if (b.dokument_id) ids.add(b.dokument_id); });
    return ids;
  }, [belegMap]);

  const sichtbareDokumente = useMemo(() =>
    zeigeAlle ? dokumente : dokumente.filter(d =>
      !belegDokIds.has(d.id) && d.dokumentenklasse !== "gutachten"
    ),
    [dokumente, belegDokIds, zeigeAlle]
  );
  const ausgeblendetAnzahl = dokumente.length - sichtbareDokumente.length;

  // Kandidaten-Lookup nach dok_id (DISP-gemappt) für Inline-Betrag
  const kandidatenNachDokId = useMemo(() => {
    const DISP = { rep_rechnung_netto:"rep_rechnung_brutto", mietwagenkosten_netto:"mietwagenkosten", abschleppkosten_netto:"abschleppkosten", standkosten_netto:"standkosten", sv_kosten_netto:"sv_kosten" };
    const map = {};
    (belegeKandidaten || []).forEach(k => {
      if (!k.dok_id || !k.position_key) return;
      const pk = DISP[k.position_key] || k.position_key;
      if (belegMap[pk]) return;
      if (!map[k.dok_id]) map[k.dok_id] = [];
      map[k.dok_id].push({ ...k, position_key: pk });
    });
    return map;
  }, [belegeKandidaten, belegMap]);

  // Inline-Beträge für Kandidaten ohne betrag_vorschlag
  const [uebernehmenLaden, setUebernehmenLaden] = useState(null); // posKey | "__alle__" | null
  const [inlineBetrag, setInlineBetrag]         = useState({});   // { posKey: "1234.50" }

  // Bester Kandidat je Display-Key (höchste Konfidenz gewinnt)
  const kandidatMap = useMemo(() => {
    const DISP = { rep_rechnung_netto:"rep_rechnung_brutto", mietwagenkosten_netto:"mietwagenkosten", abschleppkosten_netto:"abschleppkosten", standkosten_netto:"standkosten", sv_kosten_netto:"sv_kosten" };
    const map = {};
    (belegeKandidaten || []).forEach(k => {
      if (!k.position_key) return;
      const dk = DISP[k.position_key] || k.position_key;
      if (!map[dk] || (k.konfidenz || 0) > (map[dk].konfidenz || 0)) map[dk] = k;
    });
    return map;
  }, [belegeKandidaten]);

  // Anzahl sofort nehmbarer Kandidaten (mit Betrag, Konfidenz >= 0.80, noch nicht belegt)
  const alleNehmbareAnzahl = useMemo(() =>
    SCHADEN_F.filter(f =>
      !belegMap[f.k] &&
      kandidatMap[f.k]?.betrag_vorschlag != null &&
      (kandidatMap[f.k]?.konfidenz || 0) >= 0.80
    ).length,
    [belegMap, kandidatMap]
  );

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

  // E-Mail-Anhang Vorschau (Blob-URL)
  useEffect(() => {
    if (!emailAnhangVorschau) {
      if (emailAnhangUrl) { URL.revokeObjectURL(emailAnhangUrl); setEmailAnhangUrl(null); }
      return;
    }
    const { logId, index } = emailAnhangVorschau;
    const token = tokenStore.getAccess();
    fetch(`${API_BASE}/email/import/log/${logId}/anhang/${index}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => { if (!r.ok) throw new Error(); return r.blob(); })
      .then(blob => setEmailAnhangUrl(URL.createObjectURL(blob)))
      .catch(() => { setEmailAnhangUrl(null); setEmailAnhangVorschau(null); setToast("Vorschau fehlgeschlagen"); });
    return () => { if (emailAnhangUrl) URL.revokeObjectURL(emailAnhangUrl); };
  }, [emailAnhangVorschau]); // eslint-disable-line react-hooks/exhaustive-deps

  // Dokumente-Liste frisch aus der DB laden und in State schreiben
  const ladeDokumenteListe = async () => {
    try {
      const res = await apiDokumente.liste(akteId);
      if (res?.dokumente) dispatch({ type: "SET_DOKUMENTE", akteId, dokumente: res.dokumente });
    } catch {}
  };

  // Kandidaten still laden (nach Import oder Klassen-Korrektur)
  const ladeBelegeKandidaten = async () => {
    try {
      const res = await apiBelege.kandidaten(akteId);
      const kandidaten = res?.kandidaten || [];
      dispatch({ type: "SET_BELEGE_KANDIDATEN", akteId, kandidaten });
      // Neu importierte E-Akte-Dokumente → Kacheln sofort anzeigen
      if ((res?.auto_importiert ?? 0) > 0) ladeDokumenteListe();
    } catch { /* still – kein Toast, da Hintergrund-Refresh */ }
  };

  // Initial laden (auch nach erneutem Login)
  useEffect(() => {
    if (!akteId) return;
    ladeBelegeKandidaten();
  }, [akteId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!akteId) return;
    apiEmail.log({ akte_id: akteId, limit: 50 })
      .then(d => { if (d?.log) setEmailDoks(d.log); })
      .catch(() => {})
      .finally(() => setEmailGruppeGeladen(true));
  }, [akteId]);

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
      // Kacheln aktualisieren: neuParsen ändert parse_json + dokumentenklasse in DB
      ladeDokumenteListe();
      setBatchParserFortschritt(kandidaten.length);
      setBatchParserTotal(gesamtGeprueft);
      const quellen = [
        lokalGeprueft > 0 ? `${lokalGeprueft} lokal` : null,
        eakteVerfuegbar ? `${eakteGeprueft} E-Akte` : "E-Akte nicht verfügbar",
      ].filter(Boolean).join(" · ");
      const uebersprungen = res?.uebersprungen_nach_kategorie || {};
      const uebersproungenGesamt = Object.values(uebersprungen).reduce((s, n) => s + n, 0);
      setToast(`${kandidaten.length} Kandidat(en) gefunden · ${gesamtGeprueft} Dokumente geprüft (${quellen})${uebersproungenGesamt ? ` · ${uebersproungenGesamt} übersprungen` : ""}`);
      setLetzteKandidaten({ kandidaten, uebersprungen });
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
      // S1.9c: Unter INTAKE_REVIEW_PFLICHT liefert der Endpoint HTTP 202
      // mit { in_review: true, hinweis } -- keine dokumente-Zeile, das
      // Dokument wartet in der Review-Queue auf Freigabe.
      if (res?.in_review) {
        setToast("In Review-Queue: " + anzeigename + " (Freigabe im Review-UI)");
        setEakteImportiert(prev => new Set([...prev, nr]));
      } else if (res?.status === "duplikat") {
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
    let ok = 0, dup = 0, fehler = 0, review = 0;
    for (const ed of zuImportieren) {
      try {
        const res = await apiEakte.importieren(akteId, ed.nr);
        if (res?.in_review) {
          setEakteImportiert(prev => new Set([...prev, ed.nr]));
          review++;
        } else if (res?.status === "duplikat") {
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
    const teile = [
      ok > 0 ? `${ok} importiert` : null,
      review > 0 ? `${review} in Review-Queue` : null,
      dup > 0 ? `${dup} bereits vorhanden` : null,
      fehler > 0 ? `${fehler} Fehler` : null,
    ].filter(Boolean);
    setToast(teile.join(" · "));
  };

  // Gefilterte + sortierte + paginierte Liste
  const eakteGefiltert = React.useMemo(() =>
    eakteFilter
      ? eakteDoks.filter(ed => {
          const suchtext = eakteFilter.toLowerCase();
          const emp = (ed.empfaenger || "").toLowerCase();
          const bem = (ed.bemerkung || "").toLowerCase();
          return emp.includes(suchtext) || bem.includes(suchtext);
        })
      : eakteDoks,
    [eakteDoks, eakteFilter]
  );

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

  // Einzelnen Kandidaten annehmen: Beleg zuordnen + Schaden-Feld speichern
  const handleKandidatAnnehmen = async (posKey, kandidat, betragOverride = null) => {
    const betrag = parseFloat(betragOverride ?? kandidat.betrag_vorschlag) || 0;
    if (betrag <= 0) return;
    setUebernehmenLaden(posKey);
    try {
      if (kandidat.dok_id) {
        await apiBelege.zuordnen(akteId, posKey, kandidat.dok_id, betrag);
      }
      const neuerSchaden = { ...schaden, [posKey]: betrag };
      const res = await apiSchaden.speichern(akteId, neuerSchaden);
      dispatch({ type:"SAVE_SCHADEN", akteId, schaden: { ...neuerSchaden, gesamt_brutto: res?.schaden?.gesamt_brutto ?? neuerSchaden.gesamt_brutto ?? 0 } });
      const bRes = await apiBelege.liste(akteId);
      const newMap = {};
      (bRes?.belege || []).forEach(b => { newMap[b.position_key] = b; });
      setBelegMap(newMap);
      const label = SCHADEN_F.find(f => f.k === posKey)?.l || posKey;
      setToast(`✓ ${label}: ${new Intl.NumberFormat("de-DE", { style:"currency", currency:"EUR" }).format(betrag)} übernommen`);
    } catch(e) {
      setToast("Übernahme fehlgeschlagen: " + (e?.message || ""));
    } finally {
      setUebernehmenLaden(null);
    }
  };

  // Alle nehmbaren Kandidaten auf einmal übernehmen
  const handleAlleAnnehmen = async () => {
    const treffer = SCHADEN_F.filter(f =>
      !belegMap[f.k] &&
      kandidatMap[f.k]?.betrag_vorschlag != null &&
      (kandidatMap[f.k]?.konfidenz || 0) >= 0.80
    );
    if (!treffer.length) return;
    setUebernehmenLaden("__alle__");
    try {
      const neuerSchaden = { ...schaden };
      treffer.forEach(f => { neuerSchaden[f.k] = kandidatMap[f.k].betrag_vorschlag; });
      await Promise.all(treffer
        .filter(f => kandidatMap[f.k].dok_id)
        .map(f => apiBelege.zuordnen(akteId, f.k, kandidatMap[f.k].dok_id, kandidatMap[f.k].betrag_vorschlag).catch(() => {}))
      );
      const res = await apiSchaden.speichern(akteId, neuerSchaden);
      dispatch({ type:"SAVE_SCHADEN", akteId, schaden: { ...neuerSchaden, gesamt_brutto: res?.schaden?.gesamt_brutto ?? 0 } });
      const bRes = await apiBelege.liste(akteId);
      const newMap = {};
      (bRes?.belege || []).forEach(b => { newMap[b.position_key] = b; });
      setBelegMap(newMap);
      setToast(`✓ ${treffer.length} Position(en) übernommen und gespeichert`);
    } catch(e) {
      setToast("Fehler beim Übernehmen: " + (e?.message || ""));
    } finally {
      setUebernehmenLaden(null);
    }
  };

  // Inline-Zuordnung aus Dokumente-Inbox (PRD-34)
  const handleInlineAnnehmen = async (dokId, posKey, betrag) => {
    const b = parseFloat(betrag) || 0;
    if (b <= 0) return;
    setInlineAnnehmenLaden(dokId);
    try {
      await apiBelege.zuordnen(akteId, posKey, dokId, b);
      const neuerSchaden = { ...schaden, [posKey]: b };
      const res = await apiSchaden.speichern(akteId, neuerSchaden);
      dispatch({ type:"SAVE_SCHADEN", akteId, schaden: { ...neuerSchaden, gesamt_brutto: res?.schaden?.gesamt_brutto ?? 0 } });
      const bRes = await apiBelege.liste(akteId);
      const nm = {};
      (bRes?.belege || []).forEach(bv => { nm[bv.position_key] = bv; });
      setBelegMap(nm);
      setPromptForced(s => { const n = new Set(s); n.delete(dokId); return n; });
      const label = SCHADEN_F.find(f => f.k === posKey)?.l || posKey;
      setToast(`✓ ${label}: ${new Intl.NumberFormat("de-DE", { style:"currency", currency:"EUR" }).format(b)} zugeordnet`);
      setHighlightPos(posKey);
      setTimeout(() => setHighlightPos(null), 2000);
    } catch(e) {
      setToast("Zuordnung fehlgeschlagen: " + (e?.message || ""));
    } finally {
      setInlineAnnehmenLaden(null);
    }
  };

  const [uploadProgress, setUploadProgress] = useState(0);

  const ladeKiDialog = async (dokId) => {
    setKiDialog(dokId);
    setKiLaden(true);
    setKiErgebnis(null);
    setKiWahl({});
    try {
      const res = await apiDokumente.parse(akteId, dokId);
      setKiErgebnis(res?.parse_ergebnis || null);
    } catch (e) {
      setKiErgebnis(null);
      setToast("KI-Analyse konnte nicht geladen werden: " + (e?.message || "Fehler"));
    } finally {
      setKiLaden(false);
    }
  };

  const speichereKiWahl = async () => {
    if (!kiErgebnis || !kiDialog) return;
    setKiSpeichert(true);
    try {
      // Merged Parse-Ergebnis: bestehende Felder + KI-Overrides
      const sp = kiErgebnis.schadenpositionen || {};
      const merged = {
        ...kiErgebnis,
        // KI-Overrides wenn gewählt
        schadenart:                kiWahl.schadenart     === 'ki' ? (kiErgebnis.llm_schadenart              ?? kiErgebnis.schadenart)                : kiErgebnis.schadenart,
        nutzungsausfall_tagessatz: kiWahl.na_tagessatz   === 'ki' ? (kiErgebnis.llm_nutzungsausfall_tagessatz ?? kiErgebnis.nutzungsausfall_tagessatz) : kiErgebnis.nutzungsausfall_tagessatz,
        nutzungsausfall_tage:      kiWahl.na_tage        === 'ki' ? (kiErgebnis.llm_nutzungsausfall_tage      ?? kiErgebnis.nutzungsausfall_tage)      : kiErgebnis.nutzungsausfall_tage,
        schadenpositionen: {
          ...sp,
          rep_gutachten_netto: kiWahl.rep_netto     === 'ki' ? (kiErgebnis.llm_reparaturkosten_netto ?? sp.rep_gutachten_netto) : sp.rep_gutachten_netto,
          reparaturkosten:     kiWahl.rep_netto     === 'ki' ? (kiErgebnis.llm_reparaturkosten_netto ?? sp.reparaturkosten)     : sp.reparaturkosten,
          wiederbeschaffung:   kiWahl.wbw           === 'ki' ? (kiErgebnis.llm_wbw                  ?? sp.wiederbeschaffung)   : sp.wiederbeschaffung,
          restwert:            kiWahl.restwert      === 'ki' ? (kiErgebnis.llm_restwert              ?? sp.restwert)            : sp.restwert,
          wertminderung:       kiWahl.wertminderung === 'ki' ? (kiErgebnis.llm_wertminderung         ?? sp.wertminderung)       : sp.wertminderung,
          sv_kosten_netto:     kiWahl.sv_netto      === 'ki' ? (kiErgebnis.llm_sv_kosten_netto       ?? sp.sv_kosten_netto)     : sp.sv_kosten_netto,
          sv_kosten:           kiWahl.sv_netto      === 'ki' ? (kiErgebnis.llm_sv_kosten_netto       ?? sp.sv_kosten)           : sp.sv_kosten,
        },
        // LLM-Konflikt als aufgelöst markieren
        llm_konflikt: false,
      };
      await apiDokumente.korrektur(akteId, kiDialog, merged);
      setKiDialog(null);
      ladeBelegeKandidaten();
      setToast("KI-Werte übernommen · Kandidaten werden aktualisiert.");
    } catch (e) {
      setToast("Speichern fehlgeschlagen: " + (e?.message || ""));
    } finally {
      setKiSpeichert(false);
    }
  };

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
        // Inline-Prompt anzeigen wenn neue Klasse auf offene Position mappt
        const offenePos = (KLASSE_TO_POS[erg.klasse] || []).filter(pk => !belegMap[pk]);
        if (offenePos.length > 0) {
          setPromptForced(s => new Set([...s, dokId]));
          setPromptAbgelehnt(s => { const n = new Set(s); n.delete(dokId); return n; });
        }
      }
    } catch(e) {
      setToast("Korrektur fehlgeschlagen: " + (e?.message || String(e)));
    } finally {
      setKorrekturLading(null);
    }
  };

  const speichereBez = async (dokId) => {
    if (bezAbbrechenRef.current) { bezAbbrechenRef.current = false; setBezEdit(null); return; }
    try {
      await apiDokumente.setBezeichnung(akteId, dokId, bezText.trim());
    } catch (e) {
      setToast(`Umbenennen fehlgeschlagen: ${e.message}`);
    } finally {
      setBezEdit(null);
      ladeDokumenteListe();
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

  const toggleEmailExpand = async (id) => {
    const neuOffen = !emailExpanded[id];
    setEmailExpanded(prev => ({ ...prev, [id]: neuOffen }));
    if (neuOffen && !emailMeta[id]) {
      try {
        const meta = await apiEmail.meta(id);
        setEmailMeta(prev => ({ ...prev, [id]: meta }));
      } catch {
        setEmailMeta(prev => ({ ...prev, [id]: { anhaenge: [], body_text: "" } }));
      }
    }
  };

  const oeffneEmailAnhang = async (logId, index, name) => {
    try {
      await apiEmail.anhangOeffnen(logId, index, name);
    } catch {
      alert("Anhang konnte nicht geöffnet werden.");
    }
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
            style={{ border:`2px dashed ${dragging?T.accent:T.border}`, borderRadius:12, padding:"2.5rem 1.5rem", textAlign:"center", cursor:uploading?"default":"pointer", background:dragging?T.accentPale:"transparent", transition:"all 0.2s" }}>
            <input ref={inputRef} type="file" accept=".pdf,.docx,.jpg,.jpeg,.png" style={{ display:"none" }} onChange={e => fakeUpload([...e.target.files])} />
            {uploading ? (
              <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:12 }}>
                <div style={{ width:32, height:32, border:`3px solid ${T.accentTrim}`, borderTopColor:T.accent, borderRadius:"50%", animation:"spin 0.8s linear infinite" }} />
                <div style={{ fontFamily:T.fontBody, fontSize:"0.975rem", color:T.textMuted }}>Hochladen und analysieren …</div>
                {uploadProgress > 0 && uploadProgress < 100 && (
                  <div style={{ width:200 }}>
                    <div style={{ height:4, background:T.border, borderRadius:4, overflow:"hidden" }}>
                      <div style={{ height:"100%", width:`${uploadProgress}%`, background:`linear-gradient(90deg,${T.accent},${T.accentLight})`, borderRadius:4, transition:"width 0.3s" }}/>
                    </div>
                    <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.825rem", color:T.textFaint, textAlign:"center", marginTop:3 }}>{uploadProgress} %</div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:10 }}>
                <span style={{ color:dragging?T.accent:T.textFaint }}>{Ic.upload}</span>
                <div style={{ fontFamily:T.fontBody, fontSize:"1.025rem", fontWeight:600, color:dragging?T.accent:T.textMid }}>Datei hier ablegen oder klicken</div>
                <div style={{ fontFamily:T.fontBody, fontSize:"0.905rem", color:T.textFaint }}>PDF, DOCX, JPG, PNG · max. 20 MB · PDFs werden automatisch geparst</div>
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
                {alleNehmbareAnzahl > 0 && (
                  <Btn size="sm" variant="gold" onClick={handleAlleAnnehmen}
                    disabled={uebernehmenLaden === "__alle__"}
                    title={`${alleNehmbareAnzahl} Kandidat(en) mit Konfidenz ≥ 80 % übernehmen`}>
                    {uebernehmenLaden === "__alle__" ? "Speichert …" : `← Alle (${alleNehmbareAnzahl})`}
                  </Btn>
                )}
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
              const kand  = !beleg ? kandidatMap[f.k] : null;
              const isLoading = uebernehmenLaden === f.k || uebernehmenLaden === "__alle__";
              const isHigh = (kand?.konfidenz || 0) >= 0.85;
              return (
                <div key={f.k} style={{ display:"flex", alignItems:"center", gap:10,
                  padding:"7px 0", borderBottom: i < SCHADEN_F.length - 1 ? `1px solid ${T.borderSoft}` : "none",
                  background: highlightPos === f.k ? T.greenBg : "transparent",
                  transition:"background 0.4s" }}>

                  {/* Positions-Label */}
                  <div style={{ width:178, flexShrink:0, fontFamily:T.fontBody, fontSize:"0.845rem",
                    fontWeight:500, color: beleg ? T.text : kand ? T.textMid : T.textFaint }}>
                    {f.l}
                  </div>

                  {beleg ? (
                    /* ── Bereits belegt ─────────────────────────────────── */
                    <div style={{ flex:1, display:"flex", alignItems:"center", gap:8, minWidth:0 }}>
                      <button onClick={() => setBelegVorschau(beleg.dokument_id)}
                        style={{ display:"flex", alignItems:"center", gap:5, background:"none", border:"none",
                          cursor:"pointer", padding:"2px 4px", minWidth:0, overflow:"hidden" }}
                        onMouseEnter={e => e.currentTarget.querySelector("span").style.textDecoration="underline"}
                        onMouseLeave={e => e.currentTarget.querySelector("span").style.textDecoration="none"}>
                        <span style={{ color:T.red, fontSize:"0.9rem", flexShrink:0 }}>📄</span>
                        <span style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.blue,
                          overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                          {beleg.dateiname}
                        </span>
                      </button>
                      {beleg.betrag_aus_beleg > 0 && (
                        <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.82rem",
                          color:T.navy, fontWeight:600, flexShrink:0, marginLeft:"auto" }}>
                          {fmtEuro(beleg.betrag_aus_beleg)}
                        </span>
                      )}
                      <span style={{ fontSize:"0.7rem", color:T.green, background:T.greenBg,
                        border:`1px solid ${T.green}33`, borderRadius:10, padding:"1px 6px", flexShrink:0 }}>
                        ✓
                      </span>
                      <button
                        onClick={async () => {
                          if (!confirm(`Zuordnung von "${beleg.dateiname}" entfernen?`)) return;
                          try {
                            await apiBelege.entfernen(akteId, beleg.id);
                            const bRes = await apiBelege.liste(akteId);
                            const nm = {};
                            (bRes?.belege || []).forEach(bv => { nm[bv.position_key] = bv; });
                            setBelegMap(nm);
                          } catch(e) { setToast("Entfernen fehlgeschlagen: " + (e?.message || "")); }
                        }}
                        title="Zuordnung entfernen"
                        style={{ background:"none", border:"none", cursor:"pointer", color:T.textFaint,
                          fontSize:"0.72rem", padding:"0 2px", lineHeight:1, opacity:0.4, transition:"opacity 0.15s" }}
                        onMouseEnter={e => e.currentTarget.style.opacity="1"}
                        onMouseLeave={e => e.currentTarget.style.opacity="0.4"}
                      >✕</button>
                    </div>

                  ) : kand ? (
                    /* ── Kandidat verfügbar ─────────────────────────────── */
                    <div style={{ flex:1, display:"flex", alignItems:"center", gap:7, minWidth:0 }}>
                      {/* Konfidenz-Dot */}
                      <span style={{ width:7, height:7, borderRadius:"50%", flexShrink:0,
                        background: isHigh ? T.green : T.amber }} />
                      {/* Dateiname */}
                      <span style={{ fontFamily:T.fontBody, fontSize:"0.8rem", color:T.textMid,
                        overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", flex:1, minWidth:0 }}
                        title={kand.dateiname}>
                        {kand.dateiname || kand.lieferant || "Dokument"}
                      </span>
                      {/* Mit Betrag: Wert + Annehmen-Button */}
                      {kand.betrag_vorschlag != null ? (
                        <>
                          <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.82rem",
                            color:T.navy, fontWeight:600, flexShrink:0 }}>
                            {fmtEuro(kand.betrag_vorschlag)}
                          </span>
                          <button
                            onClick={() => handleKandidatAnnehmen(f.k, kand)}
                            disabled={isLoading}
                            style={{ padding:"3px 10px", borderRadius:5, border:"none",
                              background: isLoading ? T.textFaint : T.accent,
                              color:T.white, fontFamily:T.fontBody,
                              fontSize:"0.78rem", fontWeight:600,
                              cursor: isLoading ? "not-allowed" : "pointer", flexShrink:0,
                              transition:"background 0.12s" }}>
                            {isLoading ? "…" : "← Annehmen"}
                          </button>
                        </>
                      ) : (
                        /* Ohne Betrag: Inline-Eingabe */
                        <>
                          <input
                            type="number" step="0.01" min="0" placeholder="Betrag €"
                            value={inlineBetrag[f.k] || ""}
                            onChange={e => setInlineBetrag(p => ({ ...p, [f.k]: e.target.value }))}
                            style={{ width:88, fontFamily:T.fontBody, fontSize:"0.78rem",
                              padding:"3px 7px", border:`1px solid ${T.border}`, borderRadius:5,
                              outline:"none", color:T.text, background:T.surface, flexShrink:0 }}
                          />
                          <button
                            onClick={() => handleKandidatAnnehmen(f.k, kand, inlineBetrag[f.k])}
                            disabled={isLoading || !(parseFloat(inlineBetrag[f.k]) > 0)}
                            style={{ padding:"3px 10px", borderRadius:5, border:"none",
                              background: T.accent, color:T.white,
                              fontFamily:T.fontBody, fontSize:"0.78rem", fontWeight:600,
                              cursor:"pointer", flexShrink:0,
                              opacity: (isLoading || !(parseFloat(inlineBetrag[f.k]) > 0)) ? 0.4 : 1 }}>
                            {isLoading ? "…" : "Annehmen"}
                          </button>
                        </>
                      )}
                    </div>

                  ) : (
                    /* ── Kein Kandidat ──────────────────────────────────── */
                    <div style={{ flex:1, fontFamily:T.fontBody,
                      fontSize:"0.82rem", color:T.textFaint }}>—</div>
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
              zIndex:951, background:T.cardBg, borderRadius:12,
              boxShadow:"0 20px 60px rgba(0,0,0,0.3)",
              display:"flex", flexDirection:"column", overflow:"hidden" }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center",
                padding:"12px 20px", borderBottom:`1px solid ${T.border}`, background:T.surface }}>
                <span style={{ fontFamily:T.fontBody, fontSize:"0.9rem", fontWeight:600, color:T.navy,
                  overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", maxWidth:"70vw" }}>
                  📄 {dokumente.find(d => d.id === belegVorschau)?.dateiname || "Vorschau"}
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

        {/* Liste */}
        <Card>
          <CardHead
            title={`Dokumente (${sichtbareDokumente.length}${ausgeblendetAnzahl > 0 && !zeigeAlle ? ` offen / ${dokumente.length} gesamt` : ""})`}
            action={ausgeblendetAnzahl > 0 ? (
              <Btn size="sm" variant="ghost" onClick={() => setZeigeAlle(v => !v)}
                title={zeigeAlle ? "Nur unbearbeitete Dokumente anzeigen" : "Alle Dokumente anzeigen"}>
                {zeigeAlle ? "Nur offene" : `Alle (${dokumente.length})`}
              </Btn>
            ) : null}
          />
          {dokumente.length === 0 ? (
            <div style={{ padding:"2rem", textAlign:"center", fontFamily:T.fontBody, fontSize:"0.975rem", color:T.textFaint }}>Noch keine Dokumente hochgeladen.</div>
          ) : sichtbareDokumente.length === 0 ? (
            <div style={{ padding:"1.5rem", textAlign:"center", fontFamily:T.fontBody, fontSize:"0.9rem", color:T.textFaint }}>
              Alle Dokumente zugeordnet.{" "}
              <button onClick={() => setZeigeAlle(true)} style={{ background:"none", border:"none", color:T.accent, cursor:"pointer", textDecoration:"underline", fontFamily:"inherit", fontSize:"inherit" }}>Alle anzeigen</button>
            </div>
          ) : sichtbareDokumente.map((d, i) => {
            const ps = PARSE_STYLE[d.parse_status] || PARSE_STYLE.ausstehend;
            const isPdf = d.dateityp === "pdf";
            const offenePos = (KLASSE_TO_POS[d.dokumentenklasse] || []).filter(pk => !belegMap[pk]);
            const zeigPrompt = offenePos.length > 0 && !promptAbgelehnt.has(d.id) &&
              (promptForced.has(d.id) || (d.parse_konfidenz || 0) >= 0.85);
            const kands   = kandidatenNachDokId[d.id] || [];
            const gewPos  = inlineWahl[d.id] || offenePos[0];
            const gewKand = kands.find(k => k.position_key === gewPos);
            const betragV = gewKand?.betrag_vorschlag ?? null;
            return (
              <React.Fragment key={d.id}>
              <div style={{ display:"flex", alignItems:"center", gap:13, padding:"11px 1.4rem", borderBottom: zeigPrompt ? "none" : (i<sichtbareDokumente.length-1?`1px solid ${T.borderSoft}`:"none"), transition:"background 0.1s" }}
                onMouseEnter={e => e.currentTarget.style.background=T.surface}
                onMouseLeave={e => e.currentTarget.style.background="transparent"}>
                <div style={{ width:38, height:38, borderRadius:8, background:isPdf?T.redBg:T.blueBg, display:"flex", alignItems:"center", justifyContent:"center", color:isPdf?T.red:T.blue, flexShrink:0 }}>
                  {isPdf ? Ic.pdf : Ic.word}
                </div>
                <div style={{ flex:1, minWidth:0 }}>
                  <div
                    onClick={() => { setBezEdit(d.id); setBezText(d.bezeichnung || ""); }}
                    title="Klicken zum Umbenennen"
                    style={{ fontFamily:T.fontBody, fontSize:"0.975rem", fontWeight:600, color:T.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", cursor:"text" }}>
                    {d.bezeichnung || d.dateiname}
                  </div>
                  {bezEdit === d.id && (
                    <input
                      autoFocus
                      value={bezText}
                      onChange={e => setBezText(e.target.value)}
                      onBlur={() => speichereBez(d.id)}
                      onKeyDown={e => { if (e.key === "Enter") e.currentTarget.blur();
                                        if (e.key === "Escape") { bezAbbrechenRef.current = true; setBezEdit(null); } }}
                      placeholder={d.dateiname}
                      style={{ width:"100%", boxSizing:"border-box", marginTop:4,
                        fontSize:"0.9rem", padding:"3px 6px",
                        border:`1px solid ${T.border}`, borderRadius:6 }} />
                  )}
                  <div style={{ display:"flex", alignItems:"center", gap:6, marginTop:3, flexWrap:"wrap" }}>
                    <select
                      value={d.dokumentenklasse||d.typ||"sonstiges"}
                      disabled={korrekturLading===d.id}
                      onChange={e => korrigiereKlasse(d.id, e.target.value)}
                      style={{ fontFamily:T.fontBody, fontSize:"0.825rem", background:korrekturLading===d.id?T.accentPale:T.surface, color:T.textMuted, border:`1px solid ${T.border}`, borderRadius:10, padding:"1px 7px", cursor:"pointer", outline:"none", appearance:"none", WebkitAppearance:"none", paddingRight:16, backgroundImage:`url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%23999'/%3E%3C/svg%3E")`, backgroundRepeat:"no-repeat", backgroundPosition:"right 5px center" }}
                    >{DOK_TYPEN.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}</select>
                    <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.815rem", color:T.textFaint }}>{fmtSize(d.groesse)}</span>
                    {d.hochgeladen_am && (
                      <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.815rem", color:T.textFaint }}>
                        {(() => {
                          try {
                            const dt = new Date(d.hochgeladen_am.replace(" ", "T"));
                            if (isNaN(dt.getTime())) return null;
                            return dt.toLocaleString("de-DE", { day:"2-digit", month:"2-digit", year:"numeric", hour:"2-digit", minute:"2-digit" });
                          } catch { return null; }
                        })()}
                      </span>
                    )}
                    {zeigeAlle && belegDokIds.has(d.id) && (
                      <span style={{ background:T.greenBg, color:T.green, border:`1px solid ${T.green}33`,
                        borderRadius:10, fontSize:"0.72rem", padding:"1px 6px", flexShrink:0 }}>
                        zugeordnet
                      </span>
                    )}
                    {zeigeAlle && d.dokumentenklasse === "gutachten" && (
                      <span style={{ background:T.accentPale, color:T.accent, border:`1px solid ${T.accent}33`,
                        borderRadius:10, fontSize:"0.72rem", padding:"1px 6px", flexShrink:0 }}>
                        → Schaden-Reiter
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
                        <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.895rem", fontWeight:600, color:d.parse_konfidenz>0.7?T.green:d.parse_konfidenz>0.4?T.amber:T.red }}>{Math.round(d.parse_konfidenz*100)} %</span>
                      )}
                    </>
                  )}
                  {isPdf && (
                    <Btn size="sm" variant="secondary"
                      onClick={() => setBelegVorschau(belegVorschau === d.id ? null : d.id)}
                      title="Vorschau"
                      style={{ background: belegVorschau === d.id ? T.accentPale : undefined }}>
                      👁
                    </Btn>
                  )}
                  {isPdf && d.dokumentenklasse === "gutachten" && (
                    <Btn size="sm" variant="secondary"
                      onClick={() => kiDialog === d.id ? setKiDialog(null) : ladeKiDialog(d.id)}
                      title="KI-Analyse einblenden / ausblenden"
                      style={{ fontSize:"0.78rem", padding:"4px 7px",
                        background: kiDialog === d.id ? T.accentPale : undefined,
                        color:      kiDialog === d.id ? T.accent      : undefined }}>
                      🔬 KI
                    </Btn>
                  )}
                  {isPdf && (
                    <DokumentAktionsmenue
                      az={akteId}
                      dokumentId={d.id}
                      onAktion={(a) => setToast(`Aktion "${a.label}" ausgelöst (Backend-Anbindung folgt)`)}
                    />
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
              {/* ── Inline Zuordnen-Prompt (PRD-34) ── */}
              {zeigPrompt && (
                <div style={{ padding:"7px 1.4rem 7px 3.5rem", background:T.accentPale,
                  borderBottom: i < sichtbareDokumente.length-1 ? `1px solid ${T.borderSoft}` : "none",
                  display:"flex", alignItems:"center", gap:8, flexWrap:"wrap" }}>
                  <span style={{ fontSize:"0.78rem", color:T.accent, flexShrink:0 }}>↳</span>
                  {offenePos.length > 1 ? (
                    <select
                      value={gewPos || ""}
                      onChange={e => setInlineWahl(p => ({ ...p, [d.id]: e.target.value }))}
                      style={{ fontFamily:T.fontBody, fontSize:"0.8rem", background:T.cardBg,
                        color:T.textMid, border:`1px solid ${T.border}`, borderRadius:10,
                        padding:"2px 7px", cursor:"pointer", outline:"none" }}
                    >
                      {offenePos.map(pk => (
                        <option key={pk} value={pk}>{SCHADEN_F.find(f => f.k === pk)?.l || pk}</option>
                      ))}
                    </select>
                  ) : (
                    <span style={{ fontFamily:T.fontBody, fontSize:"0.8rem", fontWeight:600,
                      color:T.navy, flexShrink:0 }}>
                      {SCHADEN_F.find(f => f.k === offenePos[0])?.l || offenePos[0]}
                    </span>
                  )}
                  {betragV != null ? (
                    <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.82rem",
                      color:T.navy, fontWeight:600, flexShrink:0 }}>
                      {fmtEuro(betragV)}
                    </span>
                  ) : (
                    <input
                      type="number" step="0.01" min="0" placeholder="Betrag €"
                      value={inlineWahl[`${d.id}_b`] || ""}
                      onChange={e => setInlineWahl(p => ({ ...p, [`${d.id}_b`]: e.target.value }))}
                      style={{ width:90, fontFamily:T.fontBody, fontSize:"0.78rem",
                        padding:"2px 7px", border:`1px solid ${T.border}`, borderRadius:5,
                        outline:"none", color:T.text, background:T.cardBg }}
                    />
                  )}
                  <button
                    onClick={() => handleInlineAnnehmen(d.id, gewPos, betragV ?? inlineWahl[`${d.id}_b`])}
                    disabled={inlineAnnehmenLaden === d.id ||
                      (betragV == null && !(parseFloat(inlineWahl[`${d.id}_b`]) > 0))}
                    style={{ padding:"3px 10px", borderRadius:5, border:"none", background:T.accent,
                      color:"#fff", fontFamily:T.fontBody, fontSize:"0.78rem",
                      fontWeight:600, cursor:"pointer", flexShrink:0,
                      opacity: (inlineAnnehmenLaden === d.id ||
                        (betragV == null && !(parseFloat(inlineWahl[`${d.id}_b`]) > 0))) ? 0.5 : 1 }}>
                    {inlineAnnehmenLaden === d.id ? "…" : "← Annehmen"}
                  </button>
                  <button
                    onClick={() => {
                      setPromptAbgelehnt(s => new Set([...s, d.id]));
                      setPromptForced(s => { const n = new Set(s); n.delete(d.id); return n; });
                    }}
                    title="Schließen"
                    style={{ background:"none", border:"none", cursor:"pointer",
                      color:T.textFaint, fontSize:"0.9rem", lineHeight:1, flexShrink:0 }}>
                    ✕
                  </button>
                </div>
              )}
              </React.Fragment>
            );
          })}
        </Card>

        {/* ── Gutachten KI-Vorschau Panel (PRD-31) ───────────────────── */}
        {kiDialog && (
          <GutachtenVorschau
            erg={kiErgebnis}
            laden={kiLaden}
            wahl={kiWahl}
            setWahl={setKiWahl}
            speichert={kiSpeichert}
            onSpeichern={speichereKiWahl}
            onClose={() => setKiDialog(null)}
          />
        )}

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
                <h3 style={{ fontFamily:T.fontDisplay, fontSize:"1rem", fontWeight:700, color:T.navy, margin:0 }}>
                  E-Akte (RA-Micro)
                </h3>
                {eakteGeladen && (
                  <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.82rem", color:T.textFaint }}>
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
                <span style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color: eakteEmails ? T.text : T.textFaint }}>E-Mails</span>
                <div
                  onClick={toggleEmails}
                  style={{
                    width:36, height:20, borderRadius:10,
                    background: eakteEmails ? T.accent : T.border,
                    position:"relative", cursor:"pointer",
                    transition:"background 0.2s",
                    boxShadow: eakteEmails ? `0 0 0 1px ${T.accent}33` : "none",
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
                    <div style={{ width:24, height:24, border:`3px solid ${T.accentTrim}`, borderTopColor:T.accent, borderRadius:"50%", animation:"spin 0.8s linear infinite", margin:"0 auto 8px" }} />
                    E-Akte wird geladen…
                  </div>
                )}

                {eakteFehler && (
                  <div style={{ padding:"1rem 1.4rem", color:T.red, fontFamily:T.fontBody, fontSize:"0.9rem" }}>
                    ⚠ {eakteFehler}
                  </div>
                )}

                {!eakteLaden && !eakteFehler && eakteDoks.length === 0 && eakteGeladen && (
                  <div style={{ padding:"2rem", textAlign:"center", fontFamily:T.fontBody, fontSize:"0.975rem", color:T.textFaint }}>
                    Keine E-Akte-Dokumente gefunden.
                  </div>
                )}

                {!eakteLaden && eakteDoks.length > 0 && (
                  <>
                    {/* Filter-Leiste */}
                    <div style={{ display:"flex", alignItems:"center", gap:10, padding:"8px 1.4rem", borderBottom:`1px solid ${T.border}`, background:T.offWhite }}>
                      <span style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.textMuted, flexShrink:0 }}>Filter:</span>
                      <select
                        value={eakteFilter}
                        onChange={e => { setEakteFilter(e.target.value); setEakteSeite(0); }}
                        style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.textMid, border:`1px solid ${T.border}`, borderRadius:6, padding:"3px 8px", background:T.cardBg, maxWidth:280, cursor:"pointer" }}>
                        <option value="">Alle Absender ({eakteDoks.length})</option>
                        {eakteAbsender.map(a => (
                          <option key={a} value={a}>{a.length > 40 ? a.slice(0,40)+"…" : a}</option>
                        ))}
                      </select>
                      {eakteFilter && (
                        <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.78rem", color:T.textFaint }}>
                          {eakteGefiltert.length} Treffer
                        </span>
                      )}
                      {eakteFilter && (
                        <span onClick={() => { setEakteFilter(""); setEakteSeite(0); }}
                          style={{ fontFamily:T.fontBody, fontSize:"0.78rem", color:T.red, cursor:"pointer", textDecoration:"underline" }}>
                          Filter zurücksetzen
                        </span>
                      )}
                    </div>

                    {/* Spaltenheader (klickbar zum Sortieren) */}
                    <div style={{ display:"flex", alignItems:"center", padding:"6px 1.4rem", borderBottom:`1px solid ${T.border}`, background:T.surface }}>
                      <div style={{ width:38, flexShrink:0 }} />
                      <div onClick={() => eakteSortKlick("bemerkung")}
                        style={{ flex:2, fontFamily:T.fontBody, fontSize:"0.75rem", fontWeight:600, color: eakteSortSpalte==="bemerkung" ? T.accent : T.textFaint, textTransform:"uppercase", letterSpacing:"0.06em", paddingLeft:13, cursor:"pointer", userSelect:"none" }}>
                        Dokument{sortPfeil("bemerkung")}
                      </div>
                      <div onClick={() => eakteSortKlick("empfaenger")}
                        style={{ flex:1, fontFamily:T.fontBody, fontSize:"0.75rem", fontWeight:600, color: eakteSortSpalte==="empfaenger" ? T.accent : T.textFaint, textTransform:"uppercase", letterSpacing:"0.06em", minWidth:120, cursor:"pointer", userSelect:"none" }}>
                        Absender{sortPfeil("empfaenger")}
                      </div>
                      <div onClick={() => eakteSortKlick("sachbearbeiter")}
                        style={{ width:50, textAlign:"center", fontFamily:T.fontBody, fontSize:"0.75rem", fontWeight:600, color: eakteSortSpalte==="sachbearbeiter" ? T.accent : T.textFaint, textTransform:"uppercase", letterSpacing:"0.06em", flexShrink:0, cursor:"pointer", userSelect:"none" }}>
                        SB{sortPfeil("sachbearbeiter")}
                      </div>
                      <div onClick={() => eakteSortKlick("version")}
                        style={{ width:90, textAlign:"right", fontFamily:T.fontBody, fontSize:"0.75rem", fontWeight:600, color: eakteSortSpalte==="version" ? T.accent : T.textFaint, textTransform:"uppercase", letterSpacing:"0.06em", flexShrink:0, paddingRight:8, cursor:"pointer", userSelect:"none" }}>
                        Datum{sortPfeil("version")}
                      </div>
                      <div style={{ width:140, flexShrink:0 }} />
                    </div>

                    {eakteSeitenDoks.map((ed, i) => {
                      const istVorschau = eakteVorschau === ed.nr;
                      const absenderName = (ed.empfaenger || "").replace(/<[^>]+>/g, "").replace(/"/g, "").trim();
                      return (
                        <div key={ed.nr}>
                          <div style={{ display:"flex", alignItems:"center", padding:"10px 1.4rem", borderBottom: (!istVorschau && i < eakteSeitenDoks.length-1) ? `1px solid ${T.borderSoft}` : "none", transition:"background 0.1s", cursor:"pointer", background: istVorschau ? T.accentPale : "transparent" }}
                            onMouseEnter={e => { if (!istVorschau) e.currentTarget.style.background=T.surface; }}
                            onMouseLeave={e => { if (!istVorschau) e.currentTarget.style.background="transparent"; }}
                            onClick={() => setEakteVorschau(istVorschau ? null : ed.nr)}>
                            {/* Icon */}
                            <div style={{ width:38, height:38, borderRadius:8, background: ed.dateityp==="pdf" ? T.redBg : T.blueBg, display:"flex", alignItems:"center", justifyContent:"center", color: ed.dateityp==="pdf" ? T.red : T.blue, flexShrink:0 }}>
                              {ed.dateityp === "pdf" ? Ic.pdf : Ic.email}
                            </div>
                            {/* Dokument */}
                            <div style={{ flex:2, minWidth:0, paddingLeft:13 }}>
                              <div style={{ fontFamily:T.fontBody, fontSize:"0.93rem", fontWeight:600, color:T.text, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                                {ed.bemerkung || ed.anzeigename}
                              </div>
                              {ed.rubrik && (
                                <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.72rem", color:T.textFaint, background:T.accentPale, border:`1px solid ${T.accentTrim}`, borderRadius:4, padding:"0 4px", marginTop:2, display:"inline-block" }}>
                                  {ed.rubrik}
                                </span>
                              )}
                            </div>
                            {/* Absender */}
                            <div style={{ flex:1, minWidth:120 }}>
                              <span style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.textMuted, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", display:"block" }}>
                                {absenderName}
                              </span>
                            </div>
                            {/* SB */}
                            <div style={{ width:50, textAlign:"center", flexShrink:0 }}>
                              {ed.sachbearbeiter && (
                                <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.8rem", color:T.textMid, background:T.surface, border:`1px solid ${T.border}`, borderRadius:4, padding:"1px 6px" }}>
                                  {ed.sachbearbeiter}
                                </span>
                              )}
                            </div>
                            {/* Datum */}
                            <div style={{ width:90, textAlign:"right", flexShrink:0, paddingRight:8 }}>
                              <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.82rem", color:T.textMid }}>
                                {ed.version ? (() => {
                                  try { return new Date(ed.version).toLocaleDateString("de-DE", { day:"2-digit", month:"2-digit", year:"2-digit" }); }
                                  catch { return ""; }
                                })() : ""}
                              </span>
                            </div>
                            {/* Aktionen */}
                            <div style={{ width:140, display:"flex", alignItems:"center", justifyContent:"flex-end", gap:4, flexShrink:0 }} onClick={e => e.stopPropagation()}>
                              {eakteImportiert.has(ed.nr) ? (
                                <span style={{ fontFamily:T.fontBody, fontSize:"0.72rem", fontWeight:600, color:T.green, background:T.greenBg, border:`1px solid ${T.green}33`, borderRadius:10, padding:"2px 8px", whiteSpace:"nowrap" }}>
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
                                  <div style={{ width:24, height:24, border:`3px solid ${T.accentTrim}`, borderTopColor:T.accent, borderRadius:"50%", animation:"spin 0.8s linear infinite", marginRight:10 }} />
                                  PDF wird geladen…
                                </div>
                              )}
                              {!vorschauLaden && vorschauUrl && (
                                <iframe
                                  src={vorschauUrl}
                                  style={{ width:"100%", height:600, border:`1px solid ${T.border}`, borderRadius:8, background:T.cardBg }}
                                  title={ed.anzeigename}
                                />
                              )}
                              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginTop:8 }}>
                                <span style={{ fontFamily:T.fontBody, fontSize:"0.82rem", color:T.textFaint }}>
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
                        <span style={{ fontFamily:T.fontBody, fontSize:"0.85rem", color:T.textMid }}>
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

      {/* ── E-Mail-Gruppe ──────────────────────────────────────────────────── */}
      {emailGruppeGeladen && emailDoks.length > 0 && (
        <Card style={{ marginTop:"1.25rem" }}>
          <CardHead title={`📧 E-Mails (${emailDoks.length})`} />
          {emailDoks.map((em, i) => {
            const istOffen = !!emailExpanded[em.id];
            const meta     = emailMeta[em.id];
            return (
              <div key={em.id} style={{ borderBottom: i < emailDoks.length - 1 ? `1px solid ${T.borderSoft}` : "none" }}>
                <div
                  onClick={() => toggleEmailExpand(em.id)}
                  style={{ display:"flex", alignItems:"center", gap:10,
                    padding:"10px 1.25rem", cursor:"pointer",
                    background: istOffen ? T.accentPale : "transparent",
                    transition:"background 0.1s" }}
                  onMouseEnter={ev => { if (!istOffen) ev.currentTarget.style.background = T.surface; }}
                  onMouseLeave={ev => { if (!istOffen) ev.currentTarget.style.background = "transparent"; }}>
                  <span style={{ color:T.blue, display:"flex", flexShrink:0 }}>📧</span>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ fontFamily:T.fontBody, fontSize:"0.925rem",
                      fontWeight:500, color:T.text,
                      overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                      {em.von_name || em.absender || "Unbekannt"}
                      {em.betreff ? ` · ${em.betreff}` : ""}
                    </div>
                  </div>
                  <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.8rem",
                    color:T.textMuted, flexShrink:0 }}>
                    {em.empfangen_am ? String(em.empfangen_am).slice(0, 10) : ""}
                    {(em.anhaenge_anzahl || 0) > 0 ? ` · ${em.anhaenge_anzahl} Anhang${em.anhaenge_anzahl > 1 ? "hänge" : ""}` : ""}
                  </span>
                  <svg viewBox="0 0 24 24" fill={T.textFaint}
                    style={{ width:13, height:13, flexShrink:0,
                      transform: istOffen ? "rotate(180deg)" : "none", transition:"transform 0.2s" }}>
                    <path d="M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z"/>
                  </svg>
                </div>
                {istOffen && (
                  <div style={{ padding:"0 1.25rem 12px 2.75rem",
                    background:T.accentPale, borderTop:`1px solid ${T.border}` }}>
                    {meta?.body_text ? (
                      <div style={{ fontFamily:T.fontBody, fontSize:"0.855rem",
                        color:T.textMid, marginTop:10, marginBottom:10,
                        whiteSpace:"pre-wrap", maxHeight:120, overflowY:"auto",
                        background:T.cardBg, border:`1px solid ${T.border}`,
                        borderRadius:6, padding:"8px 10px", lineHeight:1.5 }}>
                        {meta.body_text.slice(0, 400)}{meta.body_text.length > 400 ? " …" : ""}
                      </div>
                    ) : !meta ? (
                      <div style={{ fontFamily:T.fontBody, fontSize:"0.855rem",
                        color:T.textMuted, marginTop:10 }}>Lade …</div>
                    ) : null}
                    {(meta?.anhaenge || []).length > 0 && (
                      <div style={{ display:"flex", flexDirection:"column", gap:4, marginTop: meta?.body_text ? 0 : 10 }}>
                        {meta.anhaenge.map(anh => {
                          const isPdf = (anh.ext === "pdf") || (anh.name || "").toLowerCase().endsWith(".pdf");
                          return (
                            <div key={anh.index} style={{ display:"flex", flexDirection:"column" }}>
                              <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                                <span style={{ color: isPdf ? T.red : T.blue, display:"flex", fontSize:"0.9rem", flexShrink:0 }}>
                                  {isPdf ? Ic.pdf : Ic.attach}
                                </span>
                                <span style={{ fontFamily:T.fontBody, fontSize:"0.875rem",
                                  color:T.text, flex:1 }}>
                                  {anh.name || `Anhang ${anh.index + 1}`}
                                </span>
                                <button
                                  onClick={() => {
                                    const key = `${em.id}-${anh.index}`;
                                    const aktiv = emailAnhangVorschau && `${emailAnhangVorschau.logId}-${emailAnhangVorschau.index}` === key;
                                    setEmailAnhangVorschau(aktiv ? null : { logId: em.id, index: anh.index, name: anh.name });
                                  }}
                                  style={{ background:"none", border:`1px solid ${T.border}`,
                                    borderRadius:5, padding:"2px 10px", cursor:"pointer",
                                    fontFamily:T.fontBody, fontSize:"0.815rem",
                                    color: emailAnhangVorschau && `${emailAnhangVorschau.logId}-${emailAnhangVorschau.index}` === `${em.id}-${anh.index}` ? T.accent : T.textMid }}>
                                  {emailAnhangVorschau && `${emailAnhangVorschau.logId}-${emailAnhangVorschau.index}` === `${em.id}-${anh.index}` ? "▼ Schließen" : "▶ Vorschau"}
                                </button>
                              </div>
                              {emailAnhangVorschau && `${emailAnhangVorschau.logId}-${emailAnhangVorschau.index}` === `${em.id}-${anh.index}` && (
                                <div style={{ marginTop:6 }}>
                                  {!emailAnhangUrl ? (
                                    <div style={{ height:80, display:"flex", alignItems:"center", justifyContent:"center", color:T.textMuted, fontFamily:T.fontBody, fontSize:"0.875rem" }}>
                                      <div style={{ width:16, height:16, border:`2px solid ${T.border}`, borderTopColor:T.navy, borderRadius:"50%", animation:"spin 0.7s linear infinite", marginRight:8 }} />
                                      PDF wird geladen…
                                    </div>
                                  ) : (
                                    <iframe src={emailAnhangUrl} title={anh.name}
                                      style={{ width:"100%", height:500, border:`1px solid ${T.border}`, borderRadius:6 }} />
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </Card>
      )}

      </div>

      {/* ── Debug-Dialog: Kandidaten-Übersicht ──────────────────────────── */}
      {debugKandidaten && <KandidatenDebugDialog kandidaten={debugKandidaten.kandidaten} uebersprungen={debugKandidaten.uebersprungen || {}} onClose={() => setDebugKandidaten(null)} />}
    </>
  );
}

// ── Parse-Status-Styles ──────────────────────────────────────────────────────
const PARSE_STYLE = {
  erfolgreich:        { c:T.green,    bg:T.greenBg,  label:"Geparst"   },
  fehler:             { c:T.red,      bg:T.redBg,    label:"Fehler"    },
  ausstehend:         { c:T.textMuted,bg:T.surface,  label:"Ausstehend"},
  manuell_korrigiert: { c:T.blue,     bg:T.blueBg,   label:"Korrigiert"},
};

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

function KandidatenDebugDialog({ kandidaten, uebersprungen = {}, onClose }) {
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
    Object.values(g).forEach(arr => arr.sort((a,b) => (b.konfidenz||0)-(a.konfidenz||0)));
    return g;
  }, [kandidaten]);

  // Stats für Header-Zeile
  const stats = useMemo(() => {
    const eakteList = kandidaten.filter(k => k.quelle === "eakte");
    const lokalList = kandidaten.filter(k => k.quelle === "lokal");
    const routingCounts = {};
    eakteList.forEach(k => {
      const b = k.routing_basis || "unbekannt";
      routingCounts[b] = (routingCounts[b] || 0) + 1;
    });
    return { eakte: eakteList.length, lokal: lokalList.length, routing: routingCounts };
  }, [kandidaten]);

  const ROUTING_LABEL = {
    domain_versicherer:        "Domain ✓ Versicherer",
    rubrik:                    "Rubrik-Signal",
    fallback_kein_signal:      "Fallback (kein Signal)",
    fallback_domain_unbekannt: "Fallback (Domain unbekannt)",
  };

  const SKIP_LABEL = {
    schlagwort_ebrief:           "E-Brief (Ausgehend)",
    rubrik_gerichtlich:          "Gerichtlich",
    rubrik_verwaltungsbehoerde:  "Verwaltungsbehörde",
    rubrik_an_mandant:           "An Mandant",
    empfaenger_gericht:          "Empf. Gericht",
  };
  const skipEintraege = Object.entries(uebersprungen).filter(([, n]) => n > 0);
  const ROUTING_COLOR = {
    domain_versicherer:        "#22c55e",
    rubrik:                    T.blue,
    fallback_kein_signal:      "#f59e0b",
    fallback_domain_unbekannt: "#f59e0b",
  };

  const gruppenKeys = Object.keys(gruppen).sort((a,b) => a === "__ref__" ? 1 : b === "__ref__" ? -1 : a.localeCompare(b));

  return (
    <div onClick={onClose} style={{
      position:"fixed", inset:0, background:"rgba(0,0,0,0.55)", zIndex:9999,
      display:"flex", alignItems:"center", justifyContent:"center", padding:16,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background:T.cardBg, borderRadius:12, width:"100%", maxWidth:920,
        maxHeight:"88vh", display:"flex", flexDirection:"column",
        boxShadow:"0 8px 40px rgba(0,0,0,0.28)",
      }}>
        {/* Header */}
        <div style={{ padding:"14px 20px", borderBottom:`1px solid ${T.border}` }}>
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
            <div style={{ fontFamily:T.fontBody, fontWeight:700, fontSize:"1rem", color:T.text }}>
              Auto-Parser Debug – Kandidaten
            </div>
            <button onClick={onClose} style={{ background:"none", border:"none", cursor:"pointer",
              fontSize:"1.3rem", color:T.textMuted, lineHeight:1, padding:"4px 8px" }}>✕</button>
          </div>
          <div style={{ display:"flex", gap:16, flexWrap:"wrap", marginTop:6,
            fontFamily:T.fontBody, fontSize:"0.78rem" }}>
            <span style={{ color:T.textMuted }}>
              Gesamt: <strong style={{color:T.text}}>{kandidaten.length}</strong>
            </span>
            <span style={{ color:T.textMuted }}>
              Gewinner: <strong style={{color:T.green}}>{winnerSet.size}</strong>
            </span>
            {stats.eakte > 0 && (
              <span style={{ color:T.textMuted }}>
                E-Akte: <strong style={{color:T.blue}}>{stats.eakte}</strong>
              </span>
            )}
            {stats.lokal > 0 && (
              <span style={{ color:T.textMuted }}>
                Lokal: <strong style={{color:T.text}}>{stats.lokal}</strong>
              </span>
            )}
            {Object.entries(stats.routing).map(([basis, cnt]) => (
              <span key={basis} style={{ color: ROUTING_COLOR[basis] || T.textMuted, fontWeight:600 }}>
                {ROUTING_LABEL[basis] || basis}: {cnt}
              </span>
            ))}
            {skipEintraege.length > 0 && (
              <>
                <span style={{ color:T.border, userSelect:"none" }}>|</span>
                <span style={{ color:T.textMuted, fontWeight:600 }}>Übersprungen:</span>
                {skipEintraege.map(([grund, cnt]) => (
                  <span key={grund} style={{
                    background:"#fff1f2", border:"1px solid #fca5a5",
                    borderRadius:4, padding:"1px 6px",
                    color:"#9f1239", fontWeight:600,
                  }}>
                    {SKIP_LABEL[grund] || grund}: {cnt}
                  </span>
                ))}
              </>
            )}
          </div>
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
                <div style={{ fontFamily:T.fontBody, fontSize:"0.75rem",
                  fontWeight:700, textTransform:"uppercase", letterSpacing:"0.07em",
                  color: isRef ? T.textMuted : T.accent,
                  borderBottom:`2px solid ${isRef ? T.border : T.accent+"44"}`,
                  paddingBottom:4, marginBottom:6 }}>
                  {posLabel}
                </div>

                {gruppen[dk].map((k, i) => {
                  const isWinner = winnerSet.has(k);
                  const konfPct = Math.round((k.konfidenz||0)*100);
                  const konfColor = konfPct >= 85 ? T.green : konfPct >= 65 ? T.amber : T.textMuted;
                  const isEakte = k.quelle === "eakte";
                  const routingColor = ROUTING_COLOR[k.routing_basis] || T.textFaint;
                  return (
                    <div key={i} style={{
                      padding:"6px 8px", borderRadius:6, marginBottom:4,
                      background: isWinner ? T.green+"12" : (i%2===0 ? "#fafafa" : "#fff"),
                      border: isWinner ? `1px solid ${T.green}44` : "1px solid transparent",
                      fontFamily:T.fontBody,
                      fontWeight: isWinner ? 700 : 400,
                      color: T.text,
                    }}>
                      {/* Hauptzeile */}
                      <div style={{
                        display:"grid", gridTemplateColumns:"1fr 60px 80px 1fr 110px",
                        gap:"0 10px", alignItems:"center", fontSize:"0.82rem",
                      }}>
                        <span style={{ overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}
                          title={k.dateiname}>
                          {isWinner ? "★ " : ""}{k.dateiname || "—"}
                        </span>
                        <span style={{ fontSize:"0.72rem", color: isEakte ? T.blue : T.textMuted,
                          fontWeight:600, textAlign:"center" }}>
                          {isEakte ? "E-Akte" : "lokal"}
                        </span>
                        <span style={{ color:konfColor, fontWeight:700, textAlign:"right" }}>
                          {konfPct} %
                        </span>
                        <span style={{ fontSize:"0.75rem", color:T.textMuted, overflow:"hidden",
                          textOverflow:"ellipsis", whiteSpace:"nowrap" }}
                          title={k.grund}>
                          {k.grund}
                        </span>
                        <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.8rem",
                          textAlign:"right", color: k.betrag_vorschlag != null ? T.text : T.textFaint }}>
                          {k.betrag_vorschlag != null ? fmtEuro(k.betrag_vorschlag) : "kein Betrag"}
                        </span>
                      </div>
                      {/* Metadaten-Zeile (nur E-Akte) */}
                      {isEakte && (
                        <div style={{
                          display:"flex", gap:12, flexWrap:"wrap", marginTop:3,
                          fontSize:"0.72rem", color:T.textMuted,
                        }}>
                          {k.domain && (
                            <span title="Absender-Domain">
                              <span style={{opacity:0.6}}>Domain:</span>{" "}
                              <span style={{fontFamily:"ui-monospace,monospace", color:T.text}}>{k.domain}</span>
                            </span>
                          )}
                          {k.rubrik && (
                            <span title="RA-MICRO Rubrik">
                              <span style={{opacity:0.6}}>Rubrik:</span>{" "}
                              <span style={{color:T.text}}>{k.rubrik}</span>
                            </span>
                          )}
                          {k.einf_datum && (
                            <span title="Einfüge-Datum in RA-MICRO">
                              <span style={{opacity:0.6}}>Datum:</span>{" "}
                              <span style={{color:T.text}}>{k.einf_datum.slice(0,10)}</span>
                            </span>
                          )}
                          {k.routing_basis && (
                            <span style={{ color: routingColor, fontWeight:600 }}
                              title="Routing-Signal">
                              {ROUTING_LABEL[k.routing_basis] || k.routing_basis}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
          {kandidaten.length === 0 && (
            <div style={{ textAlign:"center", padding:"2rem", color:T.textMuted,
              fontFamily:T.fontBody }}>
              Keine Kandidaten gefunden.
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding:"10px 20px", borderTop:`1px solid ${T.border}`,
          display:"flex", justifyContent:"flex-end" }}>
          <button onClick={onClose} style={{
            fontFamily:T.fontBody, fontWeight:600, fontSize:"0.875rem",
            background:T.accent, color:"#fff", border:"none", borderRadius:7,
            padding:"7px 20px", cursor:"pointer",
          }}>
            Schließen
          </button>
        </div>
      </div>
    </div>
  );
}



// ── KI-Analyse-Dialog für Gutachten (PRD-31) ─────────────────────────────────

const _fmtE = v => (v != null && v > 0 && v < 999_000)
  ? v.toLocaleString("de-DE", { minimumFractionDigits: 2 }) + "\u202f€"
  : (v === 0 ? "0,00\u202f€" : "—");

const _SCHADENART_LABEL = {
  reparaturschaden: "Reparaturschaden",
  totalschaden:     "Totalschaden",
  grenzfall:        "Grenzfall",
};

function GutachtenVorschau({ erg, laden, wahl, setWahl, speichert, onSpeichern, onClose }) {
  const istKi = erg?.llm_verwendet;
  const hatKonflikt = erg?.llm_konflikt;
  const sp = erg?.schadenpositionen || {};

  const _toggle = (field) => setWahl(w => ({ ...w, [field]: w[field] === 'ki' ? 'regex' : 'ki' }));

  // Felder-Definition: [label, regex_val, ki_val, field_key, is_int]
  const felder = erg ? [
    ["Reparaturkosten (netto)",   sp.rep_gutachten_netto,        erg.llm_reparaturkosten_netto,       "rep_netto",     false],
    ["Wiederbeschaffungswert",    sp.wiederbeschaffung,           erg.llm_wbw,                         "wbw",           false],
    ["Restwert",                  sp.restwert,                    erg.llm_restwert,                    "restwert",      false],
    ["Wertminderung",             sp.wertminderung,               erg.llm_wertminderung,               "wertminderung", false],
    ["NA-Tagessatz",              erg.nutzungsausfall_tagessatz,  erg.llm_nutzungsausfall_tagessatz,   "na_tagessatz",  false],
    ["NA-Tage (Schätzung)",       erg.nutzungsausfall_tage,       erg.llm_nutzungsausfall_tage,        "na_tage",       true],
    ["SV-Kosten (netto)",         sp.sv_kosten_netto,             erg.llm_sv_kosten_netto,             "sv_netto",      false],
  ] : [];

  const schadenartKonflikt = istKi && erg.llm_schadenart && erg.llm_schadenart !== erg.schadenart;
  const hatKiWahl = Object.values(wahl).some(v => v === 'ki');

  const btnBase = {
    padding:"2px 8px", borderRadius:4, fontSize:11, fontWeight:600,
    cursor:"pointer", border:"1px solid", transition:"border-color .1s, color .1s",
  };

  return (
    <div style={{ borderRadius:12, border:`1px solid ${T.border}`, background:T.cardBg, overflow:"hidden" }}>
      {/* Header */}
      <div style={{ padding:"12px 20px", borderBottom:`1px solid ${T.border}`, display:"flex", alignItems:"center", justifyContent:"space-between", flexWrap:"wrap", gap:8 }}>
        <div style={{ display:"flex", alignItems:"center", gap:8, flexWrap:"wrap" }}>
          <span style={{ fontFamily:T.fontBody, fontWeight:700, fontSize:"0.975rem", color:T.text }}>
            Gutachten · KI-Analyse
          </span>
          {istKi && !hatKonflikt && (
            <span style={{ background:"rgba(139,92,246,0.18)", color:"#c4b5fd",
              border:"1px solid rgba(139,92,246,0.35)", borderRadius:4, fontSize:11, fontWeight:600,
              padding:"2px 7px", letterSpacing:"0.03em" }}>
              ✦ Qwen ✓
            </span>
          )}
          {istKi && hatKonflikt && (
            <span style={{ background:"rgba(245,158,11,0.15)", color:"#f59e0b",
              border:"1px solid rgba(245,158,11,0.4)", borderRadius:4, fontSize:11, fontWeight:600,
              padding:"2px 7px" }}>
              ⚠ KI-Konflikt
            </span>
          )}
          {!istKi && erg && (
            <span style={{ fontSize:11, color:T.textFaint }}>KI nicht aktiv</span>
          )}
          {erg?.sv_buero && (
            <span style={{ fontSize:12, color:T.textMuted }}>
              SV-Büro: <strong style={{ color:T.text }}>{erg.sv_buero}</strong>
            </span>
          )}
          {erg?.schadenart && (
            <span style={{ fontSize:12, color:T.textMuted }}>
              Schadenart: <strong style={{ color:T.text }}>{_SCHADENART_LABEL[erg.schadenart] || erg.schadenart}</strong>
            </span>
          )}
          {erg?.parse_konfidenz != null && (
            <span style={{ fontSize:12, color:T.textMuted }}>
              Konfidenz: <strong style={{ color:erg.parse_konfidenz > 0.7 ? T.green : T.amber }}>{Math.round(erg.parse_konfidenz * 100)} %</strong>
            </span>
          )}
        </div>
        <button onClick={onClose} style={{ background:"none", border:"none", cursor:"pointer", fontSize:"1.3rem", color:T.textMuted, lineHeight:1 }}>✕</button>
      </div>

      {/* Body */}
      <div style={{ padding:"12px 20px" }}>
          {laden && (
            <div style={{ textAlign:"center", padding:"2rem", color:T.textMuted }}>
              <div style={{ width:24, height:24, border:`3px solid ${T.accentTrim}`, borderTopColor:T.accent, borderRadius:"50%", animation:"spin 0.8s linear infinite", margin:"0 auto 8px" }} />
              KI-Ergebnis wird geladen …
            </div>
          )}

          {!laden && !erg && (
            <div style={{ textAlign:"center", padding:"2rem", color:T.textFaint, fontFamily:T.fontBody }}>
              Kein Parse-Ergebnis verfügbar.
            </div>
          )}

          {!laden && erg && (
            <>
              {/* Vergleichstabelle */}
              <table style={{ width:"100%", borderCollapse:"collapse", fontFamily:T.fontBody, fontSize:"0.85rem" }}>
                <thead>
                  <tr style={{ background:T.surface, borderBottom:`1px solid ${T.border}` }}>
                    <th style={{ padding:"6px 10px", textAlign:"left", fontWeight:600, color:T.textMuted, fontSize:"0.75rem", textTransform:"uppercase", letterSpacing:"0.05em" }}>Position</th>
                    <th style={{ padding:"6px 10px", textAlign:"right", fontWeight:600, color:T.textMuted, fontSize:"0.75rem", textTransform:"uppercase" }}>Regex</th>
                    {istKi && <th style={{ padding:"6px 10px", textAlign:"right", fontWeight:600, color:"#a78bfa", fontSize:"0.75rem", textTransform:"uppercase" }}>Qwen KI</th>}
                    {istKi && hatKonflikt && <th style={{ padding:"6px 10px", textAlign:"center", width:120, fontWeight:600, color:T.textMuted, fontSize:"0.75rem", textTransform:"uppercase" }}>Wählen</th>}
                  </tr>
                </thead>
                <tbody>
                  {felder.map(([label, rv, lv, fk, isInt]) => {
                    const rDisp = isInt ? (rv != null ? String(rv) + " Tage" : "—") : _fmtE(rv);
                    const lDisp = isInt ? (lv != null ? String(lv) + " Tage" : "—") : _fmtE(lv);
                    // Sentinel 1_000_000 = WBW "ausreichend" → kein Konflikt
                    const istKonf = istKi && lv != null && rv != null && rv < 999_000 && (isInt ? rv !== lv : Math.abs(rv - lv) > 1.0);
                    const kiGew = wahl[fk] === 'ki';
                    return (
                      <tr key={fk} style={{ borderBottom:`1px solid ${T.borderSoft}`, background: istKonf ? "rgba(245,158,11,0.04)" : "transparent" }}>
                        <td style={{ padding:"7px 10px", color:T.text, fontWeight:500 }}>{label}</td>
                        <td style={{ padding:"7px 10px", textAlign:"right", fontFamily:"ui-monospace,monospace",
                          color: istKonf && !kiGew ? T.green : T.textMid, fontWeight: istKonf && !kiGew ? 700 : 400 }}>
                          {rDisp}
                          {istKonf && !kiGew && <span style={{marginLeft:4, fontSize:9}}>✓</span>}
                        </td>
                        {istKi && (
                          <td style={{ padding:"7px 10px", textAlign:"right", fontFamily:"ui-monospace,monospace",
                            color: istKonf ? (kiGew ? T.green : "#f59e0b") : "#a78bfa",
                            fontWeight: kiGew ? 700 : 400 }}>
                            {lDisp}
                            {istKonf && kiGew && <span style={{marginLeft:4, fontSize:9}}>✓</span>}
                          </td>
                        )}
                        {istKi && hatKonflikt && (
                          <td style={{ padding:"7px 10px", textAlign:"center" }}>
                            {istKonf ? (
                              <div style={{ display:"inline-flex", gap:4 }}>
                                <button onClick={() => kiGew && _toggle(fk)}
                                  style={{ ...btnBase, background:"transparent",
                                    borderColor: !kiGew ? T.green : T.border,
                                    color: !kiGew ? T.green : T.textMuted }}>
                                  Regex
                                </button>
                                <button onClick={() => !kiGew && _toggle(fk)}
                                  style={{ ...btnBase, background:"transparent",
                                    borderColor: kiGew ? T.green : T.border,
                                    color: kiGew ? T.green : "#a78bfa" }}>
                                  KI
                                </button>
                              </div>
                            ) : (
                              <span style={{ fontSize:11, color:T.textFaint }}>—</span>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}

                  {/* Schadenart */}
                  {schadenartKonflikt && (() => {
                    const kiGew = wahl.schadenart === 'ki';
                    return (
                      <tr style={{ borderBottom:`1px solid ${T.borderSoft}`, background:"rgba(245,158,11,0.04)" }}>
                        <td style={{ padding:"7px 10px", color:T.text, fontWeight:500 }}>Schadenart</td>
                        <td style={{ padding:"7px 10px", textAlign:"right", color: !kiGew ? T.green : T.textMid, fontWeight: !kiGew ? 700 : 400 }}>
                          {_SCHADENART_LABEL[erg.schadenart] || erg.schadenart}
                          {!kiGew && <span style={{marginLeft:4, fontSize:9}}>✓</span>}
                        </td>
                        <td style={{ padding:"7px 10px", textAlign:"right", color: kiGew ? T.green : "#f59e0b", fontWeight: kiGew ? 700 : 400 }}>
                          {_SCHADENART_LABEL[erg.llm_schadenart] || erg.llm_schadenart}
                          {kiGew && <span style={{marginLeft:4, fontSize:9}}>✓</span>}
                        </td>
                        <td style={{ padding:"7px 10px", textAlign:"center" }}>
                          <div style={{ display:"inline-flex", gap:4 }}>
                            <button onClick={() => kiGew && _toggle('schadenart')}
                              style={{ ...btnBase, background:"transparent",
                                borderColor: !kiGew ? T.green : T.border,
                                color: !kiGew ? T.green : T.textMuted }}>
                              Regex
                            </button>
                            <button onClick={() => !kiGew && _toggle('schadenart')}
                              style={{ ...btnBase, background:"transparent",
                                borderColor: kiGew ? T.green : T.border,
                                color: kiGew ? T.green : "#a78bfa" }}>
                              KI
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })()}
                </tbody>
              </table>
            </>
          )}
        </div>

        {/* Footer */}
        {!laden && erg && (
          <div style={{ padding:"12px 20px", borderTop:`1px solid ${T.border}`, display:"flex", alignItems:"center", justifyContent:"flex-end", gap:10 }}>
            <button onClick={onClose} style={{ padding:"7px 16px", borderRadius:6, border:`1px solid ${T.border}`, background:"transparent", color:T.textMid, cursor:"pointer", fontFamily:T.fontBody, fontSize:"0.875rem" }}>
              Schließen
            </button>
            {(hatKiWahl || hatKonflikt) && (
              <button onClick={onSpeichern} disabled={speichert}
                style={{ padding:"7px 16px", borderRadius:6, border:"none", background: hatKiWahl ? T.accent : T.surface,
                  color: hatKiWahl ? "#fff" : T.textMuted, cursor: speichert ? "not-allowed" : "pointer",
                  fontFamily:T.fontBody, fontSize:"0.875rem", fontWeight:600,
                  opacity: speichert ? 0.6 : 1 }}>
                {speichert ? "Speichert …" : hatKiWahl ? "KI-Werte übernehmen" : "Regex-Werte bestätigen"}
              </button>
            )}
          </div>
        )}
    </div>
  );
}


export default DokumenteSection;
