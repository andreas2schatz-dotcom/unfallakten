import React, { useState, useEffect } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { Btn, FieldInput, apiErrMsg } from "./common.jsx";
import { auth as apiAuth } from "../api.js";

function LoginPage({ onLogin }) {
  const [email, setEmail] = useState("koch@anwalt-offenbach.de");
  const [pw, setPw]       = useState("Kanzlei2024!");
  const [loading, setL]   = useState(false);
  const [fehler, setF]    = useState("");
  const [ok, setOk]       = useState(false);

  useEffect(() => { setTimeout(() => setOk(true), 60); }, []);

  const submit = async () => {
    setF("");
    if (!email || !pw) { setF("Bitte alle Felder ausfüllen."); return; }
    setL(true);
    try {
      const benutzer = await apiAuth.login(email, pw);
      if (benutzer) { onLogin(benutzer); return; }
      throw new Error("Keine Benutzerdaten erhalten.");
    } catch (apiErr) {

      setF(apiErr.status === 401 ? "Ungültige E-Mail oder Passwort." : apiErrMsg(apiErr));
    } finally {
      setL(false);
    }
  };

  const inp = {
    width:"100%", padding:"11px 14px", border:`1.5px solid ${T.border}`,
    borderRadius:8, fontSize:"1.045rem", fontFamily:"'IBM Plex Sans',sans-serif",
    color:T.text, background:T.surface, outline:"none", boxSizing:"border-box",
  };

  return (
    <div style={{ minHeight:"100vh", display:"flex", alignItems:"center", justifyContent:"center",
      background:"#ffffff", position:"relative", overflow:"hidden" }}>

      {/* Dezente Linie oben in Kanzleifarbe */}
      <div style={{ position:"fixed", top:0, left:0, right:0, height:4,
        background:`linear-gradient(90deg,${T.navy},${T.gold},${T.navy})` }} />

      {/* Zentrierte Login-Card */}
      <div style={{ position:"relative", width:"100%", maxWidth:440, padding:"1.5rem",
        opacity:ok?1:0, transform:ok?"none":"translateY(24px)",
        transition:"all 0.6s cubic-bezier(0.16,1,0.3,1)" }}>

        {/* Logo & Kanzleiname – § links neben dem Namen */}
        <div style={{ display:"flex", alignItems:"center", gap:18, marginBottom:"2rem", justifyContent:"center" }}>
          {/* Blaues §-Logo */}
          <div style={{ width:64, height:64, background:T.navy, borderRadius:16, flexShrink:0,
            display:"flex", alignItems:"center", justifyContent:"center",
            boxShadow:`0 8px 24px ${T.navy}44` }}>
            <svg viewBox="0 0 40 40" fill="white" style={{width:40,height:40}}>
              <text x="20" y="30" textAnchor="middle"
                fontFamily="Georgia,'Times New Roman',serif"
                fontSize="30" fontWeight="bold">§</text>
            </svg>
          </div>
          {/* Kanzleiname */}
          <div>
            <div style={{ fontFamily:"'Plus Jakarta Sans',sans-serif",
              fontSize:"22px", fontWeight:700, color:T.navy,
              letterSpacing:"0.01em", lineHeight:1.2 }}>
              Koch, Schatz &amp; Kollegen
            </div>
            <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.78rem",
              color:T.textMuted, letterSpacing:"0.1em", textTransform:"uppercase",
              marginTop:3 }}>
              Rechtsanwälte · Offenbach am Main
            </div>
          </div>
        </div>

        {/* Card */}
        <div style={{ background:"#ffffff", borderRadius:16, padding:"2.4rem 2.6rem",
          boxShadow:"0 4px 32px rgba(0,0,0,0.08), 0 0 0 1.5px rgba(15,30,64,0.10)" }}>
          <div style={{ fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"1.1rem",
            fontWeight:600, color:T.navy, marginBottom:"1.6rem",
            paddingBottom:"1rem", borderBottom:`1.5px solid ${T.border}` }}>
            Anmelden
          </div>
          {fehler && (
            <div style={{ background:T.redBg, border:`1px solid ${T.red}55`, borderRadius:8,
              padding:"10px 14px", marginBottom:"1.2rem",
              fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.955rem", color:T.red }}>
              {fehler}
            </div>
          )}
          <div style={{ marginBottom:"1.2rem" }}>
            <label style={{ display:"block", fontFamily:"'IBM Plex Sans',sans-serif",
              fontSize:"0.82rem", fontWeight:600, color:T.textMid,
              letterSpacing:"0.06em", textTransform:"uppercase", marginBottom:6 }}>
              E-Mail
            </label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)}
              onKeyDown={e => e.key==="Enter"&&submit()} style={inp}
              onFocus={e=>e.target.style.borderColor=T.navy}
              onBlur={e=>e.target.style.borderColor=T.border} />
          </div>
          <div style={{ marginBottom:"1.6rem" }}>
            <label style={{ display:"block", fontFamily:"'IBM Plex Sans',sans-serif",
              fontSize:"0.82rem", fontWeight:600, color:T.textMid,
              letterSpacing:"0.06em", textTransform:"uppercase", marginBottom:6 }}>
              Passwort
            </label>
            <input type="password" value={pw} onChange={e => setPw(e.target.value)}
              onKeyDown={e => e.key==="Enter"&&submit()} style={inp}
              onFocus={e=>e.target.style.borderColor=T.navy}
              onBlur={e=>e.target.style.borderColor=T.border} />
          </div>
          <button onClick={submit} disabled={loading} style={{
            width:"100%", padding:"13px", background:T.navy, color:T.white,
            border:"none", borderRadius:8, fontFamily:"'IBM Plex Sans',sans-serif",
            fontSize:"1rem", fontWeight:600, cursor:loading?"default":"pointer",
            position:"relative", overflow:"hidden",
            boxShadow:`0 4px 12px ${T.navy}44`,
            transition:"opacity 0.15s" }}>
            {loading ? "Anmelden …" : "Anmelden"}
            <div style={{ position:"absolute", bottom:0, left:0, right:0, height:3,
              background:`linear-gradient(90deg,${T.gold},${T.goldLight},${T.gold})` }} />
          </button>
        </div>

        {/* Footer */}
        <div style={{ textAlign:"center", marginTop:"1.5rem",
          fontFamily:"'IBM Plex Sans',sans-serif", fontSize:"0.78rem",
          color:T.textFaint }}>
          Unfallakten-Verwaltung · Intern
        </div>
      </div>
    </div>
  );
}



export default LoginPage;
