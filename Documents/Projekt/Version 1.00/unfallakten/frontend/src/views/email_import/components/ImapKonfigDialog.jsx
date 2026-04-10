import React, { useState } from "react";
import T from "../../../config/theme.js";
import { Btn } from "../../../components/common.jsx";
import { emailImport as apiEmail } from "../../../api.js";

function ImapKonfigDialog({ cfg, onClose, onGespeichert }) {
  const [form, setForm] = useState({
    host:      cfg?.host      || "",
    port:      cfg?.port      || 993,
    user:      cfg?.user      || "",
    password:  "",
    folder:    cfg?.folder || cfg?.ordner || "INBOX",
    max_fetch: cfg?.max_fetch || 50,
  });
  const [saving, setSaving]   = useState(false);
  const [testOk, setTestOk]   = useState(null);
  const [testMsg, setTestMsg] = useState("");

  const F = (k) => (v) => setForm(p => ({ ...p, [k]: v }));

  const handleTest = async () => {
    setSaving(true); setTestOk(null); setTestMsg("");
    try {
      const res = await apiEmail.status();
      setTestOk(res?.verbindung_ok ?? false);
      setTestMsg(res?.nachricht || (res?.verbindung_ok ? "Verbindung erfolgreich." : "Verbindung fehlgeschlagen."));
    } catch (e) {
      setTestOk(false);
      setTestMsg("Verbindungstest fehlgeschlagen: " + (e?.message || String(e)));
    } finally {
      setSaving(false);
    }
  };

  const handleSpeichern = () => {
    onGespeichert({
      host:      form.host,
      port:      Number(form.port),
      user:      form.user,
      folder:    form.folder,
      max_fetch: Number(form.max_fetch),
    });
  };

  const fieldStyle = {
    width:"100%", padding:"8px 10px",
    border:`1.5px solid ${T.border}`, borderRadius:7,
    fontFamily:"ui-monospace,monospace", fontSize:"0.925rem",
    color:T.text, background:T.white, outline:"none", boxSizing:"border-box",
  };

  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.45)", zIndex:1000, display:"flex", alignItems:"center", justifyContent:"center", padding:"1rem" }}>
      <div style={{ background:T.white, borderRadius:12, width:"100%", maxWidth:520, boxShadow:"0 8px 40px rgba(0,0,0,0.18)", overflow:"hidden" }}>
        <div style={{ background:T.navy, padding:"1rem 1.4rem", display:"flex", justifyContent:"space-between", alignItems:"center" }}>
          <div>
            <div style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"1.15rem", fontWeight:700, color:T.white }}>
              IMAP-Konfiguration
            </div>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem", color:"rgba(255,255,255,0.5)", marginTop:2 }}>
              Werte werden in der <code style={{ color:T.gold }}>.env</code>-Datei gespeichert
            </div>
          </div>
          <button onClick={onClose} aria-label="Dialog schließen" style={{ background:"none", border:"none", color:"rgba(255,255,255,0.6)", fontSize:"1.4rem", cursor:"pointer", lineHeight:1 }}>×</button>
        </div>

        <div style={{ padding:"1.2rem 1.4rem", display:"flex", flexDirection:"column", gap:"0.85rem" }}>
          <div style={{ background:T.amberBg, border:`1px solid ${T.amber}44`, borderRadius:7, padding:"8px 12px", fontSize:"0.825rem", color:T.amber, fontFamily:"'Figtree',sans-serif" }}>
            ⚠ Änderungen werden nur in der Anzeige übernommen. Um die <code>.env</code>-Datei dauerhaft zu ändern, bitte manuell bearbeiten und den Server neu starten.
          </div>

          <div style={{ display:"grid", gridTemplateColumns:"1fr auto", gap:"0.75rem", alignItems:"start" }}>
            <div>
              <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.83rem", fontWeight:600, color:T.textMid, display:"block", marginBottom:4 }}>
                IMAP-Server <span style={{ color:T.textFaint, fontWeight:400 }}>(EMAIL_HOST)</span>
              </label>
              <input style={fieldStyle} value={form.host} onChange={e => F("host")(e.target.value)} placeholder="mail.anwalt-offenbach.de" />
            </div>
            <div>
              <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.83rem", fontWeight:600, color:T.textMid, display:"block", marginBottom:4 }}>
                Port <span style={{ color:T.textFaint, fontWeight:400 }}>(EMAIL_PORT)</span>
              </label>
              <input style={{ ...fieldStyle, width:80 }} type="number" value={form.port} onChange={e => F("port")(e.target.value)} placeholder="993" />
            </div>
          </div>

          <div>
            <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.83rem", fontWeight:600, color:T.textMid, display:"block", marginBottom:4 }}>
              Benutzername <span style={{ color:T.textFaint, fontWeight:400 }}>(EMAIL_USER)</span>
            </label>
            <input style={fieldStyle} value={form.user} onChange={e => F("user")(e.target.value)} placeholder="import@anwalt-offenbach.de" />
          </div>

          <div>
            <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.83rem", fontWeight:600, color:T.textMid, display:"block", marginBottom:4 }}>
              Passwort <span style={{ color:T.textFaint, fontWeight:400 }}>(EMAIL_PASSWORD)</span>
            </label>
            <input style={fieldStyle} type="password" value={form.password} onChange={e => F("password")(e.target.value)} placeholder="Nur ausfüllen wenn ändern" autoComplete="new-password" />
          </div>

          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0.75rem" }}>
            <div>
              <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.83rem", fontWeight:600, color:T.textMid, display:"block", marginBottom:4 }}>
                Ordner <span style={{ color:T.textFaint, fontWeight:400 }}>(EMAIL_FOLDER)</span>
              </label>
              <input style={fieldStyle} value={form.folder} onChange={e => F("folder")(e.target.value)} placeholder="INBOX" />
            </div>
            <div>
              <label style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.83rem", fontWeight:600, color:T.textMid, display:"block", marginBottom:4 }}>
                Max. E-Mails <span style={{ color:T.textFaint, fontWeight:400 }}>(EMAIL_MAX_FETCH)</span>
              </label>
              <input style={fieldStyle} type="number" min="1" max="200" value={form.max_fetch} onChange={e => F("max_fetch")(e.target.value)} placeholder="50" />
            </div>
          </div>

          {testMsg && (
            <div style={{ padding:"7px 12px", borderRadius:6, fontSize:"0.83rem", fontFamily:"'Figtree',sans-serif",
              background: testOk ? T.greenBg : T.redBg,
              color:      testOk ? T.green   : T.red,
              border:`1px solid ${testOk ? T.green : T.red}33` }}>
              {testOk ? "✓" : "✗"} {testMsg}
            </div>
          )}
        </div>

        <div style={{ padding:"0.85rem 1.4rem", borderTop:`1px solid ${T.border}`, display:"flex", gap:8, justifyContent:"flex-end" }}>
          <Btn variant="ghost" onClick={onClose}>Abbrechen</Btn>
          <Btn variant="secondary" onClick={handleTest} disabled={saving}>
            {saving ? "…" : "🔌 Verbindung testen"}
          </Btn>
          <Btn variant="gold" onClick={handleSpeichern}>
            Übernehmen
          </Btn>
        </div>
      </div>
    </div>
  );
}

export default ImapKonfigDialog;
