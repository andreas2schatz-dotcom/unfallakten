import React, { useCallback, useEffect, useState } from "react";
import { apiDashboard } from "../api";
import TermineKachel        from "./action_board/TermineKachel";
import FristenKachel        from "./action_board/FristenKachel";
import WiedervorlagenKachel from "./action_board/WiedervorlagenKachel";
import PosteingangKachel    from "./action_board/PosteingangKachel";

function baseAz(azVoll) {
  return (azVoll || "").replace(/[A-Z]{2,3}$/i, "").trim();
}

const ALLE_SB    = ["AS", "PK", "CO", "MM", "AH", "TB", "SK", "EI"];
const DEFAULT_SB = new Set(["AS", "PK", "CO", "MM", "AH"]);

function sbAusAz(az) {
  const m = (az || "").match(/([A-Z]{2,3})$/);
  return m ? m[1] : null;
}

export default function ActionBoardView({ onOpenAkte, onOpenEmail }) {
  const [termine,     setTermine]     = useState([]);
  const [fristen,     setFristen]     = useState([]);
  const [wvDaten,     setWvDaten]     = useState({ wv: [], ohne_wv: [] });
  const [nachrichten, setNachrichten] = useState([]);
  const [ladeZeit,    setLadeZeit]    = useState(null);
  const [laedtGerade, setLaedtGerade] = useState(false);
  const [aktiveSB,    setAktiveSB]    = useState(DEFAULT_SB);

  function toggleSB(sb) {
    setAktiveSB(prev => {
      const next = new Set(prev);
      next.has(sb) ? next.delete(sb) : next.add(sb);
      return next;
    });
  }

  async function laden() {
    setLaedtGerade(true);
    const [r1, r2, r3, r4] = await Promise.allSettled([
      apiDashboard.termineHeute(),
      apiDashboard.fristen(),
      apiDashboard.wiedervorlagen(),
      apiDashboard.nachrichtenNeu(),
    ]);

    if (r1.status === "fulfilled") setTermine(r1.value?.eintraege ?? []);
    if (r2.status === "fulfilled") setFristen(r2.value?.eintraege ?? []);
    if (r3.status === "fulfilled") setWvDaten(r3.value ?? { wv: [], ohne_wv: [] });
    if (r4.status === "fulfilled") setNachrichten(r4.value?.eintraege ?? []);

    setLadeZeit(new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }));
    setLaedtGerade(false);
  }

  useEffect(() => { laden(); }, []);

  const oeffneAkte = useCallback((az) => {
    onOpenAkte({ az: baseAz(az), az_roh: az });
  }, [onOpenAkte]);

  const heute = new Date().toLocaleDateString("de-DE", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  return (
    <div style={{ background: "#1B2A4A", borderRadius: 8, padding: 16, fontFamily: "'Segoe UI', sans-serif" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14, flexWrap: "wrap", gap: 8 }}>
        <div style={{ color: "#e2e8f0", fontSize: 15, fontWeight: 600 }}>
          Tagesübersicht — {heute}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {ALLE_SB.map(sb => {
            const aktiv = aktiveSB.has(sb);
            return (
              <button
                key={sb}
                onClick={() => toggleSB(sb)}
                style={{
                  background: aktiv ? "#334155" : "transparent",
                  color: aktiv ? "#e2e8f0" : "#475569",
                  border: `1px solid ${aktiv ? "#64748b" : "#334155"}`,
                  borderRadius: 4,
                  padding: "2px 8px",
                  fontSize: 11,
                  fontWeight: aktiv ? 700 : 400,
                  cursor: "pointer",
                  transition: "all .15s",
                }}
              >
                {sb}
              </button>
            );
          })}
          <button
            onClick={laden}
            disabled={laedtGerade}
            style={{ background: "none", border: "none", color: "#60a5fa", fontSize: 12, cursor: "pointer", opacity: laedtGerade ? 0.4 : 0.7, marginLeft: 8 }}
          >
            {laedtGerade ? "Lädt..." : `↻ Aktualisieren${ladeZeit ? ` (${ladeZeit})` : ""}`}
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <TermineKachel
          eintraege={termine.filter(e => aktiveSB.size === 0 || aktiveSB.has(sbAusAz(e.az)))}
          onOpenAkte={oeffneAkte}
        />
        <FristenKachel
          eintraege={fristen.filter(e => aktiveSB.size === 0 || aktiveSB.has(sbAusAz(e.az)))}
          onOpenAkte={oeffneAkte}
        />
        <WiedervorlagenKachel
          wv={(wvDaten.wv || []).filter(e => aktiveSB.size === 0 || aktiveSB.has(sbAusAz(e.az)))}
          ohne_wv={(wvDaten.ohne_wv || []).filter(e => { const sb = sbAusAz(e.az); return aktiveSB.size === 0 || !sb || aktiveSB.has(sb); })}
          onOpenAkte={oeffneAkte}
        />
        <PosteingangKachel
          eintraege={nachrichten.filter(e => aktiveSB.size === 0 || aktiveSB.has(sbAusAz(e.az)))}
          onOpenEmail={onOpenEmail}
          onAlleOeffnen={undefined}
        />
      </div>
    </div>
  );
}
