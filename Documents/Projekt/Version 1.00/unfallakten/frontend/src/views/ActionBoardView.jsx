import React, { useCallback, useEffect, useState } from "react";
import { apiDashboard } from "../api";
import TermineKachel        from "./action_board/TermineKachel";
import FristenKachel        from "./action_board/FristenKachel";
import WiedervorlagenKachel from "./action_board/WiedervorlagenKachel";
import PosteingangKachel    from "./action_board/PosteingangKachel";

function baseAz(azVoll) {
  return (azVoll || "").replace(/[A-Z]{2,3}$/i, "").trim();
}

export default function ActionBoardView({ onOpenAkte, onOpenEmail }) {
  const [termine,     setTermine]     = useState([]);
  const [fristen,     setFristen]     = useState([]);
  const [wvDaten,     setWvDaten]     = useState({ wv: [], ohne_wv: [] });
  const [nachrichten, setNachrichten] = useState([]);
  const [ladeZeit,    setLadeZeit]    = useState(null);
  const [laedtGerade, setLaedtGerade] = useState(false);

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
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={{ color: "#e2e8f0", fontSize: 15, fontWeight: 600 }}>
          Tagesübersicht — {heute}
        </div>
        <button
          onClick={laden}
          disabled={laedtGerade}
          style={{ background: "none", border: "none", color: "#60a5fa", fontSize: 12, cursor: "pointer", opacity: laedtGerade ? 0.4 : 0.7 }}
        >
          {laedtGerade ? "Lädt..." : `↻ Aktualisieren${ladeZeit ? ` (${ladeZeit})` : ""}`}
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <TermineKachel
          eintraege={termine}
          onOpenAkte={oeffneAkte}
        />
        <FristenKachel
          eintraege={fristen}
          onOpenAkte={oeffneAkte}
        />
        <WiedervorlagenKachel
          wv={wvDaten.wv}
          ohne_wv={wvDaten.ohne_wv}
          onOpenAkte={oeffneAkte}
        />
        <PosteingangKachel
          eintraege={nachrichten}
          onOpenEmail={onOpenEmail}
          onAlleOeffnen={undefined}
        />
      </div>
    </div>
  );
}
