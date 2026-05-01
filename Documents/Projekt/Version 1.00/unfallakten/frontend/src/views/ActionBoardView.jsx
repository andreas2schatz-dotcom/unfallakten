import React, { useEffect, useState, useCallback } from "react";
import { apiDashboard, wiedervorlage as apiWV, akten as apiAkten } from "../api";

// ─── Theme ───────────────────────────────────────────────────
const T = {
  navy:       "#1B2A4A",
  terra:      "#A06B4A",
  terraLight: "#F3EAE2",
  bg:         "#F6F4EF",
  surface:    "#FAFAF8",
  border:     "#E2DDD3",
  red:        "#dc2626",  redBg:   "#fef2f2",
  amber:      "#d97706",  amberBg: "#fffbeb",
  green:      "#16a34a",  greenBg: "#f0fdf4",
  text:       "#1e293b",
  faint:      "#64748b",
};

const LABEL = {
  fontSize: "0.68rem", fontWeight: 700,
  textTransform: "uppercase", letterSpacing: ".06em",
  color: T.faint, marginBottom: 8,
  fontFamily: "Bricolage Grotesque",
};

function baseAz(azVoll) {
  return (azVoll || "").replace(/[A-Z]{2,3}$/i, "").trim();
}

function heuteISO() {
  return new Date().toISOString().slice(0, 10);
}

// ════════════════════════════════════════════════════════════════
//  Sub-Komponente: Fristen-Spalte (RA-MICRO)
// ════════════════════════════════════════════════════════════════
function FristenSpalte({ fristen, onOpenAkte }) {
  const bg   = (t) => t <= 14 ? T.redBg   : t <= 30 ? T.amberBg   : T.greenBg;
  const col  = (t) => t <= 14 ? T.red     : t <= 30 ? T.amber     : T.green;

  return (
    <div style={{ borderRight: `1px solid ${T.border}`, padding: 12, overflowY: "auto", background: T.surface }}>
      <div style={LABEL}>⚡ Fristen (RA-MICRO)</div>
      {fristen.length === 0 ? (
        <p style={{ fontSize: "0.78rem", color: T.faint }}>
          Keine offenen Fristen · RA-MICRO nicht verbunden
        </p>
      ) : (
        fristen.map((f, i) => (
          <div
            key={i}
            onClick={() => onOpenAkte(f.az)}
            style={{
              background: bg(f.tage_bis), borderRadius: 6,
              padding: "8px 10px", marginBottom: 6, cursor: "pointer",
              border: `1px solid ${col(f.tage_bis)}40`,
            }}
          >
            <div style={{ fontWeight: 600, fontSize: "0.8rem", color: T.text, fontFamily: "Bricolage Grotesque" }}>
              {f.az}{f.mandant ? ` — ${f.mandant}` : ""}
            </div>
            <div style={{ fontSize: "0.75rem", color: "#475569", marginTop: 2 }}>{f.frist_art}</div>
            <div style={{ fontSize: "0.8rem", fontWeight: 700, color: col(f.tage_bis), marginTop: 3 }}>
              {f.frist_datum} · {f.tage_bis} Tage
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
//  Sub-Komponente: Handlung erforderlich
// ════════════════════════════════════════════════════════════════
function HandlungSpalte({ wvFaellig, onboardingOffen, onOpenAkte }) {
  const EintragZeile = ({ az, titel, sub, rand }) => (
    <div
      onClick={() => onOpenAkte(az)}
      style={{
        borderLeft: `3px solid ${rand}`, background: T.surface,
        borderRadius: "0 6px 6px 0", padding: "7px 10px",
        marginBottom: 5, cursor: "pointer",
      }}
    >
      <div style={{ fontWeight: 600, fontSize: "0.82rem", color: T.text, fontFamily: "Bricolage Grotesque" }}>
        {az}
      </div>
      <div style={{ fontSize: "0.75rem", color: T.faint, marginTop: 1 }}>{titel}</div>
      {sub && <div style={{ fontSize: "0.72rem", color: T.faint, marginTop: 1, fontStyle: "italic" }}>{sub}</div>}
    </div>
  );

  return (
    <div style={{ borderRight: `1px solid ${T.border}`, padding: 12, overflowY: "auto" }}>
      {/* Wiedervorlage */}
      <div style={LABEL}>Wiedervorlage fällig ({wvFaellig.length})</div>
      {wvFaellig.length === 0 ? (
        <p style={{ fontSize: "0.78rem", color: T.faint, marginBottom: 16 }}>Keine fälligen Wiedervorlagen</p>
      ) : (
        <div style={{ marginBottom: 16 }}>
          {wvFaellig.slice(0, 15).map((wv, i) => {
            const az = baseAz(wv.aktenzeichen);
            const tageDiff = Math.floor((new Date(heuteISO()) - new Date(wv.datum)) / 86400000);
            const sub = tageDiff > 0 ? `${tageDiff} Tag${tageDiff !== 1 ? "e" : ""} überfällig` : "heute fällig";
            return (
              <EintragZeile
                key={i}
                az={az}
                titel={wv.mandant || wv.kurzbezeichnung || ""}
                sub={`${wv.grund || ""} · ${sub}`}
                rand={tageDiff > 0 ? T.red : T.amber}
              />
            );
          })}
        </div>
      )}

      {/* Onboarding */}
      <div style={LABEL}>Onboarding unvollständig ({onboardingOffen.length})</div>
      {onboardingOffen.length === 0 ? (
        <p style={{ fontSize: "0.78rem", color: T.faint }}>Alle Akten vollständig</p>
      ) : (
        onboardingOffen.slice(0, 10).map((ob, i) => (
          <EintragZeile
            key={i}
            az={ob.az}
            titel={ob.mandant || "–"}
            sub={ob.fehlt === "mandant" ? "Mandant fehlt" : "IBAN fehlt"}
            rand="#8b5cf6"
          />
        ))
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
//  Sub-Komponente: Nachrichten
// ════════════════════════════════════════════════════════════════
function NachrichtenSpalte({ nachrichten, onOpenAkte }) {
  const [aktiveTab, setAktiveTab] = useState("email");

  const TabBtn = ({ id, label, anzahl }) => (
    <button
      onClick={() => setAktiveTab(id)}
      style={{
        background: aktiveTab === id ? T.navy : "transparent",
        color: aktiveTab === id ? "#fff" : T.faint,
        border: `1px solid ${aktiveTab === id ? T.navy : T.border}`,
        borderRadius: 4, padding: "3px 10px",
        fontSize: "0.72rem", cursor: "pointer",
        fontFamily: "Figtree",
      }}
    >
      {label}{anzahl > 0 ? ` (${anzahl})` : ""}
    </button>
  );

  return (
    <div style={{ padding: 12, overflowY: "auto", background: T.surface }}>
      <div style={LABEL}>Nachrichten</div>
      <div style={{ display: "flex", gap: 4, marginBottom: 10, flexWrap: "wrap" }}>
        <TabBtn id="email"  label="📧 E-Mail"         anzahl={nachrichten.length} />
        <TabBtn id="portal" label="👤 Mandantenportal" anzahl={0} />
        <TabBtn id="sv"     label="🔬 SV-Portal"       anzahl={0} />
      </div>

      {aktiveTab === "email" && (
        nachrichten.length === 0 ? (
          <p style={{ fontSize: "0.78rem", color: T.faint }}>Keine neuen E-Mails</p>
        ) : (
          nachrichten.map((m, i) => (
            <div
              key={i}
              onClick={() => onOpenAkte(m.az)}
              style={{
                background: T.bg, borderRadius: 5,
                padding: "7px 10px", marginBottom: 6,
                cursor: "pointer", borderLeft: `3px solid ${T.navy}`,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontWeight: 600, fontSize: "0.78rem", color: T.navy, fontFamily: "Bricolage Grotesque" }}>
                  {m.az}
                </span>
                <span style={{ fontSize: "0.68rem", color: T.faint }}>
                  {m.datum ? m.datum.slice(0, 10) : ""}
                </span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "#475569", marginTop: 1 }}>{m.absender}</div>
              <div style={{ fontSize: "0.72rem", color: T.faint, marginTop: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {m.betreff}
              </div>
            </div>
          ))
        )
      )}

      {(aktiveTab === "portal" || aktiveTab === "sv") && (
        <p style={{ fontSize: "0.78rem", color: T.faint, fontStyle: "italic" }}>
          Demnächst verfügbar
        </p>
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
//  Neue-Akte-Modal
// ════════════════════════════════════════════════════════════════
function NeueAkteModal({ onClose, onOpenAkte }) {
  const INIT = { aktenzeichen: "", unfalldatum: "", unfallort: "", notizen: "" };
  const [felder, setFelder] = useState(INIT);
  const [fehler, setFehler] = useState({});
  const [speichern, setSpeichern] = useState(false);

  const set = (k, v) => setFelder(p => ({ ...p, [k]: v }));

  const validiere = () => {
    const f = {};
    if (!felder.aktenzeichen.match(/^\d+\/\d{2}([A-Z]{2,3})?$/i))
      f.aktenzeichen = "Format: 42/26 oder 42/26AS";
    if (!felder.unfalldatum) f.unfalldatum = "Pflichtfeld";
    setFehler(f);
    return Object.keys(f).length === 0;
  };

  const anlegen = async () => {
    if (!validiere()) return;
    setSpeichern(true);
    try {
      const res = await apiAkten.erstellen({
        aktenzeichen: felder.aktenzeichen.trim(),
        unfalldatum:  felder.unfalldatum.trim(),
        unfallort:    felder.unfallort.trim() || undefined,
        notizen:      felder.notizen.trim()   || undefined,
      });
      onOpenAkte(res.akte?.az || res.akte?.aktenzeichen || felder.aktenzeichen);
      onClose();
    } catch (e) {
      setFehler({ global: e.message || "Fehler beim Anlegen" });
    } finally {
      setSpeichern(false);
    }
  };

  const feld = (key, label, type = "text", pflicht = false) => (
    <div style={{ marginBottom: 10 }}>
      <label style={{ fontSize: "0.78rem", color: T.faint, display: "block", marginBottom: 3 }}>
        {label}{pflicht ? " *" : ""}
      </label>
      <input
        type={type}
        value={felder[key]}
        onChange={e => set(key, e.target.value)}
        style={{
          width: "100%", boxSizing: "border-box",
          border: `1px solid ${fehler[key] ? T.red : T.border}`,
          borderRadius: 5, padding: "6px 10px",
          fontSize: "0.85rem", background: T.bg,
          fontFamily: "Figtree",
        }}
      />
      {fehler[key] && <div style={{ fontSize: "0.72rem", color: T.red, marginTop: 2 }}>{fehler[key]}</div>}
    </div>
  );

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 9000, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "#fff", borderRadius: 10, padding: 24, width: 380, maxWidth: "95vw", boxShadow: "0 8px 32px rgba(0,0,0,.2)" }}>
        <div style={{ fontFamily: "Bricolage Grotesque", fontWeight: 700, fontSize: "1.1rem", color: T.navy, marginBottom: 16 }}>
          Neue Akte anlegen
        </div>
        {feld("aktenzeichen", "Aktenzeichen", "text", true)}
        {feld("unfalldatum",  "Unfalldatum",  "date", true)}
        {feld("unfallort",    "Unfallort")}
        {feld("notizen",      "Notizen")}
        {fehler.global && <div style={{ fontSize: "0.78rem", color: T.red, marginBottom: 8 }}>{fehler.global}</div>}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
          <button onClick={onClose} style={{ background: "transparent", border: `1px solid ${T.border}`, borderRadius: 5, padding: "6px 14px", cursor: "pointer", fontFamily: "Figtree" }}>
            Abbrechen
          </button>
          <button
            onClick={anlegen}
            disabled={speichern}
            style={{ background: T.terra, color: "#fff", border: "none", borderRadius: 5, padding: "6px 16px", cursor: "pointer", fontFamily: "Figtree", fontWeight: 600 }}
          >
            {speichern ? "Legt an…" : "Anlegen"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
//  Haupt-Komponente: ActionBoardView
// ════════════════════════════════════════════════════════════════
export default function ActionBoardView({ onOpenAkte }) {
  const [wvAlle,          setWvAlle]          = useState([]);
  const [onboardingOffen, setOnboardingOffen]  = useState([]);
  const [nachrichten,     setNachrichten]      = useState([]);
  const [fristen,         setFristen]          = useState([]);
  const [geladen,         setGeladen]          = useState(false);
  const [zeigeModal,      setZeigeModal]       = useState(false);

  useEffect(() => {
    Promise.allSettled([
      apiWV.liste({ nurHeute: false }),
      apiDashboard.onboardingOffen(),
      apiDashboard.nachrichtenNeu(),
      apiDashboard.ramicroFristen(),
    ]).then(([wv, ob, na, fr]) => {
      if (wv.status === "fulfilled") setWvAlle(wv.value?.wiedervorlagen || []);
      if (ob.status === "fulfilled") setOnboardingOffen(ob.value?.eintraege || []);
      if (na.status === "fulfilled") setNachrichten(na.value?.eintraege || []);
      if (fr.status === "fulfilled") setFristen(fr.value?.eintraege || []);
      setGeladen(true);
    });
  }, []);

  const oeffneAkte = useCallback((az) => {
    onOpenAkte({ az: baseAz(az), az_roh: az });
  }, [onOpenAkte]);

  const wvFaellig = wvAlle.filter(wv => wv.datum <= heuteISO());

  const heute = new Date().toLocaleDateString("de-DE", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", background: T.bg, overflow: "hidden" }}>

      {/* Kopfzeile */}
      <div style={{
        background: T.navy, padding: "10px 16px",
        display: "flex", alignItems: "center", flexShrink: 0,
      }}>
        <span style={{ fontFamily: "Bricolage Grotesque", fontWeight: 700, fontSize: "1.05rem", color: "#fff" }}>
          Action Board
        </span>
        <span style={{ color: "#94a3b8", marginLeft: 16, fontSize: "0.83rem" }}>{heute}</span>
        <button
          onClick={() => setZeigeModal(true)}
          style={{
            marginLeft: "auto", background: T.terra, color: "#fff",
            border: "none", borderRadius: 6, padding: "6px 14px",
            cursor: "pointer", fontFamily: "Figtree", fontWeight: 600,
          }}
        >
          + Neue Akte
        </button>
      </div>

      {/* 3-Spalten Grid */}
      {!geladen ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: T.faint }}>
          Lade…
        </div>
      ) : (
        <div style={{ flex: 1, display: "grid", gridTemplateColumns: "220px 1fr 300px", overflow: "hidden" }}>
          <FristenSpalte     fristen={fristen}                                    onOpenAkte={oeffneAkte} />
          <HandlungSpalte    wvFaellig={wvFaellig} onboardingOffen={onboardingOffen} onOpenAkte={oeffneAkte} />
          <NachrichtenSpalte nachrichten={nachrichten}                             onOpenAkte={oeffneAkte} />
        </div>
      )}

      {zeigeModal && (
        <NeueAkteModal
          onClose={() => setZeigeModal(false)}
          onOpenAkte={oeffneAkte}
        />
      )}
    </div>
  );
}
