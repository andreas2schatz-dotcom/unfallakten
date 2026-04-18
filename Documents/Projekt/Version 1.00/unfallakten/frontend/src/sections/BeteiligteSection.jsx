import React, { useState } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { ROLLEN, ROLLEN_MIT_AZ, ROLLEN_C } from "../config/constants.js";
import { Card, CardHead, Btn, FieldInput, FieldSelect, Toast, SlidePanel } from "../components/common.jsx";
import {
  beteiligte as apiBeteiligte,
  portalEinladen,
} from "../api.js";

function BeteiligteSection({ beteiligte, dispatch, akteId }) {
  const [panelOpen, setPOpen] = useState(false);
  const [editItem, setEdit]   = useState(null);
  const [form, setForm]       = useState({});
  const [toast, setToast]     = useState("");

  const empty = { rolle:"mandant", name:"", vorname:"", firma:"", email:"", telefon:"", anschrift:"", plz:"", ort:"", kfz:"", kfz_typ:"", versicherung:"", vers_nr:"", schaden_nr:"", iban:"", aktenzeichen:"", notizen:"" };
  const F = (k, l, t="text", ph="") => <FieldInput label={l} value={form[k]||""} onChange={v => setForm(p => ({...p,[k]:v}))} type={t} placeholder={ph} />;

  const [betSaving, setBetSaving] = useState(false);

  const save = async () => {
    if (!form.name) { alert("Name ist Pflichtfeld."); return; }
    setBetSaving(true);
    const betData = { ...form, id: editItem?.id || Date.now() };
    try {
      if (editItem?.id && typeof editItem.id === "number" && editItem.id < 1e12) {
        // Echter DB-Record → PATCH
        await apiBeteiligte.aktualisieren(akteId, editItem.id, form);
      } else {
        // Neuer Beteiligter → POST
        const created = await apiBeteiligte.erstellen(akteId, form);
        if (created?.id) betData.id = created.id;
      }
    } catch { /* Demo-Modus */ }
    dispatch({ type:"SAVE_BETEILIGTER", akteId, beteiligter: betData });
    setBetSaving(false);
    setPOpen(false);
    setToast(editItem ? "Beteiligter gespeichert." : "Beteiligter hinzugefügt.");
  };

  const handlePortalEinladen = async (beteiligter) => {
    if (!beteiligter.email) {
      setToast("Keine E-Mail-Adresse hinterlegt");
      return;
    }
    try {
      await portalEinladen(akteId, {
        beteiligter_id: beteiligter.id,
        email: beteiligter.email,
        rolle: beteiligter.rolle === "mandant" ? "privatmandant" : beteiligter.rolle,
      });
      setToast(`Einladung für ${beteiligter.name} gespeichert`);
    } catch (err) {
      console.error("Portal-Einladung fehlgeschlagen:", err);
      setToast("Einladung fehlgeschlagen");
    }
  };

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <Card>
        <CardHead title={`Beteiligte (${beteiligte.length})`} action={<Btn size="sm" onClick={() => { setEdit(null); setForm(empty); setPOpen(true); }}>{Ic.plus} Hinzufügen</Btn>} />
        {beteiligte.length === 0 ? (
          <div style={{ padding:"2rem", textAlign:"center", fontFamily:"'Figtree',sans-serif", fontSize:"0.975rem", color:T.textFaint }}>Noch keine Beteiligten erfasst.</div>
        ) : (
          <div style={{ overflowX:"auto" }}>
            <table style={{ width:"100%", borderCollapse:"collapse" }}>
              <thead><tr style={{ background:T.surface }}>{["Rolle","Name / Firma","Kontakt","KFZ","Versicherung",""].map(h => <th key={h} style={{ padding:"8px 14px", textAlign:"left", fontFamily:"'Figtree',sans-serif", fontSize:"0.815rem", fontWeight:600, color:T.textMuted, letterSpacing:"0.06em", textTransform:"uppercase", borderBottom:`1px solid ${T.border}` }}>{h}</th>)}</tr></thead>
              <tbody>
                {beteiligte.map((b, i) => {
                  const rc = ROLLEN_C[b.rolle] || ROLLEN_C.sonstiger;
                  return (
                    <tr key={b.id} style={{ borderBottom:`1px solid ${T.borderSoft}`, background:i%2===0?T.white:T.surface }}>
                      <td style={{ padding:"10px 14px" }}>
                        <span style={{ display:"inline-flex", alignItems:"center", gap:4, background:rc.bg, color:rc.c, border:`1px solid ${rc.c}33`, borderRadius:12, padding:"2px 8px", fontSize:"0.825rem", fontWeight:600 }}>
                          {ROLLEN.find(r => r.value===b.rolle)?.label || b.rolle}
                        </span>
                      </td>
                      <td style={{ padding:"10px 14px" }}>
                        <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.975rem", fontWeight:600, color:T.navy }}>{b.name}{b.vorname ? ` ${b.vorname}` : ""}</div>
                        {b.firma && <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", color:T.textMuted }}>{b.firma}</div>}
                        {(b.anschrift||b.ort) && <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.825rem", color:T.textFaint }}>{b.anschrift}{b.plz?` · ${b.plz}`:""}{b.ort?` ${b.ort}`:""}</div>}
                      </td>
                      <td style={{ padding:"10px 14px" }}>
                        {b.email && <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.925rem", color:T.textMid }}>{b.email}</div>}
                        {b.telefon && <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.895rem", color:T.textFaint }}>{b.telefon}</div>}
                      </td>
                      <td style={{ padding:"10px 14px" }}>
                        {b.kfz && <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.945rem", fontWeight:600, color:T.text }}>{b.kfz}</div>}
                        {b.kfz_typ && <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.865rem", color:T.textFaint }}>{b.kfz_typ}</div>}
                      </td>
                      <td style={{ padding:"10px 14px" }}>
                        {b.versicherung && <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.945rem", color:T.textMid }}>{b.versicherung}</div>}
                        {b.vers_nr && <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.845rem", color:T.textFaint }}>{b.vers_nr}</div>}
                        {b.schaden_nr && <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.845rem", color:T.textFaint }}>SN: {b.schaden_nr}</div>}
                      </td>
                      <td style={{ padding:"10px 14px" }}>
                        <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
                          <div style={{ display:"flex", gap:4 }}>
                            <Btn size="sm" variant="secondary" onClick={() => { setEdit(b); setForm({...b}); setPOpen(true); }}>{Ic.edit}</Btn>
                            <Btn size="sm" variant="danger"    onClick={async () => { if (confirm("Beteiligten entfernen?")) {
                            try { await apiBeteiligte.loeschen(akteId, b.id); } catch { /* Demo */ }
                            dispatch({ type:"DELETE_BETEILIGTER", akteId, id:b.id });
                          }; }}>{Ic.trash}</Btn>
                          </div>
                          {(b.rolle === "sachverstaendiger" || b.rolle === "mandant") && b.email && (
                            <Btn size="sm" variant="secondary" onClick={() => handlePortalEinladen(b)}>
                              Portal einladen
                            </Btn>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <SlidePanel open={panelOpen} onClose={() => setPOpen(false)} title={editItem ? "Beteiligten bearbeiten" : "Beteiligten hinzufügen"}>
        <div style={{ display:"flex", flexDirection:"column", gap:13 }}>
          <FieldSelect label="Rolle" value={form.rolle||"mandant"} onChange={v => setForm(p => ({...p,rolle:v}))} options={ROLLEN} />
          {ROLLEN_MIT_AZ.has(form.rolle) && (
            <div style={{ background:T.surface, border:`1.5px solid ${T.border}`, borderRadius:8, padding:"10px 12px", display:"flex", flexDirection:"column", gap:4 }}>
              {F("aktenzeichen","Aktenzeichen",undefined,"z.B. 123 Js 456/25")}
            </div>
          )}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>{F("name","Nachname *")} {F("vorname","Vorname")}</div>
          {F("firma","Firma / Organisation")}
          <hr style={{ border:"none", borderTop:`1px solid ${T.border}`, margin:"2px 0" }} />
          {F("anschrift","Anschrift")}
          <div style={{ display:"grid", gridTemplateColumns:"90px 1fr", gap:10 }}>{F("plz","PLZ")} {F("ort","Ort")}</div>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>{F("email","E-Mail","email")} {F("telefon","Telefon","tel")}</div>
          <hr style={{ border:"none", borderTop:`1px solid ${T.border}`, margin:"2px 0" }} />
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>{F("kfz","KFZ-Kennzeichen",undefined,"OF-AB 123")} {F("kfz_typ","Fahrzeugtyp",undefined,"VW Passat")}</div>
          {F("versicherung","Versicherung")}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>{F("vers_nr","Vers.-Nr.")} {F("schaden_nr","Schaden-Nr.")}</div>
          {F("iban","IBAN")}
          <hr style={{ border:"none", borderTop:`1px solid ${T.border}`, margin:"2px 0" }} />
          <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
            <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem", fontWeight:600, color:T.textMid, letterSpacing:"0.05em", textTransform:"uppercase" }}>Notizen</label>
            <textarea value={form.notizen||""} onChange={e => setForm(p => ({...p,notizen:e.target.value}))} rows={3} style={{ padding:"8px 10px", border:`1.5px solid ${T.border}`, borderRadius:7, fontFamily:"'Figtree',sans-serif", fontSize:"0.975rem", color:T.text, background:T.surface, outline:"none", resize:"vertical" }} onFocus={e => e.target.style.borderColor=T.accent} onBlur={e => e.target.style.borderColor=T.border} />
          </div>
          <div style={{ display:"flex", gap:8, paddingTop:4 }}>
            <Btn variant="primary" onClick={save} disabled={betSaving} style={{ flex:1 }}>
              {betSaving ? <><div style={{ width:12, height:12, border:"2px solid rgba(255,255,255,0.3)", borderTopColor:"white", borderRadius:"50%", animation:"spin 0.7s linear infinite" }}/> Speichern …</> : <>{Ic.check} Speichern</>}
            </Btn>
            <Btn variant="secondary" onClick={() => setPOpen(false)}>Abbrechen</Btn>
          </div>
        </div>
      </SlidePanel>
    </>
  );
}



export default BeteiligteSection;
