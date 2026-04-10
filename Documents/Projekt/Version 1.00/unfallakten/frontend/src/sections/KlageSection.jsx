import React, { useState, useEffect } from "react";
import KlageWizard from "./KlageWizard.jsx";
import { RegulierungsTabelle, TodoSection } from './UebersichtSection.jsx';
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { fmtEuro } from "../config/utils.js";
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
                      console.warn("Vertreter speichern:", e);
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
  const [zinsenAb, setZinsenAb] = useState("verzug");
  const [verzug, setVerzug]     = useState("");
  const [rvgOverride, setRvgOv] = useState("");
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
  const [wizardVerzugText, setWizardVerzugText]   = useState("");
  const [wizardVerzugDatum, setWizardVerzugDatum] = useState("");
  const [kiLaedt, setKiLaedt]                     = useState(false);
  const [lgGrenzwert, setLgGrenzwert]             = useState(10000);
  // PRD-26: neue Wizard-States
  const [wizardHq, setWizardHq]                     = useState(100);
  const [wizardHb, setWizardHb]                     = useState("");
  const [wizardMaxStep, setWizardMaxStep]           = useState(1);
  const [wizardGerichtBest, setWizardGerichtBest]   = useState(false);
  const [wizardMitFestSg, setWizardMitFestSg]       = useState(false);
  const [wizardMitFestSach, setWizardMitFestSach]   = useState(false);
  const [wizardAntraegeText, setWizardAntraegeText] = useState("");
  const [wizardRvgAussergData, setWizardRvgAussergData] = useState(null);
  const [wizardRvgAussergOv, setWizardRvgAussergOv]     = useState("");
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
        setVerzug(res.verzug_datum || "");
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
            // Faktor aus Gebühren-Tab vorbelegen
            if (gb.gespeichert.faktor_final) {
              setWizardRvgAussergOv(String(gb.gespeichert.faktor_final));
            }
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


  // RVG neu berechnen wenn Positionen sich ändern
  const klagebetrag = positionen.filter(p => p.checked).reduce((s, p) => s + (p.betrag||0), 0);
  const swAusserg   = positionen.reduce((s, p) => s + (p.betrag || 0), 0); // außergerichtl. Streitwert
  useEffect(() => {
    if (!daten) return;
    (async () => {
      try {
        const res = await apiKlage.rvgBerechnen(akteId, { streitwert: klagebetrag });
        setRvgData(res.rvg);
      } catch {}
    })();
  }, [klagebetrag]);

  // Step 9: RVG auf außergerichtl. Streitwert berechnen wenn Step 9 erreicht
  useEffect(() => {
    if (!wizardOffen || wizardStep !== 9 || wizardRvgAussergData) return;
    (async () => {
      try {
        const res = await apiKlage.rvgBerechnen(akteId, { streitwert: swAusserg });
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

  const generieren = async () => {
    setGenLaedt(true); setFehler("");
    try {
      await apiKlage.generieren(akteId, {
        gericht:               gericht,
        // Kläger immer mitsenden (kein checked-Filter), Beklagte nur wenn checked
        beklagte:              beklagte.filter(b => b.rolle_klage === "klaeger" || b.checked),
        positionen:            positionen,
        mit_schmerzensgeld:    mitSG,
        schmerzensgeld_mindest: sgMind,
        verzugsdatum:          zinsenAb === "verzug" ? verzug : null,
        zinsen_ab:             zinsenAb,
        rvg:                   rvgData,
        rvg_override:          rvgOverride ? parseFloat(rvgOverride) : null,
      });
      setToast("Klageschrift heruntergeladen.");
      // B-07: Status → klage persistieren
      try {
        await apiAkten.aktualisieren(akteId, { status: "klage" });
        if (dispatch) dispatch({ type: "SET_STATUS", akteId, status: "klage" });
      } catch { /* Status-Update nicht kritisch */ }
    } catch (e) {
      setFehler(e?.message || "Fehler bei der Generierung.");
    } finally { setGenLaedt(false); }
  };

  // ── Wizard öffnen – State aus DB-Werten initialisieren ────────────────
  const oeffneWizard = () => {
    const al = daten?.aktivlegitimation || {};
    setAktLegTyp(al.typ || "eigentum");
    setAktLegFreigabe(al.freigabe_status || "freigabe");
    setAktLegDatum(al.datum_freigabe || "");
    setWizardPos([...positionen]);
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
    setWizardHb(hb);
    const kl_dat      = weiblich ? "der Klägerin" : "des Klägers";
    const beklagteGef = beklagte.filter(b => b.rolle_klage !== "klaeger" && b.checked);
    const nrSuffix    = beklagteGef.length > 1 ? " (zu 1)" : "";
    const bek1        = beklagteGef[0];
    const bek1Maenl   = bek1 && !bek1.versicherung && !bek1.firma
                        && (bek1.anrede || "").toLowerCase() === "herr";
    const bek_gen_art = bek1Maenl ? "des" : "der";      // Genitiv: des/der Beklagten
    const bek_dat_pp  = bek1Maenl ? "bei dem" : "bei der"; // Dativ: bei dem/bei der Beklagten
    const rw_lines = hq >= 100
      ? [
          `Die alleinige Haftung ${bek_gen_art} Beklagten${nrSuffix} steht außer Frage.` +
          ` Der Unfall wurde allein schuldhaft von dem ${bek_dat_pp} Beklagten${nrSuffix} versicherten Fahrzeug verursacht.`,
          ...(gesReg > 0
            ? [`Ein wesentlicher Teil des Schadens wurde bereits bezahlt. Offen ist, ob der Schaden in voller` +
               ` Höhe beglichen wurde. Die Differenz zwischen dem geforderten und regulierten Schaden ist` +
               ` Gegenstand des Klageantrags zu 1.`]
            : [`Die Beklagte hat bislang keine Regulierung vorgenommen. ` +
               `Da trotz mehrfacher Fristsetzung keine Zahlung erfolgte, war die Klage notwendig.`]),
        ]
      : [
          `Der bei der Beklagten versicherte Unfallgegner verursachte den Unfall durch ` +
          `${hb || "sein schuldhaftes Verhalten"}. Die Haftungsquote beträgt ${Math.round(hq)} %.`,
          gesReg > 0
            ? `Die Beklagte hat eine Teilregulierung in Höhe von ` +
              `${gesReg.toLocaleString("de-DE",{minimumFractionDigits:2,maximumFractionDigits:2})} € vorgenommen. ` +
              `Die verbleibenden Kürzungen sind nicht gerechtfertigt, sodass die Klage in Höhe des offenen Restbetrages erhoben wird.`
            : `Die Beklagte hat bislang keine Regulierung vorgenommen. ` +
              `Da trotz mehrfacher Fristsetzung keine Zahlung erfolgte, war die Klage notwendig.`,
          `Die Mithaftungsquote ${kl_dat} beträgt ${Math.round(100 - hq)} %. ` +
          `Die Klageforderung wurde entsprechend gekürzt.`,
        ];
    setWizardRwText(rw_lines.join("\n\n"));

    // ── Verzug: Datum aus WDM (varVERZUGAB via verzug_datum), Fallback Rechtshängigkeit ──
    const verzugDatum = verzug || "";
    setWizardVerzugDatum(verzugDatum);
    const vdat = verzugDatum ? `spätestens am ${verzugDatum}` : "mit Rechtshängigkeit";
    setWizardVerzugText(`Verzug ist ${vdat} eingetreten.`);

    // PRD-26: neue States initialisieren
    setWizardMaxStep(1);
    setWizardGerichtBest(gericht?.quelle === "akte"); // nur vorbestätigt wenn aus Akte gespeichert
    setWizardMitFestSg(mitSG);
    setWizardMitFestSach(false);
    setWizardAntraegeText("");
    setWizardRvgAussergData(null);
    setWizardRvgAussergOv("");
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
      };
      await apiKlage.generieren(akteId, {
        gericht,
        beklagte:               beklagte.filter(b => b.rolle_klage === "klaeger" || b.checked),
        positionen:             wizardPos,
        mit_schmerzensgeld:     wizardMitSG,
        schmerzensgeld_mindest: wizardMitSG ? wizardSGMind : 0,
        verzugsdatum:           zinsenAb === "verzug" ? verzug : null,
        zinsen_ab:              zinsenAb,
        rvg:                    rvgData,
        rvg_override:           rvgOverride ? parseFloat(rvgOverride) : null,
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

  const rvgGesamt = rvgOverride ? parseFloat(rvgOverride) : (rvgData?.gesamt || 0);

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
          fahrGegnerName={daten?.unfalldetails?.fahrer_gegner || ""}
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
          wizardHb={wizardHb}           onWizardHb={setWizardHb}
          wizardRwText={wizardRwText}   onWizardRwText={setWizardRwText}
          kuerzungsarten={daten?.kuerzungsarten || []}
          onKiHaftung={handleKiHaftung} kiLaedt={kiLaedt}
          // Step 8: Verzug
          wizardVerzugText={wizardVerzugText}   onWizardVerzugText={setWizardVerzugText}
          wizardVerzugDatum={wizardVerzugDatum} onWizardVerzugDatum={setWizardVerzugDatum}
          // Step 9: Außergerichtl. Gebühren
          swAusserg={swAusserg}
          wizardRvgAussergData={wizardRvgAussergData} onRvgAussergData={setWizardRvgAussergData}
          wizardRvgAussergOv={wizardRvgAussergOv}     onRvgAussergOv={setWizardRvgAussergOv}
          wizardGebuehrenText={wizardGebuehrenText}   onGebuehrenText={setWizardGebuehrenText}
          gespeichertGb={gespeichertGb}               onGespeichertGb={setGespeichertGb}
          wizardAkteId={akteId}
          // Shared
          beklagte={beklagte}
          rvgData={rvgData}
          rvgOverride={rvgOverride}
          zinsenAb={zinsenAb}
          verzug={verzug}
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
                const name    = b.versicherung || b.firma || (`${b.vorname||""} ${b.name||""}`).trim() || "Unbekannt";
                const anschr  = [b.anschrift, [b.plz, b.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
                // istFirma: explizites versicherung- oder firma-Feld,
                // ODER kein Vorname (= kein Mensch), aber Name vorhanden
                const istFirma = !!(b.versicherung || b.firma
                  || (!b.vorname && b.name && b.rolle !== "mandant"));
                const extras  = [b.schaden_nr ? `Schaden-Nr. ${b.schaden_nr}` : null, b.kfz_kennzeichen||null].filter(Boolean);
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
                      {!b.versicherung && !b.firma && (
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
                    {b.vorschlag_beklagter && (
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
                <Btn onClick={generieren}
                  title="Veraltet – bitte Wizard verwenden"
                  disabled={generiert_laedt || !gericht ||
                    positionen.filter(p => p.checked).length === 0 ||
                    (() => {
                      const ohne = beklagte.filter(b =>
                        b.checked && b.rolle_klage !== "klaeger" &&
                        (b.versicherung || b.firma) && !b.vertreter_name);
                      return ohne.length > 0;
                    })()}
                  style={{ background:"#9ca3af", color:"white", padding:"13px 8px",
                    fontSize:"0.9rem", fontWeight:700, borderRadius:9, width:"100%",
                    textAlign:"center", opacity:0.85 }}>
                  {generiert_laedt
                    ? <><div style={{ width:12, height:12,
                        border:"2px solid rgba(255,255,255,0.3)",
                        borderTopColor:"white", borderRadius:"50%",
                        animation:"spin 0.7s linear infinite",
                        display:"inline-block", marginRight:6 }}/>Wird erstellt …</>
                    : "⚖ Klageschrift (veraltet)"}
                </Btn>
              </div>
            </Card>
          </div>{/* end rechte Kachel */}

        </div>{/* end Zweispalten-Zeile */}

        {/* 3) Schadenpositionen + Regulierungsstand (zusammengeführt) */}
        <Card>
          <KlageCardHead nr={3} title={`Schadenpositionen & Regulierung – Klagebetrag: ${fmtEuro(klagebetrag)}`} />
          <div style={{ padding:"0.75rem 1.25rem 0" }}>
            {/* Checkbox-Liste aus positionen-State (Quelle der Wahrheit für Klagebetrag) */}
            {positionen.length === 0 && (
              <div style={{ color:T.amber, fontFamily:"'Figtree',sans-serif",
                fontSize:"0.875rem", marginBottom:"0.75rem" }}>
                ⚠ Keine Schadenpositionen erfasst. Bitte zuerst Schaden erfassen.
              </div>
            )}
            {positionen.map(p => (
              <div key={p.key} style={{ display:"flex", alignItems:"center", gap:12,
                padding:"7px 0", borderBottom:`1px solid ${T.borderSoft}` }}>
                <input type="checkbox" checked={!!p.checked} onChange={() => togglePos(p.key)}
                  style={{ width:16, height:16, cursor:"pointer", flexShrink:0 }}/>
                <div style={{ flex:1, fontFamily:"'Figtree',sans-serif",
                  fontSize:"0.925rem", color:p.checked ? T.text : T.textMuted }}>{p.label}</div>
                <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.925rem",
                  fontWeight:600, color:T.navy, flexShrink:0 }}>{fmtEuro(p.betrag)}</span>
              </div>
            ))}
          </div>

          {/* Trennlinie + Regulierungsübersicht */}
          {((daten?.abrechnungen?.length || 0) > 0) && (
            <div style={{ marginTop:"1rem", borderTop:`2px solid ${T.borderSoft}` }}>
              <div style={{ padding:"0.5rem 1.25rem 0.25rem",
                fontFamily:"'Figtree',sans-serif", fontSize:"0.75rem",
                fontWeight:600, color:T.textMuted, textTransform:"uppercase",
                letterSpacing:"0.07em" }}>
                Regulierungsstand – {(daten?.abrechnungen || []).length} Abrechnungsschreiben
              </div>
              {/* Abrechnungsschreiben-Liste */}
              <div style={{ padding:"0.25rem 1.25rem 0.5rem",
                borderBottom:`1px solid ${T.borderSoft}` }}>
                {(daten?.abrechnungen || []).map((ab, i) => (
                  <div key={ab.id||i} style={{ display:"flex", justifyContent:"space-between",
                    alignItems:"center", padding:"3px 0",
                    fontFamily:"'Figtree',sans-serif", fontSize:"0.86rem" }}>
                    <span style={{ color:T.textMid }}>
                      {ab.datum
                        ? (() => {
                            try {
                              const [y,m,d] = ab.datum.split("-");
                              return `${d}.${m}.${y}`;
                            } catch { return ab.datum; }
                          })()
                        : "—"}
                      {ab.versicherung && <span style={{ color:T.textFaint, marginLeft:8 }}>{ab.versicherung}</span>}
                      {ab.referenz_nr && <span style={{ color:T.textFaint, marginLeft:6, fontSize:"0.78rem" }}>Ref: {ab.referenz_nr}</span>}
                    </span>
                    <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.86rem",
                      color:T.green }}>
                      {fmtEuro(ab.gesamt_reguliert || 0)}
                    </span>
                  </div>
                ))}
              </div>
              {/* Regulierungstabelle read-only */}
              <RegulierungsTabelle
                schaden={daten?.schaden || {}}
                abrechnungen={daten?.abrechnungen || []}
                showCheckboxes={false}
                showKlageBadge={false}
              />
            </div>
          )}
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
          <div style={{ padding:"0.75rem 1.25rem", display:"flex",
            flexDirection:"column", gap:"0.75rem" }}>
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
            {zinsenAb === "verzug" && (
              <div style={{ display:"flex", alignItems:"center", gap:12 }}>
                <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                  color:T.textMuted, whiteSpace:"nowrap" }}>Verzugsdatum:</label>
                <input type="date" value={(() => {
                    // Anzeige als YYYY-MM-DD für input[type=date]
                    if (!verzug) return "";
                    // DD.MM.YYYY → YYYY-MM-DD
                    const m = verzug.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
                    if (m) return `${m[3]}-${m[2].padStart(2,"0")}-${m[1].padStart(2,"0")}`;
                    return verzug; // bereits ISO
                  })()}
                  onChange={e => {
                    const v = e.target.value;
                    if (!v) { setVerzug(""); return; }
                    // YYYY-MM-DD → DD.MM.YYYY
                    const [y,mo,d] = v.split("-");
                    setVerzug(`${d}.${mo}.${y}`);
                  }}
                  style={{ ...inS, width:160 }}/>
                {verzug && (
                  <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem",
                    color:T.green }}>✓ Aus letztem Mahnschreiben vorbelegt</span>
                )}
              </div>
            )}
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
                      hint:"Basis für gerichtliche RVG-Gebühr" },
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
                  { label:"Gegenstandswert",                                          val: klagebetrag,                  bold: false },
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
            <div style={{ display:"flex", alignItems:"center", gap:12 }}>
              <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                color:T.textMuted, whiteSpace:"nowrap" }}>Manueller Override:</label>
              <input type="number" min="0" step="0.01"
                value={rvgOverride}
                onChange={e => setRvgOv(e.target.value)}
                placeholder={rvgData ? rvgData.gesamt.toFixed(2) : ""}
                style={{ ...inS, width:140 }}/>
              <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                color:T.textMuted }}>€ (überschreibt Berechnung)</span>
            </div>
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
                {" · "}RVG {fmtEuro(rvgGesamt)} als Nebenforderung
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
                fontSize:"0.95rem", fontWeight:600, borderRadius:9,
                marginRight:10 }}>
              🧙 Wizard
            </Btn>
            <Btn onClick={generieren}
              title="Veraltet – bitte Wizard verwenden"
              disabled={generiert_laedt || !gericht || positionen.filter(p=>p.checked).length === 0 || (() => {
                // Pflicht: Firmen brauchen Vertreter
                const firmenOhneVertreter = beklagte.filter(b =>
                  b.checked &&
                  b.rolle_klage !== "klaeger" &&
                  (b.versicherung || b.firma) &&  // ist Firma
                  !b.vertreter_name               // kein Vertreter gesetzt
                );
                return firmenOhneVertreter.length > 0;
              })()}
              style={{ background:"#9ca3af", color:"white", padding:"12px 28px",
                fontSize:"1rem", fontWeight:700, borderRadius:9, opacity:0.85 }}>
              {generiert_laedt
                ? <><div style={{ width:14, height:14, border:"2px solid rgba(255,255,255,0.3)",
                    borderTopColor:"white", borderRadius:"50%",
                    animation:"spin 0.7s linear infinite", display:"inline-block",
                    marginRight:8 }}/>Wird erstellt …</>
                : "⚖ Klageschrift generieren (veraltet)"}
            </Btn>
          </div>
        </Card>

      </div>
    </div>
  );
}


export default KlageSection;
