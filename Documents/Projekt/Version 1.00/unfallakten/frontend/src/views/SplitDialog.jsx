// frontend/src/views/SplitDialog.jsx
import { useState, useEffect, useRef } from "react";
import { apiIntake } from "../api.js";
import { gruppenAusSchnitten, schnittUmschalten } from "./splitLogik.js";

export default function SplitDialog({ docId, thumbUrl, onDone, onClose }) {
  const [seiten, setSeiten] = useState(null);
  const [schnitte, setSchnitte] = useState([]);
  const [fehler, setFehler] = useState(null);
  const [busy, setBusy] = useState(false);

  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    let aktiv = true;
    apiIntake.seiten(docId)
      .then((r) => { if (aktiv) setSeiten(r.seiten); })
      .catch(() => { if (aktiv) setFehler("Seiten konnten nicht geladen werden."); });
    return () => { aktiv = false; };
  }, [docId]);

  const gruppen = seiten ? gruppenAusSchnitten(seiten, schnitte) : [];

  const aufteilen = async () => {
    setBusy(true);
    setFehler(null);
    try {
      await apiIntake.split(docId, gruppen);
      onDone();
    } catch (e) {
      if (!mounted.current) return;
      setFehler(e?.message || "Aufteilen fehlgeschlagen.");
      setBusy(false);
    }
  };

  const overlay = {
    position: "fixed", inset: 0, background: "rgba(0,0,0,.45)",
    display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
  };
  const box = {
    background: "#fff", borderRadius: 10, padding: 20, maxWidth: "90vw",
    maxHeight: "85vh", overflow: "auto", boxShadow: "0 10px 40px rgba(0,0,0,.3)",
  };

  return (
    <div style={{ ...overlay, cursor: busy ? "wait" : "default" }}
      onClick={busy ? undefined : onClose}>
      <div style={box} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>✂ Dokument aufteilen</h3>
        {seiten === null && !fehler && <p>Lade Seiten …</p>}
        {seiten !== null && (
          <>
            <p style={{ fontSize: 13, opacity: 0.7 }}>
              Klick zwischen zwei Seiten setzt/entfernt einen Schnitt.
            </p>
            <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 2 }}>
              {Array.from({ length: seiten }, (_, i) => i + 1).map((n) => (
                <div key={n} style={{ display: "flex", alignItems: "center" }}>
                  <div style={{ textAlign: "center" }}>
                    <img src={thumbUrl(n)} alt={`Seite ${n}`}
                      style={{ width: 70, height: 92, objectFit: "contain",
                        border: "1px solid #ccc", borderRadius: 4, background: "#fafafa" }} />
                    <div style={{ fontSize: 11, opacity: 0.7 }}>{n}</div>
                  </div>
                  {n < seiten && (
                    <button
                      onClick={() => setSchnitte((s) => schnittUmschalten(s, n))}
                      title={schnitte.includes(n) ? "Schnitt entfernen" : "Hier schneiden"}
                      style={{
                        width: 26, alignSelf: "stretch", cursor: "pointer",
                        border: "none", background: "transparent",
                        color: schnitte.includes(n) ? "#e0663a" : "#bbb",
                        fontSize: 16,
                      }}>✂</button>
                  )}
                </div>
              ))}
            </div>

            <p style={{ fontSize: 13, fontWeight: 600, marginTop: 16 }}>
              Ergebnis — {gruppen.length} Teil{gruppen.length === 1 ? "" : "e"}
            </p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {gruppen.map((g, i) => (
                <span key={i} style={{
                  border: "1px solid #3b82f6", borderRadius: 8, padding: "6px 10px",
                  fontSize: 12,
                }}>
                  Teil {i + 1} · Seiten {g[0]}{g.length > 1 ? `–${g[g.length - 1]}` : ""}
                </span>
              ))}
            </div>

            {fehler && <p style={{ color: "#c0392b", fontSize: 13 }}>{fehler}</p>}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 18 }}>
              <button onClick={onClose} disabled={busy}>Abbrechen</button>
              <button onClick={aufteilen} disabled={busy || schnitte.length < 1}
                style={{ background: "#2563eb", color: "#fff", border: "none",
                  borderRadius: 6, padding: "6px 14px", cursor: "pointer" }}>
                In {gruppen.length} Teile aufteilen
              </button>
            </div>
          </>
        )}
        {fehler && seiten === null && <p style={{ color: "#c0392b" }}>{fehler}</p>}
      </div>
    </div>
  );
}
