import React, { useState, useEffect, useRef } from "react";
import T from "../../config/theme.js";
import Ic from "../../config/icons.jsx";
import { EMAIL_TYP_LABELS } from "../../config/constants.js";
import { emailImport as apiEmail, tokenStore, API_BASE } from "../../api.js";
import InAkteButton from "./components/InAkteButton.jsx";

function EmailDetailView({ entry: e, onBack, onOpenAkte, onInAkteImportiert }) {
  const [meta, setMeta]               = useState(null);
  const [metaLaedt, setMetaLaedt]     = useState(true);
  const [aktiverIdx, setAktiverIdx]   = useState(null);
  const [vorschauUrl, setVorschauUrl] = useState(null);
  const [vorschauLaedt, setVorschauLaedt] = useState(false);
  const [lokalerEintrag, setLokalerEintrag] = useState(e);
  const prevUrlRef = useRef(null);

  useEffect(() => {
    setLokalerEintrag(e);
    setMeta(null); setMetaLaedt(true);
    setAktiverIdx(null); setVorschauUrl(null);
  }, [e.id]);

  useEffect(() => {
    apiEmail.meta(lokalerEintrag.id)
      .then(m => setMeta(m))
      .catch(() => setMeta({ anhaenge: [], body_text: "" }))
      .finally(() => setMetaLaedt(false));
  }, [lokalerEintrag.id]);

  useEffect(() => () => { if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current); }, []);

  const oeffneAnhangVorschau = async (anhang) => {
    if (aktiverIdx === anhang.index) {
      setAktiverIdx(null);
      if (vorschauUrl) { URL.revokeObjectURL(vorschauUrl); prevUrlRef.current = null; }
      setVorschauUrl(null);
      return;
    }
    setAktiverIdx(anhang.index);
    setVorschauLaedt(true);
    try {
      const token = tokenStore.getAccess();
      const res = await fetch(
        `${API_BASE}/email/import/log/${lokalerEintrag.id}/anhang/${anhang.index}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      if (!res.ok) throw new Error("Anhang nicht verfügbar");
      const blob = await res.blob();
      if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);
      const url = URL.createObjectURL(blob);
      prevUrlRef.current = url;
      setVorschauUrl(url);
    } catch {
      setVorschauUrl(null);
    } finally {
      setVorschauLaedt(false);
    }
  };

  const handleInAkteImportiert = (res) => {
    setLokalerEintrag(prev => ({
      ...prev,
      in_akte_importiert: 1,
      in_akte_importiert_am: res?.importiert_am,
    }));
    if (onInAkteImportiert) onInAkteImportiert(lokalerEintrag.id, res);
  };

  const et = lokalerEintrag.email_typ && lokalerEintrag.email_typ !== "sonstiges"
    ? EMAIL_TYP_LABELS[lokalerEintrag.email_typ] : null;

  return (
    <div style={{ display:"flex", height:"100%", overflow:"hidden" }}>

      {/* ── Linke Spalte (fix 380px) ──────────────────────────── */}
      <div style={{ width:380, flexShrink:0, borderRight:`1px solid ${T.border}`,
        overflowY:"auto", display:"flex", flexDirection:"column" }}>

        {/* Navigation */}
        <div style={{ padding:"0.85rem 1.25rem", borderBottom:`1px solid ${T.border}`,
          display:"flex", alignItems:"center", gap:10, flexWrap:"wrap", flexShrink:0 }}>
          <button onClick={onBack}
            style={{ display:"flex", alignItems:"center", gap:5, background:"none",
              border:"none", cursor:"pointer", fontFamily:"'Figtree',sans-serif",
              fontSize:"0.895rem", color:T.textMid, padding:"4px 0" }}>
            ← Zurück zum Stream
          </button>
          {lokalerEintrag.akte_az && (
            <button onClick={() => onOpenAkte(lokalerEintrag)}
              style={{ display:"flex", alignItems:"center", gap:5, background:"none",
                border:`1px solid ${T.navy}`, borderRadius:6, cursor:"pointer",
                fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem",
                color:T.navy, padding:"4px 10px", marginLeft:"auto" }}>
              {Ic.akte} Akte {lokalerEintrag.akte_az} öffnen
            </button>
          )}
        </div>

        {/* Betreff */}
        <div style={{ padding:"1.25rem 1.25rem 0.75rem",
          fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"1.1rem",
          fontWeight:700, color:T.navy, lineHeight:1.3 }}>
          {lokalerEintrag.betreff || <span style={{ color:T.textMuted, fontStyle:"italic" }}>(kein Betreff)</span>}
        </div>

        {/* Metadaten */}
        <div style={{ padding:"0 1.25rem 1rem", display:"flex", flexDirection:"column", gap:6 }}>
          {[
            ["Von",   `${lokalerEintrag.von_name || ""} ${lokalerEintrag.absender ? `<${lokalerEintrag.absender}>` : ""}`.trim() || lokalerEintrag.absender || "–"],
            ["Akte",  lokalerEintrag.akte_az ? `${lokalerEintrag.akte_az} ✓ Zugeordnet` : "Nicht zugeordnet"],
            ["Datum", lokalerEintrag.empfangen_am ? String(lokalerEintrag.empfangen_am).slice(0, 16) : "–"],
            ["Typ",   et ? et.label : "Sonstiges"],
          ].map(([l, v]) => (
            <div key={l} style={{ display:"flex", gap:10, alignItems:"baseline" }}>
              <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.815rem",
                color:T.textMuted, width:44, flexShrink:0 }}>{l}</span>
              <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.895rem",
                color: l === "Akte" && lokalerEintrag.akte_az ? T.green : T.text,
                fontWeight: l === "Akte" && lokalerEintrag.akte_az ? 600 : 400 }}>{v}</span>
            </div>
          ))}
        </div>

        <div style={{ margin:"0 1.25rem", borderTop:`1px solid ${T.border}` }} />

        {/* Anhänge */}
        {(lokalerEintrag.anhaenge_anzahl || 0) > 0 && (
          <div style={{ padding:"0.85rem 1.25rem" }}>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem", fontWeight:700,
              color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em", marginBottom:8 }}>
              Anhänge ({lokalerEintrag.anhaenge_anzahl})
            </div>
            {metaLaedt ? (
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", color:T.textMuted }}>Lade …</div>
            ) : (
              <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
                {(meta?.anhaenge || []).map(anh => {
                  const isPdf = (anh.ext === "pdf") || (anh.name || "").toLowerCase().endsWith(".pdf");
                  const istAktiv = aktiverIdx === anh.index;
                  return (
                    <div key={anh.index}
                      style={{ display:"flex", alignItems:"center", gap:8,
                        background: istAktiv ? T.accentPale : T.surface,
                        border: `1.5px solid ${istAktiv ? T.accent : T.border}`,
                        borderRadius:7, padding:"6px 10px", cursor:"pointer" }}
                      onClick={() => oeffneAnhangVorschau(anh)}>
                      <span style={{ color: isPdf ? T.red : T.blue, display:"flex", flexShrink:0 }}>{isPdf ? Ic.pdf : Ic.attach}</span>
                      <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                        color:T.text, flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                        {anh.name || `Anhang ${anh.index + 1}`}
                      </span>
                      <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                        color: istAktiv ? T.accent : T.textMuted, flexShrink:0 }}>
                        {istAktiv ? "▼ Vorschau" : "▶ Vorschau"}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <div style={{ margin:"0 1.25rem", borderTop:`1px solid ${T.border}` }} />

        {/* Import-Vorschlag */}
        <div style={{ padding:"0.85rem 1.25rem", flex:1 }}>
          {lokalerEintrag.akte_az && !lokalerEintrag.in_akte_importiert ? (
            <div style={{ background:T.greenBg, border:`1.5px solid ${T.green}44`,
              borderRadius:9, padding:"0.85rem 1rem" }}>
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                fontWeight:700, color:T.green, marginBottom:4 }}>
                📥 In Akte {lokalerEintrag.akte_az} importieren?
              </div>
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.835rem",
                color:T.textMid, marginBottom:10 }}>
                {(lokalerEintrag.anhaenge_anzahl || 0) > 0
                  ? `${lokalerEintrag.anhaenge_anzahl} Anhang${lokalerEintrag.anhaenge_anzahl > 1 ? "hänge" : ""} + E-Mail-Text`
                  : "E-Mail-Text"}
              </div>
              <InAkteButton
                entry={lokalerEintrag}
                onImportiert={handleInAkteImportiert}
                onOpenAkte={null}
              />
            </div>
          ) : lokalerEintrag.in_akte_importiert ? (
            <div style={{ display:"flex", alignItems:"center", gap:7,
              background:T.greenBg, border:`1px solid ${T.green}33`,
              borderRadius:7, padding:"8px 12px",
              fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", color:T.green }}>
              {Ic.check}
              <span>In Akte importiert{lokalerEintrag.in_akte_importiert_am ? ` · ${lokalerEintrag.in_akte_importiert_am}` : ""}</span>
            </div>
          ) : (
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
              color:T.textMuted, fontStyle:"italic" }}>
              E-Mail noch keiner Akte zugeordnet
            </div>
          )}
        </div>
      </div>

      {/* ── Rechtes Vorschau-Panel ────────────────────────────── */}
      <div style={{ flex:1, overflow:"hidden", display:"flex", flexDirection:"column" }}>
        {aktiverIdx !== null ? (
          vorschauLaedt ? (
            <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center",
              fontFamily:"'Figtree',sans-serif", fontSize:"0.955rem", color:T.textMuted }}>
              <div style={{ width:20, height:20, border:`2px solid ${T.border}`,
                borderTopColor:T.navy, borderRadius:"50%", animation:"spin 0.7s linear infinite",
                marginRight:10 }} />
              Lade Vorschau …
            </div>
          ) : vorschauUrl ? (
            <>
              <div style={{ padding:"8px 14px", borderBottom:`1px solid ${T.border}`,
                display:"flex", alignItems:"center", gap:10, flexShrink:0,
                background:T.white, fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem" }}>
                <span style={{ color:T.textMid }}>
                  {(meta?.anhaenge || []).find(a => a.index === aktiverIdx)?.name || `Anhang ${aktiverIdx + 1}`}
                </span>
                <button onClick={() => apiEmail.anhangOeffnen(lokalerEintrag.id, aktiverIdx,
                    (meta?.anhaenge || []).find(a => a.index === aktiverIdx)?.name || "anhang")}
                  style={{ marginLeft:"auto", background:"none", border:`1px solid ${T.border}`,
                    borderRadius:5, padding:"3px 10px", cursor:"pointer",
                    fontFamily:"'Figtree',sans-serif", fontSize:"0.835rem", color:T.textMid }}>
                  ↗ Vollbild
                </button>
              </div>
              <iframe src={vorschauUrl} title="PDF-Vorschau"
                style={{ flex:1, border:"none", width:"100%", height:"100%" }} />
            </>
          ) : (
            <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center",
              fontFamily:"'Figtree',sans-serif", fontSize:"0.955rem", color:T.red }}>
              Anhang konnte nicht geladen werden.
            </div>
          )
        ) : (
          <div style={{ flex:1, overflowY:"auto", padding:"1.5rem" }}>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem", fontWeight:700,
              color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em", marginBottom:10 }}>
              E-Mail-Text
            </div>
            {metaLaedt ? (
              <div style={{ color:T.textMuted, fontSize:"0.895rem", fontFamily:"'Figtree',sans-serif" }}>Lade …</div>
            ) : (
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.895rem",
                color:T.textMid, whiteSpace:"pre-wrap", lineHeight:1.6 }}>
                {meta?.body_text || <span style={{ color:T.textMuted, fontStyle:"italic" }}>(kein Text)</span>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default EmailDetailView;
