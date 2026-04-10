import React, { useState, useEffect } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { KATEGORIE_CFG } from "../config/constants.js";
import { Card, CardHead, Btn, FieldInput, FieldSelect, Toast } from "../components/common.jsx";
import {
  kuerzungsarten as apiKuerzungsarten,
} from "../api.js";

function KuerzungskatalogSection() {
  const [arten, setArten]           = useState([]);
  const [loading, setLoading]       = useState(true);
  const [showForm, setShowForm]     = useState(false);
  const [editItem, setEditItem]     = useState(null);
  const [filterKat, setFilterKat]   = useState("alle");
  const [toast, setToast]           = useState("");
  const [form, setForm]             = useState({
    bezeichnung:"", kategorie:"fahrzeugschaden",
    standard_gegenargument:"", rechtsgrundlagen:"",
    hinweis_intern:"", sv_stellungnahme_erforderlich:false,
    textbaustein:"",
    sortierung:999,
  });

  const ladeArten = async () => {
    setLoading(true);
    try {
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Timeout: Server antwortet nicht (>10 s). Bitte Backend-Logs prüfen.")), 10000)
      );
      const r = await Promise.race([apiKuerzungsarten.liste(false), timeoutPromise]);
      setArten(r?.kuerzungsarten || []);
    } catch (e) {
      setToast("Kürzungskatalog konnte nicht geladen werden: " + (e?.message || String(e)));
      setArten([]);
    } finally {
      setLoading(false);
    }
  };

  // Bug 1: useEffect statt useState für Datenladen
  useEffect(() => { ladeArten(); }, []);

  const F = (k) => (v) => setForm(p => ({ ...p, [k]: v }));

  const resetForm = () => setForm({
    bezeichnung:"", kategorie:"fahrzeugschaden",
    standard_gegenargument:"", rechtsgrundlagen:"",
    hinweis_intern:"", sv_stellungnahme_erforderlich:false, textbaustein:"", sortierung:999,
  });

  const startEdit = (art) => {
    setEditItem(art.id);
    setForm({
      bezeichnung: art.bezeichnung,
      kategorie: art.kategorie,
      standard_gegenargument: art.standard_gegenargument || "",
      rechtsgrundlagen: art.rechtsgrundlagen || "",
      hinweis_intern: art.hinweis_intern || "",
      sv_stellungnahme_erforderlich: art.sv_stellungnahme_erforderlich || false,
      textbaustein: art.textbaustein || "",
      sortierung: art.sortierung || 0,
    });
    setShowForm(true);
  };

  const save = async () => {
    if (!form.bezeichnung.trim()) { alert("Bezeichnung ist erforderlich."); return; }
    try {
      if (editItem) {
        const r = await apiKuerzungsarten.update(editItem, form);
        setArten(prev => prev.map(a => a.id === editItem ? r.kuerzungsart : a));
        setToast("Kürzungsart aktualisiert.");
      } else {
        const r = await apiKuerzungsarten.erstelle(form);
        setArten(prev => [...prev, r.kuerzungsart]);
        setToast("Kürzungsart angelegt.");
      }
      setShowForm(false);
      setEditItem(null);
      resetForm();
    } catch (e) {
      setToast("Speichern fehlgeschlagen: " + (e?.message || String(e)));
    }
  };

  const toggleAktiv = async (art) => {
    try {
      await apiKuerzungsarten.toggleAktiv(art.id, !art.aktiv);
      setArten(prev => prev.map(a => a.id === art.id ? { ...a, aktiv: !a.aktiv } : a));
    } catch (e) {
      setToast("Status konnte nicht geändert werden: " + (e?.message || String(e)));
    }
  };

  const gefiltert = filterKat === "alle" ? arten : arten.filter(a => a.kategorie === filterKat);
  const grupppen = Object.keys(KATEGORIE_CFG).reduce((acc, k) => {
    acc[k] = gefiltert.filter(a => a.kategorie === k);
    return acc;
  }, {});

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <div style={{ display:"flex", flexDirection:"column", gap:"1.25rem" }}>

        <Card>
          <CardHead
            title={`Kürzungskatalog (${arten.length} Einträge)`}
            action={
              <div style={{ display:"flex", gap:8, alignItems:"center" }}>
                <select
                  value={filterKat}
                  onChange={e => setFilterKat(e.target.value)}
                  style={{ padding:"5px 10px", border:`1px solid ${T.border}`, borderRadius:7, fontSize:"0.875rem", background:T.surface, color:T.text, cursor:"pointer" }}
                >
                  <option value="alle">Alle Kategorien</option>
                  {Object.entries(KATEGORIE_CFG).map(([k,v]) => (
                    <option key={k} value={k}>{v.label}</option>
                  ))}
                </select>
                <Btn size="sm" onClick={() => { setEditItem(null); resetForm(); setShowForm(o => !o); }}>
                  {Ic.plus} Neue Kürzungsart
                </Btn>
              </div>
            }
          />

          {/* Formular */}
          {showForm && (
            <div style={{ margin:"0 1.4rem 1rem", background:T.goldPale, border:`1px solid ${T.goldTrim}`, borderRadius:10, padding:"1.1rem 1.25rem" }}>
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", fontWeight:600, color:T.navy, textTransform:"uppercase", letterSpacing:"0.07em", marginBottom:"1rem" }}>
                {editItem ? "Kürzungsart bearbeiten" : "Neue Kürzungsart"}
              </div>
              <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(200px,1fr))", gap:"0.9rem", marginBottom:"0.9rem" }}>
                <FieldInput label="Bezeichnung *" value={form.bezeichnung} onChange={F("bezeichnung")} placeholder="z.B. Lackierkosten" />
                <FieldSelect label="Kategorie" value={form.kategorie} onChange={F("kategorie")}
                  options={Object.entries(KATEGORIE_CFG).map(([k,v]) => ({value:k, label:v.label}))} />
                <FieldInput label="Rechtsgrundlagen" value={form.rechtsgrundlagen} onChange={F("rechtsgrundlagen")} placeholder="z.B. BGH VI ZR 398/02" />
                <FieldInput label="Interner Hinweis" value={form.hinweis_intern} onChange={F("hinweis_intern")} placeholder="z.B. auch fiktiv" />
              </div>
              <div style={{ marginBottom:"0.9rem" }}>
                <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem", fontWeight:600, color:T.textMid, textTransform:"uppercase", letterSpacing:"0.05em", display:"block", marginBottom:4 }}>
                  Standard-Gegenargument
                </label>
                <textarea
                  value={form.standard_gegenargument}
                  onChange={e => setForm(p => ({...p, standard_gegenargument: e.target.value}))}
                  rows={3}
                  placeholder="Bewährte Argumentation für den Klage-Generator …"
                  style={{ width:"100%", padding:"8px 10px", border:`1.5px solid ${T.border}`, borderRadius:7, fontFamily:"'Figtree',sans-serif", fontSize:"0.925rem", color:T.text, background:T.surface, outline:"none", resize:"vertical", lineHeight:1.5 }}
                  onFocus={e => e.target.style.borderColor=T.gold}
                  onBlur={e => e.target.style.borderColor=T.border}
                />
              </div>
              <div style={{ marginBottom:"0.9rem" }}>
                <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem", fontWeight:600, color:T.textMid, textTransform:"uppercase", letterSpacing:"0.05em", display:"block", marginBottom:4 }}>
                  Textbaustein Stellungnahme
                  <span style={{ fontWeight:400, textTransform:"none", fontSize:"0.78rem", color:T.textFaint, marginLeft:6 }}>
                    (ausführlicher Brieftext – wenn leer: Standard-Gegenargument wird verwendet)
                  </span>
                </label>
                <textarea
                  value={form.textbaustein}
                  onChange={e => setForm(p => ({...p, textbaustein: e.target.value}))}
                  rows={5}
                  placeholder="Ausführlicher briefreifer Text für Stellungnahmen zum Abrechnungsschreiben …"
                  style={{ width:"100%", padding:"8px 10px", border:`1.5px solid ${T.border}`, borderRadius:7, fontFamily:"'Figtree',sans-serif", fontSize:"0.925rem", color:T.text, background:T.surface, outline:"none", resize:"vertical", lineHeight:1.5 }}
                  onFocus={e => e.target.style.borderColor=T.gold}
                  onBlur={e => e.target.style.borderColor=T.border}
                />
              </div>
              <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:"1rem" }}>
                <input
                  type="checkbox"
                  id="sv_flag"
                  checked={form.sv_stellungnahme_erforderlich}
                  onChange={e => setForm(p => ({...p, sv_stellungnahme_erforderlich: e.target.checked}))}
                  style={{ width:15, height:15, cursor:"pointer" }}
                />
                <label htmlFor="sv_flag" style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.895rem", color:T.textMid, cursor:"pointer" }}>
                  SV-Stellungnahme erforderlich
                </label>
              </div>
              <div style={{ display:"flex", gap:8 }}>
                <Btn variant="gold" onClick={save}>{Ic.check} {editItem ? "Aktualisieren" : "Anlegen"}</Btn>
                <Btn variant="secondary" onClick={() => { setShowForm(false); setEditItem(null); resetForm(); }}>Abbrechen</Btn>
              </div>
            </div>
          )}

          {/* Tabelle gruppiert nach Kategorie */}
          {loading ? (
            <div style={{ padding:"2rem", textAlign:"center", color:T.textFaint, fontFamily:"'Figtree',sans-serif" }}>
              <div>Lade Kürzungskatalog …</div>
              <div style={{ fontSize:"0.8rem", marginTop:6, color:T.textFaint }}>
                Falls der Spinner nicht verschwindet:{" "}
                <button onClick={ladeArten} style={{ background:"none", border:"none", color:T.navy, cursor:"pointer", textDecoration:"underline", fontSize:"0.8rem", padding:0 }}>
                  Erneut versuchen
                </button>
              </div>
            </div>
          ) : (
            <div style={{ padding:"0 1.4rem 1rem" }}>
              {Object.entries(KATEGORIE_CFG).map(([kat, katCfg]) => {
                const eintraege = grupppen[kat] || [];
                if (eintraege.length === 0 && filterKat !== "alle") return null;
                return (
                  <div key={kat} style={{ marginBottom:"1.25rem" }}>
                    <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:"0.5rem" }}>
                      <span style={{ fontSize:"0.78rem", fontWeight:600, padding:"3px 10px", borderRadius:20, background:katCfg.bg, color:katCfg.color }}>
                        {katCfg.label}
                      </span>
                      <span style={{ fontSize:"0.82rem", color:T.textFaint, fontFamily:"'Figtree',sans-serif" }}>
                        {eintraege.length} {eintraege.length === 1 ? "Eintrag" : "Einträge"}
                      </span>
                    </div>
                    {eintraege.length === 0 ? (
                      <div style={{ padding:"0.75rem 1rem", border:`1px dashed ${T.border}`, borderRadius:8, fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", color:T.textFaint }}>
                        Keine Einträge in dieser Kategorie.
                      </div>
                    ) : (
                      <div style={{ border:`1px solid ${T.border}`, borderRadius:9, overflow:"hidden" }}>
                        {eintraege.map((art, i) => (
                          <div key={art.id}
                            style={{ padding:"0.8rem 1rem", borderBottom:i<eintraege.length-1?`1px solid ${T.border}`:"none", background:art.aktiv?T.white:"rgba(0,0,0,0.02)", opacity:art.aktiv?1:0.55 }}
                          >
                            <div style={{ display:"flex", alignItems:"flex-start", gap:10 }}>
                              <div style={{ flex:1 }}>
                                <div style={{ display:"flex", alignItems:"center", gap:8, flexWrap:"wrap", marginBottom:art.standard_gegenargument||art.hinweis_intern?4:0 }}>
                                  <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.935rem", fontWeight:600, color:art.aktiv?T.text:T.textFaint }}>
                                    {art.bezeichnung}
                                  </span>
                                  {art.sv_stellungnahme_erforderlich && (
                                    <span style={{ fontSize:"0.72rem", background:T.redBg, color:T.red, borderRadius:4, padding:"1px 5px", fontWeight:600 }}>SV erforderlich</span>
                                  )}
                                  {art.rechtsgrundlagen && (
                                    <span style={{ fontSize:"0.72rem", background:T.surface, color:T.textMuted, borderRadius:4, padding:"1px 5px", fontFamily:"ui-monospace,monospace" }}>
                                      {art.rechtsgrundlagen}
                                    </span>
                                  )}
                                  {!art.aktiv && (
                                    <span style={{ fontSize:"0.72rem", background:T.surface, color:T.textFaint, borderRadius:4, padding:"1px 5px" }}>inaktiv</span>
                                  )}
                                </div>
                                {art.standard_gegenargument && (
                                  <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem", color:T.textMuted, lineHeight:1.5, marginBottom:art.hinweis_intern?3:0 }}>
                                    {art.standard_gegenargument}
                                  </div>
                                )}
                                {art.textbaustein && (
                                  <div style={{ display:"inline-flex", alignItems:"center", gap:4, marginTop:2, marginBottom:art.hinweis_intern?3:0 }}>
                                    <span style={{ fontSize:"0.72rem", background:"#ede9fe", color:"#5b21b6", borderRadius:4, padding:"1px 6px", fontWeight:600 }}>
                                      📝 Textbaustein
                                    </span>
                                  </div>
                                )}
                                {art.hinweis_intern && (
                                  <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.82rem", color:T.amber, fontStyle:"italic" }}>
                                    Hinweis: {art.hinweis_intern}
                                  </div>
                                )}
                              </div>
                              <div style={{ display:"flex", gap:6, flexShrink:0 }}>
                                <button
                                  onClick={() => startEdit(art)}
                                  title="Bearbeiten"
                                  style={{ padding:"4px 9px", border:`1px solid ${T.border}`, borderRadius:6, background:T.surface, color:T.textMid, cursor:"pointer", fontSize:"0.8rem" }}
                                >
                                  ✏️
                                </button>
                                <button
                                  onClick={() => toggleAktiv(art)}
                                  title={art.aktiv ? "Deaktivieren" : "Aktivieren"}
                                  style={{ padding:"4px 9px", border:`1px solid ${T.border}`, borderRadius:6, background:art.aktiv?T.surface:T.greenBg, color:art.aktiv?T.textMuted:T.green, cursor:"pointer", fontSize:"0.8rem" }}
                                >
                                  {art.aktiv ? "⏸" : "▶"}
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}


export default KuerzungskatalogSection;
