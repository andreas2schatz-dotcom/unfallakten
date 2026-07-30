import React, { useState, useRef, useEffect } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { SUCHMODUS_LABEL } from "../config/constants.js";
import { Card, Btn, Toast } from "../components/common.jsx";
import AktenanlageDialog from "../components/AktenanlageDialog.jsx";
import {
  aktensuche as apiAktensuche,
  emailImport,
  eakte as apiEakte,
} from "../api.js";

// ── E-Akte Hover-Vorschau: Hilfsfunktionen ──────────────────────────────────

function typBadge(dok) {
  const text = ((dok.bemerkung || "") + " " + (dok.anzeigename || "")).toLowerCase();
  if (/regulier|schreiben|zahlung|deckung/.test(text))
    return { label: "Regulierung", bg: "#dbeafe", color: "#1e40af" };
  if (/gutachten|sachverst/.test(text))
    return { label: "Gutachten",   bg: "#d1fae5", color: "#065f46" };
  if (/polizei|bericht|anzeige/.test(text))
    return { label: "Polizei",     bg: "#fef3c7", color: "#92400e" };
  if (/rechnung|kosten|invoice/.test(text))
    return { label: "Rechnung",    bg: "#fce7f3", color: "#9d174d" };
  return { label: "Dokument", bg: "#f3f4f6", color: "#6b7280" };
}

function fmtDatum(isoStr) {
  if (!isoStr) return "–";
  const d = new Date(isoStr);
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

// ── EakteHoverPopover ────────────────────────────────────────────────────────

function EakteHoverPopover({ az, anchor, daten, akteObj, onOpenAkte, onMouseEnter, onMouseLeave }) {
  const BREITE = 320;
  const HOEHE_GESCHAETZT = 260;
  const ueberZeile = anchor.top > HOEHE_GESCHAETZT + 20;
  const top   = ueberZeile ? anchor.top - HOEHE_GESCHAETZT : anchor.bottom + 4;
  const right = Math.max(8, window.innerWidth - anchor.right);

  const oeffnen = () => onOpenAkte({ ...akteObj, initialTab: "dokumente" });

  return (
    <div
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      style={{
        position: "fixed", top, right,
        width: BREITE, background: T.cardBg,
        border: `1px solid ${T.border}`, borderRadius: 10,
        boxShadow: "0 6px 24px rgba(0,0,0,0.16)", zIndex: 500, overflow: "hidden",
      }}
    >
      {/* Header */}
      <div style={{
        padding: "8px 14px", background: T.navy,
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: "white",
          letterSpacing: "0.06em", textTransform: "uppercase",
          fontFamily: T.fontBody }}>
          E-Akte Vorschau
        </span>
        <span style={{ fontSize: 11, color: "rgba(255,255,255,0.5)",
          fontFamily: "ui-monospace,monospace" }}>
          {az}
        </span>
      </div>

      {/* Body */}
      {daten.loading ? (
        <div style={{ padding: "14px", textAlign: "center",
          color: T.textFaint, fontFamily: T.fontBody, fontSize: 13 }}>
          Lädt …
        </div>
      ) : daten.error ? (
        <div style={{ padding: "12px 14px",
          color: T.textMuted, fontFamily: T.fontBody, fontSize: 13 }}>
          {daten.error}
        </div>
      ) : daten.docs.length === 0 ? (
        <div style={{ padding: "12px 14px",
          color: T.textMuted, fontFamily: T.fontBody, fontSize: 13 }}>
          Keine E-Akte-Dokumente vorhanden.
        </div>
      ) : (
        <div style={{ padding: "6px 8px", display: "flex", flexDirection: "column", gap: 4 }}>
          {daten.docs.map(dok => {
            const badge = typBadge(dok);
            const datum = fmtDatum(dok.version || dok.einf_datum);
            return (
              <div key={dok.nr} onClick={oeffnen}
                style={{
                  padding: "7px 9px", border: `1px solid ${T.borderSoft}`,
                  borderRadius: 6, display: "flex", alignItems: "flex-start",
                  gap: 8, cursor: "pointer", background: T.cardBg,
                }}
                onMouseEnter={e => e.currentTarget.style.background = T.accentPale}
                onMouseLeave={e => e.currentTarget.style.background = T.cardBg}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 2 }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700,
                      background: badge.bg, color: badge.color,
                      borderRadius: 3, padding: "1px 5px",
                      textTransform: "uppercase", letterSpacing: "0.04em",
                      whiteSpace: "nowrap", fontFamily: T.fontBody,
                    }}>
                      {badge.label}
                    </span>
                    <span style={{ fontSize: 10, color: T.textFaint,
                      fontFamily: T.fontBody }}>
                      {datum}
                    </span>
                  </div>
                  <div style={{
                    fontSize: 12, color: T.textMid, fontWeight: 500,
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                    fontFamily: T.fontBody,
                  }}>
                    {dok.anzeigename || dok.dateiname}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Footer */}
      {!daten.loading && !daten.error && daten.docs.length > 0 && (
        <div style={{
          padding: "7px 14px", background: T.surface,
          borderTop: `1px solid ${T.borderSoft}`, textAlign: "center",
        }}>
          <button onClick={oeffnen}
            style={{
              background: "none", border: "none", cursor: "pointer",
              fontSize: 11, color: T.accent, fontWeight: 600,
              fontFamily: T.fontBody,
            }}>
            Alle Dokumente anzeigen →
          </button>
        </div>
      )}
    </div>
  );
}

// ── Autocomplete-Input ────────────────────────────────────────────────────────
function AutocompleteInput({ value, onChange, onSearch, onOpenAkte, placeholder, style, hint }) {
  const [vorschlaege, setVorschlaege] = useState([]);
  const [laedt, setLaedt]            = useState(false);
  const [offen, setOffen]            = useState(false);
  const wrapRef = useRef(null);

  // Klick außerhalb → schließen
  useEffect(() => {
    function handleOutside(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOffen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  const handleChange = async (e) => {
    const q = e.target.value;
    onChange(q);
    if (q.length < 2) { setVorschlaege([]); setOffen(false); return; }
    setLaedt(true); setOffen(true);
    try {
      const res = await emailImport.aktensuche(q);
      setVorschlaege(res?.akten || []);
    } catch {
      setVorschlaege([]);
    } finally {
      setLaedt(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter")   { setOffen(false); onSearch(); }
    if (e.key === "Escape")  { setOffen(false); }
  };

  const handleSelect = (a) => {
    setOffen(false);
    setVorschlaege([]);
    onOpenAkte({ id: a.az, az: a.az, az_roh: a.az, status: "offen",
                 unfalldatum: "", unfallort: "", hq: 100, brutto: 0 });
  };

  const inpStyle = {
    width: "100%", padding: "9px 11px", border: `1.5px solid ${T.border}`,
    borderRadius: 7, fontFamily: "ui-monospace,monospace", fontSize: "0.975rem",
    color: T.text, background: T.cardBg, outline: "none",
    boxSizing: "border-box", transition: "border-color 0.15s",
    ...style,
  };

  return (
    <div ref={wrapRef} style={{ position: "relative" }}>
      <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
        <input
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          style={inpStyle}
          onFocus={e => { e.target.style.borderColor = T.accent; if (value.length >= 2 && vorschlaege.length > 0) setOffen(true); }}
          onBlur={e  => e.target.style.borderColor = T.border}
        />
        {laedt && (
          <div style={{ position: "absolute", right: 10,
            width: 12, height: 12, border: "2px solid rgba(0,0,0,0.12)",
            borderTopColor: T.navy, borderRadius: "50%",
            animation: "spin 0.7s linear infinite" }}/>
        )}
      </div>
      {offen && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 200,
          background: T.cardBg, border: `1px solid ${T.border}`,
          borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,0.13)",
          overflow: "hidden",
        }}>
          {vorschlaege.length > 0 ? (
            <div style={{ maxHeight: 220, overflowY: "auto" }}>
              {vorschlaege.map((a, i) => (
                <button key={i}
                  onMouseDown={() => handleSelect(a)}
                  style={{
                    width: "100%", textAlign: "left", padding: "9px 14px",
                    background: "transparent", border: "none",
                    borderBottom: `1px solid ${T.borderSoft}`,
                    cursor: "pointer", fontFamily: T.fontBody,
                    fontSize: "0.925rem", color: T.text,
                    display: "flex", alignItems: "center", gap: 10,
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = T.accentPale}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <span style={{ fontFamily: "ui-monospace,monospace", fontWeight: 700,
                    color: T.navy, flexShrink: 0, minWidth: 64 }}>{a.az}</span>
                  {a.label !== a.az && (
                    <span style={{ color: T.textMuted, overflow: "hidden",
                      textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {a.label.replace(a.az, "").replace(/^[\s–\-]+/, "")}
                    </span>
                  )}
                </button>
              ))}
            </div>
          ) : !laedt ? (
            <div style={{ padding: "11px 14px", fontFamily: T.fontBody,
              fontSize: "0.9rem", color: T.textMuted }}>
              Keine Akte gefunden für „{value}"
            </div>
          ) : null}
        </div>
      )}
      {hint && (
        <div style={{ marginTop: 5, fontFamily: T.fontBody,
          fontSize: "0.75rem", color: T.textFaint, lineHeight: 1.4 }}>
          {hint}
        </div>
      )}
    </div>
  );
}

// ── Hauptkomponente ───────────────────────────────────────────────────────────
function AktensucheView({ onOpenAkte }) {
  const [az, setAz]         = useState("");
  const [kz, setKz]         = useState("");
  const [tag, setTag]       = useState("");
  const [loading, setLoad]  = useState(false);
  const [treffer, setTref]  = useState(null);
  const [suchmodus, setMod] = useState("");
  const [fehler, setFeh]    = useState("");
  const [ramicroAktiv, setRA] = useState(true);
  const [neueAkteOffen, setNeueAkteOffen] = useState(false);
  const [toast, setToast]   = useState("");

  const [hoverAz,      setHoverAz]      = useState(null);
  const [hoverAnchor,  setHoverAnchor]  = useState(null);
  const [hoverAkteObj, setHoverAkteObj] = useState(null);
  const [popoverDaten, setPopover]      = useState({ docs: [], loading: false, error: null });
  const timerRef    = useRef(null);
  const hideTimerRef = useRef(null);
  const cacheRef    = useRef(new Map());
  const hoverAzRef  = useRef(null);

  useEffect(() => {
    return () => {
      clearTimeout(timerRef.current);
      clearTimeout(hideTimerRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const close = () => setHoverAz(null);
    window.addEventListener("scroll", close, true);
    return () => window.removeEventListener("scroll", close, true);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRowEnter = (e, t) => {
    clearTimeout(hideTimerRef.current);
    const anchor = e.currentTarget.getBoundingClientRect();
    setHoverAnchor(anchor);
    setHoverAkteObj({
      id: t.az_roh, az: t.az, az_roh: t.az_roh,
      status: t.status || "offen", unfalldatum: t.unfalldatum || "",
      unfallort: t.unfallort || "", hq: t.haftungsquote || 100, brutto: 0,
    });
    if (hoverAzRef.current === t.az_roh) return;
    hoverAzRef.current = t.az_roh;
    setHoverAz(t.az_roh);
    if (cacheRef.current.has(t.az_roh)) {
      setPopover({ docs: cacheRef.current.get(t.az_roh), loading: false, error: null });
      return;
    }
    setPopover({ docs: [], loading: true, error: null });
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      const az = t.az_roh;
      try {
        const res = await apiEakte.liste(az);
        if (hoverAzRef.current !== az) return;
        const docs = (res.dokumente || []).slice(0, 5);
        cacheRef.current.set(az, docs);
        setPopover({ docs, loading: false, error: null });
      } catch {
        if (hoverAzRef.current !== az) return;
        setPopover({ docs: [], loading: false, error: "Dokumente konnten nicht geladen werden." });
      }
    }, 300);
  };

  const handleRowLeave = () => {
    clearTimeout(timerRef.current);
    hoverAzRef.current = null;
    hideTimerRef.current = setTimeout(() => {
      setHoverAz(null);
      setPopover({ docs: [], loading: false, error: null });
    }, 150);
  };

  const suchen = async (feld) => {
    const azQ = az.trim(), kzQ = kz.trim(), tagQ = tag.trim();
    const nutzAz  = feld === "az"  && azQ;
    const nutzKz  = feld === "kz"  && kzQ;
    const nutzTag = feld === "tag" && tagQ;
    if (!nutzAz && !nutzKz && !nutzTag) return;
    setLoad(true); setFeh(""); setTref(null); setMod("");
    try {
      let res;
      if (nutzKz)       res = await apiAktensuche.nachKennzeichen(kzQ);
      else if (nutzTag) res = await apiAktensuche.nachSchadentag(tagQ);
      else              res = await apiAktensuche.suchen(azQ);
      setTref(res.treffer || []);
      setMod(res.suchmodus || "");
      setRA(res.ramicro_aktiv !== false);
      if (res.hinweis) setFeh(res.hinweis);
    } catch (e) {
      setFeh(e?.message || "Fehler bei der Suche.");
      setTref([]);
    } finally {
      setLoad(false);
    }
  };

  const kachelStyle = {
    flex: 1, background: T.cardBg, border: `1px solid ${T.border}`,
    borderRadius: 10, padding: "1rem 1.1rem",
    boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
  };

  const labelStyle = {
    fontFamily: T.fontBody, fontSize: "0.78rem",
    fontWeight: 600, color: T.textMid, letterSpacing: "0.06em",
    textTransform: "uppercase", display: "block", marginBottom: 6,
  };

  return (
    <>
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: T.offWhite }}>

      {/* Header */}
      <div style={{ background: T.cardBg, borderBottom: `1px solid ${T.border}`,
        padding: "1.1rem 1.75rem", flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <h1 style={{ fontFamily: T.fontDisplay, fontSize: "1.45rem", fontWeight: 700, color: T.navy, margin: "0 0 3px" }}>
            Aktensuche
          </h1>
          <p style={{ fontFamily: T.fontBody, fontSize: "0.855rem", color: T.textMuted, margin: 0 }}>
            Direktsuche in der RA-Micro Datenbank · Alle aktiven Akten
          </p>
        </div>
        <Btn variant="gold" size="sm" onClick={() => setNeueAkteOffen(true)}>
          + Neue Akte
        </Btn>
      </div>

      {/* Drei Suchkacheln */}
      <div style={{ padding: "1.25rem 1.75rem", flexShrink: 0, display: "flex", gap: "1rem" }}>

        {/* Kachel 1: AZ / Name – mit Autocomplete */}
        <div style={kachelStyle}>
          <label style={labelStyle}>Aktenzeichen oder Name</label>
          <AutocompleteInput
            value={az}
            onChange={setAz}
            onSearch={() => suchen("az")}
            onOpenAkte={onOpenAkte}
            placeholder="42/25  ·  Müller"
            hint={<>Mit „/" → Aktenzeichen · Ohne „/" → Mandant &amp; Gegner</>}
          />
          <div style={{ marginTop: "0.7rem" }}>
            <Btn variant="gold" size="sm" onClick={() => suchen("az")} disabled={loading || !az.trim()} style={{ width: "100%" }}>
              {loading && suchmodus === "" ? "…" : "🔍 Suchen"}
            </Btn>
          </div>
        </div>

        {/* Kachel 2: KFZ – mit Autocomplete */}
        <div style={kachelStyle}>
          <label style={labelStyle}>KFZ-Kennzeichen</label>
          <AutocompleteInput
            value={kz}
            onChange={setKz}
            onSearch={() => suchen("kz")}
            onOpenAkte={onOpenAkte}
            placeholder="OF-NM 444"
            hint="Sucht via WDM varM-KZ · Teileingabe möglich"
          />
          <div style={{ marginTop: "0.7rem" }}>
            <Btn variant="gold" size="sm" onClick={() => suchen("kz")} disabled={loading || !kz.trim()} style={{ width: "100%" }}>
              🔍 Suchen
            </Btn>
          </div>
        </div>

        {/* Kachel 3: Schadentag – unverändert */}
        <div style={kachelStyle}>
          <label style={labelStyle}>Schadentag</label>
          <input
            type="date"
            value={tag} onChange={e => setTag(e.target.value)}
            onKeyDown={e => e.key === "Enter" && suchen("tag")}
            style={{
              width: "100%", padding: "9px 11px", border: `1.5px solid ${T.border}`,
              borderRadius: 7, fontFamily: T.fontBody, fontSize: "0.975rem",
              color: T.text, background: T.cardBg, outline: "none",
              boxSizing: "border-box", transition: "border-color 0.15s",
            }}
            onFocus={e => e.target.style.borderColor = T.accent}
            onBlur={e  => e.target.style.borderColor = T.border}
          />
          <div style={{ marginTop: 5, fontFamily: T.fontBody,
            fontSize: "0.75rem", color: T.textFaint, lineHeight: 1.4 }}>
            Alle Unfälle an diesem Tag · WDM varU-TAG
          </div>
          <div style={{ marginTop: "0.7rem" }}>
            <Btn variant="gold" size="sm" onClick={() => suchen("tag")} disabled={loading || !tag.trim()} style={{ width: "100%" }}>
              🔍 Suchen
            </Btn>
          </div>
        </div>
      </div>

      {/* Hinweis / Fehler */}
      {fehler && (
        <div style={{ margin: "0 1.75rem 0.75rem", padding: "9px 14px",
          background: ramicroAktiv ? T.redBg : T.amberBg,
          border: `1px solid ${ramicroAktiv ? T.red : T.amber}44`,
          borderRadius: 8, fontFamily: T.fontBody,
          fontSize: "0.855rem", color: ramicroAktiv ? T.red : T.amber }}>
          {ramicroAktiv ? "⚠" : "ℹ"} {fehler}
        </div>
      )}

      {/* Ergebnisliste */}
      {treffer !== null && (
        <div style={{ flex: 1, overflowY: "auto", padding: "0 1.75rem 1.75rem" }}>
          {treffer.length === 0 && !fehler ? (
            <div style={{ textAlign: "center", padding: "3rem 0", color: T.textFaint, fontFamily: T.fontBody }}>
              <div style={{ fontSize: "2.5rem", marginBottom: 8 }}>🗂</div>
              <div style={{ fontSize: "1rem" }}>Keine aktiven Akten gefunden</div>
              {suchmodus && <div style={{ fontSize: "0.85rem", marginTop: 4 }}>Suchmodus: {SUCHMODUS_LABEL[suchmodus]}</div>}
            </div>
          ) : treffer.length > 0 && (
            <Card>
              <div style={{ padding: "0.65rem 1.4rem", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${T.border}` }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontFamily: T.fontBody, fontSize: "0.82rem", fontWeight: 600, color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    Ergebnisse
                  </span>
                  {suchmodus && (
                    <span style={{ fontFamily: T.fontBody, fontSize: "0.78rem", background: T.accentPale, color: T.navy, border: `1px solid rgba(160,107,74,0.3)`, borderRadius: 10, padding: "1px 8px" }}>
                      {SUCHMODUS_LABEL[suchmodus]}
                    </span>
                  )}
                </div>
                <span style={{ fontFamily: T.fontBody, fontSize: "0.82rem", color: T.textFaint }}>
                  {treffer.length} Treffer
                </span>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: T.surface }}>
                    {["Aktenzeichen", "Bezeichnung", "Sachbearb.", ""].map((h, i) => (
                      <th key={i} style={{ padding: "8px 14px", textAlign: "left", fontFamily: T.fontBody, fontSize: "0.78rem", fontWeight: 600, color: T.textMuted, letterSpacing: "0.06em", textTransform: "uppercase", borderBottom: `1px solid ${T.border}`, whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {treffer.map((t, i) => (
                    <tr key={t.az + i}
                      style={{ borderBottom: `1px solid ${T.borderSoft}`, background: i % 2 === 0 ? T.cardBg : T.surface, transition: "background 0.12s", cursor: "default" }}
                      onMouseEnter={e => { e.currentTarget.style.background = T.offWhite; handleRowEnter(e, t); }}
                      onMouseLeave={e => { e.currentTarget.style.background = i % 2 === 0 ? T.cardBg : T.surface; handleRowLeave(); }}>
                      <td style={{ padding: "10px 14px", whiteSpace: "nowrap" }}>
                        <button onClick={() => onOpenAkte({ id: t.az_roh, az: t.az, az_roh: t.az_roh, status: t.status || "offen", unfalldatum: t.unfalldatum || "", unfallort: t.unfallort || "", hq: t.haftungsquote || 100, brutto: 0 })}
                          style={{ background: "none", border: "none", padding: 0, cursor: "pointer", fontFamily: "ui-monospace,monospace", fontSize: "0.875rem", fontWeight: 600, color: T.navy, textDecoration: "underline", textDecorationColor: "rgba(27,42,74,0.3)" }}>
                          {t.az}
                        </button>
                      </td>
                      <td style={{ padding: "10px 14px", maxWidth: 380 }}>
                        <div style={{ fontFamily: T.fontBody, fontSize: "0.875rem", fontWeight: 600, color: T.textMid, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                             title={t.kurzbezeichnung}>
                          {t.kurzbezeichnung || t.mandant || "–"}
                        </div>
                        {(t.bezeichnung || t.kennzeichen) && (
                          <div style={{ fontFamily: T.fontBody, fontSize: "0.795rem", color: T.textMuted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: 2 }}
                               title={[t.bezeichnung, t.kennzeichen].filter(Boolean).join(" · ")}>
                            {t.bezeichnung}
                            {t.bezeichnung && t.kennzeichen && <span style={{ margin: "0 4px", color: T.textFaint }}>·</span>}
                            {t.kennzeichen && <span style={{ fontFamily: "ui-monospace,monospace", fontSize: "0.775rem", fontWeight: 700, color: T.blue }}>{t.kennzeichen}</span>}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: "10px 14px", whiteSpace: "nowrap" }}>
                        <span style={{ fontFamily: "ui-monospace,monospace", fontSize: "0.85rem", background: T.accentPale, color: T.navy, border: `1px solid ${T.accentTrim}`, borderRadius: 5, padding: "2px 7px", fontWeight: 600 }}>
                          {t.sachbearbeiter || "–"}
                        </span>
                      </td>
                      <td style={{ padding: "10px 10px", textAlign: "right" }}>
                        <Btn size="sm" variant="secondary"
                          onClick={() => onOpenAkte({ id: t.az_roh, az: t.az, az_roh: t.az_roh, status: t.status || "offen", unfalldatum: t.unfalldatum || "", unfallort: t.unfallort || "", hq: t.haftungsquote || 100, brutto: 0 })}>
                          Öffnen
                        </Btn>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>
      )}

      {/* Leerzustand */}
      {treffer === null && !loading && (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", color: T.textFaint, fontFamily: T.fontBody, gap: 10 }}>
          <div style={{ fontSize: "3rem" }}>🔍</div>
          <div style={{ fontSize: "1rem" }}>Suchfeld ausfüllen · Vorschläge erscheinen ab 2 Zeichen</div>
          <div style={{ fontSize: "0.83rem", color: T.textFaint, textAlign: "center", maxWidth: 380, lineHeight: 1.6 }}>
            <code style={{ background: T.surface, padding: "1px 5px", borderRadius: 4 }}>42/25</code> Aktenzeichen &nbsp;·&nbsp;
            <code style={{ background: T.surface, padding: "1px 5px", borderRadius: 4 }}>Müller</code> Name &nbsp;·&nbsp;
            <code style={{ background: T.surface, padding: "1px 5px", borderRadius: 4 }}>OF-NM 444</code> Kennzeichen &nbsp;·&nbsp;
            Datum über Kalender
          </div>
        </div>
      )}
    </div>

    {hoverAz && hoverAnchor && (
      <EakteHoverPopover
        az={hoverAz}
        anchor={hoverAnchor}
        daten={popoverDaten}
        akteObj={hoverAkteObj}
        onOpenAkte={onOpenAkte}
        onMouseEnter={() => clearTimeout(hideTimerRef.current)}
        onMouseLeave={() => setHoverAz(null)}
      />
    )}
    {neueAkteOffen && (
      <AktenanlageDialog
        onClose={() => setNeueAkteOffen(false)}
        onAngelegt={(vorgang) => {
          setNeueAkteOffen(false);
          setToast(`Aktenanlage angestoßen (${vorgang.mandant_name}) — ` +
                   "RA-MICRO legt die Akte an. Fortschritt: Review-Queue.");
        }}
        onUebernehmeAz={(az) => {
          setNeueAkteOffen(false);
          onOpenAkte({ az, az_roh: az, label: az });
        }}
      />
    )}
    {toast && <Toast msg={toast} onDone={() => setToast("")} />}
    </>
  );
}

export default AktensucheView;
