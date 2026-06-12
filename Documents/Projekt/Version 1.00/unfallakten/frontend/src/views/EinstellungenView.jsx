import React, { useState, useEffect, useRef } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { KATEGORIEN } from "../config/constants.js";
import { Card, CardHead, Btn, Toast } from "../components/common.jsx";
import {
  emailImport as apiEmail,
  apiEinstellungen,
  apiSvPortal,
  apiSystem,
} from "../api.js";

function EinstellungenView({ initialTab = null, onTabMounted } = {}) {
  const [tab, setTab]           = useState(initialTab || "versicherer");
  useEffect(() => {
    if (initialTab) {
      setTab(initialTab);
      onTabMounted?.();
    }
  }, [initialTab]);
  const [vorlagen, setVorlagen] = useState([]);
  const [laedt, setLaedt]       = useState(true);
  const [toast, setToast]       = useState("");
  const [suche, setSuche]       = useState("");
  const [neuForm, setNeuForm]   = useState({
    name:"", domain:"", kategorie:"versicherung",
    versicherer_name:"", kuerzel:"", notizen:""
  });
  const [speichert, setSpeichert] = useState(false);

  // STA-Fristen + Texttemplates
  const [fristen,       setFristen]       = useState({ stufe1_tage: 14, stufe2_tage: 7, stufe3_tage: 5, stufe1_text: "", stufe2_text: "", stufe3_text: "" });
  const [fristenLaedt,  setFristenLaedt]  = useState(false);
  const [fristenSpeich, setFristenSpeich] = useState(false);

  // KI-Assistent
  const [ki,       setKi]       = useState({ modell: "claude-sonnet-4-6", system_prompt: "", user_prompt: "", modelle: [] });
  const [kiLaedt,  setKiLaedt]  = useState(false);
  const [kiSpeich, setKiSpeich] = useState(false);

  // Lokales LLM-Parsing
  const [llm,          setLlm]          = useState({ env_konfiguriert: false, aktiviert: false, verfuegbar: false, aktives_modell: "", modelle: [], base_url: "" });
  const [llmModellWechsel, setLlmModellWechsel] = useState(false);
  const [llmLaedt,     setLlmLaedt]     = useState(false);
  const [llmToggling,  setLlmToggling]  = useState(false);
  const [llmTestPrompt, setLlmTestPrompt] = useState("Erkläre in einem Satz was du bist.");
  const [llmTestLaedt, setLlmTestLaedt] = useState(false);
  const [llmTestAntwort, setLlmTestAntwort] = useState("");

  // LG-Zuständigkeitsgrenze
  const [lgGrenzwert,      setLgGrenzwert]      = useState(10000);
  const [lgGrenzwertLaedt, setLgGrenzwertLaedt] = useState(false);
  const [lgGrenzwertSpeich, setLgGrenzwertSpeich] = useState(false);

  // SV-Portal
  const [svListe,         setSvListe]         = useState([]);
  const [svLaedt,         setSvLaedt]         = useState(false);
  const [svAusgewaehlt,   setSvAusgewaehlt]   = useState(null); // adressnr
  const [svAkten,         setSvAkten]         = useState([]);
  const [svAktenLaedt,    setSvAktenLaedt]    = useState(false);
  const [svForm,          setSvForm]          = useState({ adressnr: "", vorschau: null, fehler: "" });
  const [svFormLaedt,     setSvFormLaedt]     = useState(false);
  const [svFormSpeichert, setSvFormSpeichert] = useState(false);
  const [svEinladung,     setSvEinladung]     = useState({}); // adressnr → bool
  const [svSuchVorschlaege, setSvSuchVorschlaege] = useState([]);
  const [svSuchOffen,     setSvSuchOffen]     = useState(false);
  const [svSuchLaedt,     setSvSuchLaedt]     = useState(false);
  const svSuchRef = useRef(null);

  // Klassifikations-Trainingsdaten
  const [training, setTraining] = useState(null);

  const [sysStatus,      setSysStatus]      = useState(null);
  const [sysLaedt,       setSysLaedt]       = useState(false);
  const [sysRetryLaedt,  setSysRetryLaedt]  = useState(false);

  const ladeVorlagen = async () => {
    setLaedt(true);
    try {
      const res = await apiEmail.vorlagen();
      setVorlagen(res?.vorlagen || []);
    } catch { setVorlagen([]); }
    finally { setLaedt(false); }
  };

  const ladeSvListe = async () => {
    setSvLaedt(true);
    try { setSvListe(await apiSvPortal.liste()); }
    catch { setSvListe([]); }
    finally { setSvLaedt(false); }
  };

  const ladeSvAkten = async (adressnr) => {
    setSvAktenLaedt(true);
    try { setSvAkten(await apiSvPortal.akten(adressnr)); }
    catch { setSvAkten([]); }
    finally { setSvAktenLaedt(false); }
  };

  useEffect(() => {
    function handleOutside(e) {
      if (svSuchRef.current && !svSuchRef.current.contains(e.target)) {
        setSvSuchOffen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  const svVorschauLadenNr = async (nr) => {
    if (!nr) return;
    setSvFormLaedt(true);
    try {
      const d = await apiSvPortal.vorschau(nr);
      setSvForm(p => ({ ...p, adressnr: String(nr), vorschau: d, fehler: "" }));
    } catch(e) {
      setSvForm(p => ({ ...p, vorschau: null, fehler: e?.message || "Adressnummer nicht gefunden." }));
    } finally { setSvFormLaedt(false); }
  };

  const svVorschauLaden = () => svVorschauLadenNr(parseInt(svForm.adressnr));

  const svAnlegen = async () => {
    const nr = parseInt(svForm.adressnr);
    if (!nr) return;
    setSvFormSpeichert(true);
    try {
      await apiSvPortal.anlegen(nr);
      setSvForm({ adressnr: "", vorschau: null, fehler: "" });
      await ladeSvListe();
      setToast("SV-Portal-Zugang angelegt.");
    } catch(e) {
      setSvForm(p => ({ ...p, fehler: e?.message || "Fehler beim Anlegen." }));
    } finally { setSvFormSpeichert(false); }
  };

  useEffect(() => {
    ladeVorlagen();
    setFristenLaedt(true);
    apiEinstellungen.staFristen()
      .then(d => setFristen(d))
      .catch(() => {})
      .finally(() => setFristenLaedt(false));
    apiEinstellungen.trainingStats()
      .then(d => setTraining(d))
      .catch(() => {});
    setKiLaedt(true);
    apiEinstellungen.kiEinstellungen()
      .then(d => setKi(d))
      .catch(() => {})
      .finally(() => setKiLaedt(false));
    setLgGrenzwertLaedt(true);
    apiEinstellungen.lgGrenzwert()
      .then(d => setLgGrenzwert(d.lg_grenzwert ?? 10000))
      .catch(() => {})
      .finally(() => setLgGrenzwertLaedt(false));
    setLlmLaedt(true);
    apiEinstellungen.llmStatus()
      .then(d => setLlm(d))
      .catch(() => {})
      .finally(() => setLlmLaedt(false));
  }, []);

  useEffect(() => {
    if (tab === "sv_portal") ladeSvListe();
    if (tab === "system_status") {
      setSysLaedt(true);
      apiSystem.getStatus()
        .then(setSysStatus)
        .catch(() => {})
        .finally(() => setSysLaedt(false));
    }
  }, [tab]);

  useEffect(() => {
    if (svAusgewaehlt !== null) ladeSvAkten(svAusgewaehlt);
  }, [svAusgewaehlt]);

  const speichereNeu = async () => {
    if (!neuForm.name || !neuForm.domain) return;
    setSpeichert(true);
    try {
      await apiEmail.vorlageSpeichern(neuForm);
      setNeuForm({ name:"", domain:"", kategorie:"versicherung",
                   versicherer_name:"", kuerzel:"", notizen:"" });
      await ladeVorlagen();
      setToast("Vorlage gespeichert.");
    } catch(e) {
      setToast(e?.message || "Fehler beim Speichern.");
    } finally { setSpeichert(false); }
  };

  const toggleAktiv = async (v) => {
    try {
      await apiEmail.vorlageAktualisieren(v.id, { aktiv: v.aktiv ? 0 : 1 });
      await ladeVorlagen();
    } catch { setToast("Fehler beim Aktualisieren."); }
  };

  const loeschen = async (id) => {
    if (!window.confirm("Vorlage wirklich löschen?")) return;
    try {
      await apiEmail.vorlageLoeschen(id);
      await ladeVorlagen();
      setToast("Vorlage gelöscht.");
    } catch { setToast("Fehler beim Löschen."); }
  };

  const katInfo = (id) => KATEGORIEN.find(k => k.id === id) || KATEGORIEN[3];

  // Gefiltert nach Tab + Suche
  const gefiltertVorlagen = vorlagen.filter(v => {
    const katFilter = tab === "versicherer" ? v.kategorie === "versicherung"
                    : tab === "gutachter"   ? v.kategorie === "gutachter"
                    : tab === "absender"    ? true : true;
    if (!katFilter) return false;
    if (!suche) return true;
    const s = suche.toLowerCase();
    return (v.name||"").toLowerCase().includes(s)
        || (v.domain||"").toLowerCase().includes(s)
        || (v.versicherer_name||"").toLowerCase().includes(s)
        || (v.kuerzel||"").toLowerCase().includes(s);
  });

  const inputStyle = {
    width:"100%", padding:"7px 10px", border:`1px solid ${T.border}`,
    borderRadius:7, fontFamily:"'Figtree',sans-serif",
    fontSize:"0.945rem", outline:"none", boxSizing:"border-box",
    background:T.white,
  };

  return (
    <div style={{ flex:1, overflowY:"auto", background:T.offWhite }}>
      {toast && <Toast msg={toast} onDone={() => setToast("")}/>}
      <div style={{ maxWidth:1000, margin:"0 auto", padding:"1.75rem" }}>

        <h1 style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"2rem",
          fontWeight:700, color:T.navy, margin:"0 0 1.5rem 0" }}>Einstellungen</h1>

        {/* Tab-Leiste */}
        <div style={{ display:"flex", gap:4, marginBottom:"1.5rem",
          borderBottom:`1px solid ${T.border}` }}>
          {[
            ["versicherer",   "🏦 Versicherer"],
            ["gutachter",     "🔍 Gutachter"],
            ["sv_portal",      "🔗 SV-Portal"],
            ["absender",      "📋 Alle Vorlagen"],
            ["imap",          "📧 IMAP"],
            ["fristen",       "⏱ Fristen"],
            ["ki",            "✦ KI-Assistent"],
            ["zustaendigkeit","⚖ Zuständigkeit"],
            ["system_status",  "⚙ System-Status"],
          ].map(([id, label]) => (
            <button key={id} onClick={() => { setTab(id); setSuche(""); }}
              style={{ padding:"8px 18px", border:"none", background:"transparent",
                fontFamily:"'Figtree',sans-serif", fontSize:"0.95rem", fontWeight:600,
                color: tab===id ? T.navy : T.textMuted, cursor:"pointer",
                borderBottom: tab===id ? `2px solid ${T.accent}` : "2px solid transparent",
                marginBottom:-1 }}>
              {label}
              {id !== "imap" && id !== "fristen" && id !== "ki" && id !== "zustaendigkeit" && id !== "sv_portal" && id !== "system_status" && (
                <span style={{ marginLeft:6, background:T.surface, color:T.textMuted,
                  borderRadius:10, padding:"1px 7px", fontSize:"0.8rem", fontWeight:400 }}>
                  {id === "versicherer" ? vorlagen.filter(v => v.kategorie==="versicherung").length
                   : id === "gutachter" ? vorlagen.filter(v => v.kategorie==="gutachter").length
                   : vorlagen.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* IMAP Tab */}
        {tab === "imap" && (
          <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.955rem",
            color:T.textMuted, background:T.white, borderRadius:10, padding:"1.5rem",
            border:`1px solid ${T.border}` }}>
            <p style={{ margin:"0 0 0.75rem" }}>IMAP-Konfiguration ist in der <code>.env</code>-Datei hinterlegt.</p>
            <code style={{ display:"block", background:T.offWhite, padding:"1rem",
              borderRadius:7, fontSize:"0.875rem", color:T.navy }}>
              EMAIL_HOST=imap.strato.de<br/>
              EMAIL_PORT=993<br/>
              EMAIL_USER=unfall@anwalt-offenbach.de<br/>
              EMAIL_FOLDER=INBOX<br/>
              EMAIL_MAX_FETCH=50<br/>
              KANZLEI_DOMAINS=anwalt-offenbach.de
            </code>
          </div>
        )}

        {/* Fristen-Tab */}
        {tab === "fristen" && (
          <div style={{ display:"flex", flexDirection:"column", gap:"1.25rem", maxWidth:520 }}>

            {/* Erklärung */}
            <div style={{ background:T.white, borderRadius:10, padding:"1rem 1.25rem",
              border:`1px solid ${T.border}`, fontFamily:"'Figtree',sans-serif",
              fontSize:"0.915rem", color:T.textMuted, lineHeight:1.6 }}>
              Diese Werte bestimmen die <strong style={{ color:T.text }}>Antwortfrist im Brieftext</strong> der
              Sachstandsanfrage je Eskalationsstufe. Der generierte Text wird beim nächsten Öffnen
              des STA-Dialogs automatisch aktualisiert.
            </div>

            {/* Stufen-Karte */}
            <Card>
              <CardHead title="STA-Eskalationsstufen – Fristen" />
              <div style={{ padding:"1rem 1.25rem", display:"flex", flexDirection:"column", gap:"1.1rem" }}>

                {[
                  { tageKey:"stufe1_tage", textKey:"stufe1_text", label:"Stufe 1 – Erinnerung",       farbe:"#22c55e", desc:"Freundliche Erinnerung, erste Kontaktaufnahme nach Forderungsschreiben" },
                  { tageKey:"stufe2_tage", textKey:"stufe2_text", label:"Stufe 2 – Mahnung",           farbe:"#f59e0b", desc:"Bestimmte Mahnung nach ausbleibender Antwort auf erste STA" },
                  { tageKey:"stufe3_tage", textKey:"stufe3_text", label:"Stufe 3 – Klage-Ankündigung", farbe:T.red, desc:"Unmissverständliche Ankündigung gerichtlicher Schritte" },
                ].map(({ tageKey, textKey, label, farbe, desc }, idx, arr) => (
                  <div key={tageKey} style={{ borderBottom: idx < arr.length-1 ? `1px solid ${T.border}` : "none", paddingBottom:"1.25rem" }}>

                    {/* Stufen-Header */}
                    <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:4 }}>
                      <div style={{ width:10, height:10, borderRadius:"50%", background:farbe, flexShrink:0 }} />
                      <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.9rem",
                        fontWeight:700, color:T.text }}>{label}</span>
                    </div>
                    <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem",
                      color:T.textFaint, marginBottom:10, paddingLeft:20 }}>{desc}</div>

                    {/* Frist-Eingabe */}
                    <div style={{ display:"flex", alignItems:"center", gap:10, paddingLeft:20, marginBottom:12 }}>
                      <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                        fontWeight:600, color:T.textMuted, minWidth:50 }}>Frist:</span>
                      <input
                        type="number" min={1} max={365}
                        value={fristen[tageKey] ?? ""}
                        onChange={e => setFristen(p => ({ ...p, [tageKey]: parseInt(e.target.value) || 1 }))}
                        style={{ ...inputStyle, width:80, textAlign:"center",
                          fontFamily:"ui-monospace,monospace", fontSize:"1rem", fontWeight:600 }}
                      />
                      <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", color:T.textMuted }}>
                        Tage
                      </span>
                    </div>

                    {/* Brieftext-Vorlage */}
                    <div style={{ paddingLeft:20 }}>
                      <div style={{ display:"flex", alignItems:"baseline", justifyContent:"space-between", marginBottom:5 }}>
                        <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                          fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.06em" }}>
                          Brieftext-Vorlage
                        </label>
                        <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.755rem",
                          color:T.textFaint, background:T.offWhite, padding:"2px 8px",
                          borderRadius:5, border:`1px solid ${T.border}` }}>
                          {"{Schreiben}"} · {"{Mandant}"} · {"{Frist}"}
                        </span>
                      </div>
                      <textarea
                        rows={5}
                        value={fristen[textKey] ?? ""}
                        onChange={e => setFristen(p => ({ ...p, [textKey]: e.target.value }))}
                        style={{ ...inputStyle, resize:"vertical", lineHeight:1.6,
                          fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem" }}
                      />
                    </div>
                  </div>
                ))}

                <div style={{ borderTop:`1px solid ${T.border}`, paddingTop:"1rem", display:"flex", justifyContent:"flex-end" }}>
                  <Btn
                    onClick={async () => {
                      setFristenSpeich(true);
                      try {
                        const res = await apiEinstellungen.staFristenSpeichern(fristen);
                        setFristen(res);
                        setToast("Fristen gespeichert.");
                      } catch(e) {
                        setToast(e?.message || "Fehler beim Speichern.");
                      } finally { setFristenSpeich(false); }
                    }}
                    disabled={fristenSpeich || fristenLaedt}>
                    {fristenSpeich ? "Speichern …" : "Speichern"}
                  </Btn>
                </div>
              </div>
            </Card>

            {/* Klassifikations-Lernystem */}
            <Card>
              <CardHead title="Lernystem – Dokumentenklassifikation" />
              <div style={{ padding:"1rem 1.25rem", display:"flex", flexDirection:"column", gap:"0.85rem" }}>
                <p style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.895rem",
                  color:T.textMuted, lineHeight:1.6, margin:0 }}>
                  Jede manuelle Korrektur einer Dokumentenklasse wird als Trainingsdatensatz gespeichert.
                  Ab <strong style={{ color:T.text }}>50 Einträgen</strong> kann ein TF-IDF-Modell trainiert werden,
                  das den Klassifikator automatisch verbessert.
                </p>

                {training && (
                  <>
                    {/* Fortschrittsbalken */}
                    <div>
                      <div style={{ display:"flex", justifyContent:"space-between", marginBottom:5 }}>
                        <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem",
                          fontWeight:600, color:T.text }}>
                          Gesammelte Korrekturen
                        </span>
                        <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.855rem",
                          color: training.bereit ? T.green : T.textMuted }}>
                          {training.gesamt} / {training.ziel}
                        </span>
                      </div>
                      <div style={{ height:8, borderRadius:4, background:T.borderSoft, overflow:"hidden" }}>
                        <div style={{
                          height:"100%", borderRadius:4,
                          width: `${Math.min(100, Math.round(training.gesamt / training.ziel * 100))}%`,
                          background: training.bereit ? T.green : T.accent,
                          transition:"width 0.4s ease",
                        }}/>
                      </div>
                    </div>

                    {/* Status */}
                    <div style={{
                      padding:"0.65rem 1rem", borderRadius:8,
                      background: training.bereit ? (T.green + "18") : (T.amber + "15"),
                      border: `1px solid ${training.bereit ? T.green : T.amber}44`,
                      fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem",
                      color: training.bereit ? T.green : T.amber, fontWeight:600,
                    }}>
                      {training.bereit
                        ? "✓ Genug Daten – TF-IDF-Modell kann trainiert werden."
                        : `Noch ${training.ziel - training.gesamt} Korrekturen bis zum Trainingsstart.`}
                    </div>

                    {/* Klassen-Aufschlüsselung */}
                    {training.klassen.length > 0 && (
                      <div style={{ display:"flex", flexWrap:"wrap", gap:6 }}>
                        {training.klassen.map(k => (
                          <span key={k.klasse} style={{
                            fontFamily:"ui-monospace,monospace", fontSize:"0.8rem",
                            padding:"3px 10px", borderRadius:12,
                            background:T.surface, border:`1px solid ${T.border}`,
                            color:T.textMuted,
                          }}>
                            {k.klasse} ({k.n})
                          </span>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </Card>
          </div>
        )}

        {/* KI-Assistent Tab */}
        {tab === "ki" && (
          <div style={{ display:"flex", flexDirection:"column", gap:"1.25rem", maxWidth:640 }}>

            {/* Info */}
            <div style={{ background:T.white, borderRadius:10, padding:"1rem 1.25rem",
              border:`1px solid ${T.border}`, fontFamily:"'Figtree',sans-serif",
              fontSize:"0.915rem", color:T.textMuted, lineHeight:1.6 }}>
              Konfiguriert den KI-Vorschlag-Button im Klage-Wizard (Step 7 – Rechtliche Würdigung).
              API-Keys werden in der <code>.env</code>-Datei hinterlegt:
              <code style={{ display:"block", background:T.offWhite, padding:"0.75rem 1rem",
                borderRadius:7, fontSize:"0.85rem", color:T.navy, marginTop:8, lineHeight:1.8 }}>
                ANTHROPIC_API_KEY=sk-ant-…<br/>
                GEMINI_API_KEY=AIza…
              </code>
            </div>

            <Card>
              <CardHead title="Sprachmodell" />
              <div style={{ padding:"1rem 1.25rem", display:"flex", flexDirection:"column", gap:"1rem" }}>

                <div>
                  <label style={{ display:"block", fontFamily:"'Figtree',sans-serif",
                    fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:6 }}>
                    Aktives Modell
                  </label>
                  <select value={ki.modell}
                    onChange={e => setKi(p => ({ ...p, modell: e.target.value }))}
                    style={{ ...inputStyle, maxWidth:320 }}>
                    {(ki.modelle.length ? ki.modelle : ["claude-sonnet-4-6","gemini-3.1-pro"]).map(m => (
                      <option key={m} value={m}>
                        {m === "claude-sonnet-4-6" ? "Claude Sonnet 4.6 (Anthropic)"
                       : m === "gemini-3.1-pro"    ? "Gemini 3.1 Pro (Google)"
                       : m}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <div style={{ display:"flex", justifyContent:"space-between", alignItems:"baseline", marginBottom:5 }}>
                    <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem",
                      fontWeight:600, color:T.textMuted }}>System-Prompt</label>
                  </div>
                  <textarea rows={5} value={ki.system_prompt}
                    onChange={e => setKi(p => ({ ...p, system_prompt: e.target.value }))}
                    style={{ ...inputStyle, resize:"vertical", lineHeight:1.6,
                      fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem" }} />
                </div>

                <div>
                  <div style={{ display:"flex", justifyContent:"space-between", alignItems:"baseline", marginBottom:5 }}>
                    <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem",
                      fontWeight:600, color:T.textMuted }}>User-Prompt-Vorlage</label>
                    <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.755rem",
                      color:T.textFaint, background:T.offWhite, padding:"2px 8px",
                      borderRadius:5, border:`1px solid ${T.border}` }}>
                      {"{haftung_ctx}"} · {"{schilderung}"}
                    </span>
                  </div>
                  <textarea rows={8} value={ki.user_prompt}
                    onChange={e => setKi(p => ({ ...p, user_prompt: e.target.value }))}
                    style={{ ...inputStyle, resize:"vertical", lineHeight:1.6,
                      fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem" }} />
                </div>

                <div style={{ display:"flex", justifyContent:"flex-end", gap:10 }}>
                  <Btn style={{ background:"transparent", color:T.textMuted,
                    border:`1px solid ${T.border}` }}
                    onClick={() => {
                      setKiLaedt(true);
                      apiEinstellungen.kiEinstellungen()
                        .then(d => setKi(d)).catch(() => {})
                        .finally(() => setKiLaedt(false));
                    }}
                    disabled={kiLaedt || kiSpeich}>
                    ↺ Defaults laden
                  </Btn>
                  <Btn onClick={async () => {
                    setKiSpeich(true);
                    try {
                      const res = await apiEinstellungen.kiEinstellungenSpeichern({
                        modell:        ki.modell,
                        system_prompt: ki.system_prompt,
                        user_prompt:   ki.user_prompt,
                      });
                      setKi(res);
                      setToast("KI-Einstellungen gespeichert.");
                    } catch(e) {
                      setToast(e?.message || "Fehler beim Speichern.");
                    } finally { setKiSpeich(false); }
                  }} disabled={kiSpeich || kiLaedt}>
                    {kiSpeich ? "Speichern …" : "Speichern"}
                  </Btn>
                </div>
              </div>
            </Card>

            {/* ── Lokales LLM-Parsing ───────────────────────────────────── */}
            <Card>
              <CardHead title="✦ Lokales LLM – PDF-Parsing" />
              <div style={{ padding:"1rem 1.25rem", display:"flex", flexDirection:"column", gap:"1.1rem" }}>

                {/* Status-Zeile */}
                <div style={{ display:"flex", alignItems:"center", gap:12, flexWrap:"wrap" }}>
                  {/* Aktivieren-Toggle */}
                  <label style={{ display:"flex", alignItems:"center", gap:10, cursor: llm.env_konfiguriert ? "pointer" : "not-allowed", opacity: llm.env_konfiguriert ? 1 : 0.5 }}>
                    <div
                      onClick={async () => {
                        if (!llm.env_konfiguriert || llmToggling) return;
                        setLlmToggling(true);
                        try {
                          const res = await apiEinstellungen.llmAktivieren(!llm.aktiviert);
                          setLlm(p => ({ ...p, aktiviert: res.aktiviert }));
                          setToast(res.aktiviert ? "Gemma-Parsing aktiviert." : "Gemma-Parsing deaktiviert.");
                        } catch { setToast("Fehler beim Speichern."); }
                        finally { setLlmToggling(false); }
                      }}
                      style={{
                        width:42, height:24, borderRadius:12,
                        background: llm.aktiviert ? T.green : T.border,
                        position:"relative", transition:"background 0.2s",
                        cursor: llm.env_konfiguriert ? "pointer" : "not-allowed",
                      }}>
                      <div style={{
                        position:"absolute", top:3, left: llm.aktiviert ? 21 : 3,
                        width:18, height:18, borderRadius:9, background:"#fff",
                        transition:"left 0.2s", boxShadow:"0 1px 3px rgba(0,0,0,0.2)",
                      }} />
                    </div>
                    <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.9rem",
                      fontWeight:600, color: llm.aktiviert ? T.green : T.textMuted }}>
                      {llm.aktiviert ? "Aktiv" : "Inaktiv"}
                    </span>
                  </label>

                  {/* Verbindungs-Badge */}
                  <span style={{
                    padding:"3px 10px", borderRadius:5, fontSize:12, fontWeight:600,
                    background: llm.verfuegbar ? "rgba(34,197,94,0.12)" : "rgba(156,163,175,0.12)",
                    color: llm.verfuegbar ? T.green : T.textFaint,
                    border: `1px solid ${llm.verfuegbar ? "rgba(34,197,94,0.3)" : T.border}`,
                  }}>
                    {llmLaedt ? "Prüfe …" : llm.verfuegbar ? "● LM Studio verbunden" : "○ Nicht verbunden"}
                  </span>

                  <Btn style={{ marginLeft:"auto", background:"transparent",
                    color:T.textMuted, border:`1px solid ${T.border}`, fontSize:12, padding:"4px 12px" }}
                    onClick={() => {
                      setLlmLaedt(true);
                      apiEinstellungen.llmStatus().then(d => setLlm(d)).catch(() => {}).finally(() => setLlmLaedt(false));
                    }} disabled={llmLaedt}>
                    ↺ Status prüfen
                  </Btn>
                </div>

                {/* Modell-Auswahl */}
                <div>
                  <label style={{ display:"block", fontFamily:"'Figtree',sans-serif",
                    fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:6 }}>
                    Aktives Modell
                  </label>
                  <div style={{ display:"flex", gap:8, alignItems:"center" }}>
                    <select
                      value={llm.aktives_modell || ""}
                      onChange={async e => {
                        const m = e.target.value;
                        if (!m || llmModellWechsel) return;
                        setLlmModellWechsel(true);
                        try {
                          await apiEinstellungen.llmModellSetzen(m);
                          setLlm(p => ({ ...p, aktives_modell: m }));
                          setToast(`Modell gewechselt: ${m}`);
                        } catch { setToast("Fehler beim Modellwechsel."); }
                        finally { setLlmModellWechsel(false); }
                      }}
                      disabled={!llm.env_konfiguriert || llmModellWechsel || llm.modelle.length === 0}
                      style={{ ...inputStyle, flex:1, fontFamily:"ui-monospace,monospace",
                        fontSize:"0.825rem", opacity: llm.env_konfiguriert ? 1 : 0.5 }}>
                      {(llm.modelle.length ? llm.modelle : [llm.aktives_modell || "—"]).map(m => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                    {llmModellWechsel && (
                      <span style={{ fontSize:12, color:T.textMuted }}>Wechsle …</span>
                    )}
                  </div>
                  <div style={{ marginTop:6, fontFamily:"ui-monospace,monospace",
                    fontSize:"0.775rem", color:T.textFaint }}>
                    URL: {llm.base_url || "—"}
                  </div>
                  {!llm.env_konfiguriert && (
                    <div style={{ marginTop:6, fontSize:"0.8rem", color:T.amber,
                      fontFamily:"'Figtree',sans-serif" }}>
                      ⚠ LLM_ENABLED=true fehlt in <code>.env</code> — Toggle ohne Wirkung.
                    </div>
                  )}
                </div>

                {/* Verbindungstest */}
                <div>
                  <label style={{ display:"block", fontFamily:"'Figtree',sans-serif",
                    fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:6 }}>
                    Verbindungstest
                  </label>
                  <div style={{ display:"flex", gap:8, marginBottom:8 }}>
                    <input
                      value={llmTestPrompt}
                      onChange={e => setLlmTestPrompt(e.target.value)}
                      placeholder="Testprompt …"
                      style={{ ...inputStyle, flex:1, fontSize:"0.875rem" }}
                    />
                    <Btn
                      onClick={async () => {
                        setLlmTestLaedt(true);
                        setLlmTestAntwort("");
                        try {
                          const res = await apiEinstellungen.llmTest(llmTestPrompt);
                          setLlmTestAntwort(res.antwort || "");
                        } catch(e) {
                          setLlmTestAntwort("Fehler: " + (e?.message || "Verbindung fehlgeschlagen"));
                        } finally { setLlmTestLaedt(false); }
                      }}
                      disabled={llmTestLaedt || !llm.env_konfiguriert}>
                      {llmTestLaedt ? "Warte …" : "Senden"}
                    </Btn>
                  </div>
                  {llmTestAntwort && (
                    <div style={{
                      background: llmTestAntwort.startsWith("Fehler") ? "#2a1500" : T.offWhite,
                      border:`1px solid ${llmTestAntwort.startsWith("Fehler") ? "rgba(245,158,11,0.3)" : T.border}`,
                      borderRadius:7, padding:"0.75rem 1rem",
                      fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                      color: llmTestAntwort.startsWith("Fehler") ? T.amber : T.text,
                      lineHeight:1.6, whiteSpace:"pre-wrap",
                    }}>
                      {llmTestAntwort}
                    </div>
                  )}
                </div>

              </div>
            </Card>

          </div>
        )}

        {/* Zuständigkeit Tab */}
        {tab === "zustaendigkeit" && (
          <div style={{ display:"flex", flexDirection:"column", gap:"1.25rem", maxWidth:520 }}>

            <div style={{ background:T.white, borderRadius:10, padding:"1rem 1.25rem",
              border:`1px solid ${T.border}`, fontFamily:"'Figtree',sans-serif",
              fontSize:"0.915rem", color:T.textMuted, lineHeight:1.6 }}>
              Legt fest, ab welchem Streitwert das <strong style={{ color:T.text }}>Landgericht</strong> zuständig ist.
              Im Klage-Wizard (Step 10) erscheint eine Warnung, wenn das gewählte Gericht ein Amtsgericht ist
              und der Streitwert diese Grenze überschreitet.
              <br/><br/>
              Gesetzliche Grundlage: <strong style={{ color:T.text }}>§ 23 Nr. 1 GVG</strong> (AG bis 10.000 €),
              <strong style={{ color:T.text }}> § 71 Abs. 1 GVG</strong> (LG ab 10.000 €).
              Standard: 10.000 € (seit Justizmodernisierungsgesetz 2023). Dieser Wert kann für besondere Zuständigkeitsvereinbarungen angepasst werden.
            </div>

            <Card>
              <CardHead title="LG-Zuständigkeitsgrenze" />
              <div style={{ padding:"1rem 1.25rem", display:"flex", flexDirection:"column", gap:"1rem" }}>

                <div>
                  <label style={{ display:"block", fontFamily:"'Figtree',sans-serif",
                    fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:6 }}>
                    LG-Zuständigkeitsgrenze (€)
                  </label>
                  <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                    color:T.textFaint, marginBottom:8 }}>
                    Ab diesem Streitwert ist das Landgericht zuständig (§ 23 GVG / § 71 GVG)
                  </div>
                  <input
                    type="number" min={1} max={10000000}
                    value={lgGrenzwert}
                    onChange={e => setLgGrenzwert(parseInt(e.target.value) || 10000)}
                    disabled={lgGrenzwertLaedt}
                    style={{ ...inputStyle, width:160, textAlign:"right",
                      fontFamily:"ui-monospace,monospace", fontSize:"1rem", fontWeight:600 }}
                  />
                  <span style={{ marginLeft:8, fontFamily:"'Figtree',sans-serif",
                    fontSize:"0.875rem", color:T.textMuted }}>€</span>
                </div>

                <div style={{ display:"flex", justifyContent:"flex-end" }}>
                  <Btn
                    onClick={async () => {
                      setLgGrenzwertSpeich(true);
                      try {
                        const res = await apiEinstellungen.lgGrenzwertSpeichern(lgGrenzwert);
                        setLgGrenzwert(res.lg_grenzwert ?? lgGrenzwert);
                        setToast("LG-Grenze gespeichert.");
                      } catch(e) {
                        setToast(e?.message || "Fehler beim Speichern.");
                      } finally { setLgGrenzwertSpeich(false); }
                    }}
                    disabled={lgGrenzwertSpeich || lgGrenzwertLaedt}>
                    {lgGrenzwertSpeich ? "Speichern …" : "Speichern"}
                  </Btn>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* SV-Portal Tab */}
        {tab === "sv_portal" && (
          <div style={{ display:"flex", height:"calc(100vh - 200px)", minHeight:480,
            border:`1px solid ${T.border}`, borderRadius:10, overflow:"hidden",
            background:T.white }}>

            {/* ── Linke Spalte: SV-Liste ── */}
            <div style={{ width:260, borderRight:`1px solid ${T.border}`,
              display:"flex", flexDirection:"column", flexShrink:0 }}>

              {/* Neu-anlegen-Formular */}
              <div style={{ padding:"12px", borderBottom:`1px solid ${T.border}` }}>
                <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                  fontWeight:700, color:T.textMuted, marginBottom:6, textTransform:"uppercase",
                  letterSpacing:"0.06em" }}>Sachverständigen suchen</div>
                <div ref={svSuchRef} style={{ position:"relative", marginBottom: svForm.vorschau || svForm.fehler ? 8 : 0 }}>
                  <div style={{ position:"relative" }}>
                    <input
                      type="text" placeholder="Name oder Adressnr."
                      value={svForm.adressnr}
                      onChange={async e => {
                        const q = e.target.value;
                        setSvForm(p => ({...p, adressnr: q, vorschau: null, fehler:""}));
                        if (q.length < 2) { setSvSuchVorschlaege([]); setSvSuchOffen(false); return; }
                        setSvSuchLaedt(true); setSvSuchOffen(true);
                        try { setSvSuchVorschlaege(await apiSvPortal.suche(q)); }
                        catch { setSvSuchVorschlaege([]); }
                        finally { setSvSuchLaedt(false); }
                      }}
                      onKeyDown={e => { if (e.key === "Escape") setSvSuchOffen(false); }}
                      style={{ width:"100%", padding:"6px 28px 6px 8px", border:`1px solid ${T.border}`,
                        borderRadius:6, fontFamily:"ui-monospace,monospace",
                        fontSize:"0.875rem", outline:"none", boxSizing:"border-box" }}
                    />
                    {svSuchLaedt && (
                      <div style={{ position:"absolute", right:8, top:"50%", transform:"translateY(-50%)",
                        width:11, height:11, border:"2px solid rgba(0,0,0,0.12)",
                        borderTopColor:T.navy, borderRadius:"50%",
                        animation:"spin 0.7s linear infinite" }}/>
                    )}
                  </div>
                  {svSuchOffen && (
                    <div style={{ position:"absolute", top:"calc(100% + 2px)", left:0, right:0, zIndex:300,
                      background:T.white, border:`1px solid ${T.border}`,
                      borderRadius:8, boxShadow:"0 4px 16px rgba(0,0,0,0.13)", overflow:"hidden" }}>
                      {svSuchVorschlaege.length > 0 ? (
                        <div style={{ maxHeight:200, overflowY:"auto" }}>
                          {svSuchVorschlaege.map(sv => (
                            <button key={sv.adressnr}
                              onMouseDown={() => {
                                setSvSuchOffen(false);
                                setSvSuchVorschlaege([]);
                                svVorschauLadenNr(sv.adressnr);
                              }}
                              style={{ width:"100%", textAlign:"left", padding:"8px 10px",
                                background:"transparent", border:"none",
                                borderBottom:`1px solid ${T.borderSoft}`,
                                cursor:"pointer" }}
                              onMouseEnter={e => e.currentTarget.style.background = "#eff6ff"}
                              onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.82rem",
                                fontWeight:700, color:T.text }}>
                                {sv.vorname} {sv.name}
                              </div>
                              <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.72rem",
                                color:T.textMuted }}>
                                Nr. {sv.adressnr}{sv.email ? ` · ${sv.email}` : ""}
                              </div>
                            </button>
                          ))}
                        </div>
                      ) : !svSuchLaedt ? (
                        <div style={{ padding:"9px 10px", fontFamily:"'Figtree',sans-serif",
                          fontSize:"0.8rem", color:T.textMuted }}>Keine Einträge gefunden.</div>
                      ) : null}
                    </div>
                  )}
                </div>
                {svForm.fehler && (
                  <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem",
                    color:T.red, marginBottom:6 }}>{svForm.fehler}</div>
                )}
                {svForm.vorschau && (
                  <div style={{ background:T.offWhite, border:`1px solid ${T.border}`,
                    borderRadius:6, padding:"7px 10px", marginBottom:8 }}>
                    <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.82rem",
                      fontWeight:700, color:T.text }}>
                      {svForm.vorschau.vorname} {svForm.vorschau.name}
                    </div>
                    <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.75rem",
                      color:T.textMuted }}>{svForm.vorschau.email || "⚠ Keine E-Mail"}</div>
                  </div>
                )}
                {svForm.vorschau && svForm.vorschau.email && (
                  <Btn onClick={svAnlegen} disabled={svFormSpeichert}
                    style={{ width:"100%", fontSize:"0.8rem" }}>
                    {svFormSpeichert ? "Anlegen …" : "＋ Zugang anlegen"}
                  </Btn>
                )}
              </div>

              {/* SV-Liste */}
              <div style={{ flex:1, overflowY:"auto" }}>
                {svLaedt ? (
                  <div style={{ padding:"1.5rem", textAlign:"center", color:T.textFaint,
                    fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem" }}>Lade …</div>
                ) : svListe.length === 0 ? (
                  <div style={{ padding:"1.5rem", textAlign:"center", color:T.textFaint,
                    fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem" }}>
                    Noch keine SV-Accounts.<br/>Adressnummer eingeben um zu beginnen.
                  </div>
                ) : svListe.map(sv => {
                  const istAusgewaehlt = svAusgewaehlt === sv.adressnr;
                  const dotFarbe = !sv.portal_aktiv ? T.textFaint
                    : sv.einladung_gesendet_am ? "#22c55e" : "#f59e0b";
                  return (
                    <div key={sv.adressnr}
                      onClick={() => setSvAusgewaehlt(sv.adressnr)}
                      style={{ padding:"9px 12px", cursor:"pointer",
                        borderBottom:`1px solid ${T.borderSoft}`,
                        background: istAusgewaehlt ? "#eff6ff" : "transparent",
                        borderRight: istAusgewaehlt ? `3px solid ${T.accent}` : "3px solid transparent",
                        display:"flex", alignItems:"center", gap:8,
                        opacity: sv.portal_aktiv ? 1 : 0.5 }}>
                      <div style={{ width:30, height:30, borderRadius:"50%",
                        background:"#dbeafe", display:"flex", alignItems:"center",
                        justifyContent:"center", fontSize:"0.7rem", fontWeight:800,
                        color:"#1e40af", flexShrink:0 }}>
                        {(sv.vorname?.[0] || "")}{ (sv.name?.[0] || "")}
                      </div>
                      <div style={{ flex:1, minWidth:0 }}>
                        <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.82rem",
                          fontWeight:700, color:T.text, whiteSpace:"nowrap",
                          overflow:"hidden", textOverflow:"ellipsis" }}>
                          {sv.vorname} {sv.name}
                        </div>
                        <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.72rem",
                          color:T.textMuted, whiteSpace:"nowrap", overflow:"hidden",
                          textOverflow:"ellipsis" }}>{sv.email}</div>
                      </div>
                      <div style={{ width:8, height:8, borderRadius:"50%",
                        background:dotFarbe, flexShrink:0 }} />
                    </div>
                  );
                })}
              </div>
            </div>

            {/* ── Rechte Spalte: Detail ── */}
            <div style={{ flex:1, display:"flex", flexDirection:"column",
              background:T.offWhite, overflow:"hidden" }}>
              {!svAusgewaehlt ? (
                <div style={{ flex:1, display:"flex", alignItems:"center",
                  justifyContent:"center", color:T.textFaint,
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.9rem" }}>
                  ← SV aus der Liste auswählen
                </div>
              ) : (() => {
                const sv = svListe.find(s => s.adressnr === svAusgewaehlt);
                if (!sv) return null;
                const dotFarbe = !sv.portal_aktiv ? T.textFaint
                  : sv.einladung_gesendet_am ? "#22c55e" : "#f59e0b";
                const statusText = !sv.portal_aktiv ? "Deaktiviert"
                  : sv.einladung_gesendet_am ? "Aktiv im Portal" : "Einladung ausstehend";
                const sichtbar = svAkten.filter(a => a.portal_aktiv).length;
                return (
                  <>
                    {/* SV-Header */}
                    <div style={{ padding:"14px 18px 12px", background:T.white,
                      borderBottom:`1px solid ${T.border}`,
                      display:"flex", alignItems:"flex-start", gap:12 }}>
                      <div style={{ width:42, height:42, borderRadius:"50%",
                        background:"#dbeafe", display:"flex", alignItems:"center",
                        justifyContent:"center", fontSize:"0.95rem", fontWeight:800,
                        color:"#1e40af", flexShrink:0 }}>
                        {(sv.vorname?.[0]||"")}{(sv.name?.[0]||"")}
                      </div>
                      <div style={{ flex:1 }}>
                        <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"1rem",
                          fontWeight:800, color:T.navy }}>
                          {sv.vorname} {sv.name}
                        </div>
                        <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.8rem",
                          color:T.textMuted, marginTop:1 }}>
                          {sv.email} · Nr. {sv.adressnr}
                        </div>
                        <div style={{ marginTop:6, display:"flex", alignItems:"center", gap:8 }}>
                          <span style={{ display:"inline-flex", alignItems:"center", gap:4,
                            padding:"2px 9px", borderRadius:10, fontSize:"0.73rem",
                            fontWeight:700, background: dotFarbe + "18",
                            color:dotFarbe, border:`1px solid ${dotFarbe}44` }}>
                            ● {statusText}
                          </span>
                          {sv.einladung_gesendet_am && (
                            <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.73rem",
                              color:T.textFaint }}>
                              Eingeladen: {sv.einladung_gesendet_am.slice(0,10)}
                            </span>
                          )}
                        </div>
                      </div>
                      <div style={{ display:"flex", gap:6, flexShrink:0 }}>
                        <Btn
                          disabled={svEinladung[sv.adressnr]}
                          style={{ fontSize:"0.78rem", padding:"6px 11px",
                            background:"transparent", color:T.textMuted,
                            border:`1px solid ${T.border}` }}
                          onClick={async () => {
                            setSvEinladung(p => ({...p, [sv.adressnr]: true}));
                            try {
                              await apiSvPortal.einladungSenden(sv.adressnr);
                              await ladeSvListe();
                              setToast("Einladungs-Zeitstempel gesetzt.");
                            } catch(e) { setToast(e?.message || "Fehler."); }
                            finally { setSvEinladung(p => ({...p, [sv.adressnr]: false})); }
                          }}>
                          {svEinladung[sv.adressnr] ? "…" : "✉ Einladung vermerken"}
                        </Btn>
                        <Btn
                          style={{ fontSize:"0.78rem", padding:"6px 11px",
                            background: sv.portal_aktiv ? "transparent" : T.navy,
                            color: sv.portal_aktiv ? T.red : T.white,
                            border: sv.portal_aktiv ? `1px solid #fca5a5` : "none" }}
                          onClick={async () => {
                            try {
                              await apiSvPortal.toggleAktiv(sv.adressnr, sv.portal_aktiv ? 0 : 1);
                              await ladeSvListe();
                              setToast(sv.portal_aktiv ? "SV deaktiviert." : "SV aktiviert.");
                            } catch(e) { setToast(e?.message || "Fehler."); }
                          }}>
                          {sv.portal_aktiv ? "Deaktivieren" : "Aktivieren"}
                        </Btn>
                        <Btn
                          style={{ fontSize:"0.78rem", padding:"6px 11px",
                            background:"transparent", color:T.red,
                            border:`1px solid #fca5a5` }}
                          onClick={async () => {
                            if (!window.confirm(`SV-Account für ${sv.vorname} ${sv.name} wirklich löschen?`)) return;
                            try {
                              await apiSvPortal.loeschen(sv.adressnr);
                              setSvAusgewaehlt(null);
                              setSvAkten([]);
                              await ladeSvListe();
                              setToast("SV-Account gelöscht.");
                            } catch(e) { setToast(e?.message || "Fehler."); }
                          }}>
                          Löschen
                        </Btn>
                      </div>
                    </div>

                    {/* Akten-Liste */}
                    <div style={{ flex:1, overflowY:"auto", padding:"14px 18px" }}>
                      <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:10 }}>
                        <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.75rem",
                          fontWeight:800, color:T.textMuted, textTransform:"uppercase",
                          letterSpacing:"0.07em", display:"flex", alignItems:"center", gap:6 }}>
                          Akten in RA-MICRO
                          <span style={{ background:T.surface, color:T.textMuted,
                            border:`1px solid ${T.border}`, borderRadius:8,
                            padding:"1px 7px", fontSize:"0.72rem",
                            fontWeight:600, textTransform:"none", letterSpacing:0 }}>
                            {svAkten.length}
                          </span>
                        </div>
                        <div style={{ flex:1 }} />
                        {(() => {
                          const alleAn = svAkten.length > 0 && svAkten.every(a => a.portal_aktiv);
                          return (
                            <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                              <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem",
                                color: alleAn ? "#22c55e" : T.textMuted, fontWeight:600 }}>
                                {alleAn ? "Alle freigegeben" : "Alle sperren / freigeben"}
                              </span>
                              <div
                                onClick={async () => {
                                  const neuerWert = alleAn ? 0 : 1;
                                  try {
                                    await apiSvPortal.alleToggle(sv.adressnr, neuerWert);
                                    setSvAkten(prev => prev.map(a => ({...a, portal_aktiv: neuerWert, im_system: true})));
                                    setToast(neuerWert ? "Alle Akten freigegeben." : "Alle Akten gesperrt.");
                                  } catch(e) { setToast(e?.message || "Fehler."); }
                                }}
                                style={{ width:44, height:24, borderRadius:12,
                                  background: alleAn ? "#22c55e" : T.border,
                                  position:"relative", cursor:"pointer",
                                  transition:"background 0.2s", flexShrink:0 }}>
                                <div style={{ position:"absolute", top:3,
                                  left: alleAn ? 22 : 3,
                                  width:18, height:18, borderRadius:9,
                                  background:"#fff", boxShadow:"0 1px 3px rgba(0,0,0,.25)",
                                  transition:"left 0.2s" }} />
                              </div>
                            </div>
                          );
                        })()}
                      </div>

                      {svAktenLaedt ? (
                        <div style={{ color:T.textFaint, fontFamily:"'Figtree',sans-serif",
                          fontSize:"0.875rem" }}>Lade …</div>
                      ) : svAkten.length === 0 ? (
                        <div style={{ color:T.textFaint, fontFamily:"'Figtree',sans-serif",
                          fontSize:"0.875rem" }}>
                          Keine Akten in RA-MICRO gefunden.
                        </div>
                      ) : svAkten.map(akte => (
                        <div key={akte.az} style={{ background:T.white,
                          border:`1px solid ${T.border}`, borderRadius:8,
                          padding:"9px 12px", marginBottom:6,
                          display:"flex", alignItems:"center", gap:10,
                          opacity: akte.portal_aktiv ? 1 : 0.65 }}>
                          <div style={{ fontFamily:"ui-monospace,monospace",
                            fontSize:"0.8rem", fontWeight:700, color:T.navy, minWidth:75 }}>
                            {akte.az}
                          </div>
                          <div style={{ flex:1, fontFamily:"'Figtree',sans-serif",
                            fontSize:"0.82rem", color: akte.im_system ? T.text : T.textFaint,
                            whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>
                            {akte.kurzbezeichnung || "—"}
                          </div>
                          <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.73rem",
                            color:T.textFaint, flexShrink:0 }}>
                            {akte.unfalldatum || ""}
                          </div>
                          <div
                            onClick={async () => {
                              const neuerWert = akte.portal_aktiv ? 0 : 1;
                              try {
                                await apiSvPortal.togglePortalAktiv(akte.az, neuerWert);
                                setSvAkten(prev => prev.map(a =>
                                  a.az === akte.az ? {...a, portal_aktiv: neuerWert, im_system: true} : a
                                ));
                              } catch(e) { setToast(e?.message || "Fehler."); }
                            }}
                            style={{ width:36, height:20, borderRadius:10,
                              background: akte.portal_aktiv ? "#22c55e" : T.border,
                              position:"relative", cursor:"pointer",
                              transition:"background 0.2s", flexShrink:0 }}>
                            <div style={{ position:"absolute", top:2,
                              left: akte.portal_aktiv ? 18 : 2,
                              width:16, height:16, borderRadius:8,
                              background:"#fff", boxShadow:"0 1px 3px rgba(0,0,0,.2)",
                              transition:"left 0.2s" }} />
                          </div>
                          <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.72rem",
                            fontWeight:600, minWidth:45, flexShrink:0,
                            color: akte.portal_aktiv ? "#22c55e" : T.textFaint }}>
                            {akte.portal_aktiv ? "Sichtbar" : "Gesperrt"}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Info-Leiste */}
                    <div style={{ padding:"8px 18px", background:"#eff6ff",
                      borderTop:`1px solid #bfdbfe`,
                      fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem",
                      color:"#1d4ed8", display:"flex", alignItems:"center", gap:6,
                      flexShrink:0 }}>
                      ℹ {sv.vorname} {sv.name} sieht aktuell{" "}
                      <strong style={{ margin:"0 3px" }}>{sichtbar} von {svAkten.length} Akten</strong>
                      {" "}im Portal.
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        )}

        {tab === "system_status" && (
          <div style={{ maxWidth: 680 }}>
            <Card>
              <CardHead title="System-Status" />
              {sysLaedt && <p style={{ color: T.textSub, padding: "1rem" }}>Wird geladen…</p>}
              {!sysLaedt && sysStatus && (
                <div style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>

                  {/* RA-Micro */}
                  <div style={{ background: T.cardBg, borderRadius: 8, padding: "0.75rem 1rem", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                      <span style={{ width: 12, height: 12, borderRadius: "50%", display: "inline-block", flexShrink: 0,
                        background: sysStatus.ramicro.ok === true ? "#2ecc71" : sysStatus.ramicro.ok === false ? "#e74c3c" : "#f39c12" }} />
                      <div>
                        <div style={{ color: T.text, fontWeight: 600 }}>RA-Micro Datenbank</div>
                        <div style={{ color: T.textSub, fontSize: "0.8rem" }}>
                          {sysStatus.ramicro.ok === true && "Verbunden"}
                          {sysStatus.ramicro.ok === false && `Nicht erreichbar${sysStatus.ramicro.fehler ? ` – ${sysStatus.ramicro.fehler}` : ""}`}
                          {sysStatus.ramicro.ok === null && "Noch nicht geprüft"}
                          {sysStatus.ramicro.letzter_sync_vor_s != null && (
                            <span> · vor {sysStatus.ramicro.letzter_sync_vor_s < 60 ? "wenigen Sekunden" : `${Math.round(sysStatus.ramicro.letzter_sync_vor_s / 60)} Min`}</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <Btn
                      label={sysRetryLaedt ? "…" : "↺ Neu versuchen"}
                      disabled={sysRetryLaedt}
                      onClick={async () => {
                        setSysRetryLaedt(true);
                        try {
                          const updated = await apiSystem.retryRamicro();
                          setSysStatus(prev => ({ ...prev, ramicro: updated }));
                        } catch {}
                        finally { setSysRetryLaedt(false); }
                      }}
                    />
                  </div>

                  {/* IMAP */}
                  <div style={{ color: T.textSub, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.1em", padding: "0.5rem 0 0.25rem" }}>E-Mail (IMAP)</div>
                  <div style={{ background: T.cardBg, borderRadius: 8, padding: "0.75rem 1rem", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                      <span style={{ width: 10, height: 10, borderRadius: "50%", display: "inline-block", flexShrink: 0,
                        background: sysStatus.imap?.konfiguriert ? (sysStatus.imap.ok === true ? "#2ecc71" : sysStatus.imap.ok === false ? "#e74c3c" : "#f39c12") : "#888" }} />
                      <div>
                        <div style={{ color: T.text, fontWeight: 600 }}>{sysStatus.imap?.konfiguriert ? "IMAP konfiguriert" : "IMAP nicht konfiguriert"}</div>
                        <div style={{ color: T.textSub, fontSize: "0.8rem" }}>
                          {sysStatus.imap?.konfiguriert ? "Wird in US-02 um Polling erweitert" : "EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD in .env setzen"}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* SV-Portal */}
                  <div style={{ color: T.textSub, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.1em", padding: "0.5rem 0 0.25rem" }}>Externe Dienste</div>
                  <div style={{ background: T.cardBg, borderRadius: 8, padding: "0.75rem 1rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <span style={{ width: 10, height: 10, borderRadius: "50%", display: "inline-block", flexShrink: 0, background: "#888" }} />
                    <div>
                      <div style={{ color: T.text, fontWeight: 600 }}>SV-Portal</div>
                      <div style={{ color: T.textSub, fontSize: "0.8rem" }}>Noch nicht eingerichtet (US-03)</div>
                    </div>
                  </div>

                </div>
              )}
            </Card>
          </div>
        )}

        {/* Versicherer / Gutachter / Alle Vorlagen Tabs */}
        {tab !== "imap" && tab !== "fristen" && tab !== "ki" && tab !== "zustaendigkeit" && tab !== "sv_portal" && tab !== "system_status" && (
          <div>
            {/* Neue Vorlage anlegen */}
            <Card style={{ marginBottom:"1.25rem" }}>
              <CardHead title={tab === "versicherer" ? "Neuen Versicherer anlegen"
                             : tab === "gutachter"   ? "Neuen Gutachter anlegen"
                             : "Neue Vorlage anlegen"} />
              <div style={{ padding:"1rem 1.25rem",
                display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:"0.75rem", alignItems:"end" }}>
                <div>
                  <label style={{ display:"block", fontFamily:"'Figtree',sans-serif",
                    fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:4 }}>
                    Name / Organisation *
                  </label>
                  <input value={neuForm.name}
                    onChange={e => setNeuForm(p => ({...p, name:e.target.value}))}
                    placeholder="z.B. HUK-COBURG Versicherung"
                    style={inputStyle}/>
                </div>
                <div>
                  <label style={{ display:"block", fontFamily:"'Figtree',sans-serif",
                    fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:4 }}>
                    E-Mail-Domain *
                  </label>
                  <input value={neuForm.domain}
                    onChange={e => setNeuForm(p => ({...p, domain:e.target.value.replace("@","")}))}
                    placeholder="z.B. huk-coburg.de"
                    style={inputStyle}/>
                </div>
                <div>
                  <label style={{ display:"block", fontFamily:"'Figtree',sans-serif",
                    fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:4 }}>
                    Kategorie
                  </label>
                  <select value={neuForm.kategorie}
                    onChange={e => setNeuForm(p => ({...p, kategorie:e.target.value}))}
                    style={inputStyle}>
                    {KATEGORIEN.map(k => <option key={k.id} value={k.id}>{k.label}</option>)}
                  </select>
                </div>
                {neuForm.kategorie === "versicherung" && (<>
                  <div>
                    <label style={{ display:"block", fontFamily:"'Figtree',sans-serif",
                      fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:4 }}>
                      Versicherer-Anzeigename
                    </label>
                    <input value={neuForm.versicherer_name}
                      onChange={e => setNeuForm(p => ({...p, versicherer_name:e.target.value}))}
                      placeholder="z.B. HUK-COBURG"
                      style={inputStyle}/>
                  </div>
                  <div>
                    <label style={{ display:"block", fontFamily:"'Figtree',sans-serif",
                      fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:4 }}>
                      Kürzel
                    </label>
                    <input value={neuForm.kuerzel}
                      onChange={e => setNeuForm(p => ({...p, kuerzel:e.target.value.toUpperCase()}))}
                      placeholder="z.B. HUK"
                      style={inputStyle}/>
                  </div>
                </>)}
                <div style={{ gridColumn:"1/-1" }}>
                  <input value={neuForm.notizen}
                    onChange={e => setNeuForm(p => ({...p, notizen:e.target.value}))}
                    placeholder="Notizen (optional)"
                    style={inputStyle}/>
                </div>
                <div style={{ gridColumn:"1/-1", display:"flex", justifyContent:"flex-end" }}>
                  <Btn onClick={speichereNeu}
                    disabled={speichert || !neuForm.name || !neuForm.domain}>
                    {speichert ? "Speichern …" : "Speichern"}
                  </Btn>
                </div>
              </div>
            </Card>

            {/* Suche */}
            <div style={{ marginBottom:"0.75rem", display:"flex", alignItems:"center",
              gap:8, background:T.white, border:`1px solid ${T.border}`, borderRadius:8,
              padding:"6px 12px" }}>
              <span style={{ color:T.textFaint }}>🔍</span>
              <input value={suche} onChange={e => setSuche(e.target.value)}
                placeholder="Name, Domain oder Kürzel suchen …"
                style={{ flex:1, border:"none", outline:"none", background:"transparent",
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.935rem", color:T.text }}/>
              {suche && (
                <button onClick={() => setSuche("")}
                  style={{ background:"none", border:"none", cursor:"pointer",
                    color:T.textFaint, display:"flex" }}>{Ic.x}</button>
              )}
            </div>

            {/* Vorlagen-Liste */}
            <Card>
              <CardHead title={`${gefiltertVorlagen.length} Einträge${suche ? ` (gefiltert)` : ""}`} />
              {laedt ? (
                <div style={{ padding:"2rem", textAlign:"center", color:T.textFaint,
                  fontFamily:"'Figtree',sans-serif" }}>Lade …</div>
              ) : gefiltertVorlagen.length === 0 ? (
                <div style={{ padding:"2rem", textAlign:"center", color:T.textFaint,
                  fontFamily:"'Figtree',sans-serif" }}>
                  {suche ? "Keine Treffer." : "Noch keine Einträge."}
                </div>
              ) : (
                <div>
                  {gefiltertVorlagen.map((v, i) => {
                    const kat = katInfo(v.kategorie);
                    return (
                      <div key={v.id} style={{ display:"flex", alignItems:"center",
                        gap:12, padding:"9px 1.25rem",
                        borderBottom: i < gefiltertVorlagen.length-1
                          ? `1px solid ${T.borderSoft}` : "none",
                        opacity: v.aktiv ? 1 : 0.45,
                        transition:"opacity 0.15s" }}>
                        {/* Kürzel-Badge */}
                        {v.kuerzel ? (
                          <span style={{ fontFamily:"ui-monospace,monospace",
                            fontSize:"0.755rem", fontWeight:700, background:`${T.amber}18`,
                            color:T.amber, border:`1px solid ${T.amber}30`,
                            borderRadius:6, padding:"2px 7px", flexShrink:0,
                            minWidth:50, textAlign:"center" }}>{v.kuerzel}</span>
                        ) : (
                          <span style={{ display:"inline-flex", alignItems:"center",
                            background:`${kat.color}15`, color:kat.color,
                            border:`1px solid ${kat.color}30`, borderRadius:10,
                            padding:"2px 9px", fontSize:"0.815rem", fontWeight:600,
                            flexShrink:0 }}>{kat.label}</span>
                        )}
                        <div style={{ flex:1, minWidth:0 }}>
                          <div style={{ fontFamily:"'Figtree',sans-serif",
                            fontSize:"0.935rem", fontWeight:600, color:T.text }}>
                            {v.versicherer_name || v.name}
                          </div>
                          <div style={{ display:"flex", gap:8, alignItems:"center",
                            marginTop:1 }}>
                            <span style={{ fontFamily:"ui-monospace,monospace",
                              fontSize:"0.825rem", color:T.textMuted }}>@{v.domain}</span>
                            {v.versicherer_name && v.versicherer_name !== v.name && (
                              <span style={{ fontFamily:"'Figtree',sans-serif",
                                fontSize:"0.815rem", color:T.textFaint }}>{v.name}</span>
                            )}
                          </div>
                        </div>
                        <button onClick={() => toggleAktiv(v)}
                          style={{ padding:"3px 10px", border:`1px solid ${T.border}`,
                            borderRadius:6, background:T.white, cursor:"pointer",
                            fontFamily:"'Figtree',sans-serif", fontSize:"0.815rem",
                            color: v.aktiv ? T.green : T.textMuted, fontWeight:600,
                            flexShrink:0 }}>
                          {v.aktiv ? "✓ Aktiv" : "Inaktiv"}
                        </button>
                        <button onClick={() => loeschen(v.id)}
                          style={{ padding:"4px 8px", border:"none", borderRadius:6,
                            background:"transparent", cursor:"pointer", color:T.red,
                            display:"flex", alignItems:"center", flexShrink:0 }}>
                          {Ic.trash}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Log-Eintrag normalisieren ─────────────────────────────────────────────────


export default EinstellungenView;
