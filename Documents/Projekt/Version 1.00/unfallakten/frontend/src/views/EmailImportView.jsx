import React, { useState } from "react";
import T from "../config/theme.js";
import UnfallEmailView  from "./email_import/UnfallEmailView.jsx";
import TerminEmailView  from "./email_import/TerminEmailView.jsx";
import BussgeldEmailView from "./email_import/BussgeldEmailView.jsx";

const TABS = [
  { id: "unfall",   label: "unfall@"   },
  { id: "termin",   label: "termin@"   },
  { id: "bussgeld", label: "bussgeld@" },
];

function EmailImportView({ onOpenAkte, dispatch }) {
  const [tab, setTab] = useState("unfall");

  return (
    <div style={{ flex:1, overflowY:"auto", background:T.offWhite }}>
      <div style={{ maxWidth:1600, margin:"0 auto", padding:"1.75rem" }}>

        {/* Seitenheader */}
        <div style={{ marginBottom:"1.25rem" }}>
          <h1 style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"2rem",
            fontWeight:700, color:T.navy, margin:0 }}>
            E-Mail-Import
          </h1>
          <p style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.955rem",
            color:T.textMuted, marginTop:4, marginBottom:0 }}>
            Automatischer IMAP-Import · Dokumente · Eingang
          </p>
        </div>

        {/* Tab-Leiste */}
        <div style={{ display:"flex", borderBottom:`2px solid ${T.border}`, marginBottom:"1.5rem" }}>
          {TABS.map(t => {
            const aktiv = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                style={{
                  padding:"10px 22px",
                  background:"none",
                  border:"none",
                  borderBottom: aktiv ? `2px solid ${T.navy}` : "2px solid transparent",
                  marginBottom: -2,
                  fontFamily:"ui-monospace,monospace",
                  fontSize:"0.925rem",
                  fontWeight: aktiv ? 700 : 400,
                  color: aktiv ? T.navy : T.textMuted,
                  cursor:"pointer",
                  transition:"color 0.15s",
                }}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Tab-Inhalt */}
        {tab === "unfall"   && <UnfallEmailView  onOpenAkte={onOpenAkte} dispatch={dispatch} />}
        {tab === "termin"   && <TerminEmailView  />}
        {tab === "bussgeld" && <BussgeldEmailView />}

      </div>
    </div>
  );
}

export default EmailImportView;
