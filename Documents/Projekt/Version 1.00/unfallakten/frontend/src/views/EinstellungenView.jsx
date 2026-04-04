import React, { useState, useEffect } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { KATEGORIEN } from "../config/constants.js";
import { Card, CardHead, Btn, Toast } from "../components/common.jsx";
import {
  emailImport as apiEmail,
  apiEinstellungen,
} from "../api.js";

function EinstellungenView() {
  const [tab, setTab]           = useState("versicherer");
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

  // Klassifikations-Trainingsdaten
  const [training, setTraining] = useState(null);

  const ladeVorlagen = async () => {
    setLaedt(true);
    try {
      const res = await apiEmail.vorlagen();
      setVorlagen(res?.vorlagen || []);
    } catch { setVorlagen([]); }
    finally { setLaedt(false); }
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
  }, []);

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
    borderRadius:7, fontFamily:"'IBM Plex Sans',sans-serif",
    fontSize:"0.945rem", outline:"none", boxSizing:"border-box",
    background:T.white,
  };

  return (
    <div style={{ flex:1, overflowY:"auto", background:T.offWhite }}>
      {toast && <Toast msg={toast} onDone={() => setToast("")}/>}
      <div style={{ maxWidth:1000, margin:"0 auto", padding:"1.75rem" }}>

        <h1 style={{ fontFamily:"'Plus Jakarta Sans',sans-serif", fontSize:"2rem",
          fontWeight:700, color:T.navy, margin:"0 0 1.5rem 0" }}>Einstellungen</h1>

        {/* Tab-Leiste */}
        <div style={{ display:"flex", gap:4, marginBottom:"1.5rem",
          borderBottom:`1px solid ${T.border}` }}>
          {[
            ["versicherer", "🏦 Versicherer"],
            ["gutachter",   "🔍 Gutachter"],
            ["absender",    "📋 Alle Vorlagen"],
            ["imap",        "📧 IMAP"],
            ["fristen",     "⏱ Fristen"],
          ].map(([id, label]) => (
            <button key={id} onClick={() => { setTab(id); setSuche(""); }}
              style={{ padding:"8px 18px", border:"none", background:"transparent",
                fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.95rem", fontWeight:600,
                color: tab===id ? T.navy : T.textMuted, cursor:"pointer",
                borderBottom: tab===id ? `2px solid ${T.gold}` : "2px solid transparent",
                marginBottom:-1 }}>
              {label}
              {id !== "imap" && id !== "fristen" && (
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
          <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.955rem",
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
              border:`1px solid ${T.border}`, fontFamily:"'IBM Plex Sans',sans-serif",
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
                  { tageKey:"stufe3_tage", textKey:"stufe3_text", label:"Stufe 3 – Klage-Ankündigung", farbe:"#ef4444", desc:"Unmissverständliche Ankündigung gerichtlicher Schritte" },
                ].map(({ tageKey, textKey, label, farbe, desc }, idx, arr) => (
                  <div key={tageKey} style={{ borderBottom: idx < arr.length-1 ? `1px solid ${T.border}` : "none", paddingBottom:"1.25rem" }}>

                    {/* Stufen-Header */}
                    <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:4 }}>
                      <div style={{ width:10, height:10, borderRadius:"50%", background:farbe, flexShrink:0 }} />
                      <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.9rem",
                        fontWeight:700, color:T.text }}>{label}</span>
                    </div>
                    <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.825rem",
                      color:T.textFaint, marginBottom:10, paddingLeft:20 }}>{desc}</div>

                    {/* Frist-Eingabe */}
                    <div style={{ display:"flex", alignItems:"center", gap:10, paddingLeft:20, marginBottom:12 }}>
                      <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.875rem",
                        fontWeight:600, color:T.textMuted, minWidth:50 }}>Frist:</span>
                      <input
                        type="number" min={1} max={365}
                        value={fristen[tageKey] ?? ""}
                        onChange={e => setFristen(p => ({ ...p, [tageKey]: parseInt(e.target.value) || 1 }))}
                        style={{ ...inputStyle, width:80, textAlign:"center",
                          fontFamily:"'IBM Plex Mono',monospace", fontSize:"1rem", fontWeight:600 }}
                      />
                      <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.875rem", color:T.textMuted }}>
                        Tage
                      </span>
                    </div>

                    {/* Brieftext-Vorlage */}
                    <div style={{ paddingLeft:20 }}>
                      <div style={{ display:"flex", alignItems:"baseline", justifyContent:"space-between", marginBottom:5 }}>
                        <label style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.8rem",
                          fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.06em" }}>
                          Brieftext-Vorlage
                        </label>
                        <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.755rem",
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
                          fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.875rem" }}
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
                <p style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.895rem",
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
                        <span style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.855rem",
                          fontWeight:600, color:T.text }}>
                          Gesammelte Korrekturen
                        </span>
                        <span style={{ fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.855rem",
                          color: training.bereit ? T.green : T.textMuted }}>
                          {training.gesamt} / {training.ziel}
                        </span>
                      </div>
                      <div style={{ height:8, borderRadius:4, background:T.borderSoft, overflow:"hidden" }}>
                        <div style={{
                          height:"100%", borderRadius:4,
                          width: `${Math.min(100, Math.round(training.gesamt / training.ziel * 100))}%`,
                          background: training.bereit ? T.green : T.gold,
                          transition:"width 0.4s ease",
                        }}/>
                      </div>
                    </div>

                    {/* Status */}
                    <div style={{
                      padding:"0.65rem 1rem", borderRadius:8,
                      background: training.bereit ? (T.green + "18") : (T.amber + "15"),
                      border: `1px solid ${training.bereit ? T.green : T.amber}44`,
                      fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.855rem",
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
                            fontFamily:"'IBM Plex Mono',monospace", fontSize:"0.8rem",
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

        {/* Versicherer / Gutachter / Alle Vorlagen Tabs */}
        {tab !== "imap" && tab !== "fristen" && (
          <div>
            {/* Neue Vorlage anlegen */}
            <Card style={{ marginBottom:"1.25rem" }}>
              <CardHead title={tab === "versicherer" ? "Neuen Versicherer anlegen"
                             : tab === "gutachter"   ? "Neuen Gutachter anlegen"
                             : "Neue Vorlage anlegen"} />
              <div style={{ padding:"1rem 1.25rem",
                display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:"0.75rem", alignItems:"end" }}>
                <div>
                  <label style={{ display:"block", fontFamily:"'IBM Plex Sans',sans-serif",
                    fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:4 }}>
                    Name / Organisation *
                  </label>
                  <input value={neuForm.name}
                    onChange={e => setNeuForm(p => ({...p, name:e.target.value}))}
                    placeholder="z.B. HUK-COBURG Versicherung"
                    style={inputStyle}/>
                </div>
                <div>
                  <label style={{ display:"block", fontFamily:"'IBM Plex Sans',sans-serif",
                    fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:4 }}>
                    E-Mail-Domain *
                  </label>
                  <input value={neuForm.domain}
                    onChange={e => setNeuForm(p => ({...p, domain:e.target.value.replace("@","")}))}
                    placeholder="z.B. huk-coburg.de"
                    style={inputStyle}/>
                </div>
                <div>
                  <label style={{ display:"block", fontFamily:"'IBM Plex Sans',sans-serif",
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
                    <label style={{ display:"block", fontFamily:"'IBM Plex Sans',sans-serif",
                      fontSize:"0.825rem", fontWeight:600, color:T.textMuted, marginBottom:4 }}>
                      Versicherer-Anzeigename
                    </label>
                    <input value={neuForm.versicherer_name}
                      onChange={e => setNeuForm(p => ({...p, versicherer_name:e.target.value}))}
                      placeholder="z.B. HUK-COBURG"
                      style={inputStyle}/>
                  </div>
                  <div>
                    <label style={{ display:"block", fontFamily:"'IBM Plex Sans',sans-serif",
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
                  fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.935rem", color:T.text }}/>
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
                  fontFamily:"'IBM Plex Sans',sans-serif" }}>Lade …</div>
              ) : gefiltertVorlagen.length === 0 ? (
                <div style={{ padding:"2rem", textAlign:"center", color:T.textFaint,
                  fontFamily:"'IBM Plex Sans',sans-serif" }}>
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
                          <span style={{ fontFamily:"'IBM Plex Mono',monospace",
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
                          <div style={{ fontFamily:"'IBM Plex Sans',sans-serif",
                            fontSize:"0.935rem", fontWeight:600, color:T.text }}>
                            {v.versicherer_name || v.name}
                          </div>
                          <div style={{ display:"flex", gap:8, alignItems:"center",
                            marginTop:1 }}>
                            <span style={{ fontFamily:"'IBM Plex Mono',monospace",
                              fontSize:"0.825rem", color:T.textMuted }}>@{v.domain}</span>
                            {v.versicherer_name && v.versicherer_name !== v.name && (
                              <span style={{ fontFamily:"'IBM Plex Sans',sans-serif",
                                fontSize:"0.815rem", color:T.textFaint }}>{v.name}</span>
                            )}
                          </div>
                        </div>
                        <button onClick={() => toggleAktiv(v)}
                          style={{ padding:"3px 10px", border:`1px solid ${T.border}`,
                            borderRadius:6, background:T.white, cursor:"pointer",
                            fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.815rem",
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
