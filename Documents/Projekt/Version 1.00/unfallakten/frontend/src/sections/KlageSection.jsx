import React, { useState, useEffect } from "react";
import KlageWizard, { berechneSwAussergEffektiv, buildRwVorschau, buildVerzugAutoText } from "./KlageWizard.jsx";
import { RegulierungsTabelle, TodoSection } from './UebersichtSection.jsx';
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { fmtEuro, verzugEintrittDefault } from "../config/utils.js";
import { Card, KlageCardHead, Btn, Toast } from "../components/common.jsx";
import SchmerzensgelDialog from "../components/SchmerzensgelDialog.jsx";
import {
  akten as apiAkten,
  apiKlage,
  apiGebuehren,
  apiFirmen,
  beteiligte as apiBeteiligte,
} from "../api.js";

function vertretungsHinweis(name) {
  const n = (name || "").toUpperCase();
  if (/(GMBH|GBR|\bKG\b|OHG)/.test(n)) return "– vertreten durch den/die Geschäftsführer –";
  if (/(\bAG\b|\bSE\b|KGAA)/.test(n))  return "– vertreten durch den Vorstand –";
  return "– vertreten durch den gesetzlichen Vertreter –";
}

// ── Vertreter-Lookup Modal ─────────────────────────────────────────────────


function ManuelleVertreterEingabe({ id, onSave }) {
  const [mName, setMName] = React.useState("");
  const [mFunk, setMFunk] = React.useState("Geschäftsführer");
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
      <div style={{ display:"flex", gap:8 }}>
        <select value={mFunk} onChange={e => setMFunk(e.target.value)}
          style={{ padding:"6px 8px", border:`1px solid ${T.border}`, borderRadius:6,
            fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", flexShrink:0 }}>
          <option value="Geschäftsführer">Geschäftsführer</option>
          <option value="Vorstand">Vorstand</option>
          <option value="Geschäftsführerin">Geschäftsführerin</option>
          <option value="Vorstandsvorsitzender">Vorstandsvorsitzender</option>
          <option value="gesetzlicher Vertreter">gesetzlicher Vertreter</option>
        </select>
        <input value={mName} onChange={e => setMName(e.target.value)}
          placeholder="Vor- und Nachname"
          style={{ flex:1, padding:"6px 10px", border:`1px solid ${T.border}`,
            borderRadius:6, fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem" }}/>
      </div>
      <button onClick={() => { if (mName.trim()) onSave(mName.trim(), mFunk); }}
        disabled={!mName.trim()}
        style={{ padding:"7px 16px", background:T.navy, color:"#fff", border:"none",
          borderRadius:6, cursor:"pointer", fontSize:"0.875rem", fontWeight:600,
          opacity: mName.trim() ? 1 : 0.4 }}>
        Manuell übernehmen
      </button>
    </div>
  );
};


function VertreterModal({ vertreterModal, setVModal, setBek, apiFirmen, vertreterLookup, T }) {
  if (!vertreterModal) return null;
  const { id, name, daten } = vertreterModal;
  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.45)",
      zIndex:9999, display:"flex", alignItems:"center", justifyContent:"center" }}
      onClick={() => setVModal(null)}>
      <div style={{ background:"#fff", borderRadius:12, padding:"1.75rem",
        maxWidth:480, width:"90%", boxShadow:"0 20px 60px rgba(0,0,0,0.3)" }}
        onClick={e => e.stopPropagation()}>
        <h3 style={{ fontFamily:"'Figtree',sans-serif", fontSize:"1rem",
          fontWeight:700, margin:"0 0 0.5rem", color:T.navy }}>
          Vertreter-Lookup: {name}
        </h3>
        {daten?.rechtsform && (
          <div style={{ fontSize:"0.85rem", color:T.textMuted, marginBottom:"0.75rem" }}>
            Rechtsform: <strong>{daten.rechtsform}</strong>
            {daten.registernr ? ` · ${daten.registernr}` : ""}
          </div>
        )}
        {daten?.gefunden && daten.vertreter?.length > 0 ? (
          <div>
            <div style={{ fontSize:"0.875rem", color:T.text, marginBottom:"0.5rem", fontWeight:600 }}>
              Gefundene Vertreter ({daten.quelle}):
            </div>
            {daten.vertreter.map((v, i) => (
              <div key={i} style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
                padding:"8px 10px", background:T.surface, borderRadius:7, marginBottom:6 }}>
                <div>
                  <div style={{ fontWeight:600, fontSize:"0.925rem" }}>{v.name}</div>
                  <div style={{ fontSize:"0.82rem", color:T.textMuted }}>{v.funktion}</div>
                </div>
                <button onClick={async () => {
                    // Lokal im State aktualisieren
                    setBek(prev => prev.map(b => b.id === id
                      ? {...b, vertreter_name: v.name, vertreter_funktion: v.funktion}
                      : b
                    ));
                    // Dauerhaft in DB speichern
                    try {
                      await apiFirmen.vertreterSpeichern(id, v.name, v.funktion);
                    } catch(e) {
                      // Hintergrundspeicherung – kein toast nötig
                    }
                    setVModal(null);
                  }}
                  style={{ background:T.navy, color:"#fff", border:"none", borderRadius:6,
                    padding:"5px 12px", cursor:"pointer", fontSize:"0.82rem", fontWeight:600 }}>
                  Übernehmen
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div>
            <div style={{ padding:"0.75rem 1rem", background:T.amber+"15", borderRadius:8,
              border:`1px solid ${T.amber}30`, fontSize:"0.875rem", color:T.amberText, marginBottom:"1rem" }}>
              {daten?.hinweis || "Keine automatischen Daten gefunden. Bitte manuell eintragen:"}
            </div>
            {/* Manuelle Eingabe */}
            <ManuelleVertreterEingabe id={id} onSave={(name, funk) => {
              setBek(prev => prev.map(b => b.id === id
                ? {...b, vertreter_name: name, vertreter_funktion: funk}
                : b
              ));
              apiFirmen.vertreterSpeichern(id, name, funk).catch(() => {});
              setVModal(null);
            }}/>
          </div>
        )}
        <div style={{ display:"flex", justifyContent:"flex-end", marginTop:"1rem" }}>
          <button onClick={() => setVModal(null)}
            style={{ padding:"6px 16px", border:`1px solid ${T.border}`, borderRadius:7,
              background:"#fff", cursor:"pointer", fontSize:"0.875rem" }}>
            Schließen
          </button>
        </div>
      </div>
    </div>
  );
};


function KlageSection({ akteId, akte, st, dispatch }) {
  const [daten, setDaten]       = useState(null);
  const [laedt, setLaedt]       = useState(true);
  const [generiert_laedt, setGenLaedt] = useState(false);
  const [toast, setToast]       = useState("");
  const [fehler, setFehler]     = useState("");

  // Konfiguration
  const [positionen, setPos]    = useState([]);
  const [beklagte, setBek]      = useState([]);
  const [gericht, setGericht]   = useState(null);   // gewähltes Gericht
  const [gerichtSuche, setGSuche] = useState("");
  const [gerichtTreffer, setGTreffer] = useState([]);
  const [gerichtLaedt, setGLaedt]  = useState(false);
  // Firmen-Vertreter Lookup
  const [vertreterLookup, setVLookup]   = useState({});  // {id: {laden, ergebnis}}
  const [vertreterModal, setVModal]     = useState(null); // {id, name, daten}
  const [mitSG, setMitSG]       = useState(false);
  const [sgMind, setSGMind]     = useState(0);
  const [showSgAssistent, setShowSgAssistent] = useState(false);
  const [zinsenAb, setZinsenAb]       = useState("verzug");
  const [verzugDokListe, setVerzugDokListe] = useState([]);
  const [verzugDokId, setVerzugDokId]       = useState(null);
  const [rvgData, setRvgData]   = useState(null);

  // ── Wizard-State (PRD-24) ──────────────────────────────────────────────
  const [wizardOffen, setWizardOffen]         = useState(false);
  const [wizardStep, setWizardStep]           = useState(1);
  const [aktLegTyp, setAktLegTyp]             = useState("eigentum");
  const [aktLegFreigabe, setAktLegFreigabe]   = useState("freigabe");
  const [aktLegDatum, setAktLegDatum]         = useState("");
  const [wizardPos, setWizardPos]             = useState([]);
  const [wizardMitSG, setWizardMitSG]         = useState(false);
  const [wizardSGMind, setWizardSGMind]       = useState(0);
  const [wizardSachverhaltText, setWizardSachverhaltText] = useState("");
  const [auslandsunfall, setAuslandsunfall] = useState(false);
  const [wizardUnfallText, setWizardUnfallText] = useState("");
  const [wizardRwText, setWizardRwText]         = useState("");
  const [wizardVerzugText, setWizardVerzugText]       = useState("");
  const [wizardVerzugDatum, setWizardVerzugDatum]     = useState("");
  const [wizardVerzugDokDatum, setWizardVerzugDokDatum] = useState("");
  const [wizardVerzugManuell, setWizardVerzugManuell] = useState(false);
  const [kiLaedt, setKiLaedt]                     = useState(false);
  const [lgGrenzwert, setLgGrenzwert]             = useState(10000);
  // PRD-26: neue Wizard-States
  const [wizardHq, setWizardHq]                     = useState(100);
  const [wizardHqTyp, setWizardHqTyp]               = useState("gegnerisch");
  const [wizardHb, setWizardHb]                     = useState("");
  const [wizardMaxStep, setWizardMaxStep]           = useState(1);
  const [wizardGerichtBest, setWizardGerichtBest]   = useState(false);
  const [wizardMitFestSg, setWizardMitFestSg]       = useState(false);
  const [wizardMitFestSach, setWizardMitFestSach]   = useState(false);
  const [wizardAntraegeText, setWizardAntraegeText] = useState("");
  const [wizardRvgAussergData, setWizardRvgAussergData]         = useState(null);
  const [wizardRvgAussergOv, setWizardRvgAussergOv]             = useState("");
  const [wizardRvgBereitsGezahlt, setWizardRvgBereitsGezahlt]   = useState("");
  const [wizardGebuehrenText, setWizardGebuehrenText]   = useState("");
  const [gespeichertGb, setGespeichertGb]               = useState(null); // PRD-28: gespeicherte Gebührenberechnung

  useEffect(() => {
    (async () => {
      setLaedt(true);
      try {
        const res = await apiKlage.daten(akteId);
        setDaten(res);
        setPos(res.positionen || []);
        setBek((res.beteiligte || []).map(b => ({
          ...b,
          checked: !!b.vorschlag_beklagter,
        })));
        const initVerzug = res.verzug_datum || "";
        setWizardVerzugDokDatum(initVerzug);
        setWizardVerzugDatum(verzugEintrittDefault(initVerzug));
        const vdl = res.verzug_dokumente || [];
        setVerzugDokListe(vdl);
        // Vorauswahl: mahnschreiben/verzugsschreiben bevorzugen
        const prioritaetsDok = vdl.find(d =>
          d.dokumentenklasse === "mahnschreiben" || d.dokumentenklasse === "verzugsschreiben"
        ) || vdl[0];
        setVerzugDokId(prioritaetsDok?.id ?? null);
        setRvgData(res.rvg || null);
        if (res.lg_grenzwert) setLgGrenzwert(res.lg_grenzwert);
        // Gericht-Vorschlag automatisch setzen
        if (res.gericht_vorschlag) {
          setGericht(res.gericht_vorschlag);
        }
        // PRD-28: gespeicherte Gebührenberechnung laden
        try {
          const gb = await apiGebuehren.laden(akteId);
          if (gb.gespeichert) {
            setGespeichertGb(gb.gespeichert);
          }
        } catch { /* Gebühren-Tab optional */ }
      } catch (e) {
        setFehler(e?.message || "Fehler beim Laden.");
      }
      setLaedt(false);
    })();
  }, [akteId]);


  // Auto-Vertreter-Lookup: Firmen ohne Vertreter beim Tab-Aufruf abfragen
  useEffect(() => {
    if (!beklagte.length) return;
    beklagte.forEach(b => {
      if (b.rolle_klage === "klaeger") return;
      if (b.vertreter_name) return;
      const name = b.versicherung || b.firma ||
        (String(b.vorname || "") + " " + String(b.name || "")).trim();
      const istFirma = !!(b.versicherung || b.firma ||
        (!b.vorname && b.name && b.rolle !== "mandant"));
      if (!istFirma) return;
      if (vertreterLookup[b.id]?.laden) return;
      lookupVertreter(b.id, name);
    });
  }, [beklagte]); // eslint-disable-line react-hooks/exhaustive-deps


  // Gesamte regulierte Zahlung (inkl. unzugeordneter Vorschüsse)
  const gesamtReguliert = (daten?.abrechnungen || []).reduce(
    (s, a) => s + (parseFloat(a.gesamt_reguliert) || 0), 0
  );

  // Außergerichtlicher Streitwert = Summe aller Schadenpositionen (Brutto-Forderung)
  const swAusserg = positionen.reduce((s, p) => s + (p.betrag || 0), 0);
  // KW-03: Nr.-2300-Basis quotieren bei eigener Mithaftungsquote - einzige Ableitungsstelle,
  // verwendet für beide rvgBerechnen-Aufrufe, die StepGebuehren-Prop und die Anzeige.
  const swAussergEffektiv = berechneSwAussergEffektiv(swAusserg, wizardHq, wizardHqTyp);

  // Per-Position offene Beträge — selbe _KEY_MAP-Logik wie oeffneWizard()
  const _KLAGEN_KEY_MAP = {
    "reparatur_netto":     "fahrzeugschaden",
    "reparatur_brutto":    "fahrzeugschaden",
    "reparaturkosten":     "fahrzeugschaden",
    "wba":                 "fahrzeugschaden",
    "rep_gutachten_netto": "fahrzeugschaden",
    "rep_rechnung_netto":  "fahrzeugschaden",
    "rep_rechnung_brutto": "fahrzeugschaden",
    "wiederbeschaffung":   "fahrzeugschaden",
  };
  const _posRegMap = {};
  (daten?.abrechnungen || []).forEach(ab => {
    (ab.positionen || []).forEach(rp => {
      const k = _KLAGEN_KEY_MAP[rp.position_key] || rp.position_key;
      if (k) _posRegMap[k] = (_posRegMap[k] || 0) + (parseFloat(rp.betrag_reguliert) || 0);
    });
  });
  let posOffen = positionen.map(p => ({
    ...p,
    reguliertPos: _posRegMap[p.key] || 0,
    offenBetrag:  Math.max(0, (p.betrag || 0) - (_posRegMap[p.key] || 0)),
  }));
  const _posLevelPaid = Object.values(_posRegMap).reduce((s, v) => s + v, 0);
  let _unassignedK = Math.max(0, gesamtReguliert - _posLevelPaid);
  if (_unassignedK > 0.005) {
    const _red = {};
    [...posOffen].sort((a, b) => (b.offenBetrag || 0) - (a.offenBetrag || 0)).forEach(p => {
      if (_unassignedK <= 0.005) return;
      const r = Math.min(_unassignedK, p.offenBetrag || 0);
      _red[p.key] = r;
      _unassignedK -= r;
    });
    posOffen = posOffen.map(p => ({
      ...p,
      reguliertPos: (p.reguliertPos || 0) + (_red[p.key] || 0),
      offenBetrag:  Math.max(0, (p.offenBetrag || 0) - (_red[p.key] || 0)),
    }));
  }
  // Gerichtlicher Streitwert = Summe der offenen Beträge angehakter Positionen
  const klagebetrag = Math.max(0,
    posOffen.filter(p => p.checked).reduce((s, p) => s + (p.offenBetrag || 0), 0)
  );
  useEffect(() => {
    if (!daten) return;
    (async () => {
      try {
        const res = await apiKlage.rvgBerechnen(akteId, { streitwert: swAussergEffektiv });
        setRvgData(res.rvg);
      } catch {}
    })();
  }, [swAussergEffektiv]);

  // Step 9: RVG auf außergerichtl. Streitwert berechnen wenn Step 9 erreicht
  useEffect(() => {
    if (!wizardOffen || wizardStep !== 9 || wizardRvgAussergData) return;
    (async () => {
      try {
        const res = await apiKlage.rvgBerechnen(akteId, { streitwert: swAussergEffektiv });
        setWizardRvgAussergData(res.rvg);
      } catch {}
    })();
  }, [wizardStep, wizardOffen]); // eslint-disable-line

  const togglePos = (key) =>
    setPos(p => p.map(x => x.key === key ? {...x, checked: !x.checked} : x));
  const toggleBek = (id) =>
    setBek(b => b.map(x => x.id === id ? {...x, checked: !x.checked} : x));
  const toggleHalter = async (bid, neuerWert) => {
    try {
      await apiBeteiligte.aktualisieren(akteId, bid, { ist_halter: neuerWert ? 1 : 0 });
      setBek(prev => prev.map(b => b.id === bid ? { ...b, ist_halter: neuerWert ? 1 : 0 } : b));
    } catch { /* nicht kritisch */ }
  };

  const lookupVertreter = async (id, firmenname) => {
    setVLookup(p => ({...p, [id]: {laden: true, ergebnis: null}}));
    try {
      const res = await apiFirmen.vertreter(firmenname);
      setVLookup(p => ({...p, [id]: {laden: false, ergebnis: res}}));
      setVModal({id, name: firmenname, daten: res});
    } catch(e) {
      setVLookup(p => ({...p, [id]: {laden: false, ergebnis: null}}));
      const msg = e?.status ? `HTTP ${e.status}: ${e.message}` : (e?.message || String(e));
      setToast("Vertreter-Lookup fehlgeschlagen: " + msg);
    }
  };

  const sucheGerichte = async (q) => {
    setGSuche(q);
    if (q.length < 2) { setGTreffer([]); return; }
    setGLaedt(true);
    try {
      const res = await apiKlage.gerichte(akteId, q);
      setGTreffer(res?.gerichte || []);
    } catch { setGTreffer([]); }
    finally { setGLaedt(false); }
  };

  // ── Wizard öffnen – State aus DB-Werten initialisieren ────────────────
  const oeffneWizard = () => {
    const al = daten?.aktivlegitimation || {};
    setAktLegTyp(al.typ || "eigentum");
    setAktLegFreigabe(al.freigabe_status || "freigabe");
    setAktLegDatum(al.datum_freigabe || "");
    // Offene Beträge vorausberechnen (gefordert − reguliert je Position)
    // Fahrzeugschaden-Keys aus dem Abrechnung-Parser → Wizard-Key "fahrzeugschaden"
    const _KEY_MAP = {
      "reparatur_netto":     "fahrzeugschaden",
      "reparatur_brutto":    "fahrzeugschaden",
      "reparaturkosten":     "fahrzeugschaden",
      "wba":                 "fahrzeugschaden",
      "rep_gutachten_netto": "fahrzeugschaden",
      "rep_rechnung_netto":  "fahrzeugschaden",
      "rep_rechnung_brutto": "fahrzeugschaden",
      "wiederbeschaffung":   "fahrzeugschaden",
    };
    const _regMap = {};
    (daten?.abrechnungen || []).forEach(ab => {
      (ab.positionen || []).forEach(rp => {
        const rawKey = rp.position_key;
        const k = _KEY_MAP[rawKey] || rawKey;
        if (k) _regMap[k] = (_regMap[k] || 0) + (parseFloat(rp.betrag_reguliert) || 0);
      });
    });
    // Schritt 1: positions-gebundene Regulierungen abziehen
    let _workPos = positionen.map(p => ({
      ...p,
      betragOriginal: p.betrag || 0,
      betrag: Math.max(0, (p.betrag || 0) - (_regMap[p.key] || 0)),
    }));
    // Schritt 2: ungebundene Zahlungen (Vorschuss) gierig auf größte Positionen verteilen
    const _posLevelPaid = Object.values(_regMap).reduce((s, v) => s + v, 0);
    let _unassigned = Math.max(0, gesamtReguliert - _posLevelPaid);
    if (_unassigned > 0.005) {
      const _reductions = {};
      [..._workPos].sort((a, b) => (b.betrag||0) - (a.betrag||0)).forEach(p => {
        if (_unassigned <= 0.005) return;
        const r = Math.min(_unassigned, p.betrag || 0);
        _reductions[p.key] = r;
        _unassigned -= r;
      });
      _workPos = _workPos.map(p => ({
        ...p,
        betrag: Math.max(0, (p.betrag || 0) - (_reductions[p.key] || 0)),
      }));
    }
    setWizardPos(_workPos);
    setWizardMitSG(mitSG);
    setWizardSGMind(sgMind);
    setWizardSachverhaltText("");
    setAuslandsunfall(false);

    // ── Unfallhergang: Schilderung laden + Mandant→Kläger ersetzen ──
    const klaegerObj = beklagte.find(b => b.rolle_klage === "klaeger");
    const weiblich   = (klaegerObj?.anrede || "").toLowerCase() === "frau";
    const schilderung = daten?.unfalldetails?.schilderung || "";
    let unfall = schilderung;
    if (unfall) {
      unfall = unfall.replace(/\bder Mandantin\b/gi, "der Klägerin");
      unfall = unfall.replace(/\bdes Mandanten\b/gi, weiblich ? "der Klägerin" : "des Klägers");
      unfall = unfall.replace(/\bdem Mandanten\b/gi, weiblich ? "der Klägerin" : "dem Kläger");
      unfall = unfall.replace(/\bdie Mandantin\b/gi, "die Klägerin");
      unfall = unfall.replace(/\bden Mandanten\b/gi, weiblich ? "die Klägerin" : "den Kläger");
      unfall = unfall.replace(/\bMandantin\b/g, "Klägerin");
      unfall = unfall.replace(/\bMandant\b/g, weiblich ? "Klägerin" : "Kläger");
    }
    setWizardUnfallText(unfall);

    // ── Rechtliche Würdigung: dynamisch vorbauen ──
    const hq      = parseFloat(daten?.unfalldetails?.haftungsquote || 100);
    const gesReg  = (daten?.abrechnungen || []).reduce((s, a) => s + (parseFloat(a.gesamt_reguliert) || 0), 0);
    const hb      = daten?.unfalldetails?.haftungsbegruendung || "";
    setWizardHq(hq);
    setWizardHqTyp("gegnerisch");
    setWizardHb(hb);
    setWizardRwText(buildRwVorschau(hb, hq, gesReg, weiblich, "gegnerisch", beklagte));

    const dok = wizardVerzugDokDatum || "";
    const ein = wizardVerzugDatum || "";
    setWizardVerzugText(buildVerzugAutoText(dok, ein));
    setWizardVerzugManuell(false);

    // PRD-26: neue States initialisieren
    setWizardMaxStep(1);
    setWizardGerichtBest(gericht?.quelle === "akte"); // nur vorbestätigt wenn aus Akte gespeichert
    setWizardMitFestSg(mitSG);
    setWizardMitFestSach(false);
    setWizardAntraegeText("");
    setWizardRvgAussergData(null);
    setWizardRvgAussergOv("");
    setWizardRvgBereitsGezahlt("");
    setWizardGebuehrenText("");

    setWizardStep(1);
    setWizardOffen(true);
  };

  // ── Gericht bestätigen + in Akte speichern + Wizard weiterschalten ────
  const gerichtBestaetigenUndWeiter = () => {
    if (gericht) {
      apiKlage.gerichtSpeichern(akteId, gericht).catch(() => {});
    }
    setWizardGerichtBest(true);
    const next = wizardStep + 1;
    setWizardStep(next);
    if (next > wizardMaxStep) setWizardMaxStep(next);
  };

  // ── KI-Haftungsbegründung ─────────────────────────────────────────────
  const handleKiHaftung = async () => {
    setKiLaedt(true);
    try {
      const res = await apiKlage.kiHaftung(akteId, wizardUnfallText, wizardHq);
      setWizardRwText(res.text);
    } catch (e) {
      setFehler(e.message || "KI-Aufruf fehlgeschlagen.");
    } finally {
      setKiLaedt(false);
    }
  };

  // ── Wizard generieren – mit Overrides ─────────────────────────────────
  const wizardGenerieren = async () => {
    setGenLaedt(true); setFehler("");
    try {
      const overrides = {
        aktivlegitimation_typ:             aktLegTyp,
        aktivlegitimation_freigabe:        aktLegFreigabe,
        aktivlegitimation_datum:           aktLegDatum || null,
        sachverhalt_override:              wizardSachverhaltText || null,
        schilderung:                       wizardUnfallText || null,
        rw_text_override:                  wizardRwText     || null,
        verzug_text_override:              wizardVerzugText || null,
        mit_feststellung_sg:               wizardMitFestSg,
        mit_feststellung_sach:             wizardMitFestSach,
        antraege_override:                 wizardAntraegeText || null,
        rvg_ausserg:                       wizardRvgAussergData,
        rvg_ausserg_override:              wizardRvgAussergOv ? parseFloat(wizardRvgAussergOv) : null,
        rvg_bereits_gezahlt:               wizardRvgBereitsGezahlt ? parseFloat(wizardRvgBereitsGezahlt) : null,
      };
      await apiKlage.generieren(akteId, {
        gericht,
        beklagte:               beklagte.filter(b => b.rolle_klage === "klaeger" || b.checked),
        positionen:             wizardPos,
        mit_schmerzensgeld:     wizardMitSG,
        schmerzensgeld_mindest: wizardMitSG ? wizardSGMind : 0,
        verzugsdatum:           zinsenAb === "verzug" ? (wizardVerzugDatum || null) : null,
        verzug_schreiben_datum: wizardVerzugDokDatum || null,
        zinsen_ab:              zinsenAb,
        haftungsquote:          wizardHq,
        haftungsquote_typ:      wizardHqTyp,
      }, overrides);
      setToast("Klageschrift heruntergeladen.");
      setWizardOffen(false);
      try {
        await apiAkten.aktualisieren(akteId, { status: "klage" });
        if (dispatch) dispatch({ type: "SET_STATUS", akteId, status: "klage" });
      } catch { /* Status-Update nicht kritisch */ }
    } catch (e) {
      setFehler(e?.message || "Fehler bei der Generierung.");
    } finally { setGenLaedt(false); }
  };

  const rvgGesamt = (wizardRvgAussergData?.gesamt ?? rvgData?.gesamt) || 0;

  const inS = { padding:"6px 10px", border:`1px solid ${T.border}`, borderRadius:7,
    fontFamily:"ui-monospace,monospace", fontSize:"0.915rem", outline:"none",
    background:T.white };

  if (laedt) return <div style={{ padding:"2rem", textAlign:"center", color:T.textFaint,
    fontFamily:"'Figtree',sans-serif" }}>Lade Klage-Daten …</div>;

  return (
    <div style={{ flex:1, overflowY:"auto", background:T.offWhite }}>
      <VertreterModal vertreterModal={vertreterModal} setVModal={setVModal}
        setBek={setBek} apiFirmen={apiFirmen} vertreterLookup={vertreterLookup} T={T} />
      {wizardOffen && (
        <KlageWizard
          step={wizardStep}          onStepChange={setWizardStep}
          onClose={() => setWizardOffen(false)}
          wizardMaxStep={wizardMaxStep} onMaxStep={setWizardMaxStep}
          // Step 1: Gericht
          gericht={gericht}             setGericht={setGericht}
          gerichtSuche={gerichtSuche}   setGSuche={setGSuche}
          gerichtTreffer={gerichtTreffer} setGTreffer={setGTreffer}
          gerichtLaedt={gerichtLaedt}
          sucheGerichte={sucheGerichte}
          gerichtBestaetigt={wizardGerichtBest} setGerichtBestaetigt={setWizardGerichtBest}
          onGerichtBestaetigen={gerichtBestaetigenUndWeiter}
          // Step 3: Aktivlegitimation / Sachverhalt
          aktLegTyp={aktLegTyp}         onAktLegTyp={setAktLegTyp}
          aktLegFreigabe={aktLegFreigabe} onAktLegFreigabe={setAktLegFreigabe}
          aktLegDatum={aktLegDatum}     onAktLegDatum={setAktLegDatum}
          mandantIstFahrer={daten?.aktivlegitimation?.mandant_ist_fahrer || false}
          mandantKz={daten?.unfalldetails?._wdm_mandant_kz || ""}
          sachverhaltText={wizardSachverhaltText}
          onSachverhaltText={setWizardSachverhaltText}
          auslandsunfall={auslandsunfall}
          onAuslandsunfall={setAuslandsunfall}
          mandantVorsteuer={beklagte.find(b => b.rolle_klage === "klaeger")?.vorsteuer === "J"}
          unfallort={daten?.unfallort || ""}
          // Step 4: Unfallhergang
          schilderungOriginal={daten?.unfalldetails?.schilderung || ""}
          wizardUnfallText={wizardUnfallText}
          onWizardUnfallText={setWizardUnfallText}
          // Step 5: Schadenpositionen
          abrechnungen={daten?.abrechnungen || []}
          positionen={wizardPos}        onTogglePos={key =>
            setWizardPos(p => p.map(x => x.key === key ? {...x, checked: !x.checked} : x))}
          mitSG={wizardMitSG}           onMitSG={setWizardMitSG}
          sgMind={wizardSGMind}         onSGMind={setWizardSGMind}
          // Step 6: Klageanträge
          unfalldatum={daten?.unfalldetails?.unfalldatum || ""}
          wizardMitFestSg={wizardMitFestSg}     onMitFestSg={setWizardMitFestSg}
          wizardMitFestSach={wizardMitFestSach}  onMitFestSach={setWizardMitFestSach}
          wizardAntraegeText={wizardAntraegeText} onAntraegeText={setWizardAntraegeText}
          // Step 7: Rechtliche Würdigung
          wizardHq={wizardHq}           onWizardHq={setWizardHq}
          wizardHqTyp={wizardHqTyp}     onWizardHqTyp={setWizardHqTyp}
          wizardHb={wizardHb}           onWizardHb={setWizardHb}
          wizardRwText={wizardRwText}   onWizardRwText={setWizardRwText}
          kuerzungsarten={daten?.kuerzungsarten || []}
          onKiHaftung={handleKiHaftung} kiLaedt={kiLaedt}
          // Step 8: Verzug
          wizardVerzugText={wizardVerzugText}         onWizardVerzugText={setWizardVerzugText}
          wizardVerzugDatum={wizardVerzugDatum}       onWizardVerzugDatum={setWizardVerzugDatum}
          wizardVerzugDokDatum={wizardVerzugDokDatum} onWizardVerzugDokDatum={setWizardVerzugDokDatum}
          wizardVerzugManuell={wizardVerzugManuell}   onWizardVerzugManuell={setWizardVerzugManuell}
          verzugDokListe={verzugDokListe}
          verzugDokId={verzugDokId}                   onVerzugDokId={setVerzugDokId}
          // Step 9: Außergerichtl. Gebühren
          swAusserg={swAussergEffektiv}
          wizardRvgAussergData={wizardRvgAussergData}       onRvgAussergData={setWizardRvgAussergData}
          wizardRvgAussergOv={wizardRvgAussergOv}           onRvgAussergOv={setWizardRvgAussergOv}
          wizardRvgBereitsGezahlt={wizardRvgBereitsGezahlt} onRvgBereitsGezahlt={setWizardRvgBereitsGezahlt}
          wizardGebuehrenText={wizardGebuehrenText}         onGebuehrenText={setWizardGebuehrenText}
          gespeichertGb={gespeichertGb}               onGespeichertGb={setGespeichertGb}
          wizardAkteId={akteId}
          // Shared
          beklagte={beklagte}
          zinsenAb={zinsenAb}
          lgGrenzwert={lgGrenzwert}
          // Generieren
          laedt={generiert_laedt}
          onGenerieren={wizardGenerieren}
          fehler={fehler}
        />
      )}
      {showSgAssistent && (() => {
        const kObj  = beklagte.find(b => b.rolle_klage === "klaeger");
        const klNom = (kObj?.anrede || "").toLowerCase() === "frau" ? "Die Klägerin" : "Der Kläger";
        return (
          <SchmerzensgelDialog
            az={akteId}
            kl_nom={klNom}
            onClose={() => setShowSgAssistent(false)}
            onUebernehmen={({ mitSG: sg, sgMind: mind }) => {
              setMitSG(sg);
              setSGMind(mind);
              setShowSgAssistent(false);
            }}
          />
        );
      })()}
      {toast && <Toast msg={toast} onDone={() => setToast("")}/>}
      <div style={{ maxWidth:900, margin:"0 auto", padding:"1.75rem",
        display:"flex", flexDirection:"column", gap:"1.25rem" }}>

        {fehler && (
          <div style={{ background:T.redBg, border:`1px solid ${T.red}30`, borderRadius:8,
            padding:"10px 14px", color:T.red, fontFamily:"'Figtree',sans-serif",
            fontSize:"0.915rem" }}>{fehler}</div>
        )}

        {/* Zweispaltig: Gericht+Rubrum links | Klage-Kachel rechts */}
        <div style={{ display:"flex", gap:"1.25rem", alignItems:"flex-start" }}>
          <div style={{ flex:1, display:"flex", flexDirection:"column", gap:"1.25rem" }}>

        {/* 0) Gericht */}
        <Card>
          <KlageCardHead nr={1} title="Gericht" />
          <div style={{ padding:"0.75rem 1.25rem" }}>
            {/* Gewähltes Gericht anzeigen */}
            {gericht ? (
              <div style={{ display:"flex", alignItems:"center", gap:12,
                background:T.surface, borderRadius:8, padding:"10px 14px",
                marginBottom:"0.75rem" }}>
                <div style={{ flex:1 }}>
                  <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.945rem",
                    fontWeight:700, color:T.navy }}>{gericht.name}</div>
                  <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.835rem",
                    color:T.textMuted }}>
                    {[gericht.strasse, gericht.plz, gericht.ort].filter(Boolean).join(", ")}
                  </div>
                  {gericht.quelle && (
                    <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                      marginTop:3,
                      color: gericht.quelle === "akte" ? T.green
                           : gericht.quelle === "unfallort_match" ? T.amber
                           : T.textFaint }}>
                      {gericht.quelle === "akte"
                        ? "✓ In Akte gespeichert"
                        : gericht.quelle === "unfallort_match"
                        ? `⚡ Vorschlag nach Unfallort${daten?.unfallort ? ` (${daten.unfallort})` : ""} – bitte prüfen`
                        : "Manuell gewählt"}
                    </div>
                  )}
                </div>
                <button onClick={() => { setGericht(null); setGTreffer([]); setGSuche(""); }}
                  style={{ background:"none", border:`1px solid ${T.border}`, borderRadius:6,
                    padding:"3px 10px", cursor:"pointer", color:T.textMuted,
                    fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem" }}>
                  ✕ Ändern
                </button>
              </div>
            ) : (
              <div style={{ color:T.amber, fontFamily:"'Figtree',sans-serif",
                fontSize:"0.875rem", marginBottom:"0.75rem" }}>
                ⚠ Kein Gericht ausgewählt – bitte suchen und auswählen.
              </div>
            )}

            {/* Suchfeld */}
            {!gericht && (
              <div>
                <div style={{ display:"flex", gap:8, alignItems:"center",
                  background:T.white, border:`1px solid ${T.border}`, borderRadius:8,
                  padding:"6px 12px", marginBottom:"0.5rem" }}>
                  <span style={{ color:T.textFaint }}>🔍</span>
                  <input value={gerichtSuche} onChange={e => sucheGerichte(e.target.value)}
                    placeholder="Gericht suchen (z.B. Frankfurt, Offenbach) …"
                    style={{ flex:1, border:"none", outline:"none", background:"transparent",
                      fontFamily:"'Figtree',sans-serif", fontSize:"0.935rem" }}/>
                  {gerichtLaedt && (
                    <div style={{ width:14, height:14, border:`2px solid ${T.border}`,
                      borderTopColor:T.navy, borderRadius:"50%",
                      animation:"spin 0.7s linear infinite" }}/>
                  )}
                </div>

                {/* Treffer-Liste */}
                {gerichtTreffer.length > 0 && (
                  <div style={{ border:`1px solid ${T.border}`, borderRadius:8,
                    overflow:"hidden", maxHeight:220, overflowY:"auto" }}>
                    {gerichtTreffer.map((g, i) => (
                      <div key={g.adressnr} onClick={() => { setGericht(g); setGTreffer([]); setGSuche(""); }}
                        style={{ padding:"9px 14px", cursor:"pointer",
                          borderBottom: i < gerichtTreffer.length-1 ? `1px solid ${T.borderSoft}` : "none",
                          background:T.white, transition:"background 0.1s" }}
                        onMouseEnter={e => e.currentTarget.style.background = T.surface}
                        onMouseLeave={e => e.currentTarget.style.background = T.white}>
                        <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.925rem",
                          fontWeight:600, color:T.navy }}>{g.name}</div>
                        <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.825rem",
                          color:T.textMuted }}>
                          {[g.strasse, g.plz, g.ort].filter(Boolean).join(", ")}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {gerichtSuche.length >= 2 && !gerichtLaedt && gerichtTreffer.length === 0 && (
                  <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                    color:T.textFaint, padding:"6px 0" }}>
                    Keine Gerichte gefunden.
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>

        {/* 2) Parteien – Rubrum */}
        <div id="karte-parteien" />
        <Card>
          <KlageCardHead nr={2} title="Parteien (Rubrum)" />
          <div style={{ padding:"1.25rem 1.75rem", fontFamily:"'Figtree',sans-serif" }}>
            {beklagte.length === 0 && (
              <div style={{ color:T.amber, fontSize:"0.875rem" }}>
                ⚠ Keine Beteiligten erfasst. Bitte zuerst Beteiligte anlegen.
              </div>
            )}

            {/* ── Kläger ── */}
            {(() => {
              const klaeger = beklagte.filter(b => b.rolle_klage === "klaeger");
              const mehrere = klaeger.length > 1;
              return klaeger.map((b, i) => {
                const name     = b.vorname ? `${b.vorname} ${b.name}`.trim() : b.name || b.firma || "Mandant";
                const anschr   = [b.anschrift, [b.plz, b.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
                const istFirma = !!(b.firma || b.versicherung || (!b.vorname && b.name));
                const anrede   = (b.anrede||"").toLowerCase();
                let rolleBez;
                if (mehrere) {
                  rolleBez = anrede === "frau" ? `Klägerin zu ${i+1})` : `Kläger zu ${i+1})`;
                } else {
                  rolleBez = anrede === "frau" ? "Klägerin" : "Kläger";
                }
                return (
                  <div key={b.id} style={{ marginBottom: i < klaeger.length-1 ? "0.75rem" : 0 }}>
                    {/* Name + Anschrift in einer Zeile */}
                    <div style={{ fontSize:"0.95rem", fontWeight:700, color:T.navy }}>
                      {name}{anschr ? `, ${anschr}` : ""}
                    </div>
                    {istFirma && (
                      <div style={{ display:"flex", alignItems:"center", gap:8, marginLeft:12, marginTop:2 }}>
                        <span style={{ fontSize:"0.84rem", color:T.textMuted }}>
                          {vertretungsHinweis(name)}
                        </span>
                        <button
                          onClick={() => lookupVertreter(b.id, name)}
                          disabled={vertreterLookup[b.id]?.laden}
                          title="Vertretung online nachschlagen"
                          style={{ background:"none", border:`1px solid ${T.border}`, borderRadius:5,
                            padding:"1px 7px", cursor:"pointer", fontSize:"0.78rem",
                            color:T.textMuted }}>
                          {vertreterLookup[b.id]?.laden ? "⟳" : "🔍 Lookup"}
                        </button>
                      </div>
                    )}
                    {/* Rollenbezeichnung rechtsbündig */}
                    <div style={{ textAlign:"right", fontSize:"0.875rem",
                      fontStyle:"italic", color:T.textMuted, marginTop:2 }}>
                      – {rolleBez} –
                    </div>
                  </div>
                );
              });
            })()}

            {/* Prozessbevollmächtigte */}
            {beklagte.some(b => b.rolle_klage === "klaeger") && (<>
              <div style={{ height:"0.6rem" }}/>
              <div style={{ fontSize:"0.875rem", color:T.text }}>
                Prozessbevollmächtigte: Koch, Schatz &amp; Kollegen, Tulpenhofstr. 1, 63067 Offenbach
              </div>
              <div style={{ height:"0.6rem" }}/>
            </>)}

            {/* ── gegen ── */}
            {beklagte.some(b => b.rolle_klage === "klaeger") && beklagte.some(b => b.rolle_klage !== "klaeger") && (
              <div style={{ textAlign:"center", padding:"0.6rem 0",
                fontSize:"0.9rem", letterSpacing:"0.15em", color:T.textFaint,
                borderTop:`1px solid ${T.borderSoft}`, borderBottom:`1px solid ${T.borderSoft}`,
                margin:"0.5rem 0", textTransform:"uppercase" }}>
                g e g e n
              </div>
            )}

            {/* ── Beklagte (mit Checkbox) ── */}
            {beklagte.filter(b => b.rolle_klage !== "klaeger").length > 0 && (
              <div style={{ fontSize:"0.8rem", color:T.textMuted, marginBottom:"0.5rem" }}>
                Checkbox = in Klage aufgenommen
              </div>
            )}
            {(() => {
              const bekl = beklagte.filter(b => b.rolle_klage !== "klaeger");
              const mehrere = bekl.length > 1;
              return bekl.map((b, i) => {
                const personName = (`${b.vorname||""} ${b.name||""}`).trim();
                // Personen haben Vorrang vor Firmen-/Versicherungsname (WDM-Enrichment darf nicht verstecken)
                const name    = personName || b.versicherung || b.firma || "Unbekannt";
                const anschr  = [b.anschrift, [b.plz, b.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
                // istFirma nur wenn KEIN Personenname vorhanden
                const istFirma = !personName && !!(b.versicherung || b.firma
                  || (!b.vorname && b.name && b.rolle !== "mandant"));
                // Versicherungsname als Extrainfo wenn Person bekannt
                const extras  = [
                  b.schaden_nr ? `Schaden-Nr. ${b.schaden_nr}` : null,
                  b.kfz_kennzeichen || null,
                  (personName && b.versicherung) ? `Vers.: ${b.versicherung}` : null,
                ].filter(Boolean);
                const nr      = mehrere ? ` zu ${i+1})` : "";
                // Vertreter-Suffix für Adresszeile
                const vName = b.vertreter_name || "";
                const vFunk = b.vertreter_funktion || vertretungsHinweis(name).replace("– vertreten durch ", "").replace(" –", "");
                const vertretungSuffix = vName
                  ? `, vertreten durch ${vFunk} ${vName}`
                  : "";
                const fehltVertreter = istFirma && b.checked && !vName;
                return (
                  <div key={b.id} style={{ display:"flex", gap:10, alignItems:"flex-start",
                    padding:"0.5rem 0",
                    borderBottom: i < bekl.length-1 ? `1px solid ${T.borderSoft}` : "none",
                    opacity: b.checked ? 1 : 0.45 }}>
                    <input type="checkbox" checked={!!b.checked} onChange={() => toggleBek(b.id)}
                      style={{ width:16, height:16, cursor:"pointer", flexShrink:0, marginTop:3 }}/>
                    <div style={{ flex:1 }}>
                      <div style={{ fontSize:"0.95rem", fontWeight:700, color: b.checked ? T.navy : T.textMuted }}>
                        {name}{anschr ? `, ${anschr}` : ""}{vertretungSuffix}
                      </div>
                      {istFirma && (
                        <div style={{ display:"flex", alignItems:"center", gap:8, marginLeft:0, marginTop:4 }}>
                          {fehltVertreter && (
                            <span style={{ fontSize:"0.8rem", color:T.red, fontWeight:600 }}>
                              ⚠ Vertreter fehlt – Klage nicht möglich
                            </span>
                          )}
                          {!fehltVertreter && vName && (
                            <span style={{ fontSize:"0.8rem", color:T.green }}>✓ Vertreter gesetzt</span>
                          )}
                          <button
                            onClick={() => lookupVertreter(b.id, name)}
                            disabled={vertreterLookup[b.id]?.laden}
                            title="Vertretung online nachschlagen"
                            style={{ background:"none", border:`1px solid ${T.border}`, borderRadius:5,
                              padding:"1px 7px", cursor:"pointer", fontSize:"0.78rem",
                              color: fehltVertreter ? T.red : T.textMuted, whiteSpace:"nowrap",
                              fontWeight: fehltVertreter ? 700 : 400 }}>
                            {vertreterLookup[b.id]?.laden ? "⟳" : "🔍 Lookup / Ändern"}
                          </button>
                        </div>
                      )}
                      {extras.length > 0 && (
                        <div style={{ fontSize:"0.82rem", color:T.textMuted, marginTop:2 }}>
                          {extras.join(" · ")}
                        </div>
                      )}
                      {!!personName && (
                        <label style={{ display:"flex", alignItems:"center", gap:6, marginTop:4,
                          fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem", cursor:"pointer",
                          color: T.textMuted }}>
                          <input type="checkbox"
                            checked={!!b.ist_halter}
                            onChange={() => toggleHalter(b.id, !b.ist_halter)}
                            style={{ accentColor: T.navy, cursor:"pointer" }} />
                          Ist Halter/Halterin
                        </label>
                      )}
                      {b.checked && (
                        <div style={{ textAlign:"right", fontSize:"0.875rem",
                          fontStyle:"italic", color:T.textMuted, marginTop:2 }}>
                          – Beklagte{nr} –
                        </div>
                      )}
                    </div>
                    {b.kuerzel && ["GHPV","GH","GHV","GBEV","HPV"].includes(b.kuerzel.toUpperCase()) && (
                      <span style={{ background:`${T.amber}18`, color:T.amber,
                        border:`1px solid ${T.amber}30`, borderRadius:6, padding:"2px 7px",
                        fontSize:"0.77rem", fontWeight:600, flexShrink:0 }}>GHPV</span>
                    )}
                  </div>
                );
              });
            })()}
          </div>
        </Card>

          </div>{/* end linke Spalte */}

          {/* ── Rechte Kachel: Klage starten ── */}
          <div style={{ width:210, flexShrink:0 }}>
            <Card style={{ background: T.navyLight || "#1a2744", border:"none" }}>
              <div style={{ padding:"1.25rem 1rem", display:"flex", flexDirection:"column",
                gap:10, alignItems:"stretch" }}>
                <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.76rem",
                  color:"rgba(255,255,255,0.45)", fontWeight:700, letterSpacing:"0.12em",
                  textTransform:"uppercase", textAlign:"center" }}>Klage starten</div>
                {klagebetrag > 0 && (
                  <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"1.25rem",
                    fontWeight:700, color:"white", textAlign:"center" }}>
                    {fmtEuro(klagebetrag + (mitSG ? sgMind : 0))}
                  </div>
                )}
                {gericht
                  ? <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.77rem",
                      color:"rgba(255,255,255,0.6)", textAlign:"center" }}>
                      📍 {gericht.name}
                    </div>
                  : <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.77rem",
                      color:"rgba(255,180,0,0.9)", textAlign:"center" }}>
                      ⚠ Kein Gericht gewählt
                    </div>
                }
                <div style={{ height:4 }}/>
                <Btn onClick={oeffneWizard} disabled={!daten}
                  style={{ background:"rgba(255,255,255,0.1)", color:"white",
                    border:"2px solid rgba(255,255,255,0.3)", padding:"13px 8px",
                    fontSize:"0.9rem", fontWeight:700, borderRadius:9, width:"100%",
                    textAlign:"center" }}>
                  🧙 Klage-Wizard
                </Btn>
              </div>
            </Card>
          </div>{/* end rechte Kachel */}

        </div>{/* end Zweispalten-Zeile */}

        {/* 3) Schadenpositionen + Regulierungsstand (zusammengeführt) */}
        <Card>
          <KlageCardHead nr={3} title={`Schadenpositionen & Regulierung – Klagebetrag: ${fmtEuro(klagebetrag)}`} />
          <div style={{ padding:"0.75rem 1.25rem 0" }}>
            {posOffen.length === 0 && (
              <div style={{ color:T.amber, fontFamily:"'Figtree',sans-serif",
                fontSize:"0.875rem", marginBottom:"0.75rem" }}>
                ⚠ Keine Schadenpositionen erfasst. Bitte zuerst Schaden erfassen.
              </div>
            )}
            {posOffen.length > 0 && (
              <table style={{ width:"100%", borderCollapse:"collapse", fontSize:"0.875rem" }}>
                <thead>
                  <tr style={{ background:T.surface }}>
                    {["☑","Position","Gefordert","Reguliert","Klageanteil"].map((h, i) => (
                      <th key={h} style={{
                        padding:"5px 8px", fontFamily:"'Figtree',sans-serif",
                        fontSize:"0.72rem", fontWeight:700, color:T.textMuted,
                        textTransform:"uppercase", letterSpacing:"0.06em",
                        textAlign: i === 0 ? "center" : i >= 2 ? "right" : "left",
                        width: i === 0 ? 32 : "auto",
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {posOffen.map(p => {
                    const vollReg = p.reguliertPos > 0 && p.offenBetrag <= 0.005;
                    return (
                      <tr key={p.key}
                        style={{ borderBottom:`1px solid ${T.borderSoft}`,
                          opacity: p.checked ? 1 : 0.55, cursor:"pointer" }}
                        onClick={() => togglePos(p.key)}>
                        <td style={{ padding:"8px", textAlign:"center" }}>
                          <input type="checkbox" checked={!!p.checked}
                            onChange={() => togglePos(p.key)}
                            onClick={e => e.stopPropagation()}
                            style={{ width:15, height:15, cursor:"pointer" }}/>
                        </td>
                        <td style={{ padding:"8px", fontFamily:"'Figtree',sans-serif",
                          fontSize:"0.9rem", color: p.checked ? T.text : T.textMuted }}>
                          {p.label}
                          {vollReg && (
                            <span style={{ marginLeft:8, fontSize:"0.72rem",
                              color:T.green, fontWeight:600 }}>✓ vollst. reguliert</span>
                          )}
                        </td>
                        <td style={{ padding:"8px", textAlign:"right",
                          fontFamily:"ui-monospace,monospace", fontSize:"0.875rem",
                          color:T.textMuted }}>{fmtEuro(p.betrag)}</td>
                        <td style={{ padding:"8px", textAlign:"right",
                          fontFamily:"ui-monospace,monospace", fontSize:"0.875rem",
                          color: p.reguliertPos > 0 ? T.green : T.textFaint }}>
                          {p.reguliertPos > 0 ? fmtEuro(p.reguliertPos) : "—"}
                        </td>
                        <td style={{ padding:"8px", textAlign:"right",
                          fontFamily:"ui-monospace,monospace", fontSize:"0.9rem",
                          fontWeight: p.checked ? 700 : 400,
                          color: p.checked ? T.navy : T.textMuted }}>
                          {fmtEuro(p.offenBetrag)}
                        </td>
                      </tr>
                    );
                  })}
                  <tr style={{ borderTop:`2px solid ${T.border}`, background:T.surface }}>
                    <td colSpan={4} style={{ padding:"8px 8px 8px 0",
                      fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                      fontWeight:700, color:T.navy, textAlign:"right" }}>
                      Klagebetrag (angehakte Positionen)
                    </td>
                    <td style={{ padding:"8px", textAlign:"right",
                      fontFamily:"ui-monospace,monospace", fontSize:"0.975rem",
                      fontWeight:700, color:T.navy }}>
                      {fmtEuro(klagebetrag)}
                    </td>
                  </tr>
                </tbody>
              </table>
            )}
          </div>

          {/* Trennlinie + Regulierungsübersicht */}
          {(() => {
            // Gruppieren nach Datum + Versicherung, Nulleinträge ignorieren
            const gruppenMap = new Map();
            for (const ab of (daten?.abrechnungen || [])) {
              const betrag = parseFloat(ab.gesamt_reguliert) || 0;
              if (betrag <= 0.005) continue;
              const key = `${ab.datum || ""}|${(ab.versicherung || "").trim()}`;
              if (gruppenMap.has(key)) {
                gruppenMap.get(key).summe += betrag;
              } else {
                gruppenMap.set(key, { datum: ab.datum, versicherung: ab.versicherung || "", summe: betrag });
              }
            }
            const gruppen = Array.from(gruppenMap.values())
              .sort((a, b) => (b.datum || "").localeCompare(a.datum || ""));
            if (gruppen.length === 0) return null;
            return (
              <div style={{ marginTop:"1rem", borderTop:`2px solid ${T.borderSoft}` }}>
                <div style={{ padding:"0.5rem 1.25rem 0.25rem",
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.75rem",
                  fontWeight:600, color:T.textMuted, textTransform:"uppercase",
                  letterSpacing:"0.07em" }}>
                  Regulierungsstand – {gruppen.length} Zahlung{gruppen.length !== 1 ? "en" : ""}
                </div>
                <div style={{ padding:"0.25rem 1.25rem 0.5rem",
                  borderBottom:`1px solid ${T.borderSoft}` }}>
                  {gruppen.map((g, i) => (
                    <div key={i} style={{ display:"flex", justifyContent:"space-between",
                      alignItems:"center", padding:"3px 0",
                      fontFamily:"'Figtree',sans-serif", fontSize:"0.86rem" }}>
                      <span style={{ color:T.textMid }}>
                        {g.datum ? (() => {
                          try { const [y,m,d] = g.datum.split("-"); return `${d}.${m}.${y}`; }
                          catch { return g.datum; }
                        })() : "—"}
                        {g.versicherung && <span style={{ color:T.textFaint, marginLeft:8 }}>{g.versicherung}</span>}
                      </span>
                      <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.86rem",
                        color:T.green }}>
                        {fmtEuro(g.summe)}
                      </span>
                    </div>
                  ))}
                </div>
                {/* Positionsaufschlüsselung */}
                <RegulierungsTabelle
                  schaden={daten?.schaden || {}}
                  abrechnungen={daten?.abrechnungen || []}
                  showCheckboxes={false}
                  showKlageBadge={false}
                />
              </div>
            );
          })()}
        </Card>

        {/* 3c) Personenschaden */}
        <Card>
          <KlageCardHead nr={4} title="Personenschaden" />
          <div style={{ padding:"0.75rem 1.25rem", display:"flex",
            flexDirection:"column", gap:"0.75rem" }}>
            <div style={{ display:"flex", gap:16 }}>
              <label style={{ display:"flex", alignItems:"center", gap:8, cursor:"pointer",
                fontFamily:"'Figtree',sans-serif", fontSize:"0.935rem" }}>
                <input type="radio" checked={!mitSG} onChange={() => setMitSG(false)}/> Kein Schmerzensgeld
              </label>
              <label style={{ display:"flex", alignItems:"center", gap:8, cursor:"pointer",
                fontFamily:"'Figtree',sans-serif", fontSize:"0.935rem" }}>
                <input type="radio" checked={mitSG} onChange={() => setMitSG(true)}/> Schmerzensgeld
              </label>
            </div>
            {mitSG && (
              <div style={{ display:"flex", alignItems:"center", gap:12 }}>
                <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                  color:T.textMuted, whiteSpace:"nowrap" }}>Mindestbetrag:</label>
                <input type="number" min="0" step="100" value={sgMind}
                  onChange={e => setSGMind(parseFloat(e.target.value)||0)}
                  style={{ ...inS, width:120 }}/>
                <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                  color:T.textMuted }}>€</span>
              </div>
            )}
            <div style={{ marginTop: 4 }}>
              <button
                onClick={() => setShowSgAssistent(true)}
                style={{
                  padding: "7px 14px", background: T.navy, color: "#fff",
                  border: "none", borderRadius: 7, cursor: "pointer",
                  fontFamily: "'Figtree',sans-serif", fontSize: "0.85rem", fontWeight: 600,
                }}>
                Schmerzensgeld-Assistent
              </button>
            </div>
          </div>
        </Card>

        {/* 4) Zinsen + Verzug */}
        <Card>
          <KlageCardHead nr={5} title="Zinsen und Verzug" />
          <div style={{ padding:"0.75rem 1.25rem", display:"flex", flexDirection:"column", gap:"1rem" }}>

            {/* Zinsart-Auswahl */}
            <div style={{ display:"flex", gap:16 }}>
              <label style={{ display:"flex", alignItems:"center", gap:8, cursor:"pointer",
                fontFamily:"'Figtree',sans-serif", fontSize:"0.935rem" }}>
                <input type="radio" checked={zinsenAb==="verzug"} onChange={() => setZinsenAb("verzug")}/>
                Ab Verzugseintritt
              </label>
              <label style={{ display:"flex", alignItems:"center", gap:8, cursor:"pointer",
                fontFamily:"'Figtree',sans-serif", fontSize:"0.935rem" }}>
                <input type="radio" checked={zinsenAb==="rechtshaengigkeit"} onChange={() => setZinsenAb("rechtshaengigkeit")}/>
                Ab Rechtshängigkeit
              </label>
            </div>

            {zinsenAb === "verzug" && (<>

              {/* Dokument-Karten */}
              {verzugDokListe.length > 0 && (
                <div>
                  <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem", fontWeight:600,
                    color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:6 }}>
                    Verzugsbegründendes Schreiben
                  </div>
                  <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
                    {verzugDokListe.map(dok => {
                      const sel = verzugDokId === dok.id;
                      const klasseLabel = { mahnschreiben:"Mahnschreiben", verzugsschreiben:"Verzugsschreiben", forderungsschreiben:"Forderungsschreiben" }[dok.dokumentenklasse] || dok.dokumentenklasse;
                      return (
                        <button key={dok.id} onClick={() => setVerzugDokId(dok.id)}
                          style={{ display:"flex", alignItems:"center", gap:10, padding:"9px 12px",
                            background: sel ? T.accentPale : T.white,
                            border: `1.5px solid ${sel ? T.accent : T.border}`,
                            borderRadius:7, fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                            color:T.text, cursor:"pointer", textAlign:"left", width:"100%",
                            transition:"border-color 0.15s, background 0.15s" }}
                          onMouseEnter={e => { if (!sel) { e.currentTarget.style.borderColor=T.accent; e.currentTarget.style.background=T.accentPale; }}}
                          onMouseLeave={e => { if (!sel) { e.currentTarget.style.borderColor=T.border; e.currentTarget.style.background=T.white; }}}>
                          <span style={{ color:T.red, fontSize:"1rem", flexShrink:0 }}>📄</span>
                          <div style={{ flex:1, minWidth:0 }}>
                            <div style={{ overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", fontWeight:600 }}>{dok.dateiname}</div>
                            <div style={{ fontSize:"0.75rem", color:T.textFaint }}>{klasseLabel}{dok.hochgeladen_am ? " · " + String(dok.hochgeladen_am).slice(0,10) : ""}</div>
                          </div>
                          {sel && <span style={{ fontSize:"0.78rem", fontWeight:600, color:T.accent, flexShrink:0 }}>✓ Ausgewählt</span>}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Zwei Datumsfelder */}
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
                {[
                  { label:"Datum des Schreibens", val:wizardVerzugDokDatum, set: v => setWizardVerzugDokDatum(v) },
                  { label:"Datum Verzugseintritt", val:wizardVerzugDatum,    set: v => setWizardVerzugDatum(v) },
                ].map(({ label, val, set }) => {
                  const iso = (() => {
                    if (!val) return "";
                    const m = val.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
                    return m ? `${m[3]}-${m[2].padStart(2,"0")}-${m[1].padStart(2,"0")}` : val;
                  })();
                  return (
                    <div key={label}>
                      <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem", fontWeight:600,
                        color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:4 }}>
                        {label}
                      </div>
                      <input type="date" value={iso}
                        onChange={e => {
                          const v = e.target.value;
                          if (!v) { set(""); return; }
                          const [y,mo,d] = v.split("-");
                          set(`${d}.${mo}.${y}`);
                        }}
                        style={{ ...inS, width:"100%" }}/>
                    </div>
                  );
                })}
              </div>

            </>)}
          </div>
        </Card>

        {/* 5) Vorgerichtliche Kosten */}
        <Card>
          <KlageCardHead nr={6} title="Rechtsanwaltsgebühren" />
          <div style={{ padding:"0.75rem 1.25rem" }}>
            {/* Streitwert-Split */}
            {(() => {
              // Außergerichtl. SW = Summe aller Schadenpositionen (brutto, aus Klage-Positionsdefinitionen)
              const gesamtAusserg = positionen.reduce((s, p) => s + (parseFloat(p.betrag)||0), 0);
              // Gerichtl. SW = nur angehakte Klageforderungen
              const swGericht = klagebetrag;
              return gesamtAusserg > 0.01 && (
                <div style={{ display:"flex", gap:12, marginBottom:"0.75rem" }}>
                  {[
                    { label:"Außergerichtl. Streitwert", val: gesamtAusserg,
                      hint:"Basis für vorgerichtliche RVG-Gebühr" },
                    { label:"Gerichtl. Streitwert", val: swGericht,
                      hint:"Gegenstandswert der Klage (Gebühren folgen im Kostenfestsetzungsverfahren)" },
                  ].map(sw => (
                    <div key={sw.label} style={{ flex:1, background:T.surface,
                      borderRadius:8, padding:"0.6rem 0.9rem",
                      border:`1px solid ${T.border}` }}>
                      <div style={{ fontFamily:"'Figtree',sans-serif",
                        fontSize:"0.75rem", fontWeight:600, color:T.textMuted,
                        textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:3 }}>
                        {sw.label}
                      </div>
                      <div style={{ fontFamily:"ui-monospace,monospace",
                        fontSize:"1.1rem", fontWeight:700, color:T.navy }}>
                        {fmtEuro(sw.val)}
                      </div>
                      <div style={{ fontFamily:"'Figtree',sans-serif",
                        fontSize:"0.74rem", color:T.textFaint, marginTop:2 }}>
                        {sw.hint}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}
            {rvgData && (
              <div style={{ background:T.surface, borderRadius:8, padding:"0.75rem 1rem",
                marginBottom:"0.75rem", fontFamily:"ui-monospace,monospace", fontSize:"0.875rem" }}>
                {[
                  { label:"Gegenstandswert",                                          val: swAussergEffektiv,            bold: false },
                  { label:`Geschäftsgebühr §§ 13, 14 Nr. 2300 VV RVG (${rvgData.faktor})`, val: rvgData.gebuehr_netto,   bold: false },
                  { label:"Post u. Telekommunikation Nr. 7002 VV RVG",               val: rvgData.post_pauschale,       bold: false },
                  { label:"Zwischensumme netto",                                      val: rvgData.zwischen_netto,       bold: false, faint: true },
                  { label:"19 % Umsatzsteuer",                                       val: rvgData.ust,                  bold: false },
                  { label:"Gesamtbetrag",                                             val: rvgData.gesamt,               bold: true  },
                ].map((z, i) => (
                  <div key={i} style={{ display:"flex", justifyContent:"space-between",
                    marginBottom: i < 6 ? 3 : 0,
                    paddingTop:   i === 6 ? 6 : 0,
                    borderTop:    i === 6 ? `1px solid ${T.border}` : "none",
                    fontWeight:   z.bold ? 700 : 400 }}>
                    <span style={{ color: z.faint ? T.textFaint : T.textMuted }}>{z.label}</span>
                    <span style={{ color: z.bold ? T.navy : T.text }}>{fmtEuro(z.val)}</span>
                  </div>
                ))}
                <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.7rem",
                  color: T.textFaint, marginTop: 6, textAlign: "right" }}>
                  § 13 RVG Anlage 2 – {rvgData.rvg_version === "2025"
                    ? "2. KostRMoG (ab 01.06.2025)"
                    : "KostRÄG 2021 (bis 31.05.2025)"}
                </div>
              </div>
            )}
          </div>
        </Card>

        {/* Zusammenfassung + Generieren */}
        <Card style={{ background: T.navyLight || "#1a2744", border:"none" }}>
          <div style={{ padding:"1.25rem 1.4rem", display:"flex",
            alignItems:"center", justifyContent:"space-between", gap:16 }}>
            <div>
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                color:"rgba(255,255,255,0.7)", marginBottom:4 }}>Gegenstandswert (Sachschaden)</div>
              <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"1.5rem",
                fontWeight:700, color:"white" }}>
                {fmtEuro(klagebetrag + (mitSG ? sgMind : 0))}
              </div>
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.815rem",
                color:"rgba(255,255,255,0.5)", marginTop:2 }}>
                {mitSG ? `Sachschaden ${fmtEuro(klagebetrag)} + Schmerzensgeld mind. ${fmtEuro(sgMind)}` : ""}
                {" · "}Nr. 2300 außergerichtl. {fmtEuro(rvgGesamt)} als Nebenforderung
              </div>
              {gericht
                ? <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.815rem",
                    color:"rgba(255,255,255,0.6)", marginTop:4 }}>
                    📍 {gericht.name}
                  </div>
                : <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.815rem",
                    color:"rgba(255,180,0,0.9)", marginTop:4 }}>
                    ⚠ Kein Gericht gewählt – bitte oben auswählen
                  </div>
              }
            </div>
            <Btn onClick={oeffneWizard}
              disabled={!daten}
              style={{ background:"transparent", color:T.navy,
                border:`2px solid ${T.navy}`, padding:"12px 20px",
                fontSize:"0.95rem", fontWeight:600, borderRadius:9 }}>
              🧙 Wizard
            </Btn>
          </div>
        </Card>

      </div>
    </div>
  );
}


export default KlageSection;
