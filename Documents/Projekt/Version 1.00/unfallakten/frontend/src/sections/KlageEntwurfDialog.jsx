import { formatGespeichertAm } from "./klageEntwurfLogik.js";

export default function KlageEntwurfDialog({
  typ, gespeichertAm, step, onFortsetzen, onNeuBeginnen, onAbbrechen,
}) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1100 }}>
      <div style={{ background: "#fff", borderRadius: "10px", padding: "1.5rem",
        maxWidth: "26rem", width: "90%", boxShadow: "0 10px 30px rgba(0,0,0,0.25)" }}>
        {typ === "fortsetzen" ? (
          <>
            <h3 style={{ margin: "0 0 0.5rem" }}>Gespeicherter Entwurf gefunden</h3>
            <p>
              Entwurf vom {formatGespeichertAm(gespeichertAm)}{" "}
              (Schritt {step} von 10) — fortsetzen oder neu beginnen?
            </p>
          </>
        ) : (
          <>
            <h3 style={{ margin: "0 0 0.5rem" }}>Entwurf nicht verwendbar</h3>
            <p>
              Der gespeicherte Entwurf stammt aus einer älteren Programmversion
              und kann nicht fortgesetzt werden.
            </p>
          </>
        )}
        <div style={{ display: "flex", gap: "0.6rem", justifyContent: "flex-end",
          marginTop: "1rem" }}>
          <button onClick={onAbbrechen}>Abbrechen</button>
          <button onClick={onNeuBeginnen}>Neu beginnen</button>
          {typ === "fortsetzen" && (
            <button onClick={onFortsetzen} style={{ fontWeight: 600 }}>
              ▶ Fortsetzen
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
